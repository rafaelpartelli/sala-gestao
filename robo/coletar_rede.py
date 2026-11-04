#!/usr/bin/env python3
"""Rede assistencial por municipio a partir do CNES (Dados Abertos do SUS, arquivo JSON em ZIP, 650 MB descompactado).
Le o arquivo em fluxo (sem carregar tudo na memoria) e agrega por municipio: total, ativos e contagem por tipo de unidade e esfera.
Saida: dados/rede/<UF>.json e dados/rede_resumo.json. Nenhum dado pessoal (so contagens)."""
import io, json, os, re, sys, zipfile, urllib.request
from comum import UA, escrever_json, ler_json, agora, resumo_actions

URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_json.zip"
# Codigos do campo TP_UNIDADE (tabela de dominio do CNES). Agrupamento para leitura gerencial; conferir com a tabela oficial antes de decidir com base nele.
GRUPOS = {"01": "Atenção básica", "02": "Atenção básica",
          "05": "Hospitais", "07": "Hospitais", "62": "Hospitais",
          "15": "Urgência e unidade mista", "20": "Urgência e unidade mista", "21": "Urgência e unidade mista", "73": "Urgência e unidade mista", "42": "Urgência e unidade mista",
          "04": "Ambulatório especializado", "36": "Ambulatório especializado",
          "22": "Consultório isolado",
          "39": "Apoio diagnóstico e terapêutico",
          "43": "Farmácia",
          "70": "Saúde mental (CAPS)",
          "50": "Vigilância, regulação e gestão", "64": "Vigilância, regulação e gestão", "68": "Vigilância, regulação e gestão", "76": "Vigilância, regulação e gestão", "81": "Vigilância, regulação e gestão",
          "32": "Unidades móveis", "40": "Unidades móveis",
          "77": "Atenção domiciliar"}
SEP = re.compile(r"\}\s*,\s*\{")

def esfera_curta(txt):
    t = (txt or "").upper()
    for chave, nome in (("MUNICIPAL", "Municipal"), ("ESTADUAL", "Estadual"), ("FEDERAL", "Federal"), ("PRIVAD", "Privada")):
        if chave in t:
            return nome
    return "Outra"

NATUREZAS = ("Pública", "Privada com fins lucrativos", "Privada sem fins lucrativos", "Pessoa física", "Outra")
HOSPITAIS = {"05", "07", "62"}

def natureza(r):
    """Classe pela natureza juridica (CONCLA: 1 administracao publica, 2 entidades empresariais, 3 entidades sem fins lucrativos, 4 pessoas fisicas).
    Sem a natureza, usa a esfera administrativa. 'Sem fins lucrativos' inclui as filantropicas, mas o CNES nao informa o CEBAS."""
    cod = re.sub(r"\D", "", str(r.get("CO_NATUREZA_JUR") or ""))[:1] or re.sub(r"\D", "", str(r.get("CO_NATUREZA_ORGANIZACAO") or ""))[:1]
    if cod in "1234" and cod:
        return NATUREZAS[int(cod) - 1]
    e = esfera_curta(r.get("DS_ESFERA_ADMINISTRATIVA"))
    return "Pública" if e in ("Municipal", "Estadual", "Federal") else ("Privada com fins lucrativos" if e == "Privada" else "Outra")

def nome_curto(t):
    t = " ".join(str(t or "").split()).title()
    return t[:80]

def inativo(motivo):
    return motivo not in (None, "", "0", 0, "00")

def cod6(v):
    s = re.sub(r"\D", "", str(v or ""))
    return s[:6] if len(s) >= 6 else None

def iter_registros(fluxo, tamanho=4_000_000):
    """Itera objetos de um JSON grande (lista de objetos simples) sem carregar o arquivo inteiro."""
    buf, comeco = "", False
    while True:
        bloco = fluxo.read(tamanho)
        if not bloco:
            break
        buf += bloco.decode("utf-8", "replace") if isinstance(bloco, bytes) else bloco
        if not comeco:
            i = buf.find("[")
            if i < 0:
                buf = buf[-100:]
                continue
            buf, comeco = buf[i + 1:], True
        partes = SEP.split(buf)
        buf = partes.pop()
        for p in partes:
            yield "{" + p.lstrip("{") + "}"
    fim = buf.rsplit("]", 1)[0].strip().rstrip(",").strip()
    if fim:
        yield fim if fim.startswith("{") else "{" + fim

