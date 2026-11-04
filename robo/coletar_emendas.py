#!/usr/bin/env python3
"""Emendas parlamentares da Uniao na funcao Saude (Portal da Transparencia, API com chave).
Agrega por UF, tipo de emenda e subfuncao. Nao guarda nomes de autores. Chave: variavel PORTAL_TRANSPARENCIA_KEY (segredo do GitHub).
Saida: dados/emendas.json."""
import os, re, sys, time
from comum import baixar_json, escrever_json, ler_json, agora, numero_br, sem_acento, resumo_actions, BRT
from datetime import datetime

API = "https://api.portaldatransparencia.gov.br/api-de-dados/emendas?ano={ano}&pagina={pag}&codigoFuncao=10"
PAUSA = float(os.environ.get("PAUSA", "0.8"))   # abaixo do limite por minuto da API
MAX_PAGINAS = 400

def uf_do_local(local, nomes_uf, siglas):
    """Extrai a UF de 'VITORIA - ES' ou 'ESPIRITO SANTO (UF)'. Devolve sigla ou None."""
    t = sem_acento(local)
    m = re.search(r"-\s*([A-Z]{2})$", t)
    if m and m.group(1) in siglas:
        return m.group(1)
    t2 = re.sub(r"\s*\(UF\)\s*$", "", t)
    return nomes_uf.get(t2)

def agregar(registros, nomes_uf, siglas):
    por_uf, por_tipo, por_sub = {}, {}, {}
    tot = {"empenhado": 0.0, "liquidado": 0.0, "pago": 0.0, "n": 0}
    for r in registros:
        e, l, p = (numero_br(r.get(k)) for k in ("valorEmpenhado", "valorLiquidado", "valorPago"))
        uf = uf_do_local(r.get("localidadeDoGasto"), nomes_uf, siglas) or "ND"
        for chave, dic in ((uf, por_uf), (r.get("tipoEmenda") or "ND", por_tipo), (r.get("subfuncao") or "ND", por_sub)):
            d = dic.setdefault(chave, {"empenhado": 0.0, "liquidado": 0.0, "pago": 0.0, "n": 0})
            d["empenhado"] += e; d["liquidado"] += l; d["pago"] += p; d["n"] += 1
        tot["empenhado"] += e; tot["liquidado"] += l; tot["pago"] += p; tot["n"] += 1
    arred = lambda d: {k: (round(v, 2) if k != "n" else v) for k, v in d.items()}
    return {"total": arred(tot), "por_uf": {k: arred(v) for k, v in sorted(por_uf.items())},
            "por_tipo": {k: arred(v) for k, v in sorted(por_tipo.items())}, "por_subfuncao": {k: arred(v) for k, v in sorted(por_sub.items())}}

def coletar_ano(ano, chave):
    regs = []
    for pag in range(1, MAX_PAGINAS + 1):
        lote = baixar_json(API.format(ano=ano, pag=pag), headers={"chave-api-dados": chave, "Accept": "application/json"}, timeout=60, tentativas=3, pausa=5)
        if not lote:
            break
        regs += lote
        time.sleep(PAUSA)
    return regs

def main():
    chave = os.environ.get("PORTAL_TRANSPARENCIA_KEY", "").strip()
    if not chave:
        print("sem chave: defina o segredo PORTAL_TRANSPARENCIA_KEY")
        return 1
    terr = ler_json("dados/territorio.json")
    sigla_por_cod = {m["cod"][:2]: m["uf"] for m in terr["municipios"]}   # robusto mesmo se a sigla da UF vier errada
    siglas = set(sigla_por_cod.values())
    nomes_uf = {sem_acento(u["nome"]): sigla_por_cod[u["cod"]] for u in terr["ufs"] if u["cod"] in sigla_por_cod}
    ano = datetime.now(BRT).year
    anos = {}
    for a in (ano, ano - 1):
        regs = coletar_ano(a, chave)
        anos[str(a)] = agregar(regs, nomes_uf, siglas)
        print(a, "registros:", len(regs))
    if not anos[str(ano - 1)]["total"]["n"]:
        print("validacao falhou: ano anterior sem registros")
        return 1
    escrever_json("dados/emendas.json", {"gerado_em": agora(), "fonte": "Portal da Transparencia da Uniao, emendas parlamentares, funcao Saude (codigo 10)",
                                         "observacao": "Valores agregados por localidade do gasto. Sem nomes de autores.", "anos": anos})
    resumo_actions("Emendas da Uniao em saude", [f"{a}: {d['total']['n']} registros" for a, d in anos.items()])
    return 0

if __name__ == "__main__":
    sys.exit(main())
