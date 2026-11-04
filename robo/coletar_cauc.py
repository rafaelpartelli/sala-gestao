#!/usr/bin/env python3
"""CAUC (Tesouro Nacional, dados abertos): pendencias de cada municipio nos itens de regularidade.
O CSV traz a situacao de cada item por municipio: uma data (regular), '!' (pendente) ou 'Desabilitado' (nao se aplica).
NAO traz percentuais de aplicacao. O CSV tambem nao traz a descricao dos itens: a sala mostra o codigo do item e remete ao CAUC oficial.
Saida: dados/cauc.json."""
import csv, io, re, sys
from datetime import datetime
from comum import baixar, baixar_json, escrever_json, ler_json, agora, resumo_actions

TT = "https://www.tesourotransparente.gov.br/ckan"
CSV_DIRETO = TT + "/dataset/72b5f371-0c35-4613-8076-c99c821a6410/resource/07af297a-5e59-494a-a88a-55ddfd2f4b01/download/relatorio-situacao-de-varios-entes---municipios---uf-todas---abrangencia-1.csv"
PACOTE = TT + "/api/3/action/package_show?id=72b5f371-0c35-4613-8076-c99c821a6410"
SIGLAS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())

def interpretar(txt):
    """Le o CSV do CAUC. Devolve dict com data da pesquisa, itens, pendencias por IBGE e mapa SIAFI -> IBGE."""
    linhas = list(csv.reader(io.StringIO(txt), delimiter=";"))
    i = next((k for k, l in enumerate(linhas) if l and l[0].strip() == "UF"), None)
    if i is None:
        raise ValueError("cabecalho com 'UF' nao encontrado")
    cab = [c.strip() for c in linhas[i]]
    idx = {c: j for j, c in enumerate(cab)}
    for c in ("Código IBGE", "Código SIAFI"):
        if c not in idx:
            raise ValueError(f"coluna ausente: {c}")
    itens = [c for c in cab if re.fullmatch(r"\d+(\.\d+)*", c)]
    data = None
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", linhas[0][0] if linhas and linhas[0] else "")
    if m:
        data = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    pend, siafi, uf_de, n = {}, {}, {}, 0
    for l in linhas[i + 1:]:
        if len(l) < len(cab) - 2 or l[0].strip() not in SIGLAS:
            continue
        n += 1
        ibge = l[idx["Código IBGE"]].strip()
        siafi[l[idx["Código SIAFI"]].strip()] = ibge
        uf_de[ibge] = l[0].strip()
        p = [it for it in itens if idx[it] < len(l) and l[idx[it]].strip() == "!"]
        if p:
            pend[ibge] = p
    return {"data_pesquisa": data, "itens": itens, "municipios": n, "pendencias": pend, "siafi": siafi, "uf": uf_de}

def carregar_cauc():
    """Baixa e interpreta o CSV (tenta o endereco direto e, se falhar, o catalogo CKAN)."""
    urls = [CSV_DIRETO]
    try:
        pacote = baixar_json(PACOTE, timeout=60)
        for r in pacote["result"]["resources"]:
            if "munic" in (r.get("name") or "").lower() and r.get("url"):
                urls.append(r["url"])
    except Exception:
        pass
    ultimo = None
    for u in urls:
        try:
            bruto = baixar(u, headers={"Accept": "text/csv,*/*"}, timeout=120)
            try:
                txt = bruto.decode("utf-8-sig")
            except UnicodeDecodeError:
                txt = bruto.decode("latin-1")
            r = interpretar(txt)
            if r["municipios"] >= 5000:
                return r
            ultimo = ValueError(f"so {r['municipios']} municipios")
        except Exception as e:
            ultimo = e
    raise ultimo

def resumir(r):
    n = r["municipios"]
    nac = {it: {"pendentes": 0} for it in r["itens"]}
    por_uf = {}
    for ibge, p in r["pendencias"].items():
        u = por_uf.setdefault(r["uf"][ibge], {"com_pendencia": 0})
        u["com_pendencia"] += 1
        for it in p:
            nac[it]["pendentes"] += 1
    for uf in set(r["uf"].values()):
        por_uf.setdefault(uf, {"com_pendencia": 0})["municipios"] = sum(1 for v in r["uf"].values() if v == uf)
    for it, d in nac.items():
        d["pct"] = round(100 * d["pendentes"] / n, 1) if n else None
    return nac, dict(sorted(por_uf.items()))

def main():
    r = carregar_cauc()
    nac, por_uf = resumir(r)
    saida = {"gerado_em": agora(), "fonte": "CAUC, Tesouro Nacional (Tesouro Transparente, dados abertos)", "data_pesquisa": r["data_pesquisa"],
             "observacao": "Situação por item: pendência é o sinal '!'. Não há percentual de aplicação nesta fonte. A descrição dos itens está no CAUC oficial.",
             "municipios": r["municipios"], "itens": r["itens"], "por_item": {k: v for k, v in nac.items() if v["pendentes"]}, "ufs": por_uf,
             "mun": dict(sorted(r["pendencias"].items()))}
    escrever_json("dados/cauc.json", saida)
    top = sorted(saida["por_item"].items(), key=lambda kv: -kv[1]["pendentes"])[:5]
    resumo_actions("CAUC", [f"Data da pesquisa: {r['data_pesquisa']}", f"Municípios: {r['municipios']}", f"Com alguma pendência: {len(r['pendencias'])}"] + [f"Item {k}: {v['pendentes']} ({v['pct']}%)" for k, v in top])
    print(f"municipios={r['municipios']} com_pendencia={len(r['pendencias'])}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
