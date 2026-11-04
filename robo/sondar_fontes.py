#!/usr/bin/env python3
"""Sondagem das fontes publicas da Sala de Gestao em Saude.
Testa cada API a partir do ambiente em que roda (GitHub Actions) e grava dados/sondagem.json.
Nao guarda dados de pessoas. Chaves (se houver) vem de variaveis de ambiente, nunca do codigo."""
import ftplib, json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

TIMEOUT = 30
UA = "SalaGestaoSaude/0.1 (sondagem de fontes publicas; contato: partelli.pro)"
BRT = timezone(timedelta(hours=-3))
ES_IBGE = "32"          # codigo IBGE do Espirito Santo
VITORIA = "3205309"     # municipio usado como amostra

def chaves(obj, n=14):
    if isinstance(obj, dict):
        return list(obj.keys())[:n]
    if isinstance(obj, list) and obj:
        return chaves(obj[0], n)
    return []

def contar(obj):
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        for k in ("items", "data", "results", "gazettes", "parametros", "resultado"):
            if isinstance(obj.get(k), list):
                return len(obj[k])
    return None

def http(id_, nome, url, metodo="GET", headers=None, ler=True, nota=""):
    time.sleep(0.4)
    h = {"User-Agent": UA, "Accept": "application/json, */*"}
    h.update(headers or {})
    r = {"id": id_, "nome": nome, "url": url, "metodo": metodo, "nota": nota}
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=h, method=metodo)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            r["status"] = resp.status
            r["tipo"] = resp.headers.get("Content-Type", "")
            r["tamanho_http"] = resp.headers.get("Content-Length")
            r["ultima_modificacao"] = resp.headers.get("Last-Modified")
            if ler and metodo == "GET":
                corpo = resp.read(3_000_000)
                r["bytes_lidos"] = len(corpo)
                if "json" in r["tipo"] or corpo[:1] in (b"{", b"["):
                    try:
                        obj = json.loads(corpo.decode("utf-8", "replace"))
                        r["campos"] = chaves(obj)
                        r["registros"] = contar(obj)
                    except Exception:
                        r["json_valido"] = False
                else:
                    r["inicio"] = corpo[:160].decode("utf-8", "replace")
        r["ok"] = 200 <= r["status"] < 300
    except urllib.error.HTTPError as e:
        r["status"] = e.code
        r["ok"] = False
        r["erro"] = f"HTTP {e.code}"
    except Exception as e:
        r["ok"] = False
        r["erro"] = f"{type(e).__name__}: {str(e)[:160]}"
    r["ms"] = int((time.time() - t0) * 1000)
    return r

def ftp_lista(id_, nome, host, caminhos):
    r = {"id": id_, "nome": nome, "url": f"ftp://{host}", "metodo": "FTP", "nota": "lista pastas, nao baixa arquivos"}
    t0 = time.time()
    try:
        f = ftplib.FTP(host, timeout=TIMEOUT)
        f.login()
        r["pastas"] = {}
        for c in caminhos:
            try:
                r["pastas"][c] = f.nlst(c)[:25]
            except Exception as e:
                r["pastas"][c] = f"erro: {str(e)[:80]}"
        f.quit()
        r["ok"] = any(isinstance(v, list) and v for v in r["pastas"].values())
    except Exception as e:
        r["ok"] = False
        r["erro"] = f"{type(e).__name__}: {str(e)[:160]}"
    r["ms"] = int((time.time() - t0) * 1000)
    return r

