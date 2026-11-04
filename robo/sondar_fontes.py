#!/usr/bin/env python3
"""Sondagem (rodada 2) das fontes publicas da Sala de Gestao em Saude.
Testa cada API a partir do ambiente em que roda (GitHub Actions) e grava dados/sondagem.json.
Nao guarda dados de pessoas nem valores de registros: so status, tempos, contagens e nomes de campos.
Chaves (se houver) vem de variaveis de ambiente, nunca do codigo."""
import ftplib, io, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error, zipfile
from datetime import datetime, timezone, timedelta

UA = "SalaGestaoSaude/0.2 (sondagem de fontes publicas; contato: partelli.pro)"
BRT = timezone(timedelta(hours=-3))
ES_IBGE, VITORIA = "32", "3205309"
ANO = datetime.now(BRT).year

def pedir(url, metodo="GET", headers=None, timeout=30, limite=3_000_000):
    h = {"User-Agent": UA, "Accept": "application/json, */*"}
    h.update(headers or {})
    t0 = time.time()
    o = {"url": url}
    try:
        req = urllib.request.Request(url, headers=h, method=metodo)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            o["status"] = resp.status
            o["tipo"] = resp.headers.get("Content-Type", "")
            o["tamanho_http"] = resp.headers.get("Content-Length")
            o["ultima_modificacao"] = resp.headers.get("Last-Modified")
            o["corpo"] = resp.read(limite) if metodo == "GET" else b""
    except urllib.error.HTTPError as e:
        o["status"] = e.code
        o["erro"] = f"HTTP {e.code}"
    except Exception as e:
        o["erro"] = f"{type(e).__name__}: {str(e)[:140]}"
    o["ms"] = int((time.time() - t0) * 1000)
    return o

def chaves(obj, n=16):
    if isinstance(obj, dict):
        return list(obj.keys())[:n]
    if isinstance(obj, list) and obj:
        return chaves(obj[0], n)
    return []

