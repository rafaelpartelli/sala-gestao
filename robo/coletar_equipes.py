#!/usr/bin/env python3
"""Equipes de saude ativas por municipio e tipo (CNES, arquivos EP do FTP do DATASUS).
Conta equipes distintas (IDEQUIPE, o INE) sem data de desativacao (campo em branco ou codigo 900001). Nao guarda nomes de equipes nem de profissionais.
Saida: dados/equipes.json."""
import os, sys
import cnes_ftp, dbc
from comum import escrever_json, ler_json, agora, resumo_actions

# Codigos confirmados na Nota Tecnica 23 do CNES (COSEMS-SP, 2020). Outros codigos aparecem como 'Tipo NN' ate serem conferidos.
TIPOS = {"70": "Saúde da Família (eSF e variantes, inclui eACS)", "71": "Saúde Bucal (eSB)", "73": "Consultório na Rua (eCR)",
         "74": "Atenção Primária Prisional (eAPP)", "76": "Atenção Primária (eAP)"}
CAMPOS = ["CNES", "CODUFMUN", "TIPO_EQP", "IDEQUIPE", "ID_AREA", "DT_DESAT"]

def desativada(valor):
    """DT_DESAT vem em branco ou com o codigo 900001 (sem desativacao) nas equipes ativas; data AAAAMM (ex.: 202307) indica desativada."""
    v = (valor or "").strip()
    return bool(v) and not v.startswith("9")

def agregar(registros, mapa6):
    """Devolve ({cod7: {tipo: n}}, lidos, sem_municipio, inativas)."""
    vistos, por, lidos, sem, inativas = set(), {}, 0, 0, 0
    for r in registros:
        lidos += 1
        if desativada(r.get("DT_DESAT")):
            inativas += 1
            continue
        cod = mapa6.get((r.get("CODUFMUN") or "")[:6])
        if not cod:
            sem += 1
            continue
        tipo = (r.get("TIPO_EQP") or "").strip().zfill(2)
        chave = (r.get("IDEQUIPE") or "").strip() or f"{r.get('CNES')}|{tipo}|{r.get('ID_AREA')}"
        if (chave, tipo) in vistos:
            continue
        vistos.add((chave, tipo))
        d = por.setdefault(cod, {})
        d[tipo] = d.get(tipo, 0) + 1
    return por, lidos, sem, inativas

def amostrar(registros, ac):
    """Diagnostico: guarda os valores mais comuns de DT_DESAT e imprime 3 linhas de exemplo (sem nomes nem CPF)."""
    for r in registros:
        if ac["n"] < 3:
            print("amostra", {k: r.get(k) for k in ("CODUFMUN", "TIPO_EQP", "DT_DESAT")}, flush=True)
        ac["n"] += 1
        d = r.get("DT_DESAT") or "(vazio)"
        if d in ac["dt"] or len(ac["dt"]) < 60:
            ac["dt"][d] = ac["dt"].get(d, 0) + 1
        yield r

def main():
    diag = {"n": 0, "dt": {}}
    terr = ler_json("dados/territorio.json")
    mapa6 = {m["cod"][:6]: m["cod"] for m in terr["municipios"]}
    uf_de = {m["cod"]: m["uf"] for m in terr["municipios"]}
    ufs = sorted(set(uf_de.values()))
    por = cnes_ftp.agrupar(cnes_ftp.listar("EP"), "EP")
    comp = os.environ.get("COMPETENCIA") or cnes_ftp.competencia_completa(por)
    if not comp:
        print("sem competencia completa no FTP")
        return 1
    mun, lidos, sem, inat, falhas = {}, 0, 0, 0, {}
    for uf in ufs:
        try:
            p, l, s, i = agregar(amostrar(dbc.registros(cnes_ftp.baixar_arquivo("EP", uf, comp), CAMPOS), diag), mapa6)
            mun.update(p)
            lidos += l; sem += s; inat += i
            print(f"{uf}: {l} linhas", flush=True)
        except Exception as e:
            falhas[uf] = f"{type(e).__name__}: {str(e)[:120]}"
            print("FALHA", uf, falhas[uf], flush=True)
    top = sorted(diag["dt"].items(), key=lambda x: -x[1])[:8]
    print(f"diagnostico: lidas={lidos} desativadas={inat} sem_municipio={sem} municipios_com_equipe={len(mun)} DT_DESAT mais comuns={top}", flush=True)
    if len(falhas) > 2 or not mun:
        print("validacao falhou")
        return 1
    ufs_tot = {}
    for cod, d in mun.items():
        a = ufs_tot.setdefault(uf_de[cod], {})
        for t, n in d.items():
            a[t] = a.get(t, 0) + n
    total = sum(sum(d.values()) for d in mun.values())
    escrever_json("dados/equipes.json", {"gerado_em": agora(), "fonte": "CNES, arquivos EP do FTP do DATASUS (Ministério da Saúde)", "competencia": comp,
                                         "tipos": TIPOS, "observacao": "Equipes ativas (sem data de desativação), contadas pelo INE. Códigos de tipo fora da lista aparecem como Tipo NN.",
                                         "total_ativas": total, "ufs": dict(sorted(ufs_tot.items())), "ufs_faltando": sorted(falhas), "mun": dict(sorted(mun.items()))})
    resumo_actions("Equipes (CNES, EP)", [f"Competência: {comp}", f"Equipes ativas: {total}", f"Linhas lidas: {lidos}", f"Desativadas: {inat}", f"Sem município: {sem}", f"Falhas: {falhas or 'nenhuma'}"])
    return 1 if falhas else 0

if __name__ == "__main__":
    sys.exit(main())
