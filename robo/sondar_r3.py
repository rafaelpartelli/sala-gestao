#!/usr/bin/env python3
"""Sondagem (rodada 3) das fontes da Sala de Gestao em Saude.
Foco: especificacoes de API (MS, Transferegov), RREO, volume do InfoDengue, SINASC, Querido Diario,
Atencao Primaria (indicadores, e-Gestor APS, SISAB) e radar de notas tecnicas.
Guarda so status, tempos, contagens, nomes de campos e titulos/links de paginas publicas.
Nenhum dado de pessoa e nenhum segredo e gravado."""
import json, os, re, sys, time, urllib.parse
from datetime import datetime, timezone, timedelta
from html import unescape
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sondar_fontes import pedir, sondar, chaves, itens, ftp_listas, BRT, ES_IBGE, VITORIA, ANO

RE_LINK = re.compile(r'<a\b[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)

def links(corpo, base, filtro=None, n=25):
    """Extrai (texto, url) de uma pagina HTML publica. filtro: regex aplicado ao texto ou ao href."""
    html = corpo.decode("utf-8", "replace")
    vistos, saida = set(), []
    for href, txt in RE_LINK.findall(html):
        t = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", txt))).strip()
        u = urllib.parse.urljoin(base, unescape(href))
        if filtro and not re.search(filtro, t + " " + u, re.I):
            continue
        if u in vistos:
            continue
        vistos.add(u)
        saida.append({"texto": t[:110], "url": u[:200]})
        if len(saida) >= n:
            break
    return saida

def pagina(id_, nome, url, filtro=None, nota="", timeout=45, n=25):
    o = pedir(url, headers={"Accept": "text/html,*/*"}, timeout=timeout, limite=2_000_000)
    r = {"id": id_, "nome": nome, "url": url, "metodo": "GET", "nota": nota, "ms": o["ms"], "status": o.get("status")}
    if "erro" in o:
        r["ok"] = False
        r["erro"] = o["erro"]
        return r
    r["ok"] = 200 <= o["status"] < 300
    c = o.get("corpo") or b""
    r["tipo"] = o.get("tipo")
    r["bytes_lidos"] = len(c)
    titulo = re.search(rb"<title[^>]*>(.*?)</title>", c, re.I | re.S)
    r["titulo"] = re.sub(r"\s+", " ", unescape(titulo.group(1).decode("utf-8", "replace"))).strip()[:140] if titulo else None
    r["links_encontrados"] = links(c, url, filtro, n)
    r["total_links_filtrados"] = len(r["links_encontrados"])
    r["_corpo"] = c
    return r

def spa_endpoints(id_, nome, url, nota=""):
    """e-Gestor APS e uma pagina dinamica: le a pagina e os arquivos .js para achar enderecos de API (so textos de caminho)."""
    r = pagina(id_, nome, url, nota=nota, filtro=None, n=5)
    c = r.pop("_corpo", b"")
    r["scripts"] = []
    r["enderecos_api"] = []
    if not c:
        return r
    html = c.decode("utf-8", "replace")
    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I)
    achados = set()
    for s in srcs[:6]:
        u = urllib.parse.urljoin(url, s)
        o = pedir(u, timeout=40, limite=4_000_000)
        r["scripts"].append({"url": u[:160], "status": o.get("status"), "bytes": len(o.get("corpo") or b"")})
        txt = (o.get("corpo") or b"").decode("utf-8", "replace")
        for m in re.findall(r'["\'](https?://[A-Za-z0-9._\-/]*(?:saude\.gov\.br|api)[A-Za-z0-9._\-/]*)["\']', txt):
            achados.add(m[:160])
        for m in re.findall(r'["\'](/(?:api|v1|rest|relatorio)[A-Za-z0-9._\-/]{2,80})["\']', txt):
            achados.add(m)
    r["enderecos_api"] = sorted(achados)[:40]
    return r

