"""Apoio aos coletores SICONFI de receita (RREO) e pessoal (RGF). Somente biblioteca padrao.
Estrutura dos demonstrativos conferida na API do Tesouro Nacional em 09/11/2026 (Vitoria/ES, exercicio 2025)."""
import os, re, urllib.parse
from comum import baixar_json

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/"

# Codigo IBGE das UFs, usado como id_ente dos governos estaduais no SICONFI.
UF_COD = {"RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17, "MA": 21, "PI": 22, "CE": 23, "RN": 24,
          "PB": 25, "PE": 26, "AL": 27, "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35, "PR": 41, "SC": 42,
          "RS": 43, "MT": 51, "MS": 50, "GO": 52, "DF": 53}
UFS_PILOTO = "ES,TO,PA,PE"

def ufs_do_ambiente():
    """Lista de UFs a coletar. Variavel UFS: 'BR' para todas, ou siglas separadas por virgula. Padrao: piloto."""
    v = os.environ.get("UFS", UFS_PILOTO).strip().upper()
    if v in ("BR", "TODAS"):
        return sorted(UF_COD)
    ufs = [u.strip() for u in v.split(",") if u.strip()]
    invalidas = [u for u in ufs if u not in UF_COD]
    if invalidas:
        raise ValueError("UF invalida: " + ",".join(invalidas))
    return ufs

def pedir(endpoint, params, limite_paginas=40):
    """GET paginado na API do SICONFI (hasMore/offset). Devolve a lista de itens."""
    itens, offset = [], 0
    for _ in range(limite_paginas):
        p = dict(params)
        p["offset"] = offset
        obj = baixar_json(API + endpoint + "?" + urllib.parse.urlencode(p), timeout=60, tentativas=4, pausa=3)
        pedaco = obj.get("items", [])
        itens += pedaco
        if not obj.get("hasMore") or not pedaco:
            break
        offset += obj.get("limit") or len(pedaco)
    return itens

def norm(txt):
    return re.sub(r"\s+", " ", str(txt or "")).strip().lower()

def valor(item):
    try:
        return float(item.get("valor"))
    except (TypeError, ValueError):
        return None

def populacao(itens):
    for i in itens or []:
        if i.get("populacao") not in (None, ""):
            try:
                return int(float(i["populacao"]))
            except (TypeError, ValueError):
                pass
    return None
