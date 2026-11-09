#!/usr/bin/env python3
"""Sondagem dos portais de transparencia estaduais (receita e pessoal): o que cada portal oferece de forma automatizavel.
Le config/portais_uf.json. Saida: dados/fontes_portais_uf.json. Nao coleta dados, so descobre a via de acesso."""
import sys
from comum import escrever_json, ler_json, agora, resumo_actions
from sondar_acesso import sondar_pagina

def main():
    cfg = ler_json("config/portais_uf.json")
    res = []
    for p in cfg["piloto"]:
        s = sondar_pagina(p["url"])
        s.update(uf=p["uf"], nome=p["nome"], status_cadastro=p["status"])
        s["via_automatizavel"] = bool(s.get("acessado") and s.get("links_de_interesse"))
        res.append(s)
        print(p["uf"], s.get("status"), s.get("robots"), len(s.get("links_de_interesse", [])), "links")
    escrever_json("dados/fontes_portais_uf.json", {"gerado_em": agora(), "portais": res}, indent=1)
    resumo_actions("Sondagem dos portais estaduais", [f"{s['uf']}: {'acessível' if s.get('acessado') else 'não acessado'} ({s.get('robots')}), {len(s.get('links_de_interesse', []))} links de interesse" for s in res])
    return 0

if __name__ == "__main__":
    sys.exit(main())
