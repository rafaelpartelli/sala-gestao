#!/usr/bin/env python3
"""Base territorial da Sala de Gestao: 27 UFs e 5.570 municipios a partir do SICONFI (entes).
Fonte: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes (publica, sem chave).
Saida: dados/territorio.json (UFs com totais, municipios com codigo IBGE, nome, UF, populacao, capital).
Nao tem dado pessoal. A populacao e a que o SICONFI publica para o ente (confirmar ano na validacao)."""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes"
UA = "SalaGestaoSaude/0.3 (base territorial; contato: partelli.pro)"
BRT = timezone(timedelta(hours=-3))
ESPERADO_MUNICIPIOS = 5570
ESPERADO_UFS = 27

def baixar():
    itens, offset = [], 0
    while True:
        req = urllib.request.Request(f"{URL}?offset={offset}", headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            obj = json.loads(r.read().decode("utf-8"))
        itens += obj.get("items", [])
        if not obj.get("hasMore"):
            return itens
        offset += obj.get("limit") or len(obj.get("items", [])) or 1000
        time.sleep(0.2)

def montar(itens):
    """Separa municipios (esfera M) e UFs (esfera E, mais DF) e valida contagens."""
    muni, ufs = {}, {}
    for e in itens:
        esfera = str(e.get("esfera", "")).strip().upper()
        cod = str(e.get("cod_ibge", "")).strip()
        if esfera == "M" and len(cod) == 7:
            muni[cod] = {"cod": cod, "nome": e.get("ente"), "uf": e.get("uf"), "pop": e.get("populacao"),
                         "capital": str(e.get("capital", "")).strip() in ("1", "S", "SIM", "True", "true")}
        elif esfera in ("E", "D") and len(cod) == 2:
            ufs[cod] = {"cod": cod, "nome": e.get("ente"), "uf": e.get("uf"), "regiao": e.get("regiao"), "pop": e.get("populacao")}
    por_uf = {}
    for m in muni.values():
        u = por_uf.setdefault(m["uf"], {"municipios": 0, "pop_soma": 0})
        u["municipios"] += 1
        u["pop_soma"] += int(m["pop"] or 0)
    alertas = []
    if len(muni) != ESPERADO_MUNICIPIOS:
        alertas.append(f"municipios={len(muni)} (esperado {ESPERADO_MUNICIPIOS})")
    if len(ufs) != ESPERADO_UFS:
        alertas.append(f"ufs={len(ufs)} (esperado {ESPERADO_UFS})")
    return {"municipios": sorted(muni.values(), key=lambda m: m["cod"]), "ufs": sorted(ufs.values(), key=lambda u: u["cod"]),
            "por_uf": dict(sorted(por_uf.items())), "alertas": alertas}

def main():
    itens = baixar()
    base = montar(itens)
    saida = {"gerado_em": datetime.now(BRT).isoformat(timespec="seconds"), "fonte": URL,
             "totais": {"municipios": len(base["municipios"]), "ufs": len(base["ufs"]), "entes_lidos": len(itens)}, **base}
    os.makedirs("dados", exist_ok=True)
    with open("dados/territorio.json", "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(saida["totais"]), "alertas:", base["alertas"] or "nenhum")
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as fh:
            fh.write(f"## Base territorial\n\n- Municipios: {len(base['municipios'])}\n- UFs: {len(base['ufs'])}\n- Alertas: {', '.join(base['alertas']) or 'nenhum'}\n")
    return 1 if base["alertas"] else 0

if __name__ == "__main__":
    sys.exit(main())
