import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import coletar_territorio as ct

def ente(cod, nome, uf, esfera, pop=1000, capital="0"):
    return {"cod_ibge": cod, "ente": nome, "uf": uf, "esfera": esfera, "populacao": pop, "capital": capital, "regiao": "SE"}

class T(unittest.TestCase):
    def test_separa_esferas_e_soma(self):
        itens = [ente("3205309", "Vitoria", "ES", "M", 360000, "1"), ente("3205200", "Vila Velha", "ES", "M", 500000),
                 ente("32", "Espirito Santo", "ES", "E"), ente("53", "Distrito Federal", "DF", "D"), ente("1", "Uniao", "BR", "U")]
        b = ct.montar(itens)
        self.assertEqual(len(b["municipios"]), 2)
        self.assertEqual(len(b["ufs"]), 2)
        self.assertEqual(b["por_uf"]["ES"]["pop_soma"], 860000)
        self.assertTrue(b["municipios"][1]["capital"])

    def test_sigla_da_uf_vem_dos_municipios(self):
        b = ct.montar([ente("3205309", "Vitoria", "ES", "M"), {"cod_ibge": "32", "ente": "Espirito Santo", "uf": "BR", "esfera": "E", "populacao": 1, "regiao": "SE"}])
        self.assertEqual(b["ufs"][0]["uf"], "ES")

    def test_ignora_codigo_invalido_e_duplicado(self):
        b = ct.montar([ente("320530", "Curto", "ES", "M"), ente("3205309", "A", "ES", "M"), ente("3205309", "A", "ES", "M")])
        self.assertEqual(len(b["municipios"]), 1)

    def test_alerta_quando_contagem_foge(self):
        b = ct.montar([ente("3205309", "Vitoria", "ES", "M")])
        self.assertEqual(len(b["alertas"]), 2)

    def test_populacao_ausente_nao_quebra(self):
        b = ct.montar([ente("3205309", "Vitoria", "ES", "M", None)])
        self.assertEqual(b["por_uf"]["ES"]["pop_soma"], 0)

if __name__ == "__main__":
    unittest.main()
