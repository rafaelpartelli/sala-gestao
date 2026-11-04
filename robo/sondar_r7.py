#!/usr/bin/env python3
"""Sondagem (rodada 7) da Sala de Gestao em Saude. Dois blocos independentes.

  1. ElastiCNES (elasticnes.saude.gov.br): o portal responde a partir do GitHub? Qual o enderecamento do painel
     embutido? A rota interna de dados exige login? Ha exportacao? (so status e nomes; nenhuma consulta de dados)
  2. FTP do DATASUS (CNES): pastas PF (profissionais) e EQ (equipes), competencia mais recente, UFs presentes,
     tamanho dos arquivos e o cabecalho dBase de cada DBC (nomes e tipos de campos, numero de registros).
     Le so os primeiros bytes de cada arquivo. Nenhum valor de registro e guardado.

Guarda so status, tempos, contagens e nomes de campos."""
import ftplib, json, os, re, struct, sys, time, urllib.request, urllib.error
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sondar_fontes import pedir, BRT, UA
from sondar_r5 import seguro

ELASTI = "https://elasticnes.saude.gov.br"
FTP_HOST = "ftp.datasus.gov.br"
FTP_CNES = "/dissemin/publicos/CNES/200508_/Dados"

# ---------------------------------------------------------------- funcoes puras (testadas offline)

def iframes_e_scripts(html):
    """Enderecos de iframes e quantidade de scripts na pagina inicial."""
    html = html or ""
    ifr = re.findall(r"<iframe[^>]+src=[\"']([^\"']+)[\"']", html, flags=re.I)
    scripts = re.findall(r"<script[^>]+src=[\"']([^\"']+)[\"']", html, flags=re.I)
    titulo = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
    return {"iframes": ifr[:10], "scripts": len(scripts), "titulo": (titulo.group(1).strip()[:80] if titulo else None)}

def cabecalho_dbf(b):
    """Le o cabecalho dBase (parte sem compressao de um DBC): registros, tamanho do cabecalho e campos (nome, tipo, tamanho)."""
    if not b or len(b) < 33:
        return {"erro": "poucos bytes"}
    versao = b[0]
    registros, tam_cab, tam_reg = struct.unpack("<IHH", b[4:12])
    campos = []
    pos = 32
    while pos + 32 <= len(b) and b[pos] != 0x0D:
        nome = b[pos:pos + 11].split(b"\x00")[0].decode("latin-1", "replace")
        campos.append({"campo": nome, "tipo": chr(b[pos + 11]), "tam": b[pos + 16]})
        pos += 32
    return {"versao_dbase": versao, "registros": registros, "tam_cabecalho": tam_cab, "tam_registro": tam_reg,
            "n_campos": len(campos), "campos": campos, "cabecalho_completo": pos < len(b) and b[pos] == 0x0D}

def agrupar_arquivos_cnes(nomes, prefixo):
    """De nomes como PFES2608.dbc devolve competencia mais recente (AAMM), UFs dessa competencia e total."""
    rx = re.compile(rf"^{prefixo}([A-Z]{{2}})(\d{{4}})\.dbc$", re.I)
    achados = []
    for n in nomes:
        m = rx.match(n.split("/")[-1])
        if m:
            achados.append((m.group(1).upper(), m.group(2)))
    if not achados:
        return {"total": len(nomes), "padrao_reconhecido": 0}
    ult = max(c for _, c in achados)
    ufs = sorted({u for u, c in achados if c == ult})
    competencias = sorted({c for _, c in achados})
    return {"total": len(nomes), "padrao_reconhecido": len(achados), "competencia_mais_recente": ult,
            "ufs_na_mais_recente": len(ufs), "ufs": ufs, "primeira_competencia": competencias[0], "n_competencias": len(competencias)}

# ---------------------------------------------------------------- bloco 1: ElastiCNES

