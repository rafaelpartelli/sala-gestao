#!/usr/bin/env python3
"""Sondagem (rodada 6) da Sala de Gestao em Saude. Roda tudo de uma vez, em blocos independentes.

Blocos:
  1. CAUC (Tesouro Nacional, dados abertos): situacao de cada municipio nos itens de saude (5.2 e 3.2.4).
  2. Leitos SUS 2026: colunas e tamanho do arquivo atual.
  3. ANS: arquivos de cobertura de planos e de beneficiarios (formato e colunas).
  4. Emendas (CSV completo): quanto do valor tem UF e municipio, e que textos de localidade ficam sem UF.
  5. Transferencias da Uniao (CSV mensal): recorte municipal da funcao Saude e taxa de cruzamento com o IBGE.
  6. SISAB: dicionario dos indicadores (significado dos codigos de indicador).
  7. DCA (despesa em saude): tempo, falhas e taxa de entrega de 60 municipios em paralelo.
  8. Chikungunya e zika em municipios grandes, CONASEMS (rota de dados do Next.js), SIOPS (consulta TabNet),
     API de convenios (corpo do erro 400).

Guarda so status, tempos, contagens, nomes de campos, codigos e valores agregados publicos. Nenhum dado de pessoa,
nenhum nome de favorecido, nenhum segredo (a chave do Portal da Transparencia vem de variavel de ambiente)."""
import csv, io, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error, zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import unescape
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sondar_fontes import pedir, sondar, BRT, VITORIA, ANO, UA
from sondar_r3 import pagina, mes_anterior
from sondar_r4 import texto
from sondar_r5 import primeiro_arquivo_zip, cabecalho_csv, seguro, resumir_pedidos, p95
from comum import numero_br, sem_acento

TT = "https://www.tesourotransparente.gov.br/ckan"
CAUC_CSV = TT + "/dataset/72b5f371-0c35-4613-8076-c99c821a6410/resource/07af297a-5e59-494a-a88a-55ddfd2f4b01/download/relatorio-situacao-de-varios-entes---municipios---uf-todas---abrangencia-1.csv"
S3 = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/"
PT = "https://portaldatransparencia.gov.br"
SIGLAS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())

# ---------------------------------------------------------------- funcoes puras (testadas offline)

def classe_cauc(v):
    v = (v or "").strip()
    if v == "":
        return "vazio"
    if v == "!":
        return "pendente (!)"
    if v.lower() == "desabilitado":
        return "desabilitado"
    if re.fullmatch(r"\d{2}/\d{2}/\d{2,4}", v):
        return "data"
    return "outro"

def analisar_cauc(txt, itens=("5.2", "3.2.4", "3.2.2", "5.1"), nomes_es=("Vitória", "Montanha")):
    """Conta a situacao de cada item no CSV do CAUC. Devolve resumo nacional, por UF (item 5.2) e linhas de exemplo."""
    linhas = list(csv.reader(io.StringIO(txt), delimiter=";"))
    i = next((k for k, l in enumerate(linhas) if l and l[0].strip() == "UF"), None)
    if i is None:
        return {"erro": "cabecalho com 'UF' nao encontrado"}
    cab = [c.strip() for c in linhas[i]]
    idx = {c: j for j, c in enumerate(cab)}
    dados = [l for l in linhas[i + 1:] if len(l) >= len(cab) - 2 and l[0].strip() in SIGLAS]
    r = {"data_da_pesquisa": (linhas[0][0] if linhas and linhas[0] else None), "municipios": len(dados), "colunas": len(cab),
         "itens_presentes": [c for c in itens if c in idx], "situacao": {}, "datas_item_5_2": {}, "por_uf_5_2": {}, "exemplos": {}}
    for it in r["itens_presentes"]:
        c = {}
        for l in dados:
            k = classe_cauc(l[idx[it]])
            c[k] = c.get(k, 0) + 1
        r["situacao"][it] = c
    if "5.2" in idx:
        datas = {}
        for l in dados:
            uf, k = l[0].strip(), classe_cauc(l[idx["5.2"]])
            r["por_uf_5_2"].setdefault(uf, {})[k] = r["por_uf_5_2"].setdefault(uf, {}).get(k, 0) + 1
            if k == "data":
                datas[l[idx["5.2"]]] = datas.get(l[idx["5.2"]], 0) + 1
        r["datas_item_5_2"] = dict(sorted(datas.items(), key=lambda kv: -kv[1])[:5])
    for l in dados:
        if l[0].strip() == "ES" and l[idx.get("Nome do Ente Federado", 1)].strip() in nomes_es:
            r["exemplos"][l[idx["Nome do Ente Federado"]]] = {"ibge": l[idx["Código IBGE"]], "populacao": l[idx["População"]],
                                                              **{it: l[idx[it]] for it in r["itens_presentes"]}}
    return r

