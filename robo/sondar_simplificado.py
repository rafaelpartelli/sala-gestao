#!/usr/bin/env python3
"""Diagnostico: municipios pequenos entregam o RREO e o RGF na forma simplificada? Testa as variantes e imprime contagens. Nao grava dados."""
import sys
from siconfi_comum import pedir
from collections import Counter

ENTES = {"3200102": "Afonso Claudio/ES", "3200201": "Alegre/ES", "3205309": "Vitoria/ES (controle)"}

def contar(endpoint, **p):
    try:
        it = pedir(endpoint, p)
    except Exception as e:
        return f"erro {type(e).__name__}"
    cols = Counter(str(i.get("coluna")) for i in it)
    tot = [i.get("valor") for i in it if i.get("cod_conta") in ("TotalReceitas", "SubtotalDasReceitas", "DespesaComPessoalTotal") and str(i.get("coluna")).lower().startswith(("até o", "ate o", "valor", "total (ú", "total (u"))]
    return f"{len(it)} itens; periodo/periodicidade={sorted({(i.get('periodo'), i.get('periodicidade')) for i in it})[:4]}; demonstrativo={sorted({i.get('demonstrativo') for i in it})}; colunas={list(cols)[:5]}; total={tot[:2]}"

def main():
    for cod, nome in ENTES.items():
        print("==", nome)
        for tipo in ("RREO", "RREO Simplificado"):
            for per in (1, 2, 3, 6):
                print(f"RREO tipo={tipo} periodo={per}:", contar("rreo", an_exercicio=2025, nr_periodo=per, co_tipo_demonstrativo=tipo, no_anexo="RREO-Anexo 01", id_ente=cod))
        for tipo in ("RGF", "RGF Simplificado"):
            for pd, per in (("Q", 3), ("S", 2), ("S", 1)):
                print(f"RGF tipo={tipo} {pd}{per}:", contar("rgf", an_exercicio=2025, in_periodicidade=pd, nr_periodo=per, co_tipo_demonstrativo=tipo, no_anexo="RGF-Anexo 01", co_poder="E", id_ente=cod))
    return 0

if __name__ == "__main__":
    sys.exit(main())
