#!/usr/bin/env python3
"""Recursos por municipio e do fundo estadual, a partir dos arquivos que o Radar de Recursos (partelli.pro/fundo) ja publica (InvestSUS, FNS).
Metodologia do Radar: repasses fundo a fundo em valor bruto, separados em Manutencao (custeio regular) e Estruturacao da Rede (investimento);
emendas parlamentares por ano da proposta (proposto, empenhado, pago), tratadas a parte. O Fundo Estadual e separado dos municipios.
Saida: dados/recursos/<UF>.json. Nao guarda numero de proposta nem autor."""
import difflib, re, sys, unicodedata
from comum import baixar_json, escrever_json, ler_json, agora, resumo_actions

BASE = "https://partelli.pro/fundo"
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()

def chave(nome):
    t = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", t)

# Grafias do Radar que diferem da base territorial (renomeados ou escritos de outro modo).
ALIAS = {"POXOREO": "POXOREU", "AREZ": "ARES", "ASSU": "ACU", "FLORINEA": "FLORINIA", "SAOLUIZDOANAUA": "SAOLUIZ", "JANUARIOCICCO": "BOASAUDE"}

def url_uf(uf):
    return f"{BASE}/dados.json" if uf == "ES" else f"{BASE}/dados-{uf.lower()}.json"

def emenda_ano(ano_lista, ano):
    for a in ano_lista or []:
        if a and a[0] == ano:
            return [a[1], a[2], a[3]]
    return [0, 0, 0]

def reduzir(o, ano_em):
    return {"fb": round(o.get("fb") or 0), "fl": round(o.get("fl") or 0), "fe": round(o.get("fe") or 0), "fm": round(o.get("fm") or 0),
            "s": round(o.get("s") or 0), "comp": o.get("comp") or [], "em": emenda_ano(o.get("ano"), ano_em), "eq": len(o.get("prop") or [])}

def montar(uf, dados, municipios):
    """Casa os municipios do Radar (por nome) com os codigos IBGE da base territorial. Devolve (obj, nao_casados)."""
    por_nome = {chave(m["nome"]): m["cod"] for m in municipios if m["uf"] == uf}
    ano_em = (dados.get("meta") or {}).get("anoEm")
    mun, nao = {}, []
    for m in dados.get("m", []):
        k = ALIAS.get(chave(m.get("nm") or m.get("n")), chave(m.get("nm") or m.get("n")))
        cod = por_nome.get(k)
        if not cod:
            # grafia diferente (renomeados, th/t, z/s): aceita so uma correspondencia muito proxima e ainda livre
            livres = [x for x, c in por_nome.items() if c not in mun and c not in {v for v in por_nome.values() if v in mun}]
            prox = difflib.get_close_matches(k, livres, n=2, cutoff=0.88)
            if len(prox) == 1 or (len(prox) == 2 and difflib.SequenceMatcher(None, k, prox[0]).ratio() - difflib.SequenceMatcher(None, k, prox[1]).ratio() > 0.05):
                cod = por_nome[prox[0]]
        if not cod:
            nao.append(m.get("nm") or m.get("n"))
            continue
        mun[cod] = reduzir(m, ano_em)
    meta = dados.get("meta") or {}
    return {"uf": uf, "meta": {k: meta.get(k) for k in ("extracao", "saldoData", "anoFaf", "anoEm")}, "comp": dados.get("comp"),
            "est": reduzir(dados["EST"], ano_em) if dados.get("EST") else None, "m": mun}, nao

def main():
    terr = ler_json("dados/territorio.json")
    ok, falhas, nao_total = 0, {}, 0
    resumo = []
    for uf in UFS:
        try:
            d = baixar_json(url_uf(uf), timeout=90)
            obj, nao = montar(uf, d, terr["municipios"])
            esperados = sum(1 for m in terr["municipios"] if m["uf"] == uf)
            if len(obj["m"]) < 0.9 * esperados:
                raise ValueError(f"so {len(obj['m'])} de {esperados} municipios casados")
            obj["gerado_em"] = agora()
            escrever_json(f"dados/recursos/{uf}.json", obj)
            ok += 1; nao_total += len(nao)
            resumo.append(f"{uf}: {len(obj['m'])} de {esperados}" + (f" (sem casar: {', '.join(nao[:4])})" if nao else ""))
        except Exception as e:
            falhas[uf] = f"{type(e).__name__}: {str(e)[:100]}"
            print("FALHA", uf, falhas[uf], flush=True)
    for r in resumo:
        print(r)
    resumo_actions("Recursos por municipio (Radar de Recursos)", [f"UFs: {ok} de {len(UFS)}", f"Municipios sem casar: {nao_total}", f"Falhas: {falhas or 'nenhuma'}"])
    return 1 if len(falhas) > 3 else 0

if __name__ == "__main__":
    sys.exit(main())