def agregar(textos, mapa6, hosp=None):
    """textos: iteravel de JSON em texto. mapa6: codigo de 6 digitos -> (cod7, uf). Devolve (por_municipio, lidos, erros, sem_municipio).
    hosp: lista opcional que recebe os hospitais ativos (pessoas juridicas) como [cnes, nome, cod7, uf, tipo, natureza, atende_sus]."""
    por, lidos, erros, sem = {}, 0, 0, 0
    for t in textos:
        try:
            r = json.loads(t)
        except ValueError:
            erros += 1
            continue
        lidos += 1
        alvo = mapa6.get(cod6(r.get("CO_IBGE")))
        if not alvo:
            sem += 1
            continue
        d = por.setdefault(alvo[0], {"uf": alvo[1], "total": 0, "ativos": 0, "tipos": {}, "grupos": {}, "esfera": {}, "nat": {}, "gn": {}})
        d["total"] += 1
        if not inativo(r.get("CO_MOTIVO_DESAB")):
            d["ativos"] += 1
            tp = str(r.get("TP_UNIDADE") or "").zfill(2)
            d["tipos"][tp] = d["tipos"].get(tp, 0) + 1
            g = GRUPOS.get(tp, "Outros tipos")
            d["grupos"][g] = d["grupos"].get(g, 0) + 1
            e = esfera_curta(r.get("DS_ESFERA_ADMINISTRATIVA"))
            d["esfera"][e] = d["esfera"].get(e, 0) + 1
            n = natureza(r)
            d["nat"][n] = d["nat"].get(n, 0) + 1
            gg = d["gn"].setdefault(g, {})
            gg[n] = gg.get(n, 0) + 1
            if hosp is not None and tp in HOSPITAIS and n != "Pessoa física":
                hosp.append([str(r.get("CO_CNES") or "").strip(), nome_curto(r.get("NO_FANTASIA") or r.get("NO_RAZAO_SOCIAL")), alvo[0], alvo[1], tp, n, str(r.get("CO_AMBULATORIAL_SUS") or "").strip() == "1"])
    return por, lidos, erros, sem

def main():
    terr = ler_json("dados/territorio.json")
    mapa6 = {m["cod"][:6]: (m["cod"], m["uf"]) for m in terr["municipios"]}
    arq = os.environ.get("CNES_ZIP_LOCAL")
    if arq:
        fonte = open(arq, "rb")
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        resp = urllib.request.urlopen(req, timeout=300)
        fonte = io.BytesIO(resp.read())
    with zipfile.ZipFile(fonte) as z:
        info = z.infolist()[0]
        with z.open(info) as fh:
            hosp = []
            por, lidos, erros, sem = agregar(iter_registros(fh), mapa6, hosp)
    if lidos < 100_000 or erros / max(1, lidos) > 0.001:
        print(f"validacao falhou: lidos={lidos} erros={erros}")
        return 1
    ufs = {}
    for cod, d in por.items():
        ufs.setdefault(d["uf"], {})[cod] = d
    resumo = {"gerado_em": agora(), "fonte": "CNES, Dados Abertos do SUS (Ministerio da Saude)", "arquivo": info.filename,
              "estabelecimentos_lidos": lidos, "sem_municipio": sem, "ufs": {}}
    for uf, mun in sorted(ufs.items()):
        tot = {"total": 0, "ativos": 0, "grupos": {}, "esfera": {}, "nat": {}, "gn": {}}
        for d in mun.values():
            tot["total"] += d["total"]; tot["ativos"] += d["ativos"]
            for k in ("grupos", "esfera", "nat"):
                for n, v in d[k].items():
                    tot[k][n] = tot[k].get(n, 0) + v
            for g, o in d["gn"].items():
                for n, v in o.items():
                    a = tot["gn"].setdefault(g, {})
                    a[n] = a.get(n, 0) + v
        resumo["ufs"][uf] = tot
        escrever_json(f"dados/rede/{uf}.json", {"uf": uf, "gerado_em": resumo["gerado_em"], "m": {c: {k: d[k] for k in ("total", "ativos", "grupos", "esfera", "tipos", "nat", "gn")} for c, d in sorted(mun.items())}})
    resumo["naturezas"] = list(NATUREZAS)
    resumo["observacao_natureza"] = "Natureza juridica do CNES. A classe sem fins lucrativos inclui as entidades filantropicas, mas o CNES nao informa o CEBAS."
    escrever_json("dados/rede_resumo.json", resumo)
    por_uf = {}
    for h in sorted(hosp, key=lambda x: (x[3], x[2], x[1])):
        por_uf.setdefault(h[3], []).append([h[0], h[1], h[2], h[4], h[5], h[6]])
    for uf, lista in por_uf.items():
        escrever_json(f"dados/hospitais/{uf}.json", {"uf": uf, "gerado_em": resumo["gerado_em"], "campos": ["cnes", "nome", "cod_municipio", "tipo", "natureza", "atende_sus"], "h": lista})
    resumo_actions("Rede assistencial (CNES)", [f"Estabelecimentos lidos: {lidos}", f"Sem municipio identificado: {sem}", f"Erros de leitura: {erros}", f"UFs: {len(ufs)}"])
    print(f"lidos={lidos} sem_municipio={sem} erros={erros} ufs={len(ufs)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
