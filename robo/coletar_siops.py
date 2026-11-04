#!/usr/bin/env python3
"""Aplicacao em saude (15%, LC 141/2012) por municipio, a partir do SIOPS (demonstrativo RREO Anexo 12, siops.datasus.gov.br/rel_LRF.php).
Para cada municipio guarda duas fotos: o ultimo exercicio fechado (5o bimestre, codigo 20) e o bimestre mais recente do exercicio atual.
Campos: receitas que formam a base (IPTU, ITBI, ISS, IRRF, FPM, ITR, IPVA, ICMS, IPI-exportacao, compensacoes), base total (III), valor aplicado em ASPS
(empenhado, liquidado, pago), despesa minima (15%) e percentuais aplicados. So valores agregados do municipio, sem dados pessoais.
Saida: dados/siops/<UF>.json e dados/siops_resumo.json."""
import os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import unescape
from comum import baixar, escrever_json, ler_json, agora, resumo_actions, BRT

URL = "http://siops.datasus.gov.br/rel_LRF.php?S=1&UF={uf};&Municipio={mun};&Ano={ano}&Periodo={per}"
TRABALHADORES = int(os.environ.get("TRABALHADORES", "8"))
# bimestre -> codigo do periodo no SIOPS
PERIODO = {1: 12, 2: 14, 3: 1, 4: 18, 5: 20}
NUM = r"(?:-?\d[\d\.]*,\d{2}|N/A)"
# (chave, expressao do rotulo, quantidade de colunas, coluna usada)
RECEITAS = [("iptu", r"Imposto Predial e Territorial Urbano - IPTU", 4, 2), ("itbi", r"Transmiss[ãa]o Inter Vivos - ITBI", 4, 2),
            ("iss", r"Servi[çc]os de Qualquer Natureza - ISS", 4, 2), ("irrf", r"Retido na Fonte - IRRF", 4, 2),
            ("fpm", r"Cota-Parte FPM", 4, 2), ("itr", r"Cota-Parte ITR", 4, 2), ("ipva", r"Cota-Parte do IPVA", 4, 2), ("icms", r"Cota-Parte do ICMS", 4, 2),
            ("ipi", r"Cota-Parte do IPI - Exporta[çc][ãa]o", 4, 2), ("comp", r"Compensa[çc][õo]es Financeiras Provenientes de Impostos e Transfer[êe]ncias Constitucionais", 4, 2),
            ("imp", r"RECEITA DE IMPOSTOS \(I\)", 4, 2), ("transf", r"RECEITA DE TRANSFER[ÊE]NCIAS CONSTITUCIONAIS E LEGAIS \(II\)", 4, 2),
            ("base", r"\(III\) = \(I\) \+ \(II\)", 4, 2)]
ORDEM = [k for k, *_ in RECEITAS]
TOTAIS = [("asps", r"Total das Despesas com ASPS \(XII\) = \(XI\)", 3), ("aplicado", r"VALOR APLICADO EM ASPS \(XVI\) = \(XII - XIII - XIV - XV\)", 3),
          ("pct", r"APLICADO EM ASPS \(XVI / III\)\*100 \(m[ií]nimo de 15%[^)]*\)", 3)]

def numero(t):
    return None if t == "N/A" else float(t.replace(".", "").replace(",", "."))

def texto(html):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", t))).strip()

def apos(rotulo, t, n):
    """Os n numeros que seguem o rotulo, ou None."""
    m = re.search(rotulo + r"\s*((?:" + NUM + r"\s*){%d})" % n, t)
    return [numero(x) for x in re.findall(NUM, m.group(1))] if m else None

def ler(t):
    """Le o texto do demonstrativo. Devolve dict ou None se nao houver dados validos (base zerada ou ausente)."""
    b = re.search(r"(\d)º Bimestre de (\d{4})", t)
    if not b:
        return None
    r = {"bim": int(b.group(1)), "ano": int(b.group(2))}
    h = re.search(r"Dados ([A-Za-zçãéÉ ]{4,30}?) em (\d\d/\d\d/\d\d)", t)
    r["status"] = h.group(1).strip() if h else None
    r["data"] = h.group(2) if h else None
    for k, rot, n, i in RECEITAS:
        v = apos(rot, t, n)
        r[k] = round(v[i]) if v and v[i] is not None else None
    for k, rot, n in TOTAIS:
        v = apos(rot, t, n)
        r[k] = v
    m = apos(r"Despesa M[ií]nima a ser Aplicada em ASPS \(XVII\) = \(III\) x 15% \(LC 141/2012\)", t, 1)
    r["minimo"] = round(m[0]) if m and m[0] is not None else None
    if not r.get("base") or r["base"] <= 0 or r.get("pct") is None:
        return None
    return r

