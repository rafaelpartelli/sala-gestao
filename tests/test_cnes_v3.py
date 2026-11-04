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
        self.assertEqual(hosp[0][7], "Privada")


class TestRecursosEBase15(unittest.TestCase):
    def test_base15(self):
        import coletar_base15 as b
        itens = [{"coluna": "Receitas Brutas Realizadas", "conta": "Imposto sobre a Propriedade Predial e Territorial Urbana", "valor": "1000"},
                 {"coluna": "Receitas Brutas Realizadas", "conta": "IPTU - Pessoa Fisica", "valor": "400"},
                 {"coluna": "Receitas Liquidas", "conta": "Imposto sobre a Propriedade Predial e Territorial Urbana", "valor": "9999"},
                 {"coluna": "Receitas Brutas Realizadas", "conta": "Cota-Parte do Fundo de Participacao dos Municipios - Cota Mensal", "valor": "5000"},
                 {"coluna": "Receitas Brutas Realizadas", "conta": "Cota-Parte do ICMS", "valor": "3000"}]
        r, _ = b.extrair(itens)
        self.assertEqual((r["iptu"], r["fpm"], r["icms"], r["ipi"]), (1000, 5000, 3000, 0))

    def test_recursos(self):
        import coletar_recursos as cr
        mun = [{"cod": "3200102", "nome": "Afonso Cláudio", "uf": "ES"}, {"cod": "3200201", "nome": "Água Doce do Norte", "uf": "ES"}]
        dados = {"meta": {"anoEm": 2026}, "m": [{"n": "AFONSO CLAUDIO", "nm": "Afonso Cláudio", "fb": 100, "fl": 90, "fe": 10, "fm": 90, "s": 5, "comp": [[0, 0, 100]], "ano": [[2026, 50, 40, 30]], "prop": [[1]]}],
                 "EST": {"fb": 1000, "fl": 900, "fe": 100, "fm": 900, "s": 50, "comp": [], "ano": [[2026, 5, 4, 3]]}}
        obj, nao = cr.montar("ES", dados, mun)
        self.assertEqual(obj["m"]["3200102"]["em"], [50, 40, 30])
        self.assertEqual(obj["est"]["fm"], 900)
        self.assertEqual(nao, [])
