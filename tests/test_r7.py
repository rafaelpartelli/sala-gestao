import os, struct, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "robo"))
import sondar_r7 as r7


def dbf(registros, campos):
    cab = bytearray(32)
    cab[0] = 3
    tam_cab = 32 + 32 * len(campos) + 1
    tam_reg = 1 + sum(t for _, _, t in campos)
    cab[4:12] = struct.pack("<IHH", registros, tam_cab, tam_reg)
    out = bytes(cab)
    for nome, tipo, tam in campos:
        d = bytearray(32)
        d[0:len(nome)] = nome.encode()
        d[11] = ord(tipo)
        d[16] = tam
        out += bytes(d)
    return out + b"\r"


class TestR7(unittest.TestCase):
    def test_cabecalho_dbf(self):
        r = r7.cabecalho_dbf(dbf(1234, [("CNES", "C", 7), ("CBO", "C", 6), ("QT", "N", 3)]))
        self.assertEqual(r["registros"], 1234)
        self.assertEqual(r["n_campos"], 3)
        self.assertEqual(r["campos"][1], {"campo": "CBO", "tipo": "C", "tam": 6})
        self.assertTrue(r["cabecalho_completo"])

    def test_cabecalho_curto_e_truncado(self):
        self.assertIn("erro", r7.cabecalho_dbf(b"abc"))
        b = dbf(5, [("A", "C", 1), ("B", "C", 1)])[:50]
        self.assertFalse(r7.cabecalho_dbf(b)["cabecalho_completo"])

    def test_agrupar(self):
        nomes = ["/x/PFES2607.dbc", "/x/PFSP2608.dbc", "/x/PFES2608.dbc", "/x/leia.txt"]
        r = r7.agrupar_arquivos_cnes(nomes, "PF")
        self.assertEqual(r["competencia_mais_recente"], "2608")
        self.assertEqual(r["ufs"], ["ES", "SP"])
        self.assertEqual(r["n_competencias"], 2)
        self.assertEqual(r["padrao_reconhecido"], 3)

    def test_agrupar_sem_padrao(self):
        self.assertEqual(r7.agrupar_arquivos_cnes(["a.txt"], "EQ")["padrao_reconhecido"], 0)

    def test_agrupar_nao_confunde_prefixo(self):
        self.assertEqual(r7.agrupar_arquivos_cnes(["/x/EPES2608.dbc"], "EQ")["padrao_reconhecido"], 0)

    def test_iframes(self):
        h = '<title> ElastiCNES </title><iframe src="/kibana/app/x"></iframe><script src="a.js"></script><script src="b.js"></script>'
        r = r7.iframes_e_scripts(h)
        self.assertEqual(r["iframes"], ["/kibana/app/x"])
        self.assertEqual(r["scripts"], 2)
        self.assertEqual(r["titulo"], "ElastiCNES")
        self.assertEqual(r7.iframes_e_scripts(None)["scripts"], 0)


if __name__ == "__main__":
    unittest.main()