def lista_apache(html, base):
    """Nomes de arquivos de um indice Apache ('Index of ...'), sem os links de ordenacao."""
    saida = []
    for href in re.findall(r'href="([^"?]+)"', html):
        if href.startswith(("/", "http")) and "dadosabertos.ans.gov.br" not in href:
            continue
        if href.endswith("/") or href in ("../",):
            continue
        saida.append(urllib.parse.urljoin(base, unescape(href)))
    return saida

def resumir_emendas_csv(linhas, anos=("2025", "2026"), funcao="10"):
    """Agrega o CSV completo de emendas na funcao Saude: valor pago com e sem UF e municipio, e textos de localidade sem UF."""
    leitor = csv.reader(linhas, delimiter=";")
    cab = [c.strip() for c in next(leitor)]
    ix = {c: i for i, c in enumerate(cab)}
    chaves = ("Ano da Emenda", "Código Função", "Valor Pago", "UF", "Código Município IBGE", "Localidade de aplicação do recurso", "Tipo de Emenda")
    falta = [c for c in chaves if c not in ix]
    if falta:
        return {"erro": f"colunas ausentes: {falta}", "colunas": cab[:40]}
    out = {a: {"linhas": 0, "pago": 0.0, "pago_com_uf": 0.0, "pago_com_municipio": 0.0, "linhas_sem_uf": 0, "sem_uf_localidades": {}, "tipos": {}} for a in anos}
    lidas = 0
    for l in leitor:
        lidas += 1
        if len(l) < len(cab) or l[ix["Ano da Emenda"]].strip() not in out or l[ix["Código Função"]].strip() != funcao:
            continue
        o = out[l[ix["Ano da Emenda"]].strip()]
        v = numero_br(l[ix["Valor Pago"]])
        uf, mun = l[ix["UF"]].strip().upper(), l[ix["Código Município IBGE"]].strip()
        o["linhas"] += 1
        o["pago"] += v
        o["tipos"][l[ix["Tipo de Emenda"]].strip()[:45]] = o["tipos"].get(l[ix["Tipo de Emenda"]].strip()[:45], 0.0) + v
        if uf in SIGLAS:
            o["pago_com_uf"] += v
        else:
            o["linhas_sem_uf"] += 1
            loc = l[ix["Localidade de aplicação do recurso"]].strip()[:40]
            o["sem_uf_localidades"][loc] = o["sem_uf_localidades"].get(loc, 0.0) + v
        if re.fullmatch(r"\d{7}", mun):
            o["pago_com_municipio"] += v
    for a, o in out.items():
        o["pct_valor_com_uf"] = round(100 * o["pago_com_uf"] / o["pago"], 1) if o["pago"] else None
        o["pct_valor_com_municipio"] = round(100 * o["pago_com_municipio"] / o["pago"], 1) if o["pago"] else None
        for k in ("pago", "pago_com_uf", "pago_com_municipio"):
            o[k] = round(o[k])
        o["tipos"] = {k: round(v) for k, v in sorted(o["tipos"].items(), key=lambda kv: -kv[1])[:6]}
        o["sem_uf_localidades"] = {k: round(v) for k, v in sorted(o["sem_uf_localidades"].items(), key=lambda kv: -kv[1])[:8]}
    return {"linhas_lidas": lidas, "anos": out}