def post_vazio(url):
    h = {"User-Agent": UA, "Content-Type": "application/json", "kbn-xsrf": "true", "Accept": "*/*"}
    t0 = time.time()
    o = {"url": url, "metodo": "POST (lote vazio)"}
    try:
        req = urllib.request.Request(url, data=b'{"batch":[]}', headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            o["status"] = r.status
            o["inicio"] = r.read(300).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        o["status"] = e.code
        o["inicio"] = e.read(300).decode("utf-8", "replace")
    except Exception as e:
        o["erro"] = f"{type(e).__name__}: {str(e)[:140]}"
    o["ms"] = int((time.time() - t0) * 1000)
    return o

def bloco_elasticnes():
    r = {"id": "elasticnes", "nome": "ElastiCNES a partir do GitHub", "testes": {}}
    home = pedir(ELASTI + "/profissionais", timeout=40)
    corpo = (home.pop("corpo", b"") or b"").decode("utf-8", "replace")
    r["testes"]["pagina_profissionais"] = {"status": home.get("status"), "erro": home.get("erro"), "tipo": home.get("tipo"), "ms": home.get("ms"),
                                           **iframes_e_scripts(corpo)}
    for nome, caminho in (("robots", "/robots.txt"), ("kibana_status", "/kibana/api/status"), ("kibana_dashboards", "/kibana/app/dashboards"),
                          ("kibana_reporting", "/kibana/api/reporting/jobs/list?page=0")):
        p = pedir(ELASTI + caminho, timeout=30)
        c = (p.pop("corpo", b"") or b"")[:200].decode("utf-8", "replace")
        r["testes"][nome] = {"status": p.get("status"), "erro": p.get("erro"), "tipo": p.get("tipo"), "ms": p.get("ms"),
                             "inicio": re.sub(r"\s+", " ", c)[:160]}
        time.sleep(1)
    r["testes"]["bsearch_lote_vazio"] = post_vazio(ELASTI + "/kibana/internal/bsearch")
    r["ok"] = bool(r["testes"]["pagina_profissionais"].get("status") == 200)
    r["nota"] = "so status; nenhuma consulta de dados foi feita no painel"
    return [r]

# ---------------------------------------------------------------- bloco 2: FTP CNES (PF e EQ)

def ler_inicio(f, caminho, n=16384):
    """Le so os primeiros n bytes de um arquivo no FTP e encerra a transferencia."""
    f.voidcmd("TYPE I")
    conn = f.transfercmd("RETR " + caminho)
    buf = b""
    try:
        while len(buf) < n:
            pedaco = conn.recv(min(4096, n - len(buf)))
            if not pedaco:
                break
            buf += pedaco
    finally:
        conn.close()
        try:
            f.voidresp()
        except Exception:
            pass
    return buf

def pasta_cnes(f, tipo):
    """Analisa uma pasta (PF, EQ...) do CNES no FTP."""
    caminho = f"{FTP_CNES}/{tipo}"
    item = {"pasta": caminho}
    try:
        nomes = f.nlst(caminho)
    except Exception as e:
        item["erro"] = f"nlst: {str(e)[:100]}"
        return item
    item.update(agrupar_arquivos_cnes(nomes, tipo))
    ult = item.get("competencia_mais_recente")
    if not ult:
        item["amostra_nomes"] = [n.split("/")[-1] for n in nomes[:5]]
        return item
    tam = {}
    for uf in ("ES", "SP", "MG"):
        arq = f"{caminho}/{tipo}{uf}{ult}.dbc"
        try:
            f.voidcmd("TYPE I")
            tam[uf] = f.size(arq)
        except Exception as e:
            tam[uf] = f"erro: {str(e)[:60]}"
    item["tamanho_bytes_ultima_competencia"] = tam
    soma = 0
    for uf in item.get("ufs", []):
        try:
            soma += f.size(f"{caminho}/{tipo}{uf}{ult}.dbc") or 0
        except Exception:
            pass
    item["tamanho_total_mb_ultima_competencia"] = round(soma / 1048576, 1)
    try:
        ini = ler_inicio(f, f"{caminho}/{tipo}ES{ult}.dbc")
        item["cabecalho_ES"] = cabecalho_dbf(ini)
    except Exception as e:
        item["cabecalho_ES"] = {"erro": f"{type(e).__name__}: {str(e)[:100]}"}
    return item

def bloco_ftp_cnes():
    r = {"id": "ftp_cnes_pf_eq", "nome": "DATASUS FTP: CNES profissionais (PF) e equipes (EQ)", "url": f"ftp://{FTP_HOST}{FTP_CNES}"}
    t0 = time.time()
    try:
        f = ftplib.FTP(FTP_HOST, timeout=60)
        f.login()
        try:
            r["subpastas_dados"] = sorted(n.split("/")[-1] for n in f.nlst(FTP_CNES))[:40]
        except Exception as e:
            r["subpastas_dados"] = f"erro: {str(e)[:80]}"
        r["pastas"] = {}
        for tipo in ("EQ", "PF", "EP"):
            try:
                r["pastas"][tipo] = pasta_cnes(f, tipo)
            except Exception as e:
                r["pastas"][tipo] = {"erro": f"{type(e).__name__}: {str(e)[:100]}"}
                try:
                    f.voidcmd("NOOP")
                except Exception:
                    f = ftplib.FTP(FTP_HOST, timeout=60)
                    f.login()
        try:
            f.quit()
        except Exception:
            pass
        r["ok"] = any(isinstance(v, dict) and v.get("padrao_reconhecido") for v in r["pastas"].values())
    except Exception as e:
        r["ok"] = False
        r["erro"] = f"{type(e).__name__}: {str(e)[:140]}"
    r["ms"] = int((time.time() - t0) * 1000)
    return [r]

# ---------------------------------------------------------------- execucao

def main():
    F = []
    for nome, fn in (("elasticnes", bloco_elasticnes), ("ftp_cnes_pf_eq", bloco_ftp_cnes)):
        t0 = time.time()
        F += seguro(nome, fn)
        print(f"[{int(time.time() - t0):>3}s] {nome}", flush=True)
    resumo = {"ok": sum(1 for f in F if f.get("ok") is True), "falha": sum(1 for f in F if f.get("ok") is False)}
    saida = {"rodada": 7, "gerado_em": datetime.now(BRT).isoformat(timespec="seconds"),
             "ambiente": "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local", "resumo": resumo, "fontes": F}
    os.makedirs("dados", exist_ok=True)
    with open("dados/sondagem_r7.json", "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=1)
    L = ["| Fonte | Resultado | Tempo |", "|---|---|---|"]
    for f in F:
        res = "ok" if f.get("ok") else f"FALHA {f.get('erro', '')}"
        L.append(f"| {f.get('nome', f.get('id'))} | {res} | {f.get('ms', '')} ms |")
    for f in F:
        for tipo, p in (f.get("pastas") or {}).items():
            L.append(f"| FTP {tipo} | competencia {p.get('competencia_mais_recente')}, {p.get('ufs_na_mais_recente')} UFs, "
                     f"{p.get('tamanho_total_mb_ultima_competencia')} MB, {(p.get('cabecalho_ES') or {}).get('n_campos')} campos | |")
    md = "\n".join(L)
    print(md)
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        with open(s, "a", encoding="utf-8") as fh:
            fh.write("## Sondagem das fontes (rodada 7)\n\n" + md + "\n")
    print(f"\nok={resumo['ok']} falha={resumo['falha']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
