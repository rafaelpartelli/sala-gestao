#!/usr/bin/env python3
"""Receita orcamentaria realizada dos municipios e dos estados (SICONFI, RREO Anexo 01).
Por padrao coleta o piloto (ES, TO, PA, PE); UFS=BR coleta o Brasil. Municipio que nao entregou o RREO fica sem valor (nao e erro).
Saida: dados/receita.json."""
import os, sys, time
from datetime import datetime
from comum import escrever_json, ler_json, agora, resumo_actions, BRT
from siconfi_comum import pedir, norm, valor, populacao, ufs_do_ambiente, executar, UF_COD

TRABALHADORES = int(os.environ.get("TRABALHADORES", "6"))

# cod_conta do RREO Anexo 01 (conferidos na API). Cada um gera um campo, na ordem de CAMPOS.
CONTAS = [("SubtotalDasReceitas", "total"), ("ReceitasCorrentes", "correntes"), ("ReceitasDeCapital", "capital"),
          ("ReceitaTributaria", "tributaria"), ("Impostos", "impostos"), ("TransferenciasCorrentes", "transf_correntes"),
          ("TransferenciasCorrentesDaUniaoEDeSuasEntidades", "transf_uniao"),
          ("TransferenciasCorrentesDosEstadosEDoDistritoFederalEDeSuasEntidades", "transf_estados")]
CAMPOS = [c for _, c in CONTAS] + ["prevista"]

def extrair(itens):
    """Valores realizados ('Ate o Bimestre (c)') por conta e a previsao atualizada do total.
    Devolve lista na ordem de CAMPOS + [populacao], ou None quando o ente nao tem o demonstrativo."""
    real, prev = {}, None
    total_v = None
    for i in itens or []:
        cod, col = str(i.get("cod_conta", "")), norm(i.get("coluna"))
        v = valor(i)
        if v is None:
            continue
        if col.startswith("até o bimestre") or col.startswith("ate o bimestre"):
            real.setdefault(cod, v)
        elif col.startswith("previsão atualizada") or col.startswith("previsao atualizada"):
            if cod == "SubtotalDasReceitas":
                prev = prev if prev is not None else v
            if cod == "TotalReceitas":
                total_v = total_v if total_v is not None else v
    # Sem o subtotal, usa o total (V). Os dois incluem as receitas intraorcamentarias.
    if "SubtotalDasReceitas" not in real and "TotalReceitas" in real:
        real["SubtotalDasReceitas"] = real["TotalReceitas"]
    if "SubtotalDasReceitas" not in real:
        return None
    out = [round(real.get(cod, 0.0)) for cod, _ in CONTAS]
    out.append(round(prev) if prev is not None else None)
    return out + [populacao(itens)]

# Municipios pequenos entregam o RREO simplificado (mesmo Anexo 01, mesma estrutura de colunas). Conferido na API em 09/11/2026.
TIPOS_RREO = ("RREO", "RREO Simplificado")

def pedir_ente(cod, exercicio, periodo):
    for tipo in TIPOS_RREO:
        itens = pedir("rreo", dict(an_exercicio=exercicio, nr_periodo=periodo, co_tipo_demonstrativo=tipo,
                                   no_anexo="RREO-Anexo 01", id_ente=cod))
        if itens:
            return itens
    return []

def um(args):
    ente, exercicio, periodo = args
    try:
        return ente, extrair(pedir_ente(ente["cod"], exercicio, periodo)), None
    except Exception as e:
        return ente, None, type(e).__name__

def coletar(entes, exercicio, periodo):
    t0 = time.time()
    resultado, falhos, erros = executar(entes, lambda e: um((e, exercicio, periodo)), TRABALHADORES)
    return [(e, resultado.get(e["cod"])) for e in entes], len(falhos), int(time.time() - t0), erros

def montar_entes(territorio, ufs):
    """Municipios das UFs pedidas (do territorio.json) e os governos estaduais."""
    muni = [{"cod": int(m["cod"]), "uf": m["uf"]} for m in territorio["municipios"] if m["uf"] in ufs]
    est = [{"cod": UF_COD[u], "uf": u} for u in ufs]
    return muni, est

def main():
    ufs = ufs_do_ambiente()
    muni, est = montar_entes(ler_json("dados/territorio.json"), ufs)
    exercicio = int(os.environ.get("EXERCICIO", "0")) or datetime.now(BRT).year - 1
    periodo = int(os.environ.get("PERIODO", "6"))
    res_m, falhas, seg, erros = coletar(muni, exercicio, periodo)
    res_e, _, _, _ = coletar(est, exercicio, periodo)
    ok_m = [(m, r) for m, r in res_m if r]
    taxa = falhas / max(1, len(muni))
    print(f"ufs={ufs} exercicio={exercicio} bimestre={periodo} municipios={len(muni)} com_receita={len(ok_m)} falhas={falhas} ({taxa:.1%}) estados_ok={sum(1 for _, r in res_e if r)} tempo={seg}s erros={dict(erros)}")
    if taxa > 0.05 or (muni and len(ok_m) < 0.5 * len(muni)):
        print("validacao falhou: nada gravado")
        return 1
    escrever_json("dados/receita.json", {
        "gerado_em": agora(), "fonte": "SICONFI, RREO Anexo 01 (Tesouro Nacional)", "exercicio": exercicio, "bimestre": periodo,
        "ufs": ufs, "campos": CAMPOS + ["populacao"],
        "observacao": "Valores em reais, receita realizada até o bimestre (inclui intraorçamentárias). Ente que não entregou o demonstrativo fica sem valor. Total e previsão do ente seguem o RREO entregue, sem ajuste do painel.",
        "municipios_consultados": len(muni), "municipios_com_receita": len(ok_m),
        "estados": {e["uf"]: r for e, r in res_e if r},
        "mun": {str(m["cod"]): r for m, r in ok_m}})
    resumo_actions("Receita (RREO Anexo 01)", [f"UFs: {', '.join(ufs)}", f"Exercício {exercicio}, bimestre {periodo}",
                   f"Municípios com receita: {len(ok_m)} de {len(muni)}", f"Falhas: {falhas} ({taxa:.1%})", f"Tempo: {seg // 60} min"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