def rreo_paginas():
    """Descobre os nomes dos anexos do RREO e a paginacao (limit/offset) para Vitoria."""
    base = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo?"
    p = dict(an_exercicio=ANO - 1, nr_periodo=6, co_tipo_demonstrativo="RREO", id_ente=VITORIA)
    r = {"id": "rreo_paginacao", "nome": "SICONFI RREO (Vitoria): paginacao e nomes de anexos", "metodo": "GET", "nota": "varre paginas ate achar o anexo de saude"}
    anexos, total, ms = {}, 0, 0
    campos = []
    for off in range(0, 5000, 500):
        o = pedir(base + urllib.parse.urlencode(dict(p, offset=off)), timeout=45)
        ms += o["ms"]
        if "erro" in o:
            r["erro"] = o["erro"]
            break
        try:
            obj = json.loads(o["corpo"].decode("utf-8", "replace"))
        except Exception:
            break
        lst = obj.get("items", []) if isinstance(obj, dict) else []
        if lst and not campos:
            campos = list(lst[0].keys())[:25]
        for i in lst:
            a = str(i.get("anexo", ""))
            anexos[a] = anexos.get(a, 0) + 1
        total += len(lst)
        if not obj.get("hasMore"):
            break
        time.sleep(0.3)
    r.update({"ok": total > 0, "ms": ms, "registros_lidos": total, "campos_item": campos,
              "anexos": dict(sorted(anexos.items())[:40]), "anexos_de_saude": [a for a in anexos if re.search(r"12|saude|saúde", a, re.I)]})
    return r