def itens(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ("items", "data", "results", "gazettes", "estabelecimentos"):
            if isinstance(obj.get(k), list):
                return obj[k]
    return None

def sondar(id_, nome, url, metodo="GET", headers=None, ler=True, nota="", timeout=30, tentativas=1, limite=3_000_000):
    r = {"id": id_, "nome": nome, "url": url, "metodo": metodo, "nota": nota}
    for i in range(tentativas):
        o = pedir(url, metodo, headers, timeout, limite if ler else 0)
        if "erro" not in o:
            break
        if i + 1 < tentativas:
            time.sleep(3)
    r["tentativas"] = i + 1
    r["status"] = o.get("status")
    r["ms"] = o["ms"]
    r["tipo"] = o.get("tipo")
    r["tamanho_http"] = o.get("tamanho_http")
    r["ultima_modificacao"] = o.get("ultima_modificacao")
    if "erro" in o:
        r["ok"] = False
        r["erro"] = o["erro"]
        return r
    r["ok"] = 200 <= o["status"] < 300
    corpo = o.get("corpo") or b""
    r["bytes_lidos"] = len(corpo)
    if corpo and (b"json" in (o.get("tipo") or "").encode() or corpo[:1] in (b"{", b"[")):
        try:
            obj = json.loads(corpo.decode("utf-8", "replace"))
            r["_obj"] = obj
            r["campos"] = chaves(obj)
            lst = itens(obj)
            r["registros"] = len(lst) if lst is not None else None
        except Exception:
            r["json_valido"] = False
    elif corpo:
        r["inicio"] = re.sub(r"\s+", " ", corpo[:200].decode("utf-8", "replace"))
    return r

def ftp_listas(id_, nome, host, caminhos, nota=""):
    r = {"id": id_, "nome": nome, "url": f"ftp://{host}", "metodo": "FTP", "nota": nota}
    t0 = time.time()
    try:
        f = ftplib.FTP(host, timeout=40)
        f.login()
        r["pastas"] = {}
        for c in caminhos:
            try:
                nomes = sorted(f.nlst(c))
                item = {"total": len(nomes), "ultimos": [n.split("/")[-1] for n in nomes[-6:]]}
                if nomes:
                    try:
                        f.voidcmd("TYPE I")
                        item["tamanho_ultimo_bytes"] = f.size(nomes[-1])
                    except Exception:
                        pass
                r["pastas"][c] = item
            except Exception as e:
                r["pastas"][c] = f"erro: {str(e)[:80]}"
        f.quit()
        r["ok"] = any(isinstance(v, dict) and v.get("total") for v in r["pastas"].values())
    except Exception as e:
        r["ok"] = False
        r["erro"] = f"{type(e).__name__}: {str(e)[:140]}"
    r["ms"] = int((time.time() - t0) * 1000)
    return r

def teste_volume_infodengue(entes):
    """50 municipios de varias UFs em sequencia: mede erro, limite de uso e variacao de campos."""
    r = {"id": "volume_infodengue", "nome": "InfoDengue: 50 municipios em sequencia (teste de volume)", "metodo": "GET",
         "nota": "mede estabilidade e limite de uso antes da coleta nacional"}
    muni = [e for e in entes if str(e.get("esfera", "")).strip() == "M" and e.get("cod_ibge")]
    if len(muni) < 50:
        r["ok"] = None
        r["nota"] += ". Nao testado: lista de municipios indisponivel (SICONFI falhou)."
        return r
    passo = max(1, len(muni) // 50)
    amostra = muni[::passo][:50]
    tempos, codigos, conjuntos = [], {}, set()
    t0 = time.time()
    for e in amostra:
        url = f"https://info.dengue.mat.br/api/alertcity?geocode={e['cod_ibge']}&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={ANO}&ey_end={ANO}"
        o = pedir(url, timeout=40)
        cod = str(o.get("status") or o.get("erro", "erro")[:30])
        codigos[cod] = codigos.get(cod, 0) + 1
        tempos.append(o["ms"])
        if o.get("corpo"):
            try:
                conjuntos.add(tuple(chaves(json.loads(o["corpo"].decode("utf-8", "replace")), 40)))
            except Exception:
                pass
        time.sleep(0.3)
    tempos.sort()
    ok = codigos.get("200", 0)
    r.update({"ok": ok >= 45, "municipios_testados": len(amostra), "respostas_por_codigo": codigos,
              "ms_mediana": tempos[len(tempos) // 2], "ms_p95": tempos[int(len(tempos) * 0.95) - 1],
              "segundos_total": int(time.time() - t0), "conjuntos_distintos_de_campos": len(conjuntos),
              "estimativa_min_5570_municipios_em_sequencia": round(5570 * (sum(tempos) / len(tempos) / 1000 + 0.3) / 60)})
    return r

def inspecionar_cnes():
    r = {"id": "cnes_conteudo", "nome": "CNES: download completo e estrutura do arquivo", "metodo": "GET",
         "url": "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_json.zip",
         "nota": "guarda so nomes de campos e tamanhos, nenhum valor"}
    o = pedir(r["url"], timeout=120, limite=120_000_000)
    r["ms"] = o["ms"]
    r["status"] = o.get("status")
    if "erro" in o:
        r["ok"] = False
        r["erro"] = o["erro"]
        return r
    try:
        z = zipfile.ZipFile(io.BytesIO(o["corpo"]))
        r["arquivos"] = [{"nome": i.filename, "bytes_compactado": i.compress_size, "bytes_descompactado": i.file_size} for i in z.infolist()[:5]]
        with z.open(z.infolist()[0]) as fh:
            ini = fh.read(60000).decode("utf-8", "replace")
        r["campos"] = list(dict.fromkeys(re.findall(r'"([A-Za-z_0-9]+)"\s*:', ini)))[:60]
        r["ok"] = True
    except Exception as e:
        r["ok"] = False
        r["erro"] = f"{type(e).__name__}: {str(e)[:120]}"
    return r

def transferegov(modulo):
    base = f"https://api-publica.transferegov.gestao.gov.br/{modulo}/"
    r = sondar(f"transferegov_{modulo}_raiz", f"Transferegov {modulo} (raiz, lista de tabelas)", base, nota="espera-se esquema OpenAPI com a lista de tabelas")
    obj = r.get("_obj")
    tabelas = []
    if isinstance(obj, dict) and isinstance(obj.get("paths"), dict):
        tabelas = [p.strip("/") for p in obj["paths"] if not p.startswith("/rpc")]
    r["tabelas"] = tabelas[:40]
    r["total_tabelas"] = len(tabelas)
    saida = [r]
    for t in tabelas[:2]:
        saida.append(sondar(f"transferegov_{modulo}_{t}", f"Transferegov {modulo}: tabela {t} (1 linha)", base + t + "?limit=1", nota="so nomes de campos"))
    return saida

def main():
    fontes = []
    # 1. Territorio e populacao
    fontes += [
        sondar("ibge_municipios_br", "IBGE localidades (todos os municipios)", "https://servicodados.ibge.gov.br/api/v1/localidades/municipios", timeout=45, tentativas=2, nota="espera-se 5570"),
        sondar("ibge_sidra", "IBGE SIDRA (populacao estimada, Vitoria)", f"https://apisidra.ibge.gov.br/values/t/6579/n6/{VITORIA}/v/9324/p/last", timeout=45, tentativas=2, nota="host diferente do servicodados"),
        sondar("ibge_geoftp", "IBGE geoftp (malhas, via HTTPS)", "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/", timeout=45, tentativas=2, nota="outro host do IBGE"),
    ]
    entes = sondar("siconfi_entes", "SICONFI entes (5598 esperados)", "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes", limite=3_000_000)
    lista_entes = (entes.get("_obj") or {}).get("items", []) if isinstance(entes.get("_obj"), dict) else []
    fontes.append(entes)
    # 2. Financiamento: variacoes do RREO (saude) e extrato de entregas
    base_rreo = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo?"
    variantes = [
        ("rreo_a", "RREO Anexo 12, ES, bim 6", dict(an_exercicio=ANO - 1, nr_periodo=6, co_tipo_demonstrativo="RREO", no_anexo="RREO-Anexo 12", id_ente=ES_IBGE)),
        ("rreo_b", "RREO Anexo 12, Vitoria, bim 6", dict(an_exercicio=ANO - 1, nr_periodo=6, co_tipo_demonstrativo="RREO", no_anexo="RREO-Anexo 12", id_ente=VITORIA)),
        ("rreo_c", "RREO Anexo 12, Vitoria, bim 6, ano anterior ao anterior", dict(an_exercicio=ANO - 2, nr_periodo=6, co_tipo_demonstrativo="RREO", no_anexo="RREO-Anexo 12", id_ente=VITORIA)),
        ("rreo_d", "RREO sem filtro de anexo, Vitoria (lista os anexos existentes)", dict(an_exercicio=ANO - 1, nr_periodo=6, co_tipo_demonstrativo="RREO", id_ente=VITORIA)),
    ]
    for vid, nome, p in variantes:
        r = sondar("siconfi_" + vid, "SICONFI " + nome, base_rreo + urllib.parse.urlencode(p), nota="variante de parametros")
        lst = itens(r.get("_obj")) or []
        if lst and isinstance(lst[0], dict):
            r["anexos_encontrados"] = sorted({str(i.get("anexo", i.get("no_anexo", ""))) for i in lst})[:25]
            r["campos_item"] = list(lst[0].keys())[:20]
        fontes.append(r)
    fontes.append(sondar("siconfi_extrato", "SICONFI extrato de entregas (Vitoria)", "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/extrato_entregas?" + urllib.parse.urlencode(dict(id_ente=VITORIA, an_referencia=ANO - 1)), nota="mostra quais demonstrativos o municipio entregou"))
    for m in ("fundoafundo", "especiais"):
        fontes += transferegov(m)
    # 3. Epidemiologia
    fontes.append(sondar("infodengue", "InfoDengue (Vitoria, dengue)", f"https://info.dengue.mat.br/api/alertcity?geocode={VITORIA}&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={ANO}&ey_end={ANO}"))
    fontes.append(sondar("infodengue_chik", "InfoDengue (Vitoria, chikungunya)", f"https://info.dengue.mat.br/api/alertcity?geocode={VITORIA}&disease=chikungunya&format=json&ew_start=1&ew_end=53&ey_start={ANO}&ey_end={ANO}"))
    fontes.append(teste_volume_infodengue(lista_entes))
    # 4. Rede assistencial
    fontes.append(inspecionar_cnes())
    for suf, nome in (("v1", "API do MS: raiz /v1 (documentacao)"), ("swagger.json", "API do MS: /swagger.json"), ("v1/swagger.json", "API do MS: /v1/swagger.json")):
        fontes.append(sondar("ms_" + suf.replace("/", "_").replace(".", "_"), nome, "https://apidadosabertos.saude.gov.br/" + suf, nota="busca da documentacao"))
    for caminho, nome in (("cnes/estabelecimentos?limit=2&offset=0", "CNES"), ("assistencia-a-saude/hospitais-e-leitos?limit=2&offset=0", "Hospitais e leitos (candidato)"),
                          ("arboviroses/dengue?limit=2&offset=0", "Arboviroses (candidato)")):
        fontes.append(sondar("ms_" + caminho.split("?")[0].replace("/", "_"), f"API do MS: {nome}", "https://apidadosabertos.saude.gov.br/" + caminho, nota="caminho candidato"))
    for i, u in enumerate(("https://dadosabertos.saude.gov.br/dataset/hospitais-e-leitos", "https://dadosabertos.saude.gov.br/api/action/package_show?id=hospitais-e-leitos", "https://dadosabertos.saude.gov.br/api/3/action/package_search?q=leitos&rows=3")):
        fontes.append(sondar(f"leitos_{i}", "Hospitais e Leitos (variante %d)" % (i + 1), u, nota="achar a forma de listar os arquivos por competencia"))
    # 5. Normas e saude suplementar (compras/PNCP ficam fora: a sala e para o gestor, nao para o prestador)
    fontes.append(sondar("querido_diario", "Querido Diario (busca 'saude', Vitoria)", f"https://api.queridodiario.org.br/gazettes?querystring=saude&territory_ids={VITORIA}&size=1", timeout=45))
    fontes.append(sondar("ans_http", "ANS dados abertos (diretorio PDA)", "https://dadosabertos.ans.gov.br/FTP/PDA/", nota="candidato"))
    # 6. DATASUS FTP: pastas e arquivos mais recentes
    fontes.append(ftp_listas("datasus_ftp", "DATASUS FTP: arquivos mais recentes por sistema", "ftp.datasus.gov.br", [
        "/dissemin/publicos/SIM/CID10/DORES", "/dissemin/publicos/SINASC/NOV/DNRES", "/dissemin/publicos/SIHSUS/200801_/Dados",
        "/dissemin/publicos/SINAN/DADOS/FINAIS", "/dissemin/publicos/PNI/DADOS", "/dissemin/publicos/CNES/200508_/Dados/ST", "/dissemin/publicos/ANS"]))
    # 7. Portal da Transparencia (so com chave)
    chave = os.environ.get("PORTAL_TRANSPARENCIA_KEY", "").strip()
    if chave:
        fontes.append(sondar("portal_transparencia", "Portal da Transparencia (emendas, saude)", f"https://api.portaldatransparencia.gov.br/api-de-dados/emendas?ano={ANO-1}&pagina=1&codigoFuncao=10", headers={"chave-api-dados": chave}, nota="chave vinda de segredo do GitHub"))
    else:
        fontes.append({"id": "portal_transparencia", "nome": "Portal da Transparencia (emendas, saude)", "ok": None, "nota": "nao testado: falta o segredo PORTAL_TRANSPARENCIA_KEY"})
    for f in fontes:
        f.pop("_obj", None)
    saida = {"rodada": 2, "gerado_em": datetime.now(BRT).isoformat(timespec="seconds"),
             "ambiente": "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local",
             "resumo": {"ok": sum(1 for f in fontes if f.get("ok") is True), "falha": sum(1 for f in fontes if f.get("ok") is False),
                        "nao_testado": sum(1 for f in fontes if f.get("ok") is None)}, "fontes": fontes}
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem_r2.json", "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=1)
    linhas = ["| Fonte | Resultado | Tempo | Observacao |", "|---|---|---|---|"]
    for f in fontes:
        res = "ok" if f.get("ok") else ("nao testado" if f.get("ok") is None else f"FALHA {f.get('erro', f.get('status', ''))}")
        obs = f.get("nota", "")
        if f.get("registros") is not None:
            obs = f"{f['registros']} registros. " + obs
        linhas.append(f"| {f['nome']} | {res} | {f.get('ms', '')} ms | {obs} |")
    texto = "\n".join(linhas)
    print(texto)
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as fh:
            fh.write("## Sondagem das fontes (rodada 2)\n\n" + texto + "\n")
    print(f"\nok={saida['resumo']['ok']} falha={saida['resumo']['falha']} nao_testado={saida['resumo']['nao_testado']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
