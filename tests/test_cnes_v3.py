import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import coletar_equipamentos as ce
import coletar_rede as cr

class TestEquipamentosENatureza(unittest.TestCase):
    def test_equipamentos(self):
        regs = [{"CODUFMUN": "320530", "TIPEQUIP": "01", "CODEQUIP": "11", "QT_EXIST": "2", "QT_USO": "1", "IND_SUS": "1", "NAT_JUR": "1023"},
                {"CODUFMUN": "320530", "TIPEQUIP": "1", "CODEQUIP": "11", "QT_EXIST": "3", "QT_USO": "3", "IND_SUS": "0", "NAT_JUR": "2062"},
                {"CODUFMUN": "888888", "TIPEQUIP": "1", "CODEQUIP": "11", "QT_EXIST": "9", "QT_USO": "9", "IND_SUS": "1", "NAT_JUR": "3999"}]
        por, itens, nats, lidos, sem = ce.agregar(regs, {"320530": "3205309"})
        self.assertEqual(por["3205309"]["1"], [5, 4, 2])
        self.assertEqual(nats["Pública"]["1"], 2)
        self.assertEqual(nats["Privada com fins lucrativos"]["1"], 3)
        self.assertEqual((lidos, sem), (3, 1))

    def test_natureza_rede(self):
        self.assertEqual(cr.natureza({"CO_NATUREZA_JUR": "3999"}), "Privada sem fins lucrativos")
        self.assertEqual(cr.natureza({"CO_NATUREZA_JUR": "1244"}), "Pública")
        self.assertEqual(cr.natureza({"DS_ESFERA_ADMINISTRATIVA": "MUNICIPAL"}), "Pública")
        hosp = []
        reg = {"CO_IBGE": "3205309", "TP_UNIDADE": "5", "CO_MOTIVO_DESAB": "", "CO_NATUREZA_JUR": "3999", "NO_FANTASIA": "HOSPITAL SANTA CASA", "CO_CNES": "1", "DS_ESFERA_ADMINISTRATIVA": "PRIVADA", "CO_AMBULATORIAL_SUS": "1"}
        por, *_ = cr.agregar([json.dumps(reg)], {"320530": ("3205309", "ES")}, hosp)
        self.assertEqual(por["3205309"]["gn"]["Hospitais"], {"Privada sem fins lucrativos": 1})
        self.assertEqual(hosp[0][5], "Privada sem fins lucrativos")