def infodengue_500(entes, quantos=500):
    """Teste de volume: percorre uma amostra de municipios em ordem, para medir erros e limite de uso."""
    muni = [e for e in entes if str(e.get("esfera", "")).strip() == "M" and e.get("cod_ibge")]
    r = {"id": "infodengue_volume", "nome": f"InfoDengue: {quantos} municipios em sequencia", "metodo": "GET", "nota": "para o dimensionamento da coleta nacional"}
    if len(muni) < quantos:
        r.update({"ok": None, "nota": r["nota"] + ". Nao testado: lista de municipios indisponivel."})
        return r
    passo = max(1, len(muni) // quantos)
    amostra = muni[::passo][:quantos]
    cod, tempos, erros_seguidos, t0 = {}, [], 0, time.time()
    for e in amostra:
        url = f"https://info.dengue.mat.br/api/alertcity?geocode={e['cod_ibge']}&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={ANO}&ey_end={ANO}"
        o = pedir(url, timeout=40)
        k = str(o.get("status") or o.get("erro", "erro")[:25])
        cod[k] = cod.get(k, 0) + 1
        tempos.append(o["ms"])
        erros_seguidos = 0 if k == "200" else erros_seguidos + 1
        if erros_seguidos >= 15 or time.time() - t0 > 900:
            r["interrompido"] = "muitos erros seguidos ou limite de 15 min"
            break
        time.sleep(0.1)
    tempos.sort()
    r.update({"ok": cod.get("200", 0) >= 0.95 * len(tempos), "testados": len(tempos), "respostas_por_codigo": cod,
              "ms_mediana": tempos[len(tempos) // 2], "ms_p95": tempos[max(0, int(len(tempos) * 0.95) - 1)],
              "segundos_total": int(time.time() - t0),
              "estimativa_min_5570": round(5570 * (sum(tempos) / len(tempos) / 1000 + 0.1) / 60)})
    return r

def arquivos_json(id_, nome, url, nota=""):
    """Le a pagina e seus scripts e lista caminhos de arquivos .json citados (so nomes de caminho)."""
    r = pagina(id_, nome, url, nota=nota, n=10)
    c = r.pop("_corpo", b"")
    achados = set()
    if c:
        html = c.decode("utf-8", "replace")
        textos = [html]
        for s in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I)[:8]:
            o = pedir(urllib.parse.urljoin(url, s), timeout=40, limite=3_000_000)
            textos.append((o.get("corpo") or b"").decode("utf-8", "replace"))
        for txt in textos:
            for m in re.findall(r'["\']([A-Za-z0-9_\-./]*\.json)(?:\?[^"\']*)?["\']', txt):
                achados.add(m[:120])
    r["arquivos_json"] = sorted(achados)[:40]
    return r

def mes_anterior():
    h = datetime.now(BRT).replace(day=1) - timedelta(days=1)
    return h.strftime("%Y%m")

def transparencia_e_fns(F):
    PT = "https://portaldatransparencia.gov.br"
    ym = mes_anterior()
    # Uniao: paginas de download e teste dos arquivos por HEAD (nao baixa)
    for id_, n, path in (("pt_transferencias", "Portal da Transparencia: recursos transferidos", "/download-de-dados/transferencias"),
                         ("pt_convenios", "Portal da Transparencia: convenios", "/download-de-dados/convenios"),
                         ("pt_emendas", "Portal da Transparencia: emendas parlamentares", "/download-de-dados/emendas-parlamentares"),
                         ("pt_despesas_exec", "Portal da Transparencia: execucao da despesa", "/download-de-dados/despesas-execucao")):
        p = pagina(id_, n, PT + path, filtro=r"download|\.zip|\.csv|\d{6}", nota="pagina de download (CSV)", n=15)
        p.pop("_corpo", None)
        F.append(p)
    for id_, n, path in (("pt_head_emendas", "Arquivo de emendas (HEAD)", "/download-de-dados/emendas-parlamentares/UNICO"),
                         ("pt_head_transf", f"Arquivo de transferencias {ym} (HEAD)", f"/download-de-dados/transferencias/{ym}"),
                         ("pt_head_conv", "Arquivo de convenios (HEAD)", "/download-de-dados/convenios/UNICO")):
        F.append(sondar(id_, n, PT + path, metodo="HEAD", ler=False, timeout=60, nota="padrao de URL candidato, so cabecalhos (tamanho e data)"))
    r = sondar("pt_api_docs", "API do Portal da Transparencia: especificacao", "https://api.portaldatransparencia.gov.br/v3/api-docs", nota="lista de endpoints; a chave so e pedida nas consultas")
    obj = r.pop("_obj", None)
    if isinstance(obj, dict) and isinstance(obj.get("paths"), dict):
        r["endpoints_interesse"] = sorted(p for p in obj["paths"] if re.search(r"emenda|convenio|transfer|despesa|saude|recursos", p, re.I))[:40]
        r["total_endpoints"] = len(obj["paths"])
    F.append(r)
    # Estados: portais e catalogos abertos (candidatos)
    for id_, n, url, filtro in (("uf_es_dados", "ES: base de dados abertos", "https://transparencia.es.gov.br/DadosAbertos/BaseDeDados", r"csv|json|xls|download|sa[uú]de"),
                                ("uf_sp", "SP: portal da transparencia", "https://www.transparencia.sp.gov.br/", r"dados|abert|csv|api"),
                                ("uf_pr", "PR: portal da transparencia", "https://www.transparencia.pr.gov.br/pte/", r"dados|abert|csv|api")):
        p = pagina(id_, n, url, filtro=filtro, nota="candidato: o que cada estado publica de forma aberta", n=15)
        p.pop("_corpo", None)
        F.append(p)
    for id_, n, url in (("uf_mg_ckan", "MG: catalogo de dados abertos (busca saude)", "https://dados.mg.gov.br/api/3/action/package_search?q=saude&rows=5"),
                        ("uf_pe_ckan", "PE: catalogo de dados abertos (busca saude)", "https://dados.pe.gov.br/api/3/action/package_search?q=saude&rows=5")):
        F.append(sondar(id_, n, url, timeout=45, nota="CKAN candidato"))
    # FNS e Ministerio: o que existe alem dos paineis InvestSUS
    for id_, n, url, filtro in (("fns_portal", "FNS: portal", "https://portalfns.saude.gov.br/", r"repasse|consulta|painel|relat|dados|convenio|emenda"),
                                ("fns_gov", "Ministerio da Saude: convenios e transferencias", "https://www.gov.br/saude/pt-br/acesso-a-informacao/convenios-e-transferencias", r"repasse|convenio|transfer|csv|xls|painel"),
                                ("fns_dadosabertos", "Dados Abertos SUS: busca 'fundo nacional'", "https://dadosabertos.saude.gov.br/dataset?q=fundo+nacional", r"dataset/")):
        p = pagina(id_, n, url, filtro=filtro, nota="o que o FNS publica fora dos paineis", n=20)
        p.pop("_corpo", None)
        F.append(p)
    # Ligacao com o que ja extraimos (sem refazer a coleta)
    for id_, n, url in (("elo_fundo", "partelli.pro: Radar de Recursos (arquivos de dados)", "https://partelli.pro/gestor/recursos/"),
                        ("elo_gestor", "partelli.pro: area do gestor (paginas e dados)", "https://partelli.pro/gestor/")):
        F.append(arquivos_json(id_, n, url, nota="mostra onde os dados ja coletados ficam publicados"))

def main():
    F = []
    # 1. Especificacoes de API
    for mod in ("fundoafundo", "especiais"):
        base = f"https://api-publica.transferegov.gestao.gov.br/{mod}/"
        r = sondar(f"tg_{mod}_openapi", f"Transferegov {mod}: raiz pedindo OpenAPI", base, headers={"Accept": "application/openapi+json"}, nota="PostgREST devolve o esquema com esse Accept")
        obj = r.pop("_obj", None)
        if isinstance(obj, dict) and isinstance(obj.get("paths"), dict):
            r["tabelas"] = [p.strip("/") for p in obj["paths"] if not p.startswith("/rpc")][:60]
            r["total_tabelas"] = len(r["tabelas"])
        F.append(r)
        for t in ("programa", "plano_acao", "empenho", "relatorio_gestao"):
            F.append(sondar(f"tg_{mod}_{t}", f"Transferegov {mod}: tabela {t} (1 linha)", base + t + "?limit=1", nota="candidato, so nomes de campos"))
    for i, cam in enumerate(("v3/api-docs", "openapi.json", "docs", "swagger-ui/index.html", "v1/docs", "v1/openapi.json")):
        F.append(sondar(f"ms_doc_{i}", f"API do MS: /{cam}", "https://apidadosabertos.saude.gov.br/" + cam, nota="busca da especificacao"))
    # 2. RREO
    F.append(rreo_paginas())
    # 3. InfoDengue em volume
    entes = sondar("siconfi_entes", "SICONFI entes", "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes")
    lista = (entes.pop("_obj", None) or {}).get("items", [])
    F.append(entes)
    F.append(infodengue_500(lista, 500))
    # 4. Nascimentos, vigilancia
    F.append(ftp_listas("datasus_sinasc", "DATASUS FTP: SINASC (variantes de pasta)", "ftp.datasus.gov.br",
                        ["/dissemin/publicos/SINASC", "/dissemin/publicos/SINASC/1996_/Dados/DNRES", "/dissemin/publicos/SINASC/NOV/DNRES", "/dissemin/publicos/SINAN/DADOS/FINAIS", "/dissemin/publicos/PNI/DADOS"]))
    F.append(sondar("querido_diario2", "Querido Diario (busca 'saude', Vitoria), nova tentativa", f"https://api.queridodiario.org.br/gazettes?querystring=saude&territory_ids={VITORIA}&size=1", timeout=90, tentativas=2))
    # 5. Atencao Primaria
    ds = pagina("aps_dataset", "Dados Abertos SUS: indicadores de desempenho SISAB (pagina)", "https://dadosabertos.saude.gov.br/dataset/indicadores_desempenho_sisab",
                filtro=r"\.(csv|zip|xlsx?|json|pdf)|download|s3\.", nota="lista os arquivos do conjunto e seus formatos", n=40)
    ds.pop("_corpo", None)
    F.append(ds)
    F.append(sondar("aps_ckan_pkg", "Dados Abertos SUS: package_show do conjunto (candidato)", "https://dadosabertos.saude.gov.br/api/3/action/package_show?id=indicadores_desempenho_sisab", nota="CKAN, ja falhou em variantes; retestar"))
    F.append(sondar("aps_ms_api", "API do MS: candidatos de APS", "https://apidadosabertos.saude.gov.br/cnes/equipes?limit=2&offset=0", nota="caminho candidato (equipes da APS no CNES)"))
    e = spa_endpoints("aps_egestor", "e-Gestor APS: pagina e enderecos de API nos scripts", "https://egestoraps.saude.gov.br/", nota="pagina dinamica")
    F.append(e)
    for i, (n, u) in enumerate((("SISAB (raiz)", "https://sisab.saude.gov.br/"),
                                ("SISAB relatorios publicos", "https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/federal/saude/RelSauPreNatal.xhtml"),
                                ("e-Gestor APS: informacao e gestao (cobertura)", "https://relatorioaps.saude.gov.br/"))):
        p = pagina(f"aps_sisab_{i}", n, u, filtro=r"relat|cobertura|indicador|vincul|csv|xls", nota="candidato", n=20)
        p.pop("_corpo", None)
        F.append(p)
    # 6. Notas tecnicas (radar): paginas oficiais de listagem
    nt = (("nt_ms", "Ministerio da Saude: notas tecnicas", "https://www.gov.br/saude/pt-br/centrais-de-conteudo/publicacoes/notas-tecnicas"),
          ("nt_ms_saps", "Ministerio da Saude: SAPS (atencao primaria)", "https://www.gov.br/saude/pt-br/composicao/saps"),
          ("nt_conass", "CONASS: notas tecnicas", "https://www.conass.org.br/biblioteca/notas-tecnicas/"),
          ("nt_conass_rss", "CONASS: feed de noticias (candidato)", "https://www.conass.org.br/feed/"),
          ("nt_conasems", "CONASEMS: notas tecnicas", "https://www.conasems.org.br/notas-tecnicas/"),
          ("nt_ms_rss", "gov.br/saude: feed (candidato)", "https://www.gov.br/saude/pt-br/assuntos/noticias/RSS"),
          ("nt_dou", "Imprensa Nacional: consulta DOU (pagina)", "https://www.in.gov.br/consulta"))
    for id_, n, u in nt:
        p = pagina(id_, n, u, filtro=r"nota[s]?[- _]t[eé]cnica|nota-tecnica|informe|portaria|ofício|oficio|\.pdf|<item", nota="radar de notas tecnicas: so titulo, data e link", n=20)
        p.pop("_corpo", None)
        F.append(p)
    transparencia_e_fns(F)
    chave = os.environ.get("PORTAL_TRANSPARENCIA_KEY", "").strip()
    if chave:
        F.append(sondar("portal_transparencia", "Portal da Transparencia (emendas, saude)", f"https://api.portaldatransparencia.gov.br/api-de-dados/emendas?ano={ANO-1}&pagina=1&codigoFuncao=10", headers={"chave-api-dados": chave}))
    for f in F:
        f.pop("_obj", None)
        f.pop("_corpo", None)
    saida = {"rodada": 3, "gerado_em": datetime.now(BRT).isoformat(timespec="seconds"),
             "ambiente": "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local",
             "resumo": {"ok": sum(1 for f in F if f.get("ok") is True), "falha": sum(1 for f in F if f.get("ok") is False), "nao_testado": sum(1 for f in F if f.get("ok") is None)},
             "fontes": F}
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem_r3.json", "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=1)
    L = ["| Fonte | Resultado | Tempo | Observacao |", "|---|---|---|---|"]
    for f in F:
        res = "ok" if f.get("ok") else ("nao testado" if f.get("ok") is None else f"FALHA {f.get('erro', f.get('status', ''))}")
        obs = f.get("nota", "")
        if f.get("registros") is not None:
            obs = f"{f['registros']} registros. " + obs
        if f.get("total_links_filtrados"):
            obs = f"{f['total_links_filtrados']} links. " + obs
        if f.get("arquivos_json"):
            obs = f"{len(f['arquivos_json'])} arquivos .json citados. " + obs
        if f.get("endpoints_interesse"):
            obs = f"{len(f['endpoints_interesse'])} endpoints de interesse. " + obs
        if f.get("enderecos_api"):
            obs = f"{len(f['enderecos_api'])} enderecos de API nos scripts. " + obs
        L.append(f"| {f['nome']} | {res} | {f.get('ms', '')} ms | {obs} |")
    texto = "\n".join(L)
    print(texto)
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        with open(s, "a", encoding="utf-8") as fh:
            fh.write("## Sondagem das fontes (rodada 3)\n\n" + texto + "\n")
    print(f"\nok={saida['resumo']['ok']} falha={saida['resumo']['falha']} nao_testado={saida['resumo']['nao_testado']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
