"""Codificador PKWare DCL minimo, usado so nos testes para gerar fluxos validos e conferir o leitor de .dbc.
Reaproveita as tabelas do leitor; a prova de que elas estao certas e o teste diferencial contra o blast.c original."""
import os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "robo"))
import dbc


def _inverso(sym, tam):
    inv = {}
    for p in range(1 << dbc.MAXBITS):
        if tam[p] and sym[p] not in inv:
            inv[sym[p]] = (p & ((1 << tam[p]) - 1), tam[p])
    return inv


class Codificador:
    def __init__(self, codificado=1, dic=6):
        (ls, lt), (ns, nt), (ds, dt) = dbc._tabelas()
        self.lit, self.len, self.dist = _inverso(ls, lt), _inverso(ns, nt), _inverso(ds, dt)
        self.codificado, self.dic = codificado, dic
        self.acc = self.n = 0

    def _p(self, valor, n):
        self.acc |= valor << self.n
        self.n += n

    def literal(self, b):
        self._p(0, 1)
        if self.codificado:
            c, n = self.lit[b]
            self._p(c, n)
        else:
            self._p(b, 8)

    def copia(self, comp, dist):
        self._p(1, 1)
        if comp == 2:
            s = 1
        else:
            s = max(i for i in range(16) if i != 1 and dbc.BASE[i] <= comp)
        c, n = self.len[s]
        self._p(c, n)
        self._p(comp - dbc.BASE[s], dbc.EXTRA[s])
        if comp == 519:
            return
        d = dist - 1
        baixos = 2 if comp == 2 else self.dic
        c, n = self.dist[d >> baixos]
        self._p(c, n)
        self._p(d & ((1 << baixos) - 1), baixos)

    def fim(self):
        self.copia(519, 0)
        nbytes = (self.n + 7) // 8
        return bytes([self.codificado, self.dic]) + self.acc.to_bytes(nbytes, "little")


def fluxo_aleatorio(semente, tamanho=3000, codificado=1, dic=6):
    """Devolve (fluxo comprimido, texto esperado)."""
    r = random.Random(semente)
    c = Codificador(codificado, dic)
    saida = bytearray()
    alfabeto = bytes(r.sample(range(256), r.choice([2, 4, 16, 200])))
    while len(saida) < tamanho:
        if len(saida) >= 1 and r.random() < 0.45:
            comp = r.choice([2, 3, 4, 5, 8, 9, 12, 20, 40, 100, 300, 518, r.randint(2, 518)])
            teto = min(len(saida), (64 << dic) if comp > 2 else 256)
            dist = r.randint(1, teto)
            c.copia(comp, dist)
            for _ in range(comp):
                saida.append(saida[-dist])
        else:
            b = alfabeto[r.randrange(len(alfabeto))]
            c.literal(b)
            saida.append(b)
    return c.fim(), bytes(saida)


def comprimir(dados, codificado=1, dic=6):
    """Compressao gulosa simples (literais e copias de 3 bytes ou mais) para montar .dbc de teste."""
    c = Codificador(codificado, dic)
    ultimo, i, janela = {}, 0, 64 << dic
    while i < len(dados):
        ch = bytes(dados[i:i + 3])
        j = ultimo.get(ch)
        melhor = 0
        if j is not None and i - j <= janela and len(ch) == 3:
            while i + melhor < len(dados) and melhor < 518 and dados[j + melhor] == dados[i + melhor]:
                melhor += 1
        if melhor >= 3:
            c.copia(melhor, i - j)
            for k in range(melhor):
                ultimo[bytes(dados[i + k:i + k + 3])] = i + k
            i += melhor
        else:
            c.literal(dados[i])
            ultimo[ch] = i
            i += 1
    return c.fim()


def montar_dbc(campos, registros):
    """campos: [(nome, tipo, tam)]; registros: lista de listas de textos. Devolve os bytes de um .dbc."""
    import struct
    tam_reg = 1 + sum(t for _, _, t in campos)
    tam_cab = 32 + 32 * len(campos) + 1
    cab = bytearray(32)
    cab[0] = 3
    cab[4:12] = struct.pack("<IHH", len(registros), tam_cab, tam_reg)
    for nome, tipo, tam in campos:
        d = bytearray(32)
        d[0:len(nome)] = nome.encode()
        d[11] = ord(tipo)
        d[16] = tam
        cab += d
    cab += b"\r"
    corpo = b"".join(b" " + b"".join(str(v).encode("latin-1").ljust(t)[:t] for v, (_, _, t) in zip(r, campos)) for r in registros) + b"\x1a"
    return bytes(cab) + b"\x00\x00\x00\x00" + comprimir(corpo)