def compacto(r):
    """Lista curta para o JSON: ver CAMPOS."""
    f = lambda x, i: (round(x[i]) if x and x[i] is not None else None)
    p = lambda x, i: (x[i] if x and x[i] is not None else None)
    return [r["ano"], r["bim"], r["data"], *[r[k] for k in ORDEM], r["minimo"], f(r["aplicado"], 0), f(r["aplicado"], 1), f(r["aplicado"], 2), p(r["pct"], 0), p(r["pct"], 1), p(r["pct"], 2)]
CAMPOS = ["ano", "bimestre", "homologado_em", *ORDEM, "minimo", "aplicado_empenhado", "aplicado_liquidado", "aplicado_pago", "pct_empenhado", "pct_liquidado", "pct_pago"]

def pedir(m, ano, bim):
    u = URL.format(uf=m["cod"][:2], mun=m["cod"][:6], ano=ano, per=PERIODO[bim])
    return ler(texto(baixar(u, timeout=60, tentativas=3, pausa=3).decode("latin-1", "replace")))

def um(args):
    m, anterior, atual = args
    out = {"anterior": None, "atual": None}
    erro = None
    try:
        out["anterior"] = pedir(m, anterior, 5)
    except Exception as e:
        erro = type(e).__name__
    try:
        for bim in (5, 4, 3, 2, 1):
            r = pedir(m, atual, bim)
            if r and r["ano"] == atual and r["bim"] == bim:
                out["atual"] = r
                break
            if r is None and bim == 5:
                continue
    except Exception as e:
        erro = erro or type(e).__name__
    return m, out, erro

def main():
    terr = ler_json("dados/territorio.json")
    muni = terr["municipios"]
    limite = int(os.environ.get("LIMITE", "0")) or None
    if limite:
        muni = muni[::max(1, len(muni) // limite)][:limite]
    atual = int(os.environ.get("ANO", "0")) or datetime.now(BRT).year
    t0 = time.time()
    res, falhas = [], 0
    with ThreadPoolExecutor(max_workers=TRABALHADORES) as ex:
        for m, out, erro in ex.map(um, [(m, atual - 1, atual) for m in muni]):
            falhas += 1 if erro else 0
            res.append((m, out))
    com_ant = sum(1 for _, o in res if o["anterior"])
    com_atu = sum(1 for _, o in res if o["atual"])
    taxa = falhas / max(1, len(muni))
    print(f"municipios={len(muni)} exercicio_anterior={com_ant} exercicio_atual={com_atu} falhas={falhas} ({taxa:.1%}) tempo={int(time.time() - t0)}s")
    if taxa > 0.05 or com_ant < 0.5 * len(muni):
        print("validacao falhou")
        return 1
    por_uf, resumo = {}, {}
    for m, o in res:
        por_uf.setdefault(m["uf"], {})[m["cod"]] = {k: compacto(v) for k, v in o.items() if v}
    for uf, mun in por_uf.items():
        ant = [v["anterior"] for v in mun.values() if v.get("anterior")]
        ab = [x for x in ant if x[CAMPOS.index("pct_liquidado")] is not None and x[CAMPOS.index("pct_liquidado")] < 15]
        resumo[uf] = {"municipios": sum(1 for m in muni if m["uf"] == uf), "com_dado": len(ant), "abaixo_15": len(ab),
                      "pct_mediano": (sorted(x[CAMPOS.index("pct_liquidado")] for x in ant if x[CAMPOS.index("pct_liquidado")] is not None) or [None])[len([1 for x in ant if x[CAMPOS.index("pct_liquidado")] is not None]) // 2 if ant else 0]}
        escrever_json(f"dados/siops/{uf}.json", {"uf": uf, "gerado_em": agora(), "campos": CAMPOS, "m": mun})
    escrever_json("dados/siops_resumo.json", {"gerado_em": agora(), "fonte": "SIOPS, demonstrativo RREO Anexo 12 (Ministério da Saúde)", "exercicio_anterior": atual - 1, "exercicio_atual": atual, "campos": CAMPOS, "ufs": dict(sorted(resumo.items())),
        "observacao": "Percentual aplicado em ações e serviços públicos de saúde sobre a receita de impostos e transferências constitucionais e legais (mínimo de 15%, LC 141/2012). O exercício anterior usa o 5º bimestre, o último com dados no SIOPS; o exercício atual usa o bimestre mais recente."})
    resumo_actions("SIOPS (15% em saúde)", [f"Municípios: {len(muni)}", f"Exercício {atual - 1}: {com_ant}", f"Exercício {atual}: {com_atu}", f"Falhas: {falhas} ({taxa:.1%})", f"Tempo: {int(time.time() - t0) // 60} min"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
