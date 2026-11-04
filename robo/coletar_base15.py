#!/usr/bin/env python3
"""Base de calculo dos 15% em saude (LC 141/2012, art. 6 e 7) por municipio, a partir da receita realizada no SICONFI (DCA Anexo I-C).
Fontes que entram na base: impostos municipais (IPTU, ITBI, ISS), IRRF (CF art. 158 I), cotas-partes de ITR, IPVA, ICMS e IPI-exportacao (art. 158 II a IV e 159 par. 3) e FPM (art. 159 I b).
NAO entram: transferencias do SUS, convenios, operacoes de credito, royalties. Esta coleta e preliminar: as contas sao reconhecidas pelo texto da descricao e precisam ser conferidas
(o diagnostico do primeiro municipio lista as contas e colunas encontradas). Dividas ativas, multas e juros dos impostos ficam fora ate conferencia.
O percentual realmente aplicado (recursos proprios) esta no SIOPS e nao nesta fonte. Saida: dados/base15.json."""
import os, re, sys, time, unicodedata, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from comum import baixar_json, escrever_json, ler_json, agora, resumo_actions, BRT

BASE = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca?"
TRABALHADORES = int(os.environ.get("TRABALHADORES", "6"))
# chave: (rotulo, base legal, expressao sobre a descricao sem acentos, em maiusculas)
FONTES = {
    "iptu": ("IPTU", "CF art. 156 I", r"PROPRIEDADE PREDIAL E TERRITORIAL URBANA|\bIPTU\b"),
    "itbi": ("ITBI", "CF art. 156 II", r"TRANSMISSAO .*BENS IMOVEIS|\bITBI\b"),
    "iss": ("ISS", "CF art. 156 III", r"SERVICOS DE QUALQUER NATUREZA|\bISS(QN)?\b"),
    "irrf": ("IRRF dos servidores e contratados", "CF art. 158 I", r"RETIDO NA FONTE|\bIRRF\b"),
    "itr": ("Cota-parte do ITR", "CF art. 158 II", r"TERRITORIAL RURAL|\bITR\b"),
    "ipva": ("Cota-parte do IPVA", "CF art. 158 III", r"COTA.?PARTE.*(\bIPVA\b|VEICULOS AUTOMOTORES)"),
    "icms": ("Cota-parte do ICMS", "CF art. 158 IV", r"COTA.?PARTE.*(\bICMS\b|CIRCULACAO DE MERCADORIAS)"),
    "ipi": ("Cota-parte do IPI exportação", "CF art. 159 par. 3", r"COTA.?PARTE.*(\bIPI\b|PRODUTOS INDUSTRIALIZADOS)|PRODUTOS INDUSTRIALIZADOS.*EXPORTA"),
    "fpm": ("Fundo de Participação dos Municípios (FPM)", "CF art. 159 I b", r"FUNDO DE PARTICIPACAO DOS MUNICIPIOS|\bFPM\b"),
}
ORDEM = list(FONTES)

def sem_acento(t):
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().upper()

def pedir_ente(cod, exercicio):
    itens, offset = [], 0
    while True:
        u = BASE + urllib.parse.urlencode(dict(an_exercicio=exercicio, no_anexo="DCA-Anexo I-C", id_ente=cod, offset=offset))
        obj = baixar_json(u, timeout=60, tentativas=4, pausa=3)
        itens += obj.get("items", [])
        if not obj.get("hasMore") or offset > 30000:
            return itens
        offset += obj.get("limit") or len(obj.get("items", [])) or 5000

def coluna_bruta(col):
    c = sem_acento(col)
    return "BRUTA" in c and "REALIZ" in c or c.strip() in ("RECEITAS REALIZADAS", "RECEITA REALIZADA")

