#!/usr/bin/env python3
"""Sondagem (rodada 8): como ler o SIOPS (percentual de aplicacao em saude, 15%) a partir do GitHub Actions.
O TabNet do SIOPS expirou nas rodadas anteriores, mas o portal PHP (siops.datasus.gov.br) respondeu. Esta rodada:
  1. le a pagina de consulta e lista formularios, campos, opcoes e links (so estrutura, sem copiar conteudo);
  2. tenta enderecos candidatos de relatorio por municipio (Vitoria como teste) e guarda so linhas com percentuais e palavras-chave;
  3. procura links de download (csv, xls, zip) nas paginas de indicadores do gov.br e do SIOPS.
Saida: dados/sondagem_r8.json. Nao guarda dados pessoais."""
import json, re, sys, time
from html import unescape
from sondar_fontes import pedir, BRT, ANO
from datetime import datetime

SIOPS = "http://siops.datasus.gov.br/"
GOV = "https://www.gov.br/saude/pt-br/acesso-a-informacao/siops/"

def texto(html):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", t))).strip()

def estrutura(html, base):
    """Formularios (acao, metodo, campos e primeiras opcoes), scripts e links .php/.asp/.csv/.xls/.zip encontrados."""
    forms = []
    for f in re.finditer(r"(?is)<form\b([^>]*)>(.*?)</form>", html):
        attrs = f.group(1)
        corpo = f.group(2)
        campos = []
        for i in re.finditer(r"(?is)<input\b([^>]*)>", corpo):
            n = re.search(r'name\s*=\s*["\']?([^"\' >]+)', i.group(1)); tp = re.search(r'type\s*=\s*["\']?([^"\' >]+)', i.group(1)); v = re.search(r'value\s*=\s*["\']([^"\']*)', i.group(1))
            if n:
                campos.append({"input": n.group(1), "tipo": tp.group(1) if tp else "text", "valor": (v.group(1)[:40] if v else None)})
        for s in re.finditer(r"(?is)<select\b([^>]*)>(.*?)</select>", corpo):
            n = re.search(r'name\s*=\s*["\']?([^"\' >]+)', s.group(1))
            ops = [(o.group(1).strip()[:30], texto(o.group(2))[:40]) for o in re.finditer(r'(?is)<option[^>]*value\s*=\s*["\']?([^"\' >]*)["\']?[^>]*>(.*?)</option>', s.group(2))]
            campos.append({"select": n.group(1) if n else None, "opcoes": len(ops), "primeiras": ops[:6], "ultimas": ops[-3:]})
        forms.append({"acao": (re.search(r'action\s*=\s*["\']([^"\']*)', attrs) or [None, None])[1], "metodo": (re.search(r'method\s*=\s*["\']?(\w+)', attrs) or [None, "GET"])[1], "campos": campos[:25]})
    links = sorted({m.group(1) for m in re.finditer(r'(?i)(?:href|src|action)\s*=\s*["\']([^"\']+\.(?:php|asp|aspx|csv|xls|xlsx|zip|ods)[^"\']*)', html)})[:60]
    js = sorted({m.group(1) for m in re.finditer(r'(?i)["\']([^"\']*\.php\?[^"\']{3,120})["\']', html)})[:30]
    return {"formularios": forms[:8], "links": links, "chamadas_php_no_script": js}

def linhas_chave(html, n=14):
    t = texto(html)
    partes = re.split(r"(?<=[\.\:;])\s+|\s{2,}", t)
    achadas = [p[:200] for p in partes if re.search(r"(?i)aplicad|ASPS|15\s*%|percentual|m[ií]nimo|recursos pr[óo]prios", p)]
    return achadas[:n]

def bloco_pagina_consulta():
    r = {"id": "siops_consulta", "url": SIOPS + "consleirespfiscal.php"}
    o = pedir(r["url"], timeout=60, limite=2_000_000)
    r["status"] = o.get("status"); r["erro"] = o.get("erro")
    if o.get("corpo"):
        h = o["corpo"].decode("latin-1", "replace")
        r["bytes"] = len(h); r["titulo"] = (re.search(r"(?is)<title>(.*?)</title>", h) or [None, ""])[1].strip()[:120]
        r.update(estrutura(h, SIOPS))
    return r

def candidatos():
    uf, mun = "32", "320530"
    anos = [ANO - 1, ANO - 2]
    out = []
    for ano in anos:
        for per in (6, 20, 14, 12):
            out.append(f"{SIOPS}rel_LRF.php?S=1&UF={uf};&Municipio={mun};&Ano={ano}&Periodo={per}")
    out += [f"{SIOPS}consindicadores.php", f"{SIOPS}consleiresp.php", f"{SIOPS}conssiops.php", f"{SIOPS}relatorios.php", f"{SIOPS}indicadores.php"]
    return out

def bloco_candidatos():
    F = []
    for u in candidatos():
        o = pedir(u, timeout=45, limite=800_000)
        item = {"url": u, "status": o.get("status"), "erro": o.get("erro"), "ms": o.get("ms")}
        if o.get("corpo"):
            h = o["corpo"].decode("latin-1", "replace")
            item["bytes"] = len(h); item["titulo"] = (re.search(r"(?is)<title>(.*?)</title>", h) or [None, ""])[1].strip()[:100]
            item["linhas_chave"] = linhas_chave(h)
            if len(h) < 120_000:
                item["estrutura"] = {k: v for k, v in estrutura(h, SIOPS).items() if v}
        F.append(item)
        time.sleep(1)
    return F

def bloco_downloads():
    F = []
    for u in (GOV + "indicadores", GOV + "publicacoes", "https://www.gov.br/saude/pt-br/acesso-a-informacao/siops", SIOPS):
        o = pedir(u, timeout=45, limite=1_500_000)
        item = {"url": u, "status": o.get("status"), "erro": o.get("erro")}
        if o.get("corpo"):
            h = o["corpo"].decode("utf-8", "replace")
            item["links_download"] = sorted({m.group(1) for m in re.finditer(r'(?i)href\s*=\s*["\']([^"\']+\.(?:csv|xls|xlsx|zip|ods|json)[^"\']*)', h)})[:25]
            item["links_siops"] = sorted({m.group(1) for m in re.finditer(r'(?i)href\s*=\s*["\']([^"\']*siops[^"\']*)', h)})[:25]
        F.append(item)
    return F

def bloco_tabnet_longo():
    u = "http://siops-asp.datasus.gov.br/CGI/deftohtm.exe?SIOPS/serhist/municipio/mIndicadores.def"
    o = pedir(u, timeout=180, limite=600_000)
    r = {"url": u, "status": o.get("status"), "erro": o.get("erro"), "ms": o.get("ms")}
    if o.get("corpo"):
        h = o["corpo"].decode("latin-1", "replace")
        r["bytes"] = len(h); r["estrutura"] = estrutura(h, u)
    return r

def seguro(nome, fn):
    try:
        return fn()
    except Exception as e:
        return {"erro": f"{type(e).__name__}: {str(e)[:160]}"}

def main():
    saida = {"gerado_em": datetime.now(BRT).isoformat(timespec="seconds"), "rodada": 8}
    saida["consulta"] = seguro("consulta", bloco_pagina_consulta)
    saida["candidatos"] = seguro("candidatos", bloco_candidatos)
    saida["downloads"] = seguro("downloads", bloco_downloads)
    saida["tabnet_180s"] = seguro("tabnet", bloco_tabnet_longo)
    import os
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem_r8.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print("sondagem r8 gravada")
    return 0

if __name__ == "__main__":
    sys.exit(main())
