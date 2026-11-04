#!/usr/bin/env python3
"""Sondagem (rodada 9): estrutura do demonstrativo de saude do SIOPS (RREO, Anexo 12) em siops.datasus.gov.br/rel_LRF.php.
Guarda o texto do demonstrativo de dois municipios (Vitoria e Afonso Claudio, dados publicos de orcamento) para desenhar o leitor,
os codigos de periodo (bimestres, incluindo o 6o) e o que a pagina mostra quando nao ha dados. Saida: dados/sondagem_r9.json."""
import json, os, re, sys, time
from datetime import datetime
from sondar_fontes import pedir, BRT, ANO
from sondar_r8 import texto

URL = "http://siops.datasus.gov.br/rel_LRF.php?S=1&UF={uf};&Municipio={mun};&Ano={ano}&Periodo={per}"

def pegar(uf, mun, ano, per):
    o = pedir(URL.format(uf=uf, mun=mun, ano=ano, per=per), timeout=60, limite=1_500_000)
    r = {"uf": uf, "mun": mun, "ano": ano, "periodo": per, "status": o.get("status"), "erro": o.get("erro")}
    if o.get("corpo"):
        h = o["corpo"].decode("latin-1", "replace")
        t = texto(h)
        r["bytes"] = len(h)
        m = re.search(r"(\d)º Bimestre de (\d{4})|Anual|Dados (Homologados|Não Homologados|[A-Za-zçã ]{3,30})", t)
        r["rotulo"] = re.search(r"\d+º Bimestre de \d{4}[^.]{0,60}", t).group(0)[:90] if re.search(r"\d+º Bimestre de \d{4}", t) else None
        r["tamanho_texto"] = len(t)
        r["texto"] = t[:30000]
    return r

def main():
    saida = {"gerado_em": datetime.now(BRT).isoformat(timespec="seconds"), "rodada": 9, "casos": [], "periodos": []}
    for uf, mun, ano, per in (("32", "320530", ANO - 1, 20), ("32", "320010", ANO - 1, 20), ("32", "320530", ANO - 1, 22), ("32", "320530", ANO, 18)):
        saida["casos"].append(pegar(uf, mun, ano, per)); time.sleep(1)
    for per in (1, 2, 3, 4, 5, 6, 7, 8, 12, 14, 16, 18, 20, 22, 24, 26, 99):
        r = pegar("32", "320530", ANO - 1, per)
        saida["periodos"].append({"periodo": per, "status": r["status"], "rotulo": r.get("rotulo"), "bytes": r.get("bytes")}); time.sleep(0.5)
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem_r9.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print("sondagem r9 gravada")
    return 0

if __name__ == "__main__":
    sys.exit(main())