def extrair(itens):
    """Devolve {chave: valor} com o MAIOR valor entre as contas que casam com cada fonte (a conta agregadora e maior que suas filhas), e as contas usadas."""
    achado, usadas = {}, {}
    for i in itens or []:
        if not coluna_bruta(i.get("coluna")):
            continue
        txt = sem_acento(f"{i.get('conta', '')}")
        try:
            v = float(i.get("valor"))
        except (TypeError, ValueError):
            continue
        for k, (_, _, rx) in FONTES.items():
            if re.search(rx, txt) and v >= achado.get(k, -1):
                achado[k] = v
                usadas[k] = str(i.get("cod_conta") or "") + " " + str(i.get("conta") or "")[:90]
    if not achado:
        return None, {}
    return {k: round(achado.get(k, 0)) for k in ORDEM}, usadas

def um(args):
    m, exercicio = args
    try:
        r, _ = extrair(pedir_ente(m["cod"], exercicio))
        return m, r, None
    except Exception as e:
        return m, None, type(e).__name__

def main():
    terr = ler_json("dados/territorio.json")
    muni = terr["municipios"]
    limite = int(os.environ.get("LIMITE", "0")) or None
    if limite:
        muni = muni[::max(1, len(muni) // limite)][:limite]
    exercicio = int(os.environ.get("EXERCICIO", "0")) or datetime.now(BRT).year - 1
    for tent in range(2):
        try:
            amostra = pedir_ente(muni[0]["cod"], exercicio)
            print("colunas:", sorted({str(i.get("coluna")) for i in amostra})[:12])
            _, usadas = extrair(amostra)
            for k in ORDEM:
                print("conta usada", k, "=>", usadas.get(k, "NAO ENCONTRADA"))
            break
        except Exception as e:
            print("diagnostico indisponivel:", type(e).__name__)
        break
    t0, res, falhas = time.time(), [], 0
    with ThreadPoolExecutor(max_workers=TRABALHADORES) as ex:
        for m, r, erro in ex.map(um, [(m, exercicio) for m in muni]):
            falhas += 1 if erro else 0
            res.append((m, r))
    entregaram = [(m, r) for m, r in res if r and sum(r.values()) > 0]
    if len(entregaram) < 0.5 * len(muni) and not limite:
        exercicio -= 1
        print(f"poucos municipios; tentando {exercicio}")
        res, falhas = [], 0
        with ThreadPoolExecutor(max_workers=TRABALHADORES) as ex:
            for m, r, erro in ex.map(um, [(m, exercicio) for m in muni]):
                falhas += 1 if erro else 0
                res.append((m, r))
        entregaram = [(m, r) for m, r in res if r and sum(r.values()) > 0]
    taxa = falhas / max(1, len(muni))
    print(f"exercicio={exercicio} municipios={len(muni)} com_base={len(entregaram)} falhas={falhas} ({taxa:.1%}) tempo={int(time.time() - t0)}s")
    if taxa > 0.05 or len(entregaram) < 0.5 * len(muni):
        print("validacao falhou")
        return 1
    mun = {m["cod"]: [r[k] for k in ORDEM] for m, r in entregaram}
    ufs = {}
    for m, r in entregaram:
        t = ufs.setdefault(m["uf"], [0] * len(ORDEM))
        for j, k in enumerate(ORDEM):
            t[j] += r[k]
    escrever_json("dados/base15.json", {"gerado_em": agora(), "fonte": "SICONFI, DCA Anexo I-C, receita bruta realizada (Tesouro Nacional)", "exercicio": exercicio,
        "ordem": ORDEM, "fontes": {k: {"rotulo": v[0], "base_legal": v[1]} for k, v in FONTES.items()}, "preliminar": True,
        "observacao": "Receitas que compõem a base de cálculo dos 15% (LC 141/2012, art. 6 e 7). Não inclui dívida ativa, multas e juros. Conferir as contas antes de decidir com base nestes valores.",
        "municipios_consultados": len(muni), "municipios_com_base": len(entregaram), "ufs": dict(sorted(ufs.items())), "mun": dict(sorted(mun.items()))})
    resumo_actions("Base de cálculo dos 15% (DCA I-C)", [f"Exercício: {exercicio}", f"Com base: {len(entregaram)} de {len(muni)}", f"Falhas: {falhas} ({taxa:.1%})"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
