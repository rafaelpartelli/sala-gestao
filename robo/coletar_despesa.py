#!/usr/bin/env python3
"""Despesa em saude dos municipios (SICONFI, DCA Anexo I-E, funcao '10 - Saude'): empenhada, liquidada e paga, com a populacao do ente.
Um pedido por municipio (5.570), em paralelo, com espera exponencial. Municipio que nao entregou o DCA fica sem valor (nao e erro).
Saida: dados/despesa.json."""
import os, sys, re, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from comum import baixar_json, escrever_json, ler_json, agora, resumo_actions, BRT

BASE = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca?"
TRABALHADORES = int(os.environ.get("TRABALHADORES", "6"))
COLUNAS = {"empenhadas": 0, "liquidadas": 1, "pagas": 2}

def extrair(itens):
    """De uma lista de itens do DCA devolve [empenhada, liquidada, paga, populacao] da conta '10 - Saude', ou None."""
    v = [None, None, None]
    pop = None
    for i in itens or []:
        conta = re.sub(r"\s+", " ", str(i.get("conta", ""))).strip().lower()
        if not re.fullmatch(r"10 - sa[uú]de", conta):
            continue
        col = str(i.get("coluna", "")).strip().lower()
        for chave, pos in COLUNAS.items():
            if col.startswith(f"despesas {chave}") and v[pos] is None:
                try:
                    v[pos] = float(i.get("valor"))
                except (TypeError, ValueError):
                    pass
        if pop is None and i.get("populacao") not in (None, ""):
            try:
                pop = int(float(i["populacao"]))
            except (TypeError, ValueError):
                pass
    if all(x is None for x in v):
        return None
    return [round(x or 0) for x in v] + [pop]

def pedir_ente(cod, exercicio):
    itens, offset = [], 0
    while True:
        u = BASE + urllib.parse.urlencode(dict(an_exercicio=exercicio, no_anexo="DCA-Anexo I-E", id_ente=cod, offset=offset))
        obj = baixar_json(u, timeout=60, tentativas=4, pausa=3)
        itens += obj.get("items", [])
        if not obj.get("hasMore") or offset > 20000:
            return itens
        offset += obj.get("limit") or len(obj.get("items", [])) or 5000

def um(args):
    m, exercicio = args
    try:
        return m, extrair(pedir_ente(m["cod"], exercicio)), None
    except Exception as e:
        return m, None, type(e).__name__

def coletar(muni, exercicio):
    t0 = time.time()
    res, falhas = [], 0
    with ThreadPoolExecutor(max_workers=TRABALHADORES) as ex:
        for m, r, erro in ex.map(um, [(m, exercicio) for m in muni]):
            falhas += 1 if erro else 0
            res.append((m, r))
    return res, falhas, int(time.time() - t0)

def main():
    terr = ler_json("dados/territorio.json")
    muni = terr["municipios"]
    limite = int(os.environ.get("LIMITE", "0")) or None
    if limite:
        muni = muni[::max(1, len(muni) // limite)][:limite]
    exercicio = int(os.environ.get("EXERCICIO", "0")) or datetime.now(BRT).year - 1
    try:
        amostra = pedir_ente(muni[0]["cod"], exercicio)
        print("colunas da conta 10 - Saude no primeiro municipio:", sorted({str(i.get("coluna")) for i in amostra if re.match(r"\s*10\s*-\s*sa", str(i.get("conta", "")), re.I)}))
    except Exception as e:
        print("diagnostico indisponivel:", type(e).__name__)
    res, falhas, seg = coletar(muni, exercicio)
    entregaram = [(m, r) for m, r in res if r and r[2]]
    if len(entregaram) < 0.5 * len(muni):
        exercicio -= 1
        print(f"poucos municipios com DCA; tentando {exercicio}")
        res, falhas, seg = coletar(muni, exercicio)
        entregaram = [(m, r) for m, r in res if r and r[2]]
    taxa = falhas / max(1, len(muni))
    print(f"exercicio={exercicio} municipios={len(muni)} com_despesa={len(entregaram)} falhas={falhas} ({taxa:.1%}) tempo={seg}s")
    if taxa > 0.05 or len(entregaram) < 0.5 * len(muni):
        print("validacao falhou")
        return 1
    mun = {m["cod"]: r for m, r in entregaram}
    ufs = {}
    for m, r in entregaram:
        t = ufs.setdefault(m["uf"], [0, 0, 0, 0, 0])
        for i in range(3):
            t[i] += r[i]
        t[3] += r[3] or 0
        t[4] += 1
    escrever_json("dados/despesa.json", {"gerado_em": agora(), "fonte": "SICONFI, DCA Anexo I-E, função 10 - Saúde (Tesouro Nacional)", "exercicio": exercicio,
                                         "campos": ["empenhada", "liquidada", "paga", "populacao"], "ufs_campos": ["empenhada", "liquidada", "paga", "populacao", "municipios"],
                                         "observacao": "Despesa do município em saúde no exercício, conforme a Declaração de Contas Anuais. Municípios que não entregaram ficam sem valor.",
                                         "municipios_consultados": len(muni), "municipios_com_despesa": len(entregaram), "ufs": dict(sorted(ufs.items())), "mun": dict(sorted(mun.items()))})
    resumo_actions("Despesa em saúde (DCA)", [f"Exercício: {exercicio}", f"Com despesa: {len(entregaram)} de {len(muni)}", f"Falhas: {falhas} ({taxa:.1%})", f"Tempo: {seg // 60} min"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
