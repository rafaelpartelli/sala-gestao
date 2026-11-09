#!/usr/bin/env python3
"""Despesa total com pessoal dos municipios e dos estados (SICONFI, RGF Anexo 01, Poder Executivo), com os limites da LRF.
Fecha o exercicio pelo 3o quadrimestre (periodicidade Q) e, se o ente for semestral, pelo 2o semestre (S).
Por padrao coleta o piloto (ES, TO, PA, PE); UFS=BR coleta o Brasil. Saida: dados/pessoal.json."""
import os, sys, time
from datetime import datetime
from comum import escrever_json, ler_json, agora, resumo_actions, BRT
from siconfi_comum import pedir, norm, valor, populacao, ufs_do_ambiente, executar
from coletar_receita import montar_entes

TRABALHADORES = int(os.environ.get("TRABALHADORES", "6"))
# (tipo, periodicidade, periodo): RGF quadrimestral, RGF semestral e RGF Simplificado (municipios pequenos, semestral). Conferido na API em 09/11/2026.
TENTATIVAS_PERIODO = (("RGF", "Q", 3), ("RGF", "S", 2), ("RGF Simplificado", "S", 2))
CAMPOS = ["dtp", "rcl_ajustada", "limite_maximo", "limite_prudencial", "limite_alerta", "bruta", "pct_rcl"]

def _valor_coluna(itens, cod):
    """Valor da conta na coluna de total (12 meses) ou 'Valor'. A primeira ocorrencia vale."""
    for i in itens:
        if str(i.get("cod_conta")) != cod:
            continue
        c = norm(i.get("coluna"))
        if c.startswith("total (últimos 12") or c.startswith("total (ultimos 12") or c == "valor":
            v = valor(i)
            if v is not None:
                return v
    return None

def _pct_coluna(itens, cod):
    for i in itens:
        if str(i.get("cod_conta")) == cod and norm(i.get("coluna")).startswith("% sobre"):
            v = valor(i)
            if v is not None:
                return v
    return None

def extrair(itens):
    """[dtp, rcl_ajustada, limite_maximo, limite_prudencial, limite_alerta, bruta, pct_rcl, populacao] ou None.
    O percentual e recalculado (DTP / RCL ajustada) quando a API nao o informa."""
    itens = itens or []
    dtp = _valor_coluna(itens, "DespesaComPessoalTotal")
    rcl = _valor_coluna(itens, "ReceitaCorrenteLiquidaAjustada")
    if dtp is None or not rcl:
        return None
    pct = _pct_coluna(itens, "DespesaComPessoalTotal")
    if pct is None:
        pct = dtp / rcl * 100
    def r(cod):
        v = _valor_coluna(itens, cod)
        return round(v) if v is not None else None
    return [round(dtp), round(rcl), r("LimiteMaximoDespesaComPessoalTotal"), r("LimitePrudencialDespesaComPessoalTotal"),
            r("LimiteDeAlertaDespesaComPessoalTotal"), r("DespesaComPessoalBruta"), round(pct, 2), populacao(itens)]

def faixa(r):
    """Faixa legal pelo uso do limite maximo: alerta (90%, art. 59 LRF), prudencial (95%, art. 22) e excedido (100%, art. 20).
    Devolve 'ok', 'alerta', 'prudencial', 'excedido' ou None sem limite."""
    dtp, lim = r[0], r[2]
    if not lim:
        return None
    uso = dtp / lim
    return "excedido" if uso > 1 else "prudencial" if uso >= 0.95 else "alerta" if uso >= 0.90 else "ok"

def pedir_ente(cod, exercicio):
    for tipo, periodicidade, periodo in TENTATIVAS_PERIODO:
        itens = pedir("rgf", dict(an_exercicio=exercicio, in_periodicidade=periodicidade, nr_periodo=periodo,
                                  co_tipo_demonstrativo=tipo, no_anexo="RGF-Anexo 01", co_poder="E", id_ente=cod))
        if itens:
            return itens
    return []

def um(args):
    ente, exercicio = args
    try:
        return ente, extrair(pedir_ente(ente["cod"], exercicio)), None
    except Exception as e:
        return ente, None, type(e).__name__

def coletar(entes, exercicio):
    t0 = time.time()
    resultado, falhos, erros = executar(entes, lambda e: um((e, exercicio)), TRABALHADORES)
    return [(e, resultado.get(e["cod"])) for e in entes], len(falhos), int(time.time() - t0), erros

def main():
    ufs = ufs_do_ambiente()
    muni, est = montar_entes(ler_json("dados/territorio.json"), ufs)
    exercicio = int(os.environ.get("EXERCICIO", "0")) or datetime.now(BRT).year - 1
    res_m, falhas, seg, erros = coletar(muni, exercicio)
    res_e, _, _, _ = coletar(est, exercicio)
    ok_m = [(m, r) for m, r in res_m if r]
    taxa = falhas / max(1, len(muni))
    contagem = {}
    for _, r in ok_m:
        contagem[faixa(r)] = contagem.get(faixa(r), 0) + 1
    print(f"ufs={ufs} exercicio={exercicio} municipios={len(muni)} com_pessoal={len(ok_m)} falhas={falhas} ({taxa:.1%}) faixas={contagem} tempo={seg}s erros={dict(erros)}")
    for m, r in [x for x in ok_m if faixa(x[1]) == "excedido"][:5]:
        print("amostra excedido:", m["uf"], m["cod"], "dtp", r[0], "rcl", r[1], "limite", r[2], "pct", r[6])
    if taxa > 0.05 or (muni and len(ok_m) < 0.5 * len(muni)):
        print("validacao falhou: nada gravado")
        return 1
    escrever_json("dados/pessoal.json", {
        "gerado_em": agora(), "fonte": "SICONFI, RGF Anexo 01, Poder Executivo (Tesouro Nacional)", "exercicio": exercicio, "ufs": ufs,
        "campos": CAMPOS + ["populacao"],
        "observacao": "Despesa total com pessoal (DTP) dos últimos 12 meses, RCL ajustada e limites da LRF (arts. 19, 20, 22 e 59). Só Poder Executivo. Município que não entregou o RGF fica sem valor.",
        "municipios_consultados": len(muni), "municipios_com_pessoal": len(ok_m), "faixas": contagem,
        "estados": {e["uf"]: r for e, r in res_e if r},
        "mun": {str(m["cod"]): r for m, r in ok_m}})
    resumo_actions("Pessoal (RGF Anexo 01)", [f"UFs: {', '.join(ufs)}", f"Exercício {exercicio}", f"Municípios com pessoal: {len(ok_m)} de {len(muni)}",
                   f"Faixas: {contagem}", f"Falhas: {falhas} ({taxa:.1%})", f"Tempo: {seg // 60} min"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
