#!/usr/bin/env python3
"""Dengue por municipio (InfoDengue, Fiocruz e FGV): nivel de alerta, casos e incidencia da semana mais recente.
Entrada: dados/territorio.json (5.570 municipios). Saida: dados/dengue/<UF>.json e dados/dengue_resumo.json.
Os casos sao ESTIMADOS pelo modelo do InfoDengue, nao notificacoes confirmadas."""
import os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from comum import baixar_json, escrever_json, ler_json, agora, resumo_actions, BRT
from datetime import datetime

ANO = datetime.now(BRT).year
DOENCA = os.environ.get("DOENCA", "dengue")   # dengue ou chikungunya
URL = "https://info.dengue.mat.br/api/alertcity?geocode={cod}&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={ano}&ey_end={ano}"
TRABALHADORES = int(os.environ.get("TRABALHADORES", "3"))
MAX_FALHA = 0.05

def resumir(registros):
    """Pega a semana mais recente e as ultimas 8 semanas de casos estimados. Devolve None se nao houver dados."""
    reg = [r for r in registros if isinstance(r, dict) and r.get("SE") is not None]
    if not reg:
        return None
    reg.sort(key=lambda r: r.get("data_iniSE") or 0)
    u = reg[-1]
    def num(v, nd=1):
        try:
            return round(float(v), nd)
        except (TypeError, ValueError):
            return None
    return {"se": int(u["SE"]), "nivel": int(u["nivel"]) if u.get("nivel") is not None else None,
            "casos": int(u["casos"]) if u.get("casos") is not None else None,
            "casos_est": num(u.get("casos_est"), 0), "inc": num(u.get("p_inc100k")), "rt": num(u.get("Rt"), 2),
            "serie": [num(r.get("casos_est"), 0) or 0 for r in reg[-8:]]}

def agregar_uf(itens):
    """itens: lista de (cod, nome, resumo|None). Devolve totais por nivel e casos estimados da ultima semana."""
    niveis = {1: 0, 2: 0, 3: 0, 4: 0, "sem_dado": 0}
    casos = 0
    for _, _, r in itens:
        if not r or r.get("nivel") not in (1, 2, 3, 4):
            niveis["sem_dado"] += 1
            continue
        niveis[r["nivel"]] += 1
        casos += int(r.get("casos_est") or 0)
    return {"niveis": {str(k): v for k, v in niveis.items()}, "casos_est_semana": casos}

def coletar_um(m):
    try:
        reg = baixar_json(URL.format(cod=m["cod"], ano=ANO).replace("disease=dengue", f"disease={DOENCA}"), timeout=40, tentativas=2, pausa=2)
        time.sleep(0.1)
        return m, resumir(reg), None
    except Exception as e:
        return m, None, f"{type(e).__name__}"

def main():
    terr = ler_json("dados/territorio.json")
    muni = terr["municipios"]
    limite = int(os.environ.get("LIMITE", "0")) or None
    if limite:
        muni = muni[::max(1, len(muni) // limite)][:limite]
    t0 = time.time()
    resultados, falhas = [], 0
    with ThreadPoolExecutor(max_workers=TRABALHADORES) as ex:
        for m, r, erro in ex.map(coletar_um, muni):
            if erro:
                falhas += 1
            resultados.append((m, r))
    por_uf = {}
    for m, r in resultados:
        por_uf.setdefault(m["uf"], []).append((m["cod"], m["nome"], r))
    resumo = {"gerado_em": agora(), "fonte": "InfoDengue (Fiocruz e FGV), casos estimados pelo modelo", "ano": ANO, "ufs": {}}
    se_ref = {}
    for uf, itens in sorted(por_uf.items()):
        agg = agregar_uf(itens)
        ses = [r["se"] for _, _, r in itens if r]
        se_ref[uf] = max(ses) if ses else None
        resumo["ufs"][uf] = dict(agg, se=se_ref[uf], municipios=len(itens))
        escrever_json(f"dados/{DOENCA}/{uf}.json", {
            "uf": uf, "gerado_em": resumo["gerado_em"], "ano": ANO, "se": se_ref[uf],
            "m": [[c, n, r["nivel"], r["casos"], r["casos_est"], r["inc"], r["rt"], r["serie"]] if r else [c, n, None, None, None, None, None, []] for c, n, r in itens]})
    escrever_json(f"dados/{DOENCA}_resumo.json", resumo)
    taxa = falhas / max(1, len(muni))
    segundos = int(time.time() - t0)
    resumo_actions(f"{DOENCA.capitalize()} por municipio", [f"Municipios consultados: {len(muni)}", f"Falhas: {falhas} ({taxa:.1%})", f"Tempo: {segundos // 60} min {segundos % 60} s"])
    print(f"municipios={len(muni)} falhas={falhas} taxa={taxa:.2%} tempo={segundos}s")
    return 1 if taxa > MAX_FALHA else 0

if __name__ == "__main__":
    sys.exit(main())
