#!/usr/bin/env python3
"""Radar de notas tecnicas e informes: guarda so titulo, data, fonte, tema e link (sem copiar conteudo).
Fontes: CONASS (WordPress, busca por 'nota tecnica' e 'Conass Informa') e pagina de notas tecnicas do Ministerio da Saude.
Saida: dados/notas.json."""
import re, sys
from html import unescape
from urllib.parse import quote, urljoin
from comum import baixar, baixar_json, escrever_json, agora, sem_acento, resumo_actions

CONASS = "https://www.conass.org.br/wp-json/wp/v2/posts?search={q}&per_page=40&_fields=date,link,title"
MS = "https://www.gov.br/saude/pt-br/centrais-de-conteudo/publicacoes/notas-tecnicas"
TEMAS = (("Atencao primaria", r"ATENCAO PRIMARIA|APS\b|PREVINE|ESF\b|EMULTI|SAUDE BUCAL"),
         ("Financiamento", r"FINANCIAMENTO|CUSTEIO|REPASSE|FUNDO A FUNDO|EMENDA|PISO|INCREMENTO|RECURSO"),
         ("Vigilancia", r"VIGILANCIA|DENGUE|VACINA|IMUNIZACAO|SURTO|EPIDEMI"),
         ("Assistencia farmaceutica", r"FARMAC|MEDICAMENT"),
         ("Gestao e normas", r"PORTARIA|CONSOLIDACAO|PACTUACAO|CIT\b|CONTROLE|PLANEJAMENTO"))

def tema(titulo):
    t = sem_acento(titulo)
    for nome, padrao in TEMAS:
        if re.search(padrao, t):
            return nome
    return "Outros"

def limpar(txt):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", txt or ""))).strip()

def itens_conass(posts):
    return [{"fonte": "CONASS", "data": (p.get("date") or "")[:10], "titulo": limpar((p.get("title") or {}).get("rendered")), "link": p.get("link")} for p in posts if p.get("link")]

def itens_ms(html, base=MS):
    saida, vistos = [], set()
    for href, txt in re.findall(r'<a\b[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        t = limpar(txt)
        u = urljoin(base, unescape(href))
        if len(t) < 15 or u in vistos or not re.search(r"nota[-_ ]?t[eé]cnica|notas-tecnicas/.+", u + " " + t, re.I):
            continue
        if u.rstrip("/") == base.rstrip("/"):
            continue
        vistos.add(u)
        saida.append({"fonte": "Ministerio da Saude", "data": None, "titulo": t[:200], "link": u})
    return saida

def main():
    itens, msgs = [], []
    for q in ("nota técnica", "Conass Informa"):
        try:
            novos = itens_conass(baixar_json(CONASS.format(q=quote(q)), timeout=60))
            itens += novos
            msgs.append(f"CONASS '{q}': {len(novos)}")
        except Exception as e:
            msgs.append(f"CONASS '{q}' falhou: {type(e).__name__}")
    try:
        novos = itens_ms(baixar(MS, timeout=60).decode("utf-8", "replace"))
        itens += novos
        msgs.append(f"Ministerio da Saude: {len(novos)}")
    except Exception as e:
        msgs.append(f"Ministerio da Saude falhou: {type(e).__name__}")
    vistos, unicos = set(), []
    for i in itens:
        if i["link"] in vistos:
            continue
        vistos.add(i["link"])
        i["tema"] = tema(i["titulo"])
        unicos.append(i)
    unicos.sort(key=lambda i: i["data"] or "", reverse=True)
    if not unicos:
        print("sem itens: nada gravado")
        return 1
    escrever_json("dados/notas.json", {"gerado_em": agora(), "fonte": "CONASS e Ministerio da Saude (titulo, data e link)", "itens": unicos[:80]})
    resumo_actions("Notas tecnicas e informes", msgs + [f"Total unico: {len(unicos)}"])
    print("; ".join(msgs))
    return 0

if __name__ == "__main__":
    sys.exit(main())
