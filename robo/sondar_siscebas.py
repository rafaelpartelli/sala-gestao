#!/usr/bin/env python3
"""Sondagem das informacoes livres sobre o CEBAS Saude. O SisCEBAS exige login do representante legal: este robo NAO entra
na area restrita e respeita o robots.txt. Procura apenas vias abertas: paginas publicas do Ministerio da Saude e conjuntos
de dados abertos (OpenDataSUS, CKAN). Saida: dados/fontes_siscebas.json."""
import json, sys, urllib.parse
from comum import escrever_json, baixar_json, agora, resumo_actions
from sondar_acesso import sondar_pagina

PAGINAS = [
    "http://siscebas.saude.gov.br/siscebas/",
    "https://www.gov.br/saude/pt-br/composicao/saes/dcebas",
    "https://www.gov.br/saude/pt-br/composicao/saes/dcebas/legislacao",
]
CKAN = "https://opendatasus.saude.gov.br/api/3/action/package_search?"
TERMOS = ["cebas", "entidades beneficentes", "certificacao entidades"]

def buscar_dados_abertos():
    achados = []
    for termo in TERMOS:
        try:
            obj = baixar_json(CKAN + urllib.parse.urlencode({"q": termo, "rows": 10}), timeout=40, tentativas=2)
            for d in obj.get("result", {}).get("results", []):
                achados.append({"termo": termo, "titulo": d.get("title"), "id": d.get("name"),
                                "atualizado": d.get("metadata_modified"),
                                "recursos": [{"formato": r.get("format"), "url": r.get("url")} for r in d.get("resources", [])][:6]})
        except Exception as e:
            achados.append({"termo": termo, "erro": type(e).__name__})
    return achados

def main():
    paginas = [sondar_pagina(u) for u in PAGINAS]
    abertos = buscar_dados_abertos()
    uteis = [a for a in abertos if a.get("recursos")]
    falhou = abertos and all(a.get("erro") for a in abertos)
    conclusao = ("Há conjunto de dados aberto sobre CEBAS: validar campos antes de coletar." if uteis else
                 "A busca no OpenDataSUS falhou nesta rodada (resposta inesperada): sem conclusão sobre dados abertos de CEBAS. Verificar manualmente." if falhou else
                 "Nenhum conjunto de dados aberto sobre CEBAS foi encontrado nesta rodada. Coleta de dados do SisCEBAS segue bloqueada até haver fonte aberta.")
    escrever_json("dados/fontes_siscebas.json", {"gerado_em": agora(), "paginas": paginas, "dados_abertos": abertos, "conclusao": conclusao}, indent=1)
    for p in paginas:
        print(p["url"], p.get("robots"), p.get("status"))
    print(conclusao)
    resumo_actions("Sondagem SisCEBAS", [f"{p['url']}: {p.get('robots')}" for p in paginas] + [f"Conjuntos abertos com arquivos: {len(uteis)}", conclusao])
    return 0

if __name__ == "__main__":
    sys.exit(main())
