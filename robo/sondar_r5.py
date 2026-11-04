#!/usr/bin/env python3
"""Sondagem (rodada 5) da Sala de Gestao em Saude. Roda tudo de uma vez, em blocos independentes.
Cada bloco que falha vira uma linha de falha e nao derruba os demais.

Blocos:
  A. Validar o que a v1 assume: formato real do CNES, limite do InfoDengue em paralelo, emendas, colunas do SISAB.
  B. Fontes novas: SIOPS e despesa em saude (SICONFI DCA e RREO), indice das pastas do Dados Abertos SUS,
     convenios e transferencias (API e CSV do Portal da Transparencia), ANS, CONASEMS, e-Gestor APS.
  C. Significado dos campos do Radar de Recursos (fbEst, sEst, eq, nIdx) por hipoteses testadas nos dados.

Guarda so status, tempos, contagens, nomes de campos, codigos e enderecos publicos. Nenhum dado de pessoa,
nenhum segredo (a chave do Portal da Transparencia vem de variavel de ambiente e nunca e gravada)."""
import io, json, os, re, struct, sys, time, urllib.parse, urllib.request, urllib.error, zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sondar_fontes import pedir, sondar, chaves, BRT, ES_IBGE, VITORIA, ANO, UA
from sondar_r3 import pagina, mes_anterior, rreo_paginas
from sondar_r4 import texto, ckan_recursos, HTML
import coletar_rede, coletar_emendas, coletar_dengue

S3 = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/"
PT_API = "https://api.portaldatransparencia.gov.br"
SICONFI = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/"

# ---------------------------------------------------------------- funcoes puras (testadas offline)

def primeiro_arquivo_zip(dados, max_saida=None):
    """Le o primeiro arquivo de um ZIP mesmo truncado. Devolve {'nome','metodo','bytes'} ou None."""
    if not dados or dados[:4] != b"PK\x03\x04":
        return None
    metodo = struct.unpack("<H", dados[8:10])[0]
    nome_len, extra_len = struct.unpack("<HH", dados[26:30])
    nome = dados[30:30 + nome_len].decode("utf-8", "replace")
    corpo = dados[30 + nome_len + extra_len:]
    if metodo == 8:
        d = zlib.decompressobj(-15)
        saida = d.decompress(corpo, max_saida) if max_saida else d.decompress(corpo)
    elif metodo == 0:
        saida = corpo[:max_saida] if max_saida else corpo
    else:
        return {"nome": nome, "metodo": metodo, "bytes": b""}
    return {"nome": nome, "metodo": metodo, "bytes": saida}

def separador(linha):
    return max((";", ",", "\t", "|"), key=lambda s: linha.count(s))

def cabecalho_csv(bytes_, linhas=3):
    """Cabecalho e primeiras linhas de um CSV (a ultima linha lida pode estar cortada e e descartada)."""
    for cod in ("utf-8-sig", "latin-1"):
        try:
            t = bytes_.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    partes = t.splitlines()
    if len(partes) > 1:
        partes = partes[:-1]
    if not partes:
        return {}
    sep = separador(partes[0])
    return {"codificacao": cod, "separador": sep, "colunas": [c.strip().strip('"') for c in partes[0].split(sep)][:60],
            "amostra": [l[:300] for l in partes[1:1 + linhas]]}

def params_openapi(spec, padrao):
    """Lista {'path','params':[{name,in,required}]} das rotas GET cujo caminho casa com o padrao."""
    saida = []
    for path, item in (spec.get("paths") or {}).items():
        if not re.search(padrao, path, re.I) or not isinstance(item, dict):
            continue
        op = item.get("get")
        if not isinstance(op, dict):
            continue
        ps = (item.get("parameters") or []) + (op.get("parameters") or [])
        saida.append({"path": path, "params": [{"name": p.get("name"), "in": p.get("in"), "required": bool(p.get("required"))}
                                               for p in ps if isinstance(p, dict)]})
    return saida

def montar_parametros(params, hoje):
    """Monta uma consulta minima com os parametros obrigatorios que sabemos preencher. Devolve (consulta, faltam)."""
    ini = (hoje - timedelta(days=30)).strftime("%d/%m/%Y")
    fim = hoje.strftime("%d/%m/%Y")
    q, faltam = {}, []
    for p in params:
        if p.get("in") != "query" or not p.get("required"):
            continue
        n, nl = p["name"], p["name"].lower()
        if nl in ("pagina", "page"):
            q[n] = 1
        elif "inicio" in nl or "inicial" in nl:
            q[n] = ini
        elif "fim" in nl or "final" in nl:
            q[n] = fim
        elif "orgao" in nl:
            q[n] = "36000"
        elif nl == "uf":
            q[n] = "ES"
        elif nl.startswith("ano"):
            q[n] = hoje.year - 1
        elif "mesano" in nl:
            q[n] = (hoje - timedelta(days=45)).strftime("%Y%m")
        else:
            faltam.append(n)
    return q, faltam