def resumir_transferencias_csv(linhas, nomes_ibge, funcao="10"):
    """Transferencias da Uniao na funcao Saude: por tipo, UF e taxa de cruzamento do municipio (nome+UF) com o IBGE."""
    leitor = csv.reader(linhas, delimiter=";")
    cab = [c.strip() for c in next(leitor)]
    ix = {c: i for i, c in enumerate(cab)}
    need = ("TIPO TRANSFERÊNCIA", "UF", "CÓDIGO MUNICÍPIO SIAFI", "NOME MUNICÍPIO", "CÓDIGO FUNÇÃO", "VALOR TRANSFERIDO", "TIPO FAVORECIDO")
    falta = [c for c in need if c not in ix]
    if falta:
        return {"erro": f"colunas ausentes: {falta}", "colunas": cab[:40]}
    tipos, ufs, muni, tfav = {}, {}, {}, {}
    total, lidas, saude = 0.0, 0, 0
    for l in leitor:
        lidas += 1
        if len(l) < len(cab) or l[ix["CÓDIGO FUNÇÃO"]].strip() != funcao:
            continue
        v = numero_br(l[ix["VALOR TRANSFERIDO"]])
        saude += 1
        total += v
        t = l[ix["TIPO TRANSFERÊNCIA"]].strip()[:50]
        tipos[t] = tipos.get(t, 0.0) + v
        uf = l[ix["UF"]].strip().upper()
        ufs[uf] = ufs.get(uf, 0.0) + v
        tf = l[ix["TIPO FAVORECIDO"]].strip()[:40]
        tfav[tf] = tfav.get(tf, 0.0) + v
        chave = (l[ix["CÓDIGO MUNICÍPIO SIAFI"]].strip(), uf, sem_acento(l[ix["NOME MUNICÍPIO"]]))
        muni[chave] = muni.get(chave, 0.0) + v
    com_mun = [k for k in muni if k[0] and k[2] and k[1] in SIGLAS]
    casou = [k for k in com_mun if (k[2], k[1]) in nomes_ibge]
    top = lambda d, n=8: {k: round(v) for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]}
    return {"linhas_lidas": lidas, "linhas_saude": saude, "total_saude": round(total), "por_tipo": top(tipos), "por_tipo_favorecido": top(tfav),
            "ufs_com_valor": len([u for u in ufs if u in SIGLAS]), "municipios_distintos": len(com_mun), "municipios_casados_com_ibge": len(casou),
            "pct_casados": round(100 * len(casou) / len(com_mun), 1) if com_mun else None,
            "nao_casados_amostra": sorted({f"{k[2]}-{k[1]}" for k in com_mun if k not in casou and (k[2], k[1]) not in nomes_ibge})[:8],
            "valor_com_municipio_pct": round(100 * sum(muni[k] for k in com_mun) / total, 1) if total else None}

