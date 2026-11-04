#!/usr/bin/env python3
"""Sondagem (rodada 4) da Sala de Gestao em Saude.
Foco: ler as especificacoes de API (Transferegov, Ministerio da Saude, e-Gestor APS), achar o padrao dos
arquivos do Portal da Transparencia, localizar o anexo de saude do RREO, listar os arquivos dos conjuntos
de dados abertos do SUS e ler a estrutura dos arquivos ja publicados pelo Radar de Recursos.
Guarda so status, tempos, contagens, nomes de campos e enderecos publicos. Nenhum dado de pessoa, nenhum segredo."""
import json, os, re, sys, time, urllib.parse
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sondar_fontes import pedir, sondar, chaves, BRT, ES_IBGE, VITORIA, ANO
from sondar_r3 import pagina, mes_anterior, links

HTML = {"Accept": "text/html,*/*"}

def texto(o):
    return (o.get("corpo") or b"").decode("utf-8", "replace")

def achar_specs(html, base):
    """Procura enderecos de especificacao OpenAPI em um HTML de Swagger UI."""
    cand = set()
    for m in re.findall(r'(?:url|spec-?url|configUrl)["\']?\s*[:=]\s*["\']([^"\']+)["\']', html, re.I):
        cand.add(urllib.parse.urljoin(base, m))
    for m in re.findall(r'["\']([^"\']*(?:openapi|swagger|api-docs)[^"\']*\.(?:json|yaml))["\']', html, re.I):
        cand.add(urllib.parse.urljoin(base, m))
    return sorted(cand)[:10]

def caminhos_openapi(obj):
    if isinstance(obj, dict) and isinstance(obj.get("paths"), dict):
        return sorted(obj["paths"].keys())
    return []

def spec_api(id_, nome, base, extras=()):
    """Le o HTML do Swagger, acha a especificacao, lista caminhos e testa 1 linha de ate 3 tabelas."""
    r = {"id": id_, "nome": nome, "url": base, "metodo": "GET"}
    o = pedir(base, headers=HTML, timeout=45, limite=2_000_000)
    r["ms"] = o["ms"]
    if "erro" in o:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    html = texto(o)
    cand = achar_specs(html, base) + [urllib.parse.urljoin(base, e) for e in extras]
    r["especificacoes_candidatas"] = cand[:12]
    for u in list(dict.fromkeys(cand)):
        s = pedir(u, headers={"Accept": "application/json"}, timeout=45, limite=6_000_000)
        if "erro" in s or not (200 <= s["status"] < 300):
            continue
        try:
            obj = json.loads(texto(s))
        except Exception:
            continue
        caminhos = caminhos_openapi(obj)
        if caminhos:
            r["especificacao_ok"] = u
            r["caminhos"] = caminhos[:80]
            r["total_caminhos"] = len(caminhos)
            tabelas = [c for c in caminhos if c.count("/") == 1 and not c.startswith("/rpc")][:3]
            r["amostras"] = []
            for t in tabelas:
                a = sondar("amostra", t, base.rstrip("/") + t + "?limit=1", nota="1 linha")
                a.pop("_obj", None)
                r["amostras"].append({"tabela": t, "ok": a.get("ok"), "campos": a.get("campos"), "status": a.get("status")})
            break
    r["ok"] = bool(r.get("especificacao_ok"))
    return r