def main():
    ano = datetime.now(BRT).year
    fontes = [
        # Territorio e populacao
        http("ibge_municipios", "IBGE localidades (municipios do ES)", f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{ES_IBGE}/municipios"),
        http("ibge_malha", "IBGE malha municipal do ES", f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{ES_IBGE}?formato=application/vnd.geo%2Bjson&intrarregiao=municipio&qualidade=minima", nota="espera-se 78 municipios"),
        http("ibge_populacao", "IBGE SIDRA populacao estimada (Vitoria)", f"https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/-1/variaveis/9324?localidades=N6[{VITORIA}]", nota="agregado 6579, variavel 9324 (a confirmar)"),
        # Escala nacional (Brasil todo)
        http("ibge_municipios_br", "IBGE localidades (todos os municipios do Brasil)", "https://servicodados.ibge.gov.br/api/v1/localidades/municipios", nota="espera-se 5570 municipios"),
        http("ibge_malha_br", "IBGE malha do Brasil por UF", "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo%2Bjson&intrarregiao=UF&qualidade=minima", nota="espera-se 27 UFs"),
        http("ibge_regioes_saude", "IBGE regioes de saude (candidato)", "https://servicodados.ibge.gov.br/api/v1/localidades/regioes-intermediarias", nota="regiao de saude vem do MS, nao do IBGE: so para comparar recortes"),
        # Epidemiologia
        http("infodengue", "InfoDengue alertas (Vitoria, dengue)", f"https://info.dengue.mat.br/api/alertcity?geocode={VITORIA}&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={ano}&ey_end={ano}"),
        http("infodengue_sp", "InfoDengue amostra Sudeste (Sao Paulo)", f"https://info.dengue.mat.br/api/alertcity?geocode=3550308&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={ano}&ey_end={ano}"),
        http("infodengue_manaus", "InfoDengue amostra Norte (Manaus)", f"https://info.dengue.mat.br/api/alertcity?geocode=1302603&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={ano}&ey_end={ano}"),
        http("infodengue_recife", "InfoDengue amostra Nordeste (Recife)", f"https://info.dengue.mat.br/api/alertcity?geocode=2611606&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={ano}&ey_end={ano}"),
        http("infodengue_poa", "InfoDengue amostra Sul (Porto Alegre)", f"https://info.dengue.mat.br/api/alertcity?geocode=4314902&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={ano}&ey_end={ano}"),
        # Rede assistencial
        http("cnes_zip", "CNES estabelecimentos (JSON em ZIP, so cabecalho)", "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_json.zip", metodo="HEAD"),
        http("ms_api_raiz", "API de Dados Abertos do MS (raiz)", "https://apidadosabertos.saude.gov.br/", nota="documentacao nao carregou na pesquisa"),
        http("ms_api_cnes", "API de Dados Abertos do MS (CNES, candidato)", "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos?limit=2&offset=0", nota="caminho candidato, a confirmar"),
        http("ms_api_docs", "API de Dados Abertos do MS (documentacao, candidato)", "https://apidadosabertos.saude.gov.br/docs", nota="caminho candidato, a confirmar"),
        http("ckan_leitos", "Portal de Dados Abertos do SUS (catalogo CKAN, Hospitais e Leitos)", "https://dadosabertos.saude.gov.br/api/3/action/package_show?id=hospitais-e-leitos", nota="lista os arquivos por competencia"),
        # Financiamento
        http("transferegov_fundoafundo", "Transferegov fundo a fundo (documentacao)", "https://api-publica.transferegov.gestao.gov.br/fundoafundo/docs", ler=False),
        http("transferegov_especiais", "Transferegov transferencias especiais (documentacao)", "https://api-publica.transferegov.gestao.gov.br/especiais/docs", ler=False),
        http("siconfi_entes", "SICONFI entes", "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes"),
        http("siconfi_rreo_es", "SICONFI RREO do ES (Anexo 12, saude), candidato", f"https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo?an_exercicio={ano-1}&nr_periodo=6&co_tipo_demonstrativo=RREO&no_anexo=RREO-Anexo%2012&id_ente={ES_IBGE}", nota="parametros a confirmar"),
        # Compras
        http("pncp_controle", "PNCP propostas abertas (controle, amostra ES)", "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta?dataFinal=" + (datetime.now(BRT) + timedelta(days=180)).strftime("%Y%m%d") + "&uf=ES&pagina=1&tamanhoPagina=10"),
        # Normas e diarios
        http("querido_diario", "Querido Diario (busca 'saude', amostra Vitoria)", f"https://api.queridodiario.org.br/gazettes?querystring=saude&territory_ids={VITORIA}&size=1"),
        # Cobertura suplementar
        http("ans_dados", "ANS operadoras ativas (catalogo dados.gov.br)", "https://dados.gov.br/dados/api/publico/conjuntos-dados/operadoras-de-planos-privados-de-saude", nota="caminho candidato"),
        # DATASUS
        ftp_lista("datasus_ftp", "DATASUS FTP (SIM, SINASC, SIH, SIA, CNES)", "ftp.datasus.gov.br",
                  ["/dissemin/publicos", "/dissemin/publicos/SIM", "/dissemin/publicos/SINASC", "/dissemin/publicos/SIHSUS", "/dissemin/publicos/SIASUS", "/dissemin/publicos/CNES"]),
    ]
    chave = os.environ.get("PORTAL_TRANSPARENCIA_KEY", "").strip()
    if chave:
        fontes.append(http("portal_transparencia", "Portal da Transparencia (emendas, saude)",
                           f"https://api.portaldatransparencia.gov.br/api-de-dados/emendas?ano={ano-1}&pagina=1&codigoFuncao=10",
                           headers={"chave-api-dados": chave}, nota="chave vinda de segredo do GitHub"))
    else:
        fontes.append({"id": "portal_transparencia", "nome": "Portal da Transparencia (emendas, saude)", "ok": None,
                       "nota": "nao testado: falta o segredo PORTAL_TRANSPARENCIA_KEY"})
    saida = {"gerado_em": datetime.now(BRT).isoformat(timespec="seconds"),
             "ambiente": "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local",
             "resumo": {"ok": sum(1 for f in fontes if f.get("ok") is True),
                        "falha": sum(1 for f in fontes if f.get("ok") is False),
                        "nao_testado": sum(1 for f in fontes if f.get("ok") is None)},
             "fontes": fontes}
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem.json", "w", encoding="utf-8") as fh:
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
            fh.write("## Sondagem das fontes\n\n" + texto + "\n")
    print(f"\nok={saida['resumo']['ok']} falha={saida['resumo']['falha']} nao_testado={saida['resumo']['nao_testado']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
