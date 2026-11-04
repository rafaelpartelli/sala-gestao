#!/usr/bin/env python3
"""Financiamento: copia para a sala os arquivos que o Radar de Recursos (partelli.pro) ja publica, com validacao.
Fonte primaria dos dados: Paineis InvestSUS, Fundo Nacional de Saude. O robo que os extrai roda no computador do Rafael.
Saida: dados/financiamento.json (resumo das 27 UFs) e dados/portarias.json (radar de portarias do Ministerio da Saude)."""
import sys
from comum import baixar_json, escrever_json, agora, resumo_actions

BASE = "https://partelli.pro"
CAMPOS = ("mun", "pop", "fb", "fbEst", "ep", "ee", "eg", "s", "sEst", "anoFaf", "anoEm", "saldoData", "extracao")

def validar_financiamento(obj):
    erros = []
    ufs = obj.get("uf") if isinstance(obj, dict) else None
    if not isinstance(ufs, dict) or len(ufs) != 27:
        erros.append(f"esperadas 27 UFs, vieram {len(ufs) if isinstance(ufs, dict) else 0}")
        return erros
    for sigla, d in ufs.items():
        faltam = [c for c in CAMPOS if c not in d]
        if faltam:
            erros.append(f"{sigla}: faltam campos {faltam}")
        elif not (d["fb"] > 0 and d["mun"] > 0):
            erros.append(f"{sigla}: repasse ou municipios zerados")
    return erros

def validar_portarias(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get("portarias"), list) or not obj["portarias"]:
        return ["sem portarias"]
    return []

def main():
    fin = baixar_json(BASE + "/fundo/brasil.json", timeout=60)
    erros = validar_financiamento(fin)
    if erros:
        print("validacao falhou:", "; ".join(erros[:5]))
        return 1
    escrever_json("dados/financiamento.json", {"baixado_em": agora(), "fonte": "Radar de Recursos (partelli.pro), dados do InvestSUS/FNS", "dados": fin})
    msgs = [f"UFs: {len(fin['uf'])}", f"Extracao do InvestSUS: {fin['meta'].get('gerado')}"]
    try:
        por = baixar_json(BASE + "/radar/radar.json", timeout=60)
        if not validar_portarias(por):
            escrever_json("dados/portarias.json", {"baixado_em": agora(), "atualizado": por.get("atualizado"),
                                                    "portarias": [{k: p.get(k) for k in ("data", "tipo", "orgao", "tema", "titulo", "resumo", "url")} for p in por["portarias"][:40]]})
            msgs.append(f"Portarias: {len(por['portarias'])} (atualizado em {por.get('atualizado')})")
    except Exception as e:
        msgs.append(f"Portarias indisponiveis: {type(e).__name__}")
    resumo_actions("Financiamento", msgs)
    print("; ".join(msgs))
    return 0

if __name__ == "__main__":
    sys.exit(main())
