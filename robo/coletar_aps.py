#!/usr/bin/env python3
"""Atencao Primaria: baixa os arquivos abertos de indicadores de desempenho do SISAB (Previne Brasil, 2024) e registra a estrutura.
Fonte: Dados Abertos do SUS (S3 do Ministerio da Saude). Carga fechada, o modelo foi substituido pela Portaria GM/MS 3.493/2024.
Os arquivos vem compactados (.csv.zip). Nao guardamos copia dos CSV no repositorio (tamanho): so dados/aps_meta.json (colunas, linhas, tamanho)."""
import csv, io, os, sys, zipfile
from comum import baixar, escrever_json, agora, resumo_actions

BASE = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/sisab/indicador_desempenho/csv/sisab_indicador_desempenho_{tri}.csv.zip"
TRIMESTRES = ("2024Q1", "2024Q2", "2024Q3")

def estrutura(texto):
    """Detecta o separador e devolve (colunas, total_de_linhas_de_dados)."""
    amostra = texto[:4096]
    sep = ";" if amostra.count(";") >= amostra.count(",") else ","
    leitor = csv.reader(io.StringIO(texto), delimiter=sep)
    colunas = next(leitor, [])
    n = sum(1 for _ in leitor)
    return [c.strip() for c in colunas], n, sep

def ler_zip_csv(bruto):
    """Abre o ZIP do SISAB e devolve (nome_do_csv, texto). Aceita tambem um CSV puro."""
    if bruto[:2] != b"PK":
        return "(csv sem zip)", bruto.decode("utf-8-sig", "replace")
    with zipfile.ZipFile(io.BytesIO(bruto)) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        return nome, z.read(nome).decode("utf-8-sig", "replace")

def main():
    meta = {"gerado_em": agora(), "fonte": "Dados Abertos do SUS: indicadores de desempenho SISAB (Previne Brasil)", "arquivos": []}
    for tri in TRIMESTRES:
        try:
            bruto = baixar(BASE.format(tri=tri), timeout=120)
        except Exception as e:
            meta["arquivos"].append({"trimestre": tri, "ok": False, "erro": f"{type(e).__name__}: {str(e)[:100]}"})
            continue
        nome, texto = ler_zip_csv(bruto)
        colunas, n, sep = estrutura(texto)
        meta["arquivos"].append({"trimestre": tri, "ok": True, "arquivo": nome, "bytes_zip": len(bruto), "linhas": n, "separador": sep, "colunas": colunas})
    ok = [a for a in meta["arquivos"] if a.get("ok")]
    escrever_json("dados/aps_meta.json", meta)
    resumo_actions("Atencao Primaria (indicadores 2024)", [f"{a['trimestre']}: " + (f"{a['linhas']} linhas, {len(a['colunas'])} colunas" if a.get("ok") else "falhou") for a in meta["arquivos"]])
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