def egestor_api():
    """O e-Gestor APS cita apiegestoraps.saude.gov.br: testa a raiz e procura caminhos publicos no script principal."""
    base = "https://apiegestoraps.saude.gov.br"
    r = {"id": "egestor_api", "nome": "e-Gestor APS: API (raiz e caminhos no script)", "url": base, "metodo": "GET", "testes": []}
    for c in ("/", "/swagger-ui/index.html", "/v3/api-docs", "/v2/api-docs", "/swagger-ui.html"):
        o = pedir(base + c, headers={"Accept": "application/json,text/html"}, timeout=30, limite=300_000)
        r["testes"].append({"caminho": c, "status": o.get("status"), "erro": o.get("erro"), "tipo": o.get("tipo"),
                            "inicio": re.sub(r"\s+", " ", texto(o)[:120])})
    pg = pedir("https://egestoraps.saude.gov.br/", headers=HTML, timeout=40)
    scripts = re.findall(r'src=["\'](main\.[A-Za-z0-9]+\.js)["\']', texto(pg))
    achados = set()
    if scripts:
        js = texto(pedir("https://egestoraps.saude.gov.br/" + scripts[0], timeout=60, limite=4_000_000))
        for m in re.findall(r'["\'](/[A-Za-z0-9_\-/{}]{3,70})["\']', js):
            if re.search(r"relat|public|cobertura|financ|equipe|municip|estabelec|competenc|download|export", m, re.I):
                achados.add(m)
    r["caminhos_no_script"] = sorted(achados)[:80]
    r["ok"] = any(t.get("status") and t["status"] < 500 for t in r["testes"]) or bool(achados)
    return r

def transparencia():
    F = []
    PT = "https://portaldatransparencia.gov.br"
    ym = mes_anterior()
    p = pagina("pt_conv_pagina", "Portal da Transparencia: pagina de convenios (padrao dos arquivos)", PT + "/download-de-dados/convenios", n=5)
    html = p.pop("_corpo", b"").decode("utf-8", "replace")
    p["padroes_de_arquivo"] = sorted(set(re.findall(r'/download-de-dados/convenios/[A-Za-z0-9_\-/]*', html)))[:10]
    F.append(p)
    ano_mes = datetime.now(BRT).replace(day=1)
    anterior2 = (ano_mes.replace(day=1) - timedelta(days=40)).strftime("%Y%m")
    for sufixo in ("UNICO", ym, anterior2, str(ANO)):
        F.append(sondar(f"pt_conv_{sufixo}", f"Convenios, arquivo {sufixo} (HEAD)", f"{PT}/download-de-dados/convenios/{sufixo}", metodo="HEAD", ler=False, timeout=60, nota="so cabecalhos"))
    chave = os.environ.get("PORTAL_TRANSPARENCIA_KEY", "").strip()
    if chave:
        H = {"chave-api-dados": chave}
        api = "https://api.portaldatransparencia.gov.br/api-de-dados"
        for id_, n, rota in (("pt_api_emendas", "API: emendas (2025, pagina 1)", f"/emendas?ano={ANO-1}&pagina=1"),
                             ("pt_api_funcoes", "API: funcoes da despesa", "/despesas/funcional-programatica/funcoes?pagina=1"),
                             ("pt_api_subfuncoes", "API: subfuncoes da despesa", "/despesas/funcional-programatica/subfuncoes?pagina=1")):
            s = sondar(id_, n, api + rota, headers=H, timeout=45, nota="chave vinda de segredo")
            obj = s.pop("_obj", None)
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                s["campos_item"] = list(obj[0].keys())[:30]
            F.append(s)
    else:
        F.append({"id": "pt_api", "nome": "API do Portal da Transparencia", "ok": None, "nota": "sem chave"})
    return F

def rreo_saude():
    """Descobre onde esta o demonstrativo de saude (anexo 12) em entes e periodos diferentes."""
    F = []
    base = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/"
    ex = sondar("extrato_vitoria", "SICONFI extrato de entregas (Vitoria, 2025): demonstrativos", base + "extrato_entregas?" + urllib.parse.urlencode(dict(id_ente=VITORIA, an_referencia=ANO - 1)), nota="lista o que foi entregue")
    obj = ex.pop("_obj", None)
    itens = obj.get("items", []) if isinstance(obj, dict) else []
    if itens:
        ex["campos_item"] = list(itens[0].keys())[:20]
        ex["entregaveis"] = sorted({str(i.get("entregavel", i.get("demonstrativo", ""))) for i in itens})[:40]
        ex["periodos"] = sorted({str(i.get("periodo", "")) for i in itens})[:12]
    F.append(ex)
    entes = [("ES", ES_IBGE), ("Vitoria", VITORIA), ("Sao Paulo", "3550308"), ("Irupi (pequeno)", "3202900")]
    for nome, cod in entes:
        for per in (3, 5):
            for anexo in ("RREO-Anexo 12", "RREO-Anexo 08"):
                p = dict(an_exercicio=ANO - 1, nr_periodo=per, co_tipo_demonstrativo="RREO", no_anexo=anexo, id_ente=cod)
                r = sondar(f"rreo_{cod}_{per}_{anexo[-2:]}", f"RREO {anexo[-8:]} {nome} bim {per}", base + "rreo?" + urllib.parse.urlencode(p), nota="busca do anexo de saude")
                o = r.pop("_obj", None)
                if isinstance(o, dict):
                    r["total_itens"] = len(o.get("items", []))
                F.append(r)
    # variante "RREO Simplificado"
    p = dict(an_exercicio=ANO - 1, nr_periodo=6, co_tipo_demonstrativo="RREO Simplificado", id_ente="3202900")
    r = sondar("rreo_simplificado", "RREO simplificado (Irupi, bim 6)", base + "rreo?" + urllib.parse.urlencode(p))
    o = r.pop("_obj", None)
    if isinstance(o, dict):
        r["total_itens"] = len(o.get("items", []))
        r["anexos_encontrados"] = sorted({str(i.get("anexo", "")) for i in o.get("items", [])})[:20]
    F.append(r)
    return F

