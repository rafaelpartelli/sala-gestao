#!/usr/bin/env python3
"""Leitos hospitalares por municipio (CNES, arquivo Leitos_SUS dos Dados Abertos do SUS).
Soma, por municipio, leitos existentes, leitos SUS e leitos de UTI (total, adulto, pediatrico, neonatal). Usa so a competencia mais recente do arquivo.
Nao guarda nome de estabelecimento, endereco, telefone nem e-mail.
Saida: dados/leitos.json."""
import csv, io, sys, zipfile
from datetime import datetime
from comum import baixar, escrever_json, ler_json, agora, resumo_actions, BRT

S3 = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_{ano}.zip"
CAMPOS = ["EST", "EXIST", "SUS", "UTI_EXIST", "UTI_SUS", "UTI_AD_SUS", "UTI_PED_SUS", "UTI_NEO_SUS"]
COLUNAS = {"EXIST": "LEITOS_EXISTENTES", "SUS": "LEITOS_SUS", "UTI_EXIST": "UTI_TOTAL_EXIST", "UTI_SUS": "UTI_TOTAL_SUS",
           "UTI_AD_SUS": "UTI_ADULTO_SUS", "UTI_PED_SUS": "UTI_PEDIATRICO_SUS", "UTI_NEO_SUS": "UTI_NEONATAL_SUS"}

def inteiro(v):
    try:
        return int(float(str(v).replace(",", ".").strip() or 0))
    except ValueError:
        return 0

def agregar(linhas, mapa6):
    """Devolve (competencia, {cod7: [EST, EXIST, ...]}, lidas, sem_municipio). Mantem so a competencia mais recente."""
    leitor = csv.reader(linhas, delimiter=";")
    cab = [c.strip() for c in next(leitor)]
    ix = {c: i for i, c in enumerate(cab)}
    falta = [c for c in ["COMP", "CO_IBGE", *COLUNAS.values()] if c not in ix]
    if falta:
        raise ValueError(f"colunas ausentes: {falta}")
    por_comp, lidas, sem = {}, 0, 0
    for l in leitor:
        if len(l) < len(cab):
            continue
        lidas += 1
        cod = mapa6.get(l[ix["CO_IBGE"]].strip()[:6])
        comp = l[ix["COMP"]].strip()
        if not cod:
            sem += 1
            continue
        a = por_comp.setdefault(comp, {}).setdefault(cod, [0] * len(CAMPOS))
        a[0] += 1
        for k, nome in enumerate(COLUNAS, start=1):
            a[k] += inteiro(l[ix[COLUNAS[nome]]])
    if not por_comp:
        raise ValueError("nenhuma linha com municipio")
    comp = max(por_comp)
    return comp, por_comp[comp], lidas, sem

def main():
    terr = ler_json("dados/territorio.json")
    mapa6 = {m["cod"][:6]: m["cod"] for m in terr["municipios"]}
    uf_de = {m["cod"]: m["uf"] for m in terr["municipios"]}
    ultimo = None
    for ano in (datetime.now(BRT).year, datetime.now(BRT).year - 1):
        try:
            z = zipfile.ZipFile(io.BytesIO(baixar(S3.format(ano=ano), timeout=300, tentativas=3, pausa=10)))
            nome = next(i.filename for i in z.infolist() if i.filename.lower().endswith(".csv"))
            comp, mun, lidas, sem = agregar(io.TextIOWrapper(z.open(nome), encoding="latin-1", newline=""), mapa6)
            break
        except Exception as e:
            ultimo = e
            print(f"{ano}: {type(e).__name__}: {str(e)[:100]}")
    else:
        raise ultimo
    ufs = {}
    for cod, a in mun.items():
        t = ufs.setdefault(uf_de[cod], [0] * len(CAMPOS))
        for i, v in enumerate(a):
            t[i] += v
    total = sum(a[1] for a in mun.values())
    if len(mun) < 1500 or total < 100_000:
        print(f"validacao falhou: {len(mun)} municipios, {total} leitos")
        return 1
    escrever_json("dados/leitos.json", {"gerado_em": agora(), "fonte": "CNES, Leitos SUS (Dados Abertos do SUS, Ministério da Saúde)", "competencia": comp,
                                        "campos": CAMPOS, "observacao": "Leitos existentes e leitos SUS cadastrados no CNES na competência indicada.",
                                        "ufs": dict(sorted(ufs.items())), "mun": dict(sorted(mun.items()))})
    resumo_actions("Leitos (CNES)", [f"Competência: {comp}", f"Municípios com leitos: {len(mun)}", f"Leitos existentes: {total}", f"Linhas sem município: {sem} de {lidas}"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
