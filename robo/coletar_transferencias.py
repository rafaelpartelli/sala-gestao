#!/usr/bin/env python3
"""Transferencias da Uniao na funcao Saude (codigo 10), por municipio e mes (Portal da Transparencia, CSV mensal sem chave).
O municipio vem em codigo SIAFI: o mapa SIAFI para IBGE sai do CAUC; o que sobrar casa por nome e UF.
Ficam de fora das linhas por municipio as transferencias sem municipio (somadas por UF). Nao guarda nomes de favorecidos.
Saida: dados/transferencias.json."""
import csv, io, os, sys, zipfile
from datetime import datetime
from comum import baixar, escrever_json, ler_json, agora, numero_br, sem_acento, resumo_actions, BRT
import coletar_cauc

PT = "https://portaldatransparencia.gov.br/download-de-dados/transferencias/{ym}"
MESES = int(os.environ.get("MESES", "3"))
NECESSARIAS = ("UF", "CÓDIGO MUNICÍPIO SIAFI", "NOME MUNICÍPIO", "CÓDIGO FUNÇÃO", "VALOR TRANSFERIDO")

def meses_candidatos(hoje, n=8):
    ano, mes = hoje.year, hoje.month
    out = []
    for _ in range(n):
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
        out.append(f"{ano}{mes:02d}")
    return out

def agregar(linhas, siafi_para_ibge, nome_uf_para_ibge, funcao="10"):
    """linhas: iteravel de linhas de texto do CSV. Devolve (mun {ibge: valor}, uf {sigla: valor}, sem_mun_valor, total, nao_casados)."""
    leitor = csv.reader(linhas, delimiter=";")
    cab = [c.strip() for c in next(leitor)]
    ix = {c: i for i, c in enumerate(cab)}
    falta = [c for c in NECESSARIAS if c not in ix]
    if falta:
        raise ValueError(f"colunas ausentes: {falta}")
    mun, uf, nao, total, sem_mun = {}, {}, set(), 0.0, 0.0
    for l in leitor:
        if len(l) < len(cab) or l[ix["CÓDIGO FUNÇÃO"]].strip() != funcao:
            continue
        v = numero_br(l[ix["VALOR TRANSFERIDO"]])
        sig = l[ix["UF"]].strip().upper()
        total += v
        if sig:
            uf[sig] = uf.get(sig, 0.0) + v
        siafi = l[ix["CÓDIGO MUNICÍPIO SIAFI"]].strip()
        nome = sem_acento(l[ix["NOME MUNICÍPIO"]])
        if not siafi and not nome:
            sem_mun += v
            continue
        ibge = siafi_para_ibge.get(siafi) or nome_uf_para_ibge.get((nome, sig))
        if not ibge:
            nao.add(f"{nome}-{sig}")
            sem_mun += v
            continue
        mun[ibge] = mun.get(ibge, 0.0) + v
    return mun, uf, sem_mun, total, nao

def baixar_mes(ym):
    bruto = baixar(PT.format(ym=ym), timeout=300, tentativas=3, pausa=10)
    z = zipfile.ZipFile(io.BytesIO(bruto))
    nome = next(i.filename for i in z.infolist() if i.filename.lower().endswith(".csv"))
    return io.TextIOWrapper(z.open(nome), encoding="latin-1", newline="")

def main():
    terr = ler_json("dados/territorio.json")
    nome_uf = {(sem_acento(m["nome"]), m["uf"]): m["cod"] for m in terr["municipios"]}
    cauc = coletar_cauc.carregar_cauc()
    meses, mun_m, uf_m, pct, nao_tot = [], [], [], {}, set()
    for ym in meses_candidatos(datetime.now(BRT)):
        if len(meses) >= MESES:
            break
        try:
            mun, uf, sem_mun, total, nao = agregar(baixar_mes(ym), cauc["siafi"], nome_uf)
        except Exception as e:
            print(f"{ym}: indisponivel ({type(e).__name__}: {str(e)[:80]})")
            continue
        if not total:
            print(f"{ym}: sem valores na funcao saude")
            continue
        meses.append(ym); mun_m.append(mun); uf_m.append(uf); nao_tot |= nao
        pct[ym] = round(100 * (total - sem_mun) / total, 1)
        print(f"{ym}: R$ {total:,.0f}, {len(mun)} municipios, {pct[ym]}% do valor com municipio")
    if not meses:
        print("validacao falhou: nenhum mes coletado")
        return 1
    meses.reverse(); mun_m.reverse(); uf_m.reverse()
    codigos = sorted(set().union(*[set(m) for m in mun_m]))
    siglas = sorted(set().union(*[set(u) for u in uf_m]) & set(terr["por_uf"]))
    escrever_json("dados/transferencias.json", {
        "gerado_em": agora(), "fonte": "Portal da Transparência da União, transferências, função Saúde (código 10)", "meses": meses,
        "pct_valor_com_municipio": {k: pct[k] for k in meses}, "municipios_nao_casados": len(nao_tot),
        "observacao": "Valores transferidos no mês, em reais. Parte das transferências não traz município e fica só no total do estado.",
        "ufs": {u: [round(m.get(u, 0)) for m in uf_m] for u in siglas},
        "mun": {c: [round(m.get(c, 0)) for m in mun_m] for c in codigos}})
    resumo_actions("Transferências federais em saúde", [f"Meses: {', '.join(meses)}", f"Municípios com valor: {len(codigos)}", f"Nomes não casados: {len(nao_tot)}"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