def s3_parse(xml):
    """Le uma listagem S3 (ListObjectsV2): pastas e arquivos."""
    pastas = re.findall(r"<CommonPrefixes><Prefix>([^<]+)</Prefix>", xml)
    arqs = re.findall(r"<Contents><Key>([^<]+)</Key><LastModified>([^<]+)</LastModified>(?:<ETag>[^<]*</ETag>)?<Size>(\d+)</Size>", xml)
    return pastas, [{"chave": k, "modificado": m[:10], "bytes": int(s)} for k, m, s in arqs]

def analisar_cnes(textos):
    """Estrutura e distribuicoes de uma amostra do CNES: campos, tipos de unidade, descricoes, esferas, UFs."""
    campos, tipos, esferas, ufs, motivos = {}, {}, {}, {}, {}
    desc_tipo, tam_ibge, lidos, erros, amostra_chaves = {}, {}, 0, 0, None
    for t in textos:
        try:
            r = json.loads(t)
        except ValueError:
            erros += 1
            continue
        if not isinstance(r, dict):
            erros += 1
            continue
        lidos += 1
        if amostra_chaves is None:
            amostra_chaves = list(r.keys())
        tp = str(r.get("TP_UNIDADE", "")).zfill(2)
        tipos[tp] = tipos.get(tp, 0) + 1
        for k, v in r.items():
            if k != "TP_UNIDADE" and re.search(r"(DS|NO|DESC).*(TP_UNID|TIPO)|(TP_UNID|TIPO).*(DS|DESC)", k, re.I) and v:
                desc_tipo.setdefault(tp, {})[k] = str(v)[:60]
            if re.search(r"ESFERA", k, re.I) and "DS" in k.upper():
                esferas[str(v)[:40]] = esferas.get(str(v)[:40], 0) + 1
        m = str(r.get("CO_MOTIVO_DESAB", ""))
        motivos[m or "(vazio)"] = motivos.get(m or "(vazio)", 0) + 1
        ci = re.sub(r"\D", "", str(r.get("CO_IBGE", "")))
        tam_ibge[len(ci)] = tam_ibge.get(len(ci), 0) + 1
        uf = str(r.get("CO_UF", ci[:2] if ci else ""))
        ufs[uf] = ufs.get(uf, 0) + 1
    top = lambda d, n=12: dict(sorted(d.items(), key=lambda kv: -kv[1])[:n])
    return {"lidos": lidos, "erros_leitura": erros, "campos": amostra_chaves or [], "tipos_unidade": top(tipos, 40),
            "descricao_do_tipo": dict(list(desc_tipo.items())[:60]), "esferas": top(esferas), "motivos_desativacao": top(motivos),
            "tamanho_co_ibge": tam_ibge, "ufs_na_amostra": top(ufs, 30)}

def p95(valores):
    v = sorted(valores)
    return v[min(len(v) - 1, int(len(v) * 0.95))] if v else None

