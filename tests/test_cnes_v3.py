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


class TestRecursosESiops(unittest.TestCase):
    def test_recursos(self):
        import coletar_recursos as cr
        mun = [{"cod": "3200102", "nome": "Afonso Cláudio", "uf": "ES"}, {"cod": "3200201", "nome": "Água Doce do Norte", "uf": "ES"}]
        dados = {"meta": {"anoEm": 2026}, "m": [{"n": "AFONSO CLAUDIO", "nm": "Afonso Cláudio", "fb": 100, "fl": 90, "fe": 10, "fm": 90, "s": 5, "comp": [[0, 0, 100]], "ano": [[2026, 50, 40, 30]], "prop": [[1]]}],
                 "EST": {"fb": 1000, "fl": 900, "fe": 100, "fm": 900, "s": 50, "comp": [], "ano": [[2026, 5, 4, 3]]}}
        obj, nao = cr.montar("ES", dados, mun)
        self.assertEqual(obj["m"]["3200102"]["em"], [50, 40, 30])
        self.assertEqual(obj["est"]["fm"], 900)
        self.assertEqual(nao, [])


class TestNomes(unittest.TestCase):
    def test_nomes(self):
        self.assertEqual(cr.nome_curto("HOSPITAL E MATERNIDADE SANTA ROSA LTDA"), "Hospital e Maternidade Santa Rosa LTDA")
        self.assertEqual(cr.nome_curto("HMS"), "HMS")
        self.assertEqual(cr.nome_estabelecimento({"NO_FANTASIA": "HEG", "NO_RAZAO_SOCIAL": "HOSPITAL ESPECIALIZADO GOIANIA S/A"}, "1"), "Hospital Especializado Goiania S/A")
        self.assertEqual(cr.nome_estabelecimento({"NO_FANTASIA": "SANTA CASA DE MISERICORDIA", "NO_RAZAO_SOCIAL": "IRMANDADE X"}, "1"), "Santa Casa de Misericordia")
        self.assertEqual(cr.nome_estabelecimento({"NO_FANTASIA": "", "NO_RAZAO_SOCIAL": ""}, "2569809"), "Estabelecimento CNES 2569809")


TEXTO_SIOPS = ("Afonso Cláudio RELATÓRIO RESUMIDO 5º Bimestre de 2025 Dados Homologados em 15/12/25 08:44:45 RECEITAS RESULTANTES "
    "RECEITA DE IMPOSTOS (I) 7.742.500,00 7.742.500,00 9.104.000,51 117,58 Receita Resultante do Imposto Predial e Territorial Urbano - IPTU 1.322.000,00 1.322.000,00 1.105.275,77 83,61 "
    "Cota-Parte FPM 44.500.001,00 44.500.001,00 36.970.620,40 83,08 "
    "RECEITA DE TRANSFERÊNCIAS CONSTITUCIONAIS E LEGAIS (II) 86.985.001,00 86.985.001,00 72.027.268,57 82,80 "
    "TOTAL DAS RECEITAS RESULTANTES DE IMPOSTOS E TRANFERÊNCIAS CONSTITUCIONAIS E LEGAIS - (III) = (I) + (II) 94.727.501,00 94.727.501,00 81.131.269,08 85,65 "
    "Total das Despesas com ASPS (XII) = (XI) 22.288.158,92 19.799.926,27 19.684.507,39 "
    "(=) VALOR APLICADO EM ASPS (XVI) = (XII - XIII - XIV - XV) 22.288.158,92 19.799.926,27 19.684.507,39 "
    "Despesa Mínima a ser Aplicada em ASPS (XVII) = (III) x 15% (LC 141/2012) 12.169.690,36 Despesa Mínima ... (Lei Orgânica Municipal) N/A "
    "PERCENTUAL DA RECEITA DE IMPOSTOS E TRANSFERÊNCIAS CONSTITUCIONAIS E LEGAIS APLICADO EM ASPS (XVI / III)*100 (mínimo de 15% conforme LC n° 141/2012 ou % da Lei Orgânica Municipal) 27,47 24,40 24,26 CONTROLE")

class TestSiops(unittest.TestCase):
    def test_ler(self):
        import coletar_siops as cs
        r = cs.ler(TEXTO_SIOPS)
        self.assertEqual((r["ano"], r["bim"], r["data"]), (2025, 5, "15/12/25"))
        self.assertEqual((r["iptu"], r["fpm"], r["base"], r["minimo"]), (1105276, 36970620, 81131269, 12169690))
        self.assertEqual(r["pct"], [27.47, 24.4, 24.26])
        self.assertEqual(len(cs.compacto(r)), len(cs.CAMPOS))

    def test_sem_dados(self):
        import coletar_siops as cs
        self.assertIsNone(cs.ler("pagina sem demonstrativo"))