def ckan_recursos(id_, nome, slug, limite=10):
    """Le a pagina de um conjunto do Dados Abertos SUS, abre as paginas dos recursos e testa os enderecos de download (HEAD)."""
    base = "https://dadosabertos.saude.gov.br"
    r = {"id": id_, "nome": nome, "url": f"{base}/dataset/{slug}", "metodo": "GET", "recursos": []}
    o = pedir(r["url"], headers=HTML, timeout=45, limite=3_000_000)
    r["ms"] = o["ms"]
    if "erro" in o:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    html = texto(o)
    recs = sorted(set(re.findall(r'/dataset/' + re.escape(slug) + r'/resource/[A-Za-z0-9\-]+', html)))[:limite]
    r["total_recursos_na_pagina"] = len(recs)
    for rc in recs:
        d = {"pagina": rc}
        p = pedir(base + rc, headers=HTML, timeout=40, limite=1_500_000)
        h = texto(p)
        t = re.search(r"<title[^>]*>(.*?)</title>", h, re.I | re.S)
        d["titulo"] = re.sub(r"\s+", " ", t.group(1)).strip()[:110] if t else None
        arq = re.findall(r'href=["\'](https?://[^"\']+\.(?:csv|zip|json|xlsx?|parquet|ods|dbf|dbc)(?:\?[^"\']*)?)["\']', h, re.I)
        d["arquivos"] = list(dict.fromkeys(arq))[:3]
        if d["arquivos"]:
            hd = sondar("head", "arquivo", d["arquivos"][0], metodo="HEAD", ler=False, timeout=40)
            d["tamanho_bytes"] = hd.get("tamanho_http")
            d["ultima_modificacao"] = hd.get("ultima_modificacao")
            d["status_download"] = hd.get("status")
        r["recursos"].append(d)
        time.sleep(0.2)
    r["ok"] = any(x.get("arquivos") for x in r["recursos"])
    return r

def notas():
    F = []
    for id_, n, url in (("nt_conasems_wp", "CONASEMS: posts sobre nota tecnica (WordPress)", "https://www.conasems.org.br/wp-json/wp/v2/posts?search=nota%20t%C3%A9cnica&per_page=5&_fields=date,link,title"),
                        ("nt_conass_wp", "CONASS: posts sobre nota tecnica (WordPress)", "https://www.conass.org.br/wp-json/wp/v2/posts?search=nota%20t%C3%A9cnica&per_page=5&_fields=date,link,title")):
        r = sondar(id_, n, url, timeout=45, nota="candidato: lista com data, titulo e link")
        o = r.pop("_obj", None)
        if isinstance(o, list):
            r["itens"] = [{"data": i.get("date"), "titulo": (i.get("title") or {}).get("rendered", "")[:110], "link": i.get("link")} for i in o[:5]]
        F.append(r)
    return F

