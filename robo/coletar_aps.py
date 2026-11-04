#!/usr/bin/env python3
"""Atencao Primaria: baixa os arquivos abertos de indicadores de desempenho do SISAB (Previne Brasil, 2024) e registra a estrutura.
Fonte: Dados Abertos do SUS (S3 do Ministerio da Saude). Carga fechada, o modelo foi substituido pela Portaria GM/MS 3.493/2024.
Saida: dados/aps/indicadores_2024Q1..Q3.csv (copia) e dados/aps_meta.json (colunas, linhas, tamanho, data do arquivo)."""
import csv, io, os, sys
from comum import baixar, escrever_json, agora, resumo_actions

BASE = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/sisab/indicador_desempenho/csv/sisab_indicador_desempenho_{tri}.csv"
TRIMESTRES = ("2024Q1", "2024Q2", "2024Q3")

def estrutura(texto):
    """Detecta o separador e devolve (colunas, total_de_linhas_de_dados)."""
    amostra = texto[:4096]
    sep = ";" if amostra.count(";") >= amostra.count(",") else ","
    leitor = csv.reader(io.StringIO(texto), delimiter=sep)
    colunas = next(leitor, [])
    n = sum(1 for _ in leitor)
    return [c.strip() for c in colunas], n, sep

def main():
    meta = {"gerado_em": agora(), "fonte": "Dados Abertos do SUS: indicadores de desempenho SISAB (Previne Brasil)", "arquivos": []}
    os.makedirs("dados/aps", exist_ok=True)
    for tri in TRIMESTRES:
        try:
            bruto = baixar(BASE.format(tri=tri), timeout=120)
        except Exception as e:
            meta["arquivos"].append({"trimestre": tri, "ok": False, "erro": type(e).__name__})
            continue
        texto = bruto.decode("utf-8-sig", "replace")
        colunas, n, sep = estrutura(texto)
        with open(f"dados/aps/indicadores_{tri}.csv", "w", encoding="utf-8", newline="") as fh:
            fh.write(texto)
        meta["arquivos"].append({"trimestre": tri, "ok": True, "bytes": len(bruto), "linhas": n, "separador": sep, "colunas": colunas})
    ok = [a for a in meta["arquivos"] if a.get("ok")]
    escrever_json("dados/aps_meta.json", meta)
    resumo_actions("Atencao Primaria (indicadores 2024)", [f"{a['trimestre']}: " + (f"{a['linhas']} linhas, {len(a['colunas'])} colunas" if a.get("ok") else "falhou") for a in meta["arquivos"]])
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
