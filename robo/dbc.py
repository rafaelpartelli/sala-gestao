"""Leitor de arquivos .dbc do DATASUS (dBase com registros comprimidos no formato PKWare DCL, o 'implode').
So biblioteca padrao. Porta para Python do algoritmo 'blast' de Mark Adler (zlib/contrib/blast), validada
contra o decodificador original em C nos testes (tests/test_dbc.py).

Estrutura do .dbc: cabecalho dBase sem compressao (tamanho em H = bytes 8 e 9), 4 bytes de CRC32 e,
em seguida, os registros comprimidos. O fluxo descomprimido sao os registros, um apos o outro."""
import struct

MAXBITS = 13
JANELA = 4096
BLOCO = 1 << 20   # tamanho dos blocos de saida (os testes reduzem)

LITLEN = bytes([11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8, 9, 7, 6, 7, 8, 7, 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12,
                6, 7, 22, 5, 7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7, 9, 8, 25, 11, 8, 11, 9, 12, 8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10,
                53, 8, 7, 24, 10, 27, 44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45, 44, 173])
LENLEN = bytes([2, 35, 36, 53, 38, 23])
DISTLEN = bytes([2, 20, 53, 230, 247, 151, 248])
BASE = (3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264)
EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8)


class ErroDBC(ValueError):
    pass


def _construir(rep):
    """Tabelas de decodificacao: para cada padrao de 13 bits (primeiro bit do fluxo no bit menos significativo)
    devolve o simbolo e o tamanho do codigo (0 = codigo invalido)."""
    comp = []
    for b in rep:
        comp += [b & 15] * ((b >> 4) + 1)
    cont = [0] * (MAXBITS + 1)
    for c in comp:
        cont[c] += 1
    offs = [0] * (MAXBITS + 2)
    for c in range(1, MAXBITS):
        offs[c + 1] = offs[c] + cont[c]
    simbolos = [0] * len(comp)
    for s, c in enumerate(comp):
        if c:
            simbolos[offs[c]] = s
            offs[c] += 1
    sym = [0] * (1 << MAXBITS)
    tam = [0] * (1 << MAXBITS)
    for p in range(1 << MAXBITS):
        code = first = index = 0
        for n in range(1, MAXBITS + 1):
            code |= ((p >> (n - 1)) & 1) ^ 1
            c = cont[n]
            if code < first + c:
                sym[p], tam[p] = simbolos[index + code - first], n
                break
            index += c
            first += c
            first <<= 1
            code <<= 1
    return sym, tam


_TABELAS = None


def _tabelas():
    global _TABELAS
    if _TABELAS is None:
        _TABELAS = (_construir(LITLEN), _construir(LENLEN), _construir(DISTLEN))
    return _TABELAS