def ligacao_radar():
    """Le a estrutura dos arquivos ja publicados pelo Radar de Recursos para ligar a sala sem refazer a coleta."""
    F = []
    for id_, url in (("rad_brasil", "https://partelli.pro/fundo/brasil.json"), ("rad_mapa", "https://partelli.pro/gestor/recursos/mapa-brasil.json"),
                     ("rad_radar", "https://partelli.pro/radar/radar.json"), ("rad_novidades", "https://partelli.pro/gestor/novidades.json")):
        r = sondar(id_, f"partelli.pro: {url.split('partelli.pro')[1]}", url, timeout=60, limite=15_000_000, nota="estrutura do arquivo publicado")
        obj = r.pop("_obj", None)
        if isinstance(obj, dict):
            r["chaves_topo"] = list(obj.keys())[:30]
            if isinstance(obj.get("meta"), dict):
                r["meta"] = {k: obj["meta"][k] for k in list(obj["meta"].keys())[:12] if not isinstance(obj["meta"][k], (dict, list))}
            for k, v in obj.items():
                if isinstance(v, (list, dict)):
                    r.setdefault("tamanhos", {})[k] = len(v)
        elif isinstance(obj, list):
            r["total_itens"] = len(obj)
            if obj and isinstance(obj[0], dict):
                r["campos_item"] = list(obj[0].keys())[:25]
        F.append(r)
    return F

def main():
    F = []
    F.append(spec_api("tg_fundoafundo_spec", "Transferegov fundo a fundo: especificacao", "https://api-publica.transferegov.gestao.gov.br/fundoafundo/",
                      extras=("swagger.json", "openapi.json", "../fundoafundo/swagger.json")))
    F.append(spec_api("tg_especiais_spec", "Transferegov especiais: especificacao", "https://api-publica.transferegov.gestao.gov.br/especiais/",
                      extras=("swagger.json", "openapi.json")))
    F.append(spec_api("ms_spec", "API de Dados Abertos do MS: especificacao", "https://apidadosabertos.saude.gov.br/", extras=("swagger.json", "v1/swagger.json", "openapi.json")))
    F.append(egestor_api())
    F += transparencia()
    F += rreo_saude()
    F.append(ckan_recursos("ckan_indicadores", "Dados Abertos SUS: indicadores de desempenho SISAB (recursos)", "indicadores_desempenho_sisab", 14))
    F.append(ckan_recursos("ckan_leitos", "Dados Abertos SUS: hospitais e leitos (recursos)", "hospitais-e-leitos", 6))
    F += notas()
    F += ligacao_radar()
    for f in F:
        f.pop("_obj", None)
        f.pop("_corpo", None)
    saida = {"rodada": 4, "gerado_em": datetime.now(BRT).isoformat(timespec="seconds"),
             "ambiente": "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local",
             "resumo": {"ok": sum(1 for f in F if f.get("ok") is True), "falha": sum(1 for f in F if f.get("ok") is False), "nao_testado": sum(1 for f in F if f.get("ok") is None)},
             "fontes": F}
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem_r4.json", "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=1)
    L = ["| Fonte | Resultado | Tempo | Observacao |", "|---|---|---|---|"]
    for f in F:
        res = "ok" if f.get("ok") else ("nao testado" if f.get("ok") is None else f"FALHA {f.get('erro', f.get('status', ''))}")
        obs = []
        for k, rot in (("total_caminhos", "caminhos"), ("total_recursos_na_pagina", "recursos"), ("total_itens", "itens")):
            if f.get(k) is not None:
                obs.append(f"{f[k]} {rot}")
        if f.get("caminhos_no_script"):
            obs.append(f"{len(f['caminhos_no_script'])} caminhos no script")
        if f.get("tamanho_http"):
            obs.append(f"{int(f['tamanho_http'])//1024} KB")
        L.append(f"| {f['nome']} | {res} | {f.get('ms', '')} ms | {'; '.join(obs)} |")
    texto_md = "\n".join(L)
    print(texto_md)
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        with open(s, "a", encoding="utf-8") as fh:
            fh.write("## Sondagem das fontes (rodada 4)\n\n" + texto_md + "\n")
    print(f"\nok={saida['resumo']['ok']} falha={saida['resumo']['falha']} nao_testado={saida['resumo']['nao_testado']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
