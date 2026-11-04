import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "robo"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dbc
from dbc_codificador import fluxo_aleatorio, montar_dbc

# Vetor gerado pelo codificador e conferido com o blast.c original (zlib/contrib/blast): 'abcabcabc' com literais codificados.
class Explodir(unittest.TestCase):
    def test_fluxos_aleatorios_voltam_ao_texto_original(self):
        for semente in range(60):
            for cod in (0, 1):
                for dic in (4, 5, 6):
                    fluxo, esperado = fluxo_aleatorio(semente * 5 + dic + cod, tamanho=[40, 700, 5000][semente % 3], codificado=cod, dic=dic)
                    self.assertEqual(b"".join(dbc.explodir(fluxo, 0)), esperado, (semente, cod, dic))

    def test_blocos_pequenos_nao_alteram_a_saida(self):
        fluxo, esperado = fluxo_aleatorio(7, tamanho=20000)
        self.assertEqual(b"".join(dbc.explodir(fluxo, 0, bloco=500)), esperado)

    def test_fluxo_truncado_e_erro(self):
        fluxo, _ = fluxo_aleatorio(3, tamanho=4000)
        with self.assertRaises(dbc.ErroDBC):
            b"".join(dbc.explodir(fluxo[:len(fluxo) // 2], 0))

    def test_cabecalho_invalido(self):
        with self.assertRaises(dbc.ErroDBC):
            list(dbc.explodir(bytes([2, 6, 0, 0]), 0))
        with self.assertRaises(dbc.ErroDBC):
            list(dbc.explodir(bytes([0, 9, 0, 0]), 0))


class Leitura(unittest.TestCase):
    CAMPOS = [("CODUFMUN", "C", 6), ("CBO", "C", 6), ("HORA", "N", 3)]

    def test_registros_e_campos(self):
        regs = [["320530", "225125", 20], ["320530", "223505", 40], ["999999", "515105", 40]] * 200
        bruto = montar_dbc(self.CAMPOS, regs)
        cab = dbc.cabecalho(bruto)
        self.assertEqual((cab["registros"], cab["tam_registro"]), (600, 16))
        self.assertEqual([c[0] for c in cab["campos"]], ["CODUFMUN", "CBO", "HORA"])
        dbc.BLOCO = 700
        try:
            lidos = list(dbc.registros(bruto, ["CODUFMUN", "CBO", "HORA"]))
        finally:
            dbc.BLOCO = 1 << 20
        self.assertEqual(len(lidos), 600)
        self.assertEqual(lidos[1], {"CODUFMUN": "320530", "CBO": "223505", "HORA": "40"})

    def test_campo_inexistente(self):
        with self.assertRaises(dbc.ErroDBC):
            list(dbc.registros(montar_dbc(self.CAMPOS, [["1", "2", 3]]), ["NAO_EXISTE"]))

    def test_contagem_diferente_do_cabecalho_e_erro(self):
        bruto = bytearray(montar_dbc(self.CAMPOS, [["320530", "225125", 20]] * 3000))
        bruto[4:8] = (9999).to_bytes(4, "little")
        with self.assertRaises(dbc.ErroDBC):
            list(dbc.registros(bytes(bruto), ["CBO"]))


if __name__ == "__main__":
    unittest.main()