def textos_xlsx(bytes_, n=140):
    """Textos de uma planilha .xlsx (strings compartilhadas) e nomes das abas, so com a biblioteca padrao."""
    with zipfile.ZipFile(io.BytesIO(bytes_)) as z:
        nomes = z.namelist()
        ss = z.read("xl/sharedStrings.xml").decode("utf-8", "replace") if "xl/sharedStrings.xml" in nomes else ""
        wb = z.read("xl/workbook.xml").decode("utf-8", "replace") if "xl/workbook.xml" in nomes else ""
    abas = re.findall(r'<sheet [^>]*name="([^"]+)"', wb)
    textos = [re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", t))).strip() for t in re.findall(r"<si>(.*?)</si>", ss, re.S)]
    return abas, [t[:160] for t in textos if t][:n]

def saude_do_dca(items):
    """Despesa paga na funcao '10 - Saude' de uma resposta do DCA (Anexo I-E). None se nao houver."""
    for i in items or []:
        if re.match(r"\s*10\s*-\s*sa[uú]de", str(i.get("conta", "")), re.I) and "paga" in str(i.get("coluna", "")).lower():
            return i.get("valor")
    return None

# ---------------------------------------------------------------- blocos

def baixar_zip_ou_csv(url, limite, headers=None, timeout=180):
    o = pedir(url, headers=headers, timeout=timeout, limite=limite)
    if "erro" in o:
        return None, o
    c = o["corpo"]
    return c, o

def bloco_cauc():
    F = []
    r = {"id": "cauc_csv", "nome": "CAUC municipios (Tesouro Transparente): situacao dos itens de saude", "url": CAUC_CSV}
    c, o = baixar_zip_ou_csv(CAUC_CSV, 12_000_000, headers={"Accept": "text/csv,*/*"})
    r["ms"], r["status"] = o["ms"], o.get("status")
    if c is None:
        r.update({"ok": False, "erro": o["erro"]})
    else:
        try:
            txt = c.decode("utf-8-sig")
        except UnicodeDecodeError:
            txt = c.decode("latin-1")
        r["bytes"] = len(c)
        r.update(analisar_cauc(txt))
        r["ok"] = r.get("municipios", 0) >= 5000 and "5.2" in r.get("itens_presentes", [])
    F.append(r)
    s = sondar("cauc_ckan", "Tesouro Transparente: API do catalogo (CAUC)", TT + "/api/3/action/package_show?id=72b5f371-0c35-4613-8076-c99c821a6410", timeout=45)
    o2 = s.pop("_obj", None)
    if isinstance(o2, dict) and isinstance(o2.get("result"), dict):
        s["recursos"] = [{"nome": (x.get("name") or "")[:70], "formato": x.get("format"), "atualizado": (x.get("last_modified") or x.get("metadata_modified") or "")[:10]}
                         for x in o2["result"].get("resources", [])][:8]
        s["atualizado_conjunto"] = (o2["result"].get("metadata_modified") or "")[:10]
    F.append(s)
    return F

def bloco_leitos():
    url = S3 + "Leitos_SUS/Leitos_csv_2026.zip"
    r = {"id": "leitos_2026", "nome": "Leitos SUS 2026 (zip): colunas e tamanho", "url": url}
    c, o = baixar_zip_ou_csv(url, 30_000_000)
    r["ms"], r["status"] = o["ms"], o.get("status")
    if c is None:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    with zipfile.ZipFile(io.BytesIO(c)) as z:
        r["arquivos_no_zip"] = [(i.filename, i.file_size) for i in z.infolist()][:6]
        nome = next((i.filename for i in z.infolist() if i.filename.lower().endswith(".csv")), None)
        if not nome:
            r.update({"ok": False, "erro": "sem csv dentro do zip"})
            return r
        with z.open(nome) as fh:
            ini = fh.read(300_000)
            n = ini.count(b"\n")
            while True:
                b = fh.read(4_000_000)
                if not b:
                    break
                n += b.count(b"\n")
    r.update(cabecalho_csv(ini, linhas=2))
    r["linhas"] = n
    r["ok"] = bool(r.get("colunas")) and len(r["colunas"]) > 5
    return r

def bloco_ans():
    F = []
    base = "https://dadosabertos.ans.gov.br/FTP/PDA/"
    for id_, pasta in (("ans_cobertura", "taxa_de_cobertura_de_planos_de_saude-047/"), ("ans_regiao", "dados_de_beneficiarios_por_regiao_geografica/"),
                       ("ans_consolidado", "informacoes_consolidadas_de_beneficiarios-024/")):
        url = base + pasta
        o = pedir(url, headers={"Accept": "text/html,*/*"}, timeout=45, limite=1_500_000)
        r = {"id": id_, "nome": f"ANS PDA: {pasta.rstrip('/')}", "url": url, "ms": o["ms"], "status": o.get("status")}
        if "erro" in o:
            r.update({"ok": False, "erro": o["erro"]})
            F.append(r)
            continue
        arqs = lista_apache(texto(o), url)
        r["arquivos"] = [a.split("/")[-1][:70] for a in arqs][-10:]
        r["total_arquivos"] = len(arqs)
        dados = [a for a in arqs if re.search(r"\.(csv|zip)$", a, re.I)]
        if dados:
            alvo = sorted(dados)[-1]
            r["lido"] = alvo.split("/")[-1]
            p = pedir(alvo, headers={"Range": "bytes=0-600000"}, timeout=90, limite=620_000)
            if "erro" not in p:
                z = primeiro_arquivo_zip(p["corpo"], max_saida=500_000) if alvo.lower().endswith(".zip") else {"nome": r["lido"], "bytes": p["corpo"]}
                if z and z["bytes"]:
                    r["arquivo"] = z["nome"]
                    r.update(cabecalho_csv(z["bytes"], linhas=2))
        r["ok"] = bool(r.get("colunas")) or bool(arqs)
        F.append(r)
    return F

def abrir_csv_zip(c, nome_contem=".csv", codificacao="latin-1"):
    z = zipfile.ZipFile(io.BytesIO(c))
    nome = next(i.filename for i in z.infolist() if nome_contem in i.filename.lower())
    return nome, io.TextIOWrapper(z.open(nome), encoding=codificacao, newline="")

def bloco_emendas_csv():
    r = {"id": "emendas_csv", "nome": "Emendas (CSV completo, funcao Saude): valor com UF e municipio"}
    for sufixo in ("UNICO", mes_anterior()):
        url = f"{PT}/download-de-dados/emendas-parlamentares/{sufixo}"
        c, o = baixar_zip_ou_csv(url, 120_000_000, timeout=300)
        r["url"], r["ms"], r["status"] = url, o["ms"], o.get("status")
        if c is not None:
            break
    if c is None:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    r["bytes_zip"] = len(c)
    nome, fh = abrir_csv_zip(c)
    r["arquivo"] = nome
    r.update(resumir_emendas_csv(fh))
    a = (r.get("anos") or {}).get(str(ANO)) or {}
    r["ok"] = bool(a.get("linhas"))
    return r

def nomes_ibge():
    with open("dados/territorio.json", encoding="utf-8") as fh:
        t = json.load(fh)
    return {(sem_acento(m["nome"]), m["uf"]) for m in t["municipios"]}

def bloco_transferencias():
    r = {"id": "transferencias_csv", "nome": "Transferencias da Uniao (CSV mensal): funcao Saude por municipio"}
    ym = mes_anterior()
    url = f"{PT}/download-de-dados/transferencias/{ym}"
    h = pedir(url, metodo="HEAD", timeout=60, limite=0)
    r["url"], r["tamanho_http"] = url, h.get("tamanho_http")
    if h.get("tamanho_http") and int(h["tamanho_http"]) > 150_000_000:
        r.update({"ok": None, "nota": "arquivo maior que 150 MB, nao baixado"})
        return r
    c, o = baixar_zip_ou_csv(url, 150_000_000, timeout=300)
    r["ms"], r["status"] = o["ms"], o.get("status")
    if c is None:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    r["bytes_zip"] = len(c)
    nome, fh = abrir_csv_zip(c)
    r["arquivo"] = nome
    try:
        nm = nomes_ibge()
    except Exception as e:
        r["aviso"] = f"sem territorio.json ({type(e).__name__}): cruzamento nao feito"
        nm = set()
    r.update(resumir_transferencias_csv(fh, nm))
    r["ok"] = bool(r.get("linhas_saude"))
    return r

def bloco_sisab_dicionario():
    url = S3 + "sisab/indicadores_desempenho/PDA_2024_2026_etapa_1__dicionario_de_dados_indicadores_desempenho.xlsx"
    r = {"id": "sisab_dicionario", "nome": "SISAB: dicionario dos indicadores (xlsx)", "url": url}
    c, o = baixar_zip_ou_csv(url, 2_000_000, timeout=60)
    r["ms"], r["status"] = o["ms"], o.get("status")
    if c is None:
        r.update({"ok": False, "erro": o["erro"]})
        return r
    abas, textos = textos_xlsx(c)
    r["abas"], r["textos"] = abas, textos
    r["ok"] = bool(textos)
    return r

def bloco_dca_escala():
    r = {"id": "dca_escala", "nome": "SICONFI DCA: 60 municipios em paralelo (tempo, falhas e entrega)"}
    try:
        with open("dados/territorio.json", encoding="utf-8") as fh:
            muni = json.load(fh)["municipios"]
    except Exception as e:
        r.update({"ok": None, "nota": f"sem territorio.json ({type(e).__name__})"})
        return r
    amostra = muni[::max(1, len(muni) // 60)][:60]
    base = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca?"

    def um(m):
        u = base + urllib.parse.urlencode(dict(an_exercicio=ANO - 1, no_anexo="DCA-Anexo I-E", id_ente=m["cod"]))
        t0 = time.time()
        o = pedir(u, timeout=60, limite=2_000_000)
        ms = int((time.time() - t0) * 1000)
        if "erro" in o:
            return (o.get("status") or 0, ms, None, m["uf"])
        try:
            its = json.loads(o["corpo"].decode("utf-8", "replace")).get("items", [])
        except ValueError:
            return (0, ms, None, m["uf"])
        return (200, ms, saude_do_dca(its) if its else "sem_entrega", m["uf"])

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        rs = list(ex.map(um, amostra))
    seg = max(time.time() - t0, 0.001)
    res = resumir_pedidos([(st, ms, None) for st, ms, _, _ in rs])
    entregaram = sum(1 for st, _, v, _ in rs if st == 200 and v not in (None, "sem_entrega"))
    sem = sum(1 for st, _, v, _ in rs if st == 200 and v == "sem_entrega")
    r.update(res)
    r.update({"com_despesa_saude": entregaram, "sem_entrega_dca": sem, "pct_entrega": round(100 * entregaram / len(rs), 1),
              "pedidos_por_segundo": round(len(rs) / seg, 2), "minutos_para_5570": round(5570 / (len(rs) / seg) / 60, 1)})
    r["ok"] = res["taxa_erro"] is not None and res["taxa_erro"] <= 0.05
    return r

def bloco_arboviroses_grandes():
    import coletar_dengue
    r = {"id": "arbo_grandes", "nome": "InfoDengue: chikungunya e zika em municipios grandes", "resultados": {}}
    for dz in ("chikungunya", "zika"):
        for nome, cod in (("Rio de Janeiro", "3304557"), ("Sao Paulo", "3550308"), ("Goiania", "5208707"), ("Belo Horizonte", "3106200"), ("Recife", "2611606")):
            u = coletar_dengue.URL.format(cod=cod, ano=ANO).replace("disease=dengue", f"disease={dz}")
            o = pedir(u, timeout=40)
            n = None
            if "erro" not in o:
                try:
                    reg = json.loads(o["corpo"].decode("utf-8", "replace"))
                    n = len(reg) if isinstance(reg, list) else None
                except ValueError:
                    n = "json invalido"
            r["resultados"][f"{dz} {nome}"] = n if "erro" not in o else o["erro"]
            time.sleep(0.3)
    r["ok"] = any(isinstance(v, int) and v > 0 for v in r["resultados"].values())
    return r

def bloco_conasems_next():
    r = {"id": "conasems_next", "nome": "CONASEMS: rota de dados do Next.js (_next/data)"}
    o = pedir("https://www.conasems.org.br/", headers={"Accept": "text/html,*/*"}, timeout=45, limite=2_000_000)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', texto(o), re.S)
    if not m:
        r.update({"ok": False, "erro": "sem __NEXT_DATA__"})
        return r
    nd = json.loads(m.group(1))
    bid = nd.get("buildId")
    r["build_id_presente"] = bool(bid)
    dados = (nd.get("props") or {}).get("pageProps", {}).get("data")
    r["data_tipo"] = type(dados).__name__
    r["data_chaves"] = list(dados.keys())[:20] if isinstance(dados, dict) else (len(dados) if isinstance(dados, list) else None)
    achados = []

    def varrer(x, prof=0):
        if prof > 6 or len(achados) >= 12:
            return
        if isinstance(x, dict):
            t = x.get("title") or x.get("titulo") or x.get("name")
            if isinstance(t, str) and re.search(r"nota t[eé]cnica|nota", t, re.I):
                achados.append({"titulo": t[:110], "slug": str(x.get("slug") or x.get("url") or "")[:80], "data": str(x.get("date") or x.get("publishedAt") or "")[:10]})
            for v in x.values():
                varrer(v, prof + 1)
        elif isinstance(x, list):
            for v in x[:60]:
                varrer(v, prof + 1)
    varrer(dados)
    r["notas_na_home"] = achados
    if bid:
        s = pedir(f"https://www.conasems.org.br/_next/data/{bid}/index.json", timeout=40, limite=3_000_000)
        r["rota_next_data"] = {"status": s.get("status"), "erro": s.get("erro")}
    r["ok"] = bool(bid)
    return r

def pedir_com_corpo(url, headers=None):
    """GET que devolve (status, inicio do corpo), mesmo em erro HTTP (para ler a mensagem da API)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status, resp.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(400).decode("utf-8", "replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {str(e)[:100]}"

def bloco_siops_e_convenios(chave):
    F = []
    for id_, n, url in (("siops_tabnet", "SIOPS: consulta de indicadores municipais (TabNet)", "https://siops-asp.datasus.gov.br/CGI/tabcgi.exe?SIOPS/serhist/municipio/mIndicadores.def"),
                        ("siops_tabnet_http", "SIOPS: consulta de indicadores municipais (HTTP)", "http://siops-asp.datasus.gov.br/CGI/deftohtm.exe?SIOPS/serhist/municipio/mIndicadores.def"),
                        ("siops_cons", "SIOPS: portal de consultas", "http://siops.datasus.gov.br/consleirespfiscal.php")):
        s = sondar(id_, n, url, timeout=60, limite=800_000, nota="procura de acesso aos indicadores do SIOPS")
        s.pop("_obj", None)
        F.append(s)
    if chave:
        ini, fim = "01/10/2026", "31/10/2026"
        c = {"id": "convenios_400", "nome": "API de convenios: variacoes do pedido e mensagem de erro", "variacoes": {}}
        for nome, q in (("so_pagina", {"pagina": 1}), ("datas", {"dataInicial": ini, "dataFinal": fim, "pagina": 1}),
                        ("datas_vigencia", {"dataVigenciaInicial": ini, "dataVigenciaFinal": fim, "pagina": 1}),
                        ("ultima_liberacao", {"dataUltimaLiberacaoInicial": ini, "dataUltimaLiberacaoFinal": fim, "pagina": 1})):
            st, corpo = pedir_com_corpo(f"{PT.replace('//', '//api.')}/api-de-dados/convenios?" + urllib.parse.urlencode(q), {"chave-api-dados": chave})
            c["variacoes"][nome] = {"status": st, "inicio": re.sub(r"\s+", " ", corpo)[:160]}
            time.sleep(1)
        c["ok"] = any(v["status"] == 200 for v in c["variacoes"].values())
        F.append(c)
    return F

# ---------------------------------------------------------------- execucao

def main():
    chave = os.environ.get("PORTAL_TRANSPARENCIA_KEY", "").strip()
    F = []
    for nome, fn, args in (
        ("cauc", bloco_cauc, ()), ("leitos_2026", bloco_leitos, ()), ("ans", bloco_ans, ()), ("sisab_dicionario", bloco_sisab_dicionario, ()),
        ("emendas_csv", bloco_emendas_csv, ()), ("transferencias_csv", bloco_transferencias, ()), ("dca_escala", bloco_dca_escala, ()),
        ("arbo_grandes", bloco_arboviroses_grandes, ()), ("conasems_next", bloco_conasems_next, ()), ("siops_convenios", bloco_siops_e_convenios, (chave,))):
        t0 = time.time()
        F += seguro(nome, fn, *args)
        print(f"[{int(time.time() - t0):>3}s] {nome}", flush=True)
    for f in F:
        f.pop("_obj", None)
        f.pop("_corpo", None)
    resumo = {"ok": sum(1 for f in F if f.get("ok") is True), "falha": sum(1 for f in F if f.get("ok") is False),
              "nao_testado": sum(1 for f in F if f.get("ok") is None)}
    saida = {"rodada": 6, "gerado_em": datetime.now(BRT).isoformat(timespec="seconds"),
             "ambiente": "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local", "resumo": resumo, "fontes": F}
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem_r6.json", "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=1)
    L = ["| Fonte | Resultado | Tempo | Observacao |", "|---|---|---|---|"]
    for f in F:
        res = "ok" if f.get("ok") else ("nao testado" if f.get("ok") is None else f"FALHA {f.get('erro', f.get('status', ''))}")
        obs = []
        for k, rot in (("municipios", "municipios"), ("linhas", "linhas"), ("pct_entrega", "% com despesa em saude"), ("pct_casados", "% casados com IBGE"), ("total_arquivos", "arquivos")):
            if f.get(k) is not None:
                obs.append(f"{f[k]} {rot}")
        if f.get("minutos_para_5570"):
            obs.append(f"{f['minutos_para_5570']} min para 5570")
        L.append(f"| {f.get('nome', f.get('id'))} | {res} | {f.get('ms', '')} ms | {'; '.join(obs)} |")
    md = "\n".join(L)
    print(md)
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        with open(s, "a", encoding="utf-8") as fh:
            fh.write("## Sondagem das fontes (rodada 6)\n\n" + md + "\n")
    print(f"\nok={resumo['ok']} falha={resumo['falha']} nao_testado={resumo['nao_testado']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
