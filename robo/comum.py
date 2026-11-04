"""Funcoes comuns dos coletores da Sala de Gestao em Saude. Somente biblioteca padrao."""
import json, os, re, time, unicodedata, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))
UA = "SalaGestaoSaude/1.0 (coleta de dados publicos; contato: partelli.pro)"

def agora():
    return datetime.now(BRT).isoformat(timespec="seconds")

def baixar(url, headers=None, timeout=60, tentativas=3, pausa=3, limite=None):
    """GET com novas tentativas. Devolve bytes. Levanta a ultima excecao se todas falharem."""
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(limite) if limite else r.read()
        except Exception as e:
            ultimo = e
            if isinstance(e, urllib.error.HTTPError) and e.code in (400, 401, 403, 404):
                break
            time.sleep(pausa * (i + 1))
    raise ultimo

def baixar_json(url, **kw):
    return json.loads(baixar(url, **kw).decode("utf-8"))

def escrever_json(caminho, obj, indent=None):
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":") if indent is None else None, indent=indent)

def ler_json(caminho):
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)

def sem_acento(txt):
    n = unicodedata.normalize("NFD", str(txt or ""))
    return "".join(c for c in n if unicodedata.category(c) != "Mn").upper().strip()

def numero_br(v):
    """Converte '1.234,56', '1234,56', '1234.56' ou numero em float. Vazio vira 0."""
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0

def resumo_actions(titulo, linhas):
    """Escreve no resumo da execucao do GitHub Actions, quando existir."""
    arq = os.environ.get("GITHUB_STEP_SUMMARY")
    if arq:
        with open(arq, "a", encoding="utf-8") as fh:
            fh.write(f"## {titulo}\n\n" + "\n".join(f"- {l}" for l in linhas) + "\n")