def explodir(dados, inicio=0, bloco=1 << 20):
    """Descomprime um fluxo PKWare DCL a partir de dados[inicio:]. Gera blocos de bytes na ordem da saida."""
    (lit_sym, lit_tam), (len_sym, len_tam), (dist_sym, dist_tam) = _tabelas()
    n = len(dados)
    if n - inicio < 2:
        raise ErroDBC("fluxo curto demais")
    codificado, dic = dados[inicio], dados[inicio + 1]
    if codificado > 1:
        raise ErroDBC("cabecalho invalido (literais)")
    if dic < 4 or dic > 6:
        raise ErroDBC("cabecalho invalido (dicionario)")
    pos = inicio + 2
    bitbuf = 0
    bitcnt = 0
    out = bytearray()
    produzido = 0
    mascara = (1 << MAXBITS) - 1
    while True:
        while bitcnt < 56 and pos < n:
            bitbuf |= dados[pos] << bitcnt
            pos += 1
            bitcnt += 8
        if bitbuf & 1:                                   # comprimento e distancia
            bitbuf >>= 1
            bitcnt -= 1
            p = bitbuf & mascara
            t = len_tam[p]
            if not t:
                raise ErroDBC("codigo de comprimento invalido")
            s = len_sym[p]
            bitbuf >>= t
            bitcnt -= t
            ex = EXTRA[s]
            comp = BASE[s] + (bitbuf & ((1 << ex) - 1))
            bitbuf >>= ex
            bitcnt -= ex
            if comp == 519:
                break
            p = bitbuf & mascara
            t = dist_tam[p]
            if not t:
                raise ErroDBC("codigo de distancia invalido")
            baixos = 2 if comp == 2 else dic
            dist = (dist_sym[p] << baixos)
            bitbuf >>= t
            bitcnt -= t
            dist += bitbuf & ((1 << baixos) - 1)
            bitbuf >>= baixos
            bitcnt -= baixos
            dist += 1
            if dist > produzido:
                raise ErroDBC("distancia maior que o ja produzido")
            if bitcnt < 0:
                raise ErroDBC("fluxo truncado")
            ini = len(out) - dist
            if dist >= comp:
                out += out[ini:ini + comp]
            else:
                out += (out[ini:] * (comp // dist + 1))[:comp]
            produzido += comp
        else:                                            # literal
            bitbuf >>= 1
            bitcnt -= 1
            if codificado:
                p = bitbuf & mascara
                t = lit_tam[p]
                if not t:
                    raise ErroDBC("codigo de literal invalido")
                out.append(lit_sym[p])
            else:
                t = 8
                out.append(bitbuf & 255)
            bitbuf >>= t
            bitcnt -= t
            produzido += 1
            if bitcnt < 0:
                raise ErroDBC("fluxo truncado")
        if len(out) >= bloco + JANELA:
            corte = len(out) - JANELA
            yield bytes(out[:corte])
            del out[:corte]
    if bitcnt < 0:
        raise ErroDBC("fluxo truncado")
    if out:
        yield bytes(out)


def cabecalho(dados):
    """Cabecalho dBase (parte sem compressao): registros, tamanho do cabecalho, tamanho do registro e campos."""
    if len(dados) < 33:
        raise ErroDBC("arquivo curto demais")
    registros, tam_cab, tam_reg = struct.unpack("<IHH", dados[4:12])
    if tam_cab < 33 or tam_cab > len(dados):
        raise ErroDBC("tamanho de cabecalho implausivel")
    campos, pos, desloc = [], 32, 1
    while pos + 32 <= tam_cab and dados[pos] != 0x0D:
        nome = dados[pos:pos + 11].split(b"\x00")[0].decode("latin-1", "replace")
        tam = dados[pos + 16]
        campos.append((nome, chr(dados[pos + 11]), tam, desloc))
        desloc += tam
        pos += 32
    return {"registros": registros, "tam_cabecalho": tam_cab, "tam_registro": tam_reg, "campos": campos}


def registros(dados, campos_desejados=None):
    """Gera um dict por registro ativo, com so os campos pedidos (texto latin-1 sem espacos nas pontas).
    Registros marcados como apagados (primeiro byte '*') sao ignorados."""
    cab = cabecalho(dados)
    tam_reg = cab["tam_registro"]
    pos_campos = {nome: (desloc, desloc + tam) for nome, _, tam, desloc in cab["campos"]}
    if campos_desejados is None:
        campos_desejados = list(pos_campos)
    faltam = [c for c in campos_desejados if c not in pos_campos]
    if faltam:
        raise ErroDBC(f"campos ausentes: {faltam}")
    fatias = [(c, *pos_campos[c]) for c in campos_desejados]
    resto = b""
    lidos = 0
    for bloco in explodir(dados, cab["tam_cabecalho"] + 4, BLOCO):
        buf = resto + bloco
        total = len(buf) // tam_reg
        for i in range(total):
            base = i * tam_reg
            if buf[base] == 0x2A:
                continue
            yield {c: buf[base + a:base + b].decode("latin-1").strip() for c, a, b in fatias}
        lidos += total
        resto = buf[total * tam_reg:]
    if abs(lidos - cab["registros"]) > max(5, cab["registros"] // 1000):
        raise ErroDBC(f"registros lidos {lidos} diferem do cabecalho {cab['registros']}")
