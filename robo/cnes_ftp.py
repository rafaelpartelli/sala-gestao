"""Acesso ao FTP do DATASUS para os arquivos mensais do CNES (.dbc): descobre a competencia mais recente completa e baixa por UF."""
import ftplib, io, re, time
from comum import espera_para

HOST = "ftp.datasus.gov.br"
PASTA = "/dissemin/publicos/CNES/200508_/Dados"

def agrupar(nomes, prefixo):
    """De nomes como PFES2608.dbc devolve {competencia(AAMM): [UFs]}."""
    rx = re.compile(rf"^{prefixo}([A-Z]{{2}})(\d{{4}})\.dbc$", re.I)
    por = {}
    for n in nomes:
        m = rx.match(n.split("/")[-1])
        if m:
            por.setdefault(m.group(2), set()).add(m.group(1).upper())
    return por

def competencia_completa(por, minimo_ufs=27):
    """Competencia (AAMM) mais recente com todas as UFs. None se nenhuma."""
    ok = [c for c, ufs in por.items() if len(ufs) >= minimo_ufs]
    return max(ok) if ok else None

def conectar(tentativas=4, pausa=5):
    ultimo = None
    for i in range(tentativas):
        try:
            f = ftplib.FTP(HOST, timeout=120)
            f.login()
            return f
        except Exception as e:
            ultimo = e
            if i + 1 < tentativas:
                time.sleep(espera_para(e, i, pausa))
    raise ultimo

def listar(tipo):
    f = conectar()
    try:
        return f.nlst(f"{PASTA}/{tipo}")
    finally:
        try:
            f.quit()
        except Exception:
            pass

def baixar_arquivo(tipo, uf, comp, tentativas=4, pausa=5):
    """Baixa PF/EP/... da UF e competencia. Devolve bytes."""
    caminho = f"{PASTA}/{tipo}/{tipo}{uf}{comp}.dbc"
    ultimo = None
    for i in range(tentativas):
        f = None
        try:
            f = conectar()
            buf = io.BytesIO()
            f.voidcmd("TYPE I")
            f.retrbinary("RETR " + caminho, buf.write, blocksize=1 << 16)
            return buf.getvalue()
        except Exception as e:
            ultimo = e
            if i + 1 < tentativas:
                time.sleep(espera_para(e, i, pausa))
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass
    raise ultimo
