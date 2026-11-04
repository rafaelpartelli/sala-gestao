#!/usr/bin/env python3
"""Profissionais de saude por municipio (CNES, arquivos PF do FTP do DATASUS).
Conta VINCULOS profissionais (uma pessoa com dois vinculos conta duas vezes), por grupo de CBO, e soma as horas semanais.
Nao guarda nome, CPF, CNS nem registro: so contagens por municipio.
Saida: dados/profissionais/<UF>.json e dados/profissionais_resumo.json."""
import os, sys, time
from concurrent.futures import ProcessPoolExecutor
import cnes_ftp, dbc
from comum import escrever_json, ler_json, agora, resumo_actions, numero_br

# Grupos por prefixo da CBO 2002 (conferir com a tabela oficial da CBO antes de decidir com base nelas).
GRUPOS_CBO = [
    ("Médicos", ("2251", "2252", "2253", "2231")),
    ("Enfermeiros", ("2235",)),
    ("Técnicos e auxiliares de enfermagem", ("3222",)),
    ("Agentes comunitários de saúde", ("515105",)),
    ("Cirurgiões-dentistas", ("2232",)),
    ("Técnicos e auxiliares de saúde bucal", ("3224",)),
    ("Farmacêuticos", ("2234",)),
    ("Psicólogos", ("2515",)),
    ("Fisioterapeutas", ("2236",)),
    ("Nutricionistas", ("2237",)),
    ("Assistentes sociais", ("2516",)),
    ("Fonoaudiólogos e terapeutas ocupacionais", ("2238", "2239")),
]
NOMES = [g for g, _ in GRUPOS_CBO] + ["Outros", "Total"]
CAMPOS = ["CODUFMUN", "CBO", "PROF_SUS", "HORA_AMB", "HORAOUTR", "HORAHOSP"]

def grupo_cbo(cbo):
    c = (cbo or "").strip()
    for nome, prefixos in GRUPOS_CBO:
        if c.startswith(prefixos):
            return nome
    return "Outros"

def agregar(registros, mapa6):
    """registros: iteravel de dicts com CAMPOS. mapa6: cod6 -> cod7. Devolve (por_municipio, lidos, sem_municipio)."""
    por, lidos, sem = {}, 0, 0
    for r in registros:
        lidos += 1
        cod = mapa6.get((r.get("CODUFMUN") or "")[:6])
        if not cod:
            sem += 1
            continue
        horas = int(numero_br(r.get("HORA_AMB")) + numero_br(r.get("HORAOUTR")) + numero_br(r.get("HORAHOSP")))
        sus = 1 if (r.get("PROF_SUS") or "").strip() == "1" else 0
        m = por.setdefault(cod, {})
        for g in (grupo_cbo(r.get("CBO")), "Total"):
            a = m.setdefault(g, [0, 0, 0])
            a[0] += 1
            a[1] += sus
            a[2] += horas
    return por, lidos, sem

def processar_uf(args):
    uf, comp, mapa6 = args
    t0 = time.time()
    try:
        bruto = cnes_ftp.baixar_arquivo("PF", uf, comp)
        por, lidos, sem = agregar(dbc.registros(bruto, CAMPOS), mapa6)
        return uf, {"m": por, "lidos": lidos, "sem_municipio": sem, "mb": round(len(bruto) / 1048576, 1), "s": int(time.time() - t0)}, None
    except Exception as e:
        return uf, None, f"{type(e).__name__}: {str(e)[:120]}"

def somar_uf(mun):
    tot = {}
    for m in mun.values():
        for g, v in m.items():
            a = tot.setdefault(g, [0, 0, 0])
            for i in range(3):
                a[i] += v[i]
    return tot

def main():
    terr = ler_json("dados/territorio.json")
    mapa6 = {m["cod"][:6]: m["cod"] for m in terr["municipios"]}
    ufs = sorted({m["uf"] for m in terr["municipios"]})
    por = cnes_ftp.agrupar(cnes_ftp.listar("PF"), "PF")
    comp = os.environ.get("COMPETENCIA") or cnes_ftp.competencia_completa(por)
    if not comp:
        print("sem competencia completa no FTP")
        return 1
    limite = os.environ.get("UFS")
    if limite:
        ufs = [u for u in ufs if u in limite.split(",")]
    print(f"competencia {comp}, {len(ufs)} UFs")
    n = int(os.environ.get("PROCESSOS", "4"))
    resultados, falhas = {}, {}
    with ProcessPoolExecutor(max_workers=n) as ex:
        for uf, r, erro in ex.map(processar_uf, [(u, comp, mapa6) for u in ufs]):
            if erro:
                falhas[uf] = erro
                print("FALHA", uf, erro, flush=True)
            else:
                resultados[uf] = r
                print(f"{uf}: {r['lidos']} vinculos, {r['mb']} MB, {r['s']} s", flush=True)
    if len(resultados) < 20:
        print("validacao falhou: poucas UFs")
        return 1
    gerado = agora()
    resumo = {"gerado_em": gerado, "fonte": "CNES, arquivos PF do FTP do DATASUS (Ministério da Saúde)", "competencia": comp, "grupos": NOMES,
              "unidade": "vínculos profissionais (não pessoas); horas semanais somam ambulatorial, hospitalar e outras", "ufs": {}, "ufs_faltando": sorted(falhas)}
    for uf, r in sorted(resultados.items()):
        resumo["ufs"][uf] = somar_uf(r["m"])
        escrever_json(f"dados/profissionais/{uf}.json", {"uf": uf, "competencia": comp, "gerado_em": gerado, "grupos": NOMES, "m": r["m"]})
    escrever_json("dados/profissionais_resumo.json", resumo)
    tot = sum(r["lidos"] for r in resultados.values())
    sem = sum(r["sem_municipio"] for r in resultados.values())
    resumo_actions("Profissionais (CNES, PF)", [f"Competência: {comp}", f"UFs: {len(resultados)}", f"Vínculos lidos: {tot}", f"Sem município: {sem}", f"Falhas: {falhas or 'nenhuma'}"])
    return 1 if falhas else 0

if __name__ == "__main__":
    sys.exit(main())