def resumir_pedidos(rs):
    """rs: lista de (status, ms, extra). Estatistica de uma rodada de testes de volume."""
    n = len(rs)
    por = {}
    for st, _, _ in rs:
        por[str(st)] = por.get(str(st), 0) + 1
    ms = [m for st, m, _ in rs if st == 200]
    return {"pedidos": n, "status": por, "ok": por.get("200", 0), "taxa_erro": round(1 - por.get("200", 0) / n, 4) if n else None,
            "mediana_ms": sorted(ms)[len(ms) // 2] if ms else None, "p95_ms": p95(ms),
            "retry_after": sorted({str(e) for st, _, e in rs if st in (429, 503) and e})[:3]}

def linhas_uf(obj):
    """Acha o dicionario UF -> campos dentro do brasil.json, qualquer que seja o envelope."""
    uf2 = lambda d: isinstance(d, dict) and sum(1 for k in d if isinstance(k, str) and len(k) == 2 and k.isalpha()) >= 20
    if uf2(obj):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            if uf2(v):
                return v
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        chave = next((k for k in ("uf", "sigla", "UF") if k in obj[0]), None)
        if chave:
            return {str(o[chave]): o for o in obj}
    return {}

def hipoteses_fundo(brasil):
    """Testa o que fbEst, sEst, eq e nIdx podem ser, comparando campos em todas as UFs."""
    L = linhas_uf(brasil)
    n = len(L)
    def conta(f):
        return sum(1 for d in L.values() if isinstance(d, dict) and f(d))
    num = lambda d, k: d.get(k) if isinstance(d.get(k), (int, float)) else None
    def cmp(a, b, op):
        return lambda d: num(d, a) is not None and num(d, b) is not None and op(num(d, a), num(d, b))
    h = {"ufs": n,
         "fbEst <= fb": conta(cmp("fbEst", "fb", lambda x, y: x <= y)),
         "sEst <= s": conta(cmp("sEst", "s", lambda x, y: x <= y)),
         "fbEst == 0": conta(lambda d: num(d, "fbEst") == 0),
         "nIdx == mun": conta(cmp("nIdx", "mun", lambda x, y: x == y)),
         "nIdx <= mun": conta(cmp("nIdx", "mun", lambda x, y: x <= y)),
         "eq e inteiro": conta(lambda d: num(d, "eq") is not None and float(d["eq"]).is_integer()),
         "eq <= ep": conta(cmp("eq", "ep", lambda x, y: x <= y)),
         "ep >= ee >= eg": conta(lambda d: all(num(d, k) is not None for k in ("ep", "ee", "eg")) and d["ep"] >= d["ee"] >= d["eg"])}
    h["amostra"] = {uf: {k: L[uf].get(k) for k in ("mun", "pop", "fb", "fbEst", "s", "sEst", "ep", "ee", "eg", "eq", "nIdx")}
                    for uf in ("ES", "SP", "AC") if uf in L and isinstance(L[uf], dict)}
    return h

def trechos_js(txt, palavras, n=15):
    """Textos curtos entre aspas de um script que citam palavras-chave (para achar enderecos e nomes de arquivo)."""
    achados = []
    for m in re.findall(r'["\']([^"\'\n]{4,110})["\']', txt):
        if re.search(palavras, m, re.I) and m not in achados:
            achados.append(m)
        if len(achados) >= n:
            break
    return achados

# ---------------------------------------------------------------- blocos A: validar a v1

def bloco_cnes():
    """Baixa o inicio do ZIP do CNES e testa o leitor real da v1 (coletar_rede.iter_registros)."""
    r = {"id": "cnes_formato", "nome": "CNES JSON: formato real e tipos de unidade (amostra do inicio do arquivo)", "url": coletar_rede.URL}
    o = pedir(coletar_rede.URL, headers={"Range": "bytes=0-5000000"}, timeout=120, limite=5_100_000)
    r["ms"], r["status"] = o["ms"], o.get("status")
    if "erro" in o:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    z = primeiro_arquivo_zip(o["corpo"])
    if not z or not z["bytes"]:
        r.update({"ok": False, "erro": "nao e um ZIP legivel", "bytes": len(o["corpo"])})
        return r
    r["arquivo_dentro_do_zip"], r["metodo_compressao"], r["bytes_descompactados"] = z["nome"], z["metodo"], len(z["bytes"])
    ini = z["bytes"][:2000].decode("utf-8", "replace")
    r["comeca_com"] = re.sub(r"[^\[\]{}:,\"]", "", ini)[:40]   # so a pontuacao: mostra se e lista, objeto ou envelope
    textos = list(coletar_rede.iter_registros(io.BytesIO(z["bytes"]), tamanho=2_000_000))
    r.update(analisar_cnes(textos))
    nao_mapeados = [t for t in r["tipos_unidade"] if t not in coletar_rede.GRUPOS]
    r["tipos_fora_dos_grupos"] = nao_mapeados
    r["ok"] = r["lidos"] >= 1000 and r["erros_leitura"] <= r["lidos"] * 0.001 and "TP_UNIDADE" in r["campos"]
    return r

def pedir_status(url):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": coletar_dengue.__dict__.get("UA", UA)})
        with urllib.request.urlopen(req, timeout=40) as resp:
            resp.read()
            return 200, int((time.time() - t0) * 1000), None
    except urllib.error.HTTPError as e:
        return e.code, int((time.time() - t0) * 1000), e.headers.get("Retry-After") if e.headers else None
    except Exception as e:
        return 0, int((time.time() - t0) * 1000), type(e).__name__

def bloco_infodengue_paralelo():
    r = {"id": "infodengue_paralelo", "nome": "InfoDengue: limite de uso com 3 e 6 pedidos em paralelo"}
    try:
        with open("dados/territorio.json", encoding="utf-8") as fh:
            muni = json.load(fh)["municipios"]
    except Exception as e:
        r.update({"ok": None, "nota": f"sem dados/territorio.json ({type(e).__name__}). Rode 'Coletar base territorial' antes."})
        return r
    passo = max(1, len(muni) // 180)
    amostra = muni[::passo]
    urls = [coletar_dengue.URL.format(cod=m["cod"], ano=coletar_dengue.ANO) for m in amostra]
    fases = [(3, urls[:90]), (6, urls[90:180])]
    r["fases"] = {}
    for i, (trab, lote) in enumerate(fases):
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=trab) as ex:
            rs = list(ex.map(pedir_status, lote))
        seg = max(time.time() - t0, 0.001)
        res = resumir_pedidos(rs)
        res["pedidos_por_segundo"] = round(len(lote) / seg, 2)
        res["minutos_para_5570"] = round(5570 / (len(lote) / seg) / 60, 1)
        r["fases"][f"{trab}_em_paralelo"] = res
        if res["taxa_erro"] and res["taxa_erro"] > 0.05:
            r["parou_na_fase"] = trab
            break
        time.sleep(3)
    f3 = r["fases"].get("3_em_paralelo", {})
    r["ok"] = f3.get("taxa_erro") is not None and f3["taxa_erro"] <= 0.05
    return r

def bloco_arboviroses():
    F = []
    for dz in ("chikungunya", "zika"):
        url = coletar_dengue.URL.format(cod=VITORIA, ano=coletar_dengue.ANO).replace("disease=dengue", f"disease={dz}")
        s = sondar(f"info_{dz}", f"InfoDengue: {dz} (Vitoria)", url, timeout=40, tentativas=2, nota="mesma rota, outro agravo")
        o = s.pop("_obj", None)
        if isinstance(o, list):
            s["semanas"] = len(o)
            s["campos_item"] = list(o[0].keys())[:12] if o and isinstance(o[0], dict) else []
        F.append(s)
    return F

def bloco_emendas(chave):
    r = {"id": "emendas_amostra", "nome": "Emendas (API): campos, paginacao e reconhecimento da UF", "metodo": "GET"}
    if not chave:
        r.update({"ok": None, "nota": "sem chave"})
        return r
    H = {"chave-api-dados": chave}
    terr = json.load(open("dados/territorio.json", encoding="utf-8")) if os.path.exists("dados/territorio.json") else None
    for ano in (ANO, ANO - 1):
        o = pedir(coletar_emendas.API.format(ano=ano, pag=1), headers=H, timeout=60)
        if "erro" in o:
            r[f"erro_{ano}"] = o["erro"]
            continue
        try:
            lote = json.loads(o["corpo"].decode("utf-8", "replace"))
        except ValueError:
            r[f"json_invalido_{ano}"] = True
            continue
        r[f"itens_pagina1_{ano}"] = len(lote)
        r[f"campos_{ano}"] = list(lote[0].keys())[:25] if lote and isinstance(lote[0], dict) else []
        if terr and lote:
            sigla = {m["cod"][:2]: m["uf"] for m in terr["municipios"]}
            nomes = {coletar_emendas.sem_acento(u["nome"]): sigla[u["cod"]] for u in terr["ufs"] if u["cod"] in sigla}
            rec = [coletar_emendas.uf_do_local(x.get("localidadeDoGasto"), nomes, set(sigla.values())) for x in lote]
            r[f"uf_reconhecida_{ano}"] = f"{sum(1 for x in rec if x)} de {len(rec)}"
            r[f"exemplos_local_nao_reconhecido_{ano}"] = sorted({str(x.get('localidadeDoGasto'))[:50] for x, u in zip(lote, rec) if not u})[:8]
        time.sleep(1)
    r["ok"] = any(k.startswith("itens_pagina1") and v for k, v in r.items())
    return r

def bloco_sisab_colunas():
    F = []
    for q in ("2024Q1", "2024Q3"):
        url = f"{S3}sisab/indicador_desempenho/csv/sisab_indicador_desempenho_{q}.csv.zip"
        o = pedir(url, timeout=90, limite=6_000_000)
        r = {"id": f"sisab_{q}", "nome": f"SISAB indicadores de desempenho {q}: colunas", "url": url, "ms": o["ms"], "status": o.get("status")}
        if "erro" in o:
            r.update({"ok": False, "erro": o["erro"]})
        else:
            z = primeiro_arquivo_zip(o["corpo"], max_saida=600_000)
            if not z or not z["bytes"]:
                r.update({"ok": False, "erro": "nao e um ZIP legivel"})
            else:
                r["arquivo"] = z["nome"]
                r.update(cabecalho_csv(z["bytes"]))
                r["ok"] = bool(r.get("colunas")) and len(r["colunas"]) > 3
        F.append(r)
    return F

# ---------------------------------------------------------------- blocos B: fontes novas

def bloco_s3_indice():
    """Lista as pastas do bucket publico do Dados Abertos SUS e as ultimas chaves das que interessam a gestao."""
    r = {"id": "s3_indice", "nome": "Dados Abertos SUS (S3): pastas e arquivos mais recentes", "url": S3}
    o = pedir(S3 + "?" + urllib.parse.urlencode({"list-type": "2", "delimiter": "/", "max-keys": 1000}), timeout=45, limite=2_000_000)
    r["ms"], r["status"] = o["ms"], o.get("status")
    if "erro" in o:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    pastas, _ = s3_parse(o["corpo"].decode("utf-8", "replace"))
    r["pastas"] = [p.rstrip("/") for p in pastas]
    r["total_pastas"] = len(pastas)
    interesse = re.compile(r"siops|fns|fundo|financ|orcam|repasse|emenda|sisab|cnes|^sim|sinasc|sinan|sih|sia|pni|leito|hospital|mortal|nascid|vacina|farmac|regula|rnds|egestor|aps", re.I)
    r["detalhe"] = {}
    for p in pastas:
        if not interesse.search(p.rstrip("/")):
            continue
        s = pedir(S3 + "?" + urllib.parse.urlencode({"list-type": "2", "delimiter": "/", "prefix": p, "max-keys": 200}), timeout=40, limite=1_500_000)
        if "erro" in s:
            r["detalhe"][p] = s["erro"]
            continue
        sub, arqs = s3_parse(s["corpo"].decode("utf-8", "replace"))
        arqs.sort(key=lambda a: a["modificado"])
        r["detalhe"][p] = {"subpastas": [x.rstrip("/").split("/")[-1] for x in sub][:12], "arquivos": len(arqs),
                           "mais_recentes": [f"{a['chave'].split('/')[-1]} ({a['modificado']}, {a['bytes'] // 1024} KB)" for a in arqs[-4:]]}
        time.sleep(0.2)
        if len(r["detalhe"]) >= 40:
            break
    r["ok"] = len(pastas) > 0
    return r

def bloco_ckan_busca():
    F = []
    for termo in ("siops", "orcamento", "financiamento", "repasse"):
        s = sondar(f"ckan_busca_{termo}", f"Dados Abertos SUS: busca '{termo}'",
                   f"https://dadosabertos.saude.gov.br/api/3/action/package_search?q={termo}&rows=8", timeout=45)
        o = s.pop("_obj", None)
        if isinstance(o, dict) and isinstance(o.get("result"), dict):
            s["total"] = o["result"].get("count")
            s["conjuntos"] = [{"nome": p.get("name"), "titulo": (p.get("title") or "")[:90], "recursos": len(p.get("resources") or []),
                               "atualizado": (p.get("metadata_modified") or "")[:10]} for p in o["result"].get("results", [])[:8]]
        F.append(s)
    return F

def bloco_siops_paginas():
    F = []
    for id_, n, url, filtro in (("siops_gov", "SIOPS: pagina no gov.br", "https://www.gov.br/saude/pt-br/acesso-a-informacao/siops", r"dado|download|consulta|indicador|relat|csv|tabela|planilha|siops"),
                                ("siops_datasus", "SIOPS: portal do DATASUS", "https://siops.datasus.gov.br/", r"consulta|indicador|relat|municip|download|dado"),
                                ("siops_info", "SIOPS: pagina de informacoes", "https://www.gov.br/saude/pt-br/acesso-a-informacao/siops/dados", r"dado|download|csv|planilha|indicador")):
        p = pagina(id_, n, url, filtro=filtro, n=20)
        p.pop("_corpo", None)
        F.append(p)
    return F

def bloco_siconfi():
    """Despesa em saude por municipio pelo SICONFI: DCA (anual, por funcao) e anexos do RREO."""
    F = []
    dca = {"id": "siconfi_dca", "nome": "SICONFI DCA (Vitoria): anexos com despesa por funcao", "metodo": "GET", "tentativas_por_anexo": {}}
    achou = None
    for anexo in ("DCA-Anexo I-E", "DCA-Anexo I-D", "DCA-Anexo I-C", "DCA-Anexo I-F", "DCA-Anexo I-G", "DCA-Anexo I-HI"):
        for ano in (ANO - 1, ANO - 2):
            p = dict(an_exercicio=ano, no_anexo=anexo, id_ente=VITORIA)
            s = sondar("dca", anexo, SICONFI + "dca?" + urllib.parse.urlencode(p), timeout=60)
            o = s.pop("_obj", None)
            itens_ = o.get("items", []) if isinstance(o, dict) else []
            dca["tentativas_por_anexo"][f"{anexo} {ano}"] = len(itens_) if "erro" not in s else s.get("erro")
            if itens_:
                saude = [i for i in itens_ if re.search(r"sa[uú]de", str(i.get("conta", "")), re.I)]
                if saude and not achou:
                    achou = {"anexo": anexo, "ano": ano, "campos": list(itens_[0].keys())[:20], "linhas": len(itens_), "linhas_saude": len(saude),
                             "amostra_saude": [{"conta": str(i.get("conta"))[:70], "coluna": str(i.get("coluna"))[:50], "valor": i.get("valor")} for i in saude[:6]]}
                break
            time.sleep(0.3)
        if achou:
            break
    dca["anexo_com_saude"] = achou
    dca["ok"] = bool(achou)
    F.append(dca)
    base = rreo_paginas()
    base.pop("_obj", None)
    F.append(base)
    nomes = base.get("anexos_de_saude") or []
    for anexo in nomes[:2]:
        for nome, cod in (("Vitoria", VITORIA), ("Irupi", "3202900"), ("ES", ES_IBGE)):
            p = dict(an_exercicio=ANO - 1, nr_periodo=6, co_tipo_demonstrativo="RREO", no_anexo=anexo, id_ente=cod)
            s = sondar(f"rreo_v2_{cod}", f"RREO '{anexo}' {nome}, bim 6", SICONFI + "rreo?" + urllib.parse.urlencode(p), timeout=60,
                       nota="nome exato do anexo, vindo da paginacao")
            o = s.pop("_obj", None)
            if isinstance(o, dict):
                its = o.get("items", [])
                s["total_itens"] = len(its)
                s["amostra"] = [{"conta": str(i.get("conta"))[:70], "coluna": str(i.get("coluna"))[:40], "valor": i.get("valor")}
                                for i in its if re.search(r"m[ií]nimo|percentual|15|aplicad", str(i.get("conta", "")), re.I)][:6]
            F.append(s)
            time.sleep(0.3)
    return F

def bloco_transparencia(chave):
    F = []
    if not chave:
        return [{"id": "pt_spec", "nome": "Portal da Transparencia (API)", "ok": None, "nota": "sem chave"}]
    spec_r = sondar("pt_spec", "Portal da Transparencia: especificacao da API", PT_API + "/v3/api-docs", headers={"chave-api-dados": chave}, timeout=60, limite=8_000_000)
    spec = spec_r.pop("_obj", None)
    if not isinstance(spec, dict):
        spec_r["ok"] = False
        return [spec_r]
    rotas = params_openapi(spec, r"convenio|transferenc|funcao|saude|favorecid|emenda")
    spec_r["rotas_de_interesse"] = [{"path": x["path"], "obrigatorios": [p["name"] for p in x["params"] if p["required"]],
                                     "opcionais": [p["name"] for p in x["params"] if not p["required"]][:10]} for x in rotas][:30]
    F.append(spec_r)
    H = {"chave-api-dados": chave}
    hoje = datetime.now(BRT)
    for x in rotas:
        if not re.search(r"convenio|transferenc", x["path"], re.I) or "{" in x["path"]:
            continue
        q, faltam = montar_parametros(x["params"], hoje)
        if faltam:
            F.append({"id": "pt_teste", "nome": f"{x['path']}: nao testado", "ok": None, "nota": f"obrigatorios sem valor: {', '.join(faltam)}"})
            continue
        base = PT_API + (x["path"] if x["path"].startswith("/api-de-dados") else "/api-de-dados" + x["path"])
        s = sondar("pt_teste", f"{x['path']}: 1 pagina", base + "?" + urllib.parse.urlencode(q), headers=H, timeout=60,
                   nota="consulta minima dos ultimos 30 dias, orgao 36000 (Ministerio da Saude)")
        o = s.pop("_obj", None)
        if isinstance(o, list):
            s["total_itens"] = len(o)
            s["campos_item"] = list(o[0].keys())[:25] if o and isinstance(o[0], dict) else []
        F.append(s)
        time.sleep(1)
        if len(F) > 8:
            break
    PT = "https://portaldatransparencia.gov.br"
    for rotulo, caminho in (("transferencias", "transferencias"), ("emendas", "emendas-parlamentares")):
        for sufixo in (mes_anterior(), "UNICO") if rotulo == "emendas" else (mes_anterior(),):
            url = f"{PT}/download-de-dados/{caminho}/{sufixo}"
            o = pedir(url, headers={"Range": "bytes=0-400000"}, timeout=90, limite=410_000)
            r = {"id": f"pt_csv_{rotulo}", "nome": f"CSV de {rotulo} ({sufixo}): colunas", "url": url, "ms": o["ms"], "status": o.get("status")}
            if "erro" in o:
                r.update({"ok": False, "erro": o["erro"]})
            else:
                z = primeiro_arquivo_zip(o["corpo"])
                dados = z["bytes"] if z and z["bytes"] else o["corpo"]
                r["arquivo"] = z["nome"] if z else "(nao e zip)"
                r.update(cabecalho_csv(dados, linhas=0))
                r["ok"] = bool(r.get("colunas")) and len(r["colunas"]) > 3
            F.append(r)
            if r.get("ok"):
                break
    return F

def bloco_ans():
    F = []
    for u in ("https://www.ans.gov.br/operadoras-entity/v1/", "https://www.ans.gov.br/operadoras-entity/v1/operadoras?page=0&size=1"):
        s = sondar("ans_api", f"ANS API de operadoras: {u.split('v1/')[1] or 'raiz'}", u, timeout=45, nota="o documento cita este endereco, sem autenticacao")
        o = s.pop("_obj", None)
        if isinstance(o, (dict, list)):
            s["tipo_resposta"] = type(o).__name__
        F.append(s)
    p = pagina("ans_pda", "ANS Dados Abertos (PDA): indice", "https://dadosabertos.ans.gov.br/FTP/PDA/", filtro=r"benefici|operadora|cobertura|informacoes|taxa", n=30)
    p.pop("_corpo", None)
    F.append(p)
    pasta = next((x["url"] for x in p.get("links_encontrados", []) if re.search(r"benefici", x["texto"] + x["url"], re.I)), None)
    if pasta:
        q = pagina("ans_benef", "ANS: pasta de beneficiarios", pasta, n=60)
        q.pop("_corpo", None)
        q["links_encontrados"] = q.get("links_encontrados", [])[-12:]
        F.append(q)
    return F

def bloco_conasems():
    r = {"id": "conasems_tecnica", "nome": "CONASEMS: tecnica de leitura (site em Next.js)", "url": "https://www.conasems.org.br/"}
    o = pedir(r["url"], headers=HTML, timeout=45, limite=2_000_000)
    r["ms"], r["status"] = o["ms"], o.get("status")
    if "erro" in o:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    html = texto(o)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            nd = json.loads(m.group(1))
            r["next_build_id"] = bool(nd.get("buildId"))
            r["pageProps_chaves"] = list((nd.get("props") or {}).get("pageProps", {}).keys())[:20]
        except ValueError:
            r["next_data_invalido"] = True
    r["tem_next_data"] = bool(m)
    for caminho in ("sitemap.xml", "feed", "rss.xml"):
        s = pedir("https://www.conasems.org.br/" + caminho, headers=HTML, timeout=30, limite=1_500_000)
        d = {"status": s.get("status"), "erro": s.get("erro"), "tipo": s.get("tipo")}
        if caminho == "sitemap.xml" and not s.get("erro"):
            locs = re.findall(r"<loc>([^<]+)</loc>", texto(s))
            d["urls"] = len(locs)
            d["amostra_nota"] = [u for u in locs if re.search(r"nota|tecnic", u, re.I)][:8]
        r.setdefault("testes", {})[caminho] = d
    r["ok"] = r.get("tem_next_data") or any(t.get("status") == 200 for t in r.get("testes", {}).values())
    return r

def bloco_relatorioaps():
    r = {"id": "relatorioaps_js", "nome": "e-Gestor APS (relatorioaps): enderecos e arquivos citados nos scripts", "url": "https://relatorioaps.saude.gov.br/"}
    o = pedir(r["url"], headers=HTML, timeout=45, limite=2_000_000)
    r["ms"], r["status"] = o["ms"], o.get("status")
    if "erro" in o:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    html = texto(o)
    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', html, re.I)
    r["scripts"] = len(srcs)
    achados, apis = [], set()
    for s in srcs[:8]:
        u = urllib.parse.urljoin(r["url"], s)
        js = pedir(u, timeout=60, limite=6_000_000)
        txt = texto(js)
        achados += trechos_js(txt, r"competencia|download|export|xlsx|csv|baixar|\.zip", 12)
        for m in re.findall(r'["\'](https?://[A-Za-z0-9._\-/]*saude\.gov\.br[A-Za-z0-9._\-/]*)["\']', txt):
            apis.add(m[:140])
        for m in re.findall(r'["\'](/(?:api|v1|rest|relatorio)[A-Za-z0-9._\-/]{2,70})["\']', txt):
            apis.add(m)
    r["trechos_sobre_download"] = list(dict.fromkeys(achados))[:25]
    r["enderecos"] = sorted(apis)[:40]
    r["ok"] = bool(srcs)
    return r

# ---------------------------------------------------------------- bloco C: significado dos campos do Radar

def bloco_radar_campos():
    r = sondar("radar_brasil", "Radar de Recursos: brasil.json (teste de hipoteses dos campos)", "https://partelli.pro/fundo/brasil.json", timeout=60, limite=5_000_000)
    obj = r.pop("_obj", None)
    if obj is None:
        return r
    r["hipoteses"] = hipoteses_fundo(obj)
    r["ok"] = r["hipoteses"]["ufs"] >= 20
    return r

def bloco_leitos():
    return ckan_recursos("ckan_leitos5", "Dados Abertos SUS: hospitais e leitos (recursos mais recentes)", "hospitais-e-leitos", 20)

# ---------------------------------------------------------------- execucao

def seguro(nome, fn, *a):
    try:
        r = fn(*a)
    except Exception as e:
        return [{"id": nome, "nome": nome, "ok": False, "erro": f"{type(e).__name__}: {str(e)[:160]}"}]
    return r if isinstance(r, list) else [r]

def main():
    chave = os.environ.get("PORTAL_TRANSPARENCIA_KEY", "").strip()
    F = []
    for nome, fn, args in (
        ("cnes_formato", bloco_cnes, ()), ("infodengue_paralelo", bloco_infodengue_paralelo, ()), ("arboviroses", bloco_arboviroses, ()),
        ("emendas_amostra", bloco_emendas, (chave,)), ("sisab_colunas", bloco_sisab_colunas, ()),
        ("radar_campos", bloco_radar_campos, ()), ("s3_indice", bloco_s3_indice, ()), ("ckan_busca", bloco_ckan_busca, ()),
        ("siops_paginas", bloco_siops_paginas, ()), ("siconfi", bloco_siconfi, ()), ("transparencia", bloco_transparencia, (chave,)),
        ("ans", bloco_ans, ()), ("conasems", bloco_conasems, ()), ("relatorioaps", bloco_relatorioaps, ()), ("leitos", bloco_leitos, ())):
        t0 = time.time()
        F += seguro(nome, fn, *args)
        print(f"[{int(time.time() - t0):>3}s] {nome}", flush=True)
    for f in F:
        f.pop("_obj", None)
        f.pop("_corpo", None)
    resumo = {"ok": sum(1 for f in F if f.get("ok") is True), "falha": sum(1 for f in F if f.get("ok") is False),
              "nao_testado": sum(1 for f in F if f.get("ok") is None)}
    saida = {"rodada": 5, "gerado_em": datetime.now(BRT).isoformat(timespec="seconds"),
             "ambiente": "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local", "resumo": resumo, "fontes": F}
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem_r5.json", "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=1)
    L = ["| Fonte | Resultado | Tempo | Observacao |", "|---|---|---|---|"]
    for f in F:
        res = "ok" if f.get("ok") else ("nao testado" if f.get("ok") is None else f"FALHA {f.get('erro', f.get('status', ''))}")
        obs = []
        for k, rot in (("lidos", "registros lidos"), ("total_pastas", "pastas"), ("total_itens", "itens"), ("total_links_filtrados", "links")):
            if f.get(k) is not None:
                obs.append(f"{f[k]} {rot}")
        if f.get("fases"):
            obs.append("; ".join(f"{k}: erro {v['taxa_erro']}, {v['minutos_para_5570']} min/5570" for k, v in f["fases"].items()))
        if f.get("colunas"):
            obs.append(f"{len(f['colunas'])} colunas")
        L.append(f"| {f.get('nome', f.get('id'))} | {res} | {f.get('ms', '')} ms | {'; '.join(obs)} |")
    md = "\n".join(L)
    print(md)
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        with open(s, "a", encoding="utf-8") as fh:
            fh.write("## Sondagem das fontes (rodada 5)\n\n" + md + "\n")
    print(f"\nok={resumo['ok']} falha={resumo['falha']} nao_testado={resumo['nao_testado']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
