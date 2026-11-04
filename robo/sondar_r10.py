#!/usr/bin/env python3
"""Sondagem (rodada 10): consulta 'Calculo do % aplicado em Saude, LC 141/2012' do SIOPS (rel_perc_LC141.php).
Guarda o HTML do formulario (campos, opcoes) e tenta algumas consultas por estado para ver se uma pagina traz todos os municipios.
Saida: dados/sondagem_r10.json."""
import json, os, re, sys, time
from datetime import datetime
from sondar_fontes import pedir, BRT, ANO
from sondar_r8 import texto

BASE = "http://siops.datasus.gov.br/"

def pegar(url):
    o = pedir(url, timeout=60, limite=3_000_000)
    r = {"url": url, "status": o.get("status"), "erro": o.get("erro")}
    if o.get("corpo"):
        h = o["corpo"].decode("latin-1", "replace")
        r["bytes"] = len(h)
        r["html"] = h[:20000]
        r["texto"] = texto(h)[:8000]
    return r

def main():
    s = {"gerado_em": datetime.now(BRT).isoformat(timespec="seconds"), "rodada": 10, "casos": []}
    s["casos"].append(pegar(BASE + "rel_perc_LC141.php?e=2"))
    time.sleep(1)
    for url in (BASE + "rel_perc_LC141.php?e=2&UF=32&Ano=%d" % (ANO - 1),
                BASE + "rel_perc_LC141.php?S=1&UF=32;&Ano=%d&e=2" % (ANO - 1),
                BASE + "rel_perc_LC141.php?e=2&uf=32&ano=%d&periodo=20" % (ANO - 1),
                BASE + "cons_perc_apl_saude_EC29.php",
                BASE + "consleirespfiscal.php"):
        s["casos"].append(pegar(url)); time.sleep(1)
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem_r10.json", "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    print("sondagem r10 gravada")
    return 0

if __name__ == "__main__":
    sys.exit(main())
