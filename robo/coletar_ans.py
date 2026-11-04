#!/usr/bin/env python3
"""Cobertura de planos privados de saude por municipio (ANS, Painel de Dados Abertos, taxa de cobertura).
Soma beneficiarios de assistencia medica e populacao por municipio (todas as linhas de sexo e faixa etaria) no periodo mais recente do arquivo
e calcula a cobertura no painel. Le o CSV em fluxo (sem carregar tudo na memoria). Nao tem dado de pessoa.
Saida: dados/ans.json."""
import csv, io, sys, urllib.request
from comum import UA, escrever_json, ler_json, agora, resumo_actions

URL = "https://dadosabertos.ans.gov.br/FTP/PDA/taxa_de_cobertura_de_planos_de_saude-047/pda-047-taxa_cobertura.csv"
NECESSARIAS = ["PERIODO", "CD_MUNICIPIO", "SEXO", "FAIXA_ETARIA", "BENEF_ASSISTENCIA_MEDICA", "POPULACAO"]

def inteiro(v):
    try:
        return int(float(str(v).replace(",", ".").strip() or 0))
    except ValueError:
        return 0

def agregar(linhas):
    """Devolve ({periodo: {cd6: [benef_medica, populacao]}}, valores_sexo, valores_faixa, linhas_ignoradas_por_total)."""
    leitor = csv.reader(linhas, delimiter=";")
    cab = [c.strip().lstrip("﻿") for c in next(leitor)]
    ix = {c: i for i, c in enumerate(cab)}
    falta = [c for c in NECESSARIAS if c not in ix]
    if falta:
        raise ValueError(f"colunas ausentes: {falta}")
    por, sexos, faixas, totais = {}, set(), set(), 0
    for l in leitor:
        if len(l) < len(cab):
            continue
        sx, fx = l[ix["SEXO"]].strip(), l[ix["FAIXA_ETARIA"]].strip()
        sexos.add(sx)
        faixas.add(fx)
        if "total" in sx.lower() or "total" in fx.lower():
            totais += 1
            continue
        a = por.setdefault(l[ix["PERIODO"]].strip(), {}).setdefault(l[ix["CD_MUNICIPIO"]].strip()[:6], [0, 0])
        a[0] += inteiro(l[ix["BENEF_ASSISTENCIA_MEDICA"]])
        a[1] += inteiro(l[ix["POPULACAO"]])
    return por, sorted(sexos)[:10], sorted(faixas)[:30], totais

def abrir():
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "text/csv,*/*"})
    resp = urllib.request.urlopen(req, timeout=600)
    return io.TextIOWrapper(resp, encoding="utf-8", errors="replace", newline="")

def main():
    terr = ler_json("dados/territorio.json")
    mapa6 = {m["cod"][:6]: m["cod"] for m in terr["municipios"]}
    uf_de = {m["cod"]: m["uf"] for m in terr["municipios"]}
    por, sexos, faixas, totais = agregar(abrir())
    if not por:
        print("validacao falhou: sem linhas")
        return 1
    periodo = max(por)
    mun, sem = {}, 0
    for cd6, (b, p) in por[periodo].items():
        cod = mapa6.get(cd6)
        if cod:
            mun[cod] = [b, p]
        else:
            sem += 1
    cob = [b / p for b, p in mun.values() if p]
    plausiveis = sum(1 for c in cob if c <= 1) / max(1, len(cob))
    if len(mun) < 5000 or plausiveis < 0.95:
        print(f"validacao falhou: {len(mun)} municipios, {plausiveis:.1%} com cobertura <= 100%")
        return 1
    ufs = {}
    for cod, (b, p) in mun.items():
        t = ufs.setdefault(uf_de[cod], [0, 0])
        t[0] += b; t[1] += p
    escrever_json("dados/ans.json", {"gerado_em": agora(), "fonte": "ANS, Painel de Dados Abertos, taxa de cobertura de planos de saúde", "periodo": periodo,
                                     "campos": ["beneficiarios_assistencia_medica", "populacao"],
                                     "observacao": "Cobertura = beneficiários de assistência médica ÷ população do município, ambos como publicados pela ANS.",
                                     "valores_sexo": sexos, "valores_faixa": faixas, "ufs": dict(sorted(ufs.items())), "mun": dict(sorted(mun.items()))})
    resumo_actions("Planos de saúde (ANS)", [f"Período: {periodo}", f"Municípios: {len(mun)}", f"Linhas de total ignoradas: {totais}", f"Municípios sem código IBGE: {sem}"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
