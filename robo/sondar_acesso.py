"""Sondagem educada de fontes publicas: respeita o robots.txt, nao faz login e nao baixa dados, so registra o que a pagina oferece."""
import re, urllib.parse, urllib.request, urllib.robotparser
from comum import UA, agora

PALAVRAS = re.compile(r"dados abertos|api|csv|download|receita|despesa|pessoal|servidor|remunera|contrato de gest|certifica", re.I)

def robots_permite(url, timeout=20):
    """(permitido, descricao). Sem robots.txt acessivel, considera permitido e registra o motivo."""
    p = urllib.parse.urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = urllib.request.Request(f"{p.scheme}://{p.netloc}/robots.txt", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rp.parse(r.read().decode("utf-8", "replace").splitlines())
    except Exception as e:
        return True, f"robots.txt indisponivel ({type(e).__name__})"
    ok = rp.can_fetch(UA, url)
    return ok, "robots.txt permite" if ok else "robots.txt bloqueia o acesso automatico"

def sondar_pagina(url, timeout=30):
    """Registra status, tipo, titulo e links com palavras de interesse. Nao segue links."""
    permitido, motivo = robots_permite(url)
    out = {"url": url, "verificado_em": agora(), "robots": motivo}
    if not permitido:
        out["acessado"] = False
        return out
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            corpo = r.read(400000).decode("utf-8", "replace")
            out.update(acessado=True, status=r.status, tipo=r.headers.get("Content-Type", ""), url_final=r.geturl())
    except Exception as e:
        out.update(acessado=False, erro=type(e).__name__, status=getattr(e, "code", None))
        return out
    t = re.search(r"<title[^>]*>(.*?)</title>", corpo, re.I | re.S)
    out["titulo"] = re.sub(r"\s+", " ", t.group(1)).strip()[:160] if t else None
    links = []
    for href, txt in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', corpo, re.I | re.S):
        txt = re.sub(r"<[^>]+>|\s+", " ", txt).strip()
        if PALAVRAS.search(txt) or PALAVRAS.search(href):
            links.append({"texto": txt[:90], "href": urllib.parse.urljoin(url, href)[:200]})
    vistos, unicos = set(), []
    for l in links:
        if l["href"] not in vistos:
            vistos.add(l["href"])
            unicos.append(l)
    out["links_de_interesse"] = unicos[:25]
    return out
