"""Testes offline dos coletores de receita (RREO) e pessoal (RGF). Valores de Vitoria/ES, exercicio 2025, conferidos na API do SICONFI em 09/11/2026."""
import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import coletar_receita as rec
import coletar_pessoal as pes
import siconfi_comum as sc

def rreo(cod, coluna, v):
    return {"cod_conta": cod, "coluna": coluna, "valor": v, "populacao": 322869}

ITENS_RREO = [
    rreo("ReceitasCorrentes", "Até o Bimestre (c)", 3541245790.24),
    rreo("ReceitasDeCapital", "Até o Bimestre (c)", 97512689.44),
    rreo("ReceitaTributaria", "Até o Bimestre (c)", 1451483083.94),
    rreo("Impostos", "Até o Bimestre (c)", 1365921203.04),
    rreo("TransferenciasCorrentes", "Até o Bimestre (c)", 1467803500.39),
    rreo("TransferenciasCorrentes", "No Bimestre (b)", 1.0),
    rreo("TotalReceitas", "Até o Bimestre (c)", 3786072168.87),
    rreo("TotalReceitas", "PREVISÃO ATUALIZADA (a)", 3900000000.0),
]

def rgf(cod, coluna, v):
    return {"cod_conta": cod, "coluna": coluna, "valor": v}

ITENS_RGF = [
    rgf("DespesaComPessoalBruta", "TOTAL (ÚLTIMOS 12 MESES) (a)", 1621358892.89),
    rgf("DespesaComPessoalTotal", "Valor", 1330838337.47),
    rgf("DespesaComPessoalTotal", "% sobre a RCL Ajustada", 41.17),
    rgf("ReceitaCorrenteLiquidaAjustada", "Valor", 3232371975.86),
    rgf("LimiteMaximoDespesaComPessoalTotal", "Valor", 1745480866.96),
    rgf("LimitePrudencialDespesaComPessoalTotal", "Valor", 1658206823.61),
    rgf("LimiteDeAlertaDespesaComPessoalTotal", "Valor", 1570932780.26),
]

class TesteReceita(unittest.TestCase):
    def test_extrai_campos_e_usa_total_v_quando_nao_ha_subtotal(self):
        r = dict(zip(rec.CAMPOS + ["populacao"], rec.extrair(ITENS_RREO)))
        self.assertEqual(r["total"], 3786072169)
        self.assertEqual(r["correntes"], 3541245790)
        self.assertEqual(r["impostos"], 1365921203)
        self.assertEqual(r["transf_correntes"], 1467803500)
        self.assertEqual(r["transf_uniao"], 0)
        self.assertEqual(r["populacao"], 322869)

    def test_ente_sem_demonstrativo_vira_none(self):
        self.assertIsNone(rec.extrair([]))
        self.assertIsNone(rec.extrair([rreo("ReceitasCorrentes", "No Bimestre (b)", 5.0)]))

    def test_nao_confunde_coluna_do_bimestre_com_acumulado(self):
        itens = [rreo("SubtotalDasReceitas", "No Bimestre (b)", 10.0), rreo("SubtotalDasReceitas", "Até o Bimestre (c)", 99.0)]
        self.assertEqual(rec.extrair(itens)[0], 99)

class TestePessoal(unittest.TestCase):
    def test_extrai_dtp_limites_e_percentual(self):
        r = dict(zip(pes.CAMPOS + ["populacao"], pes.extrair(ITENS_RGF)))
        self.assertEqual(r["dtp"], 1330838337)
        self.assertEqual(r["limite_maximo"], 1745480867)
        self.assertEqual(r["pct_rcl"], 41.17)

    def test_percentual_e_recalculado_sem_a_coluna(self):
        itens = [i for i in ITENS_RGF if not i["coluna"].startswith("%")]
        self.assertAlmostEqual(pes.extrair(itens)[6], 41.17, places=2)

    def test_faixas_da_lrf(self):
        r = pes.extrair(ITENS_RGF)
        self.assertEqual(pes.faixa(r), "ok")  # 76,2% do limite
        for dtp, esperado in ((0.90, "alerta"), (0.95, "prudencial"), (1.0, "prudencial"), (1.01, "excedido"), (0.89, "ok")):
            self.assertEqual(pes.faixa([dtp * 1000, 0, 1000]), esperado)
        self.assertIsNone(pes.faixa([5, 0, None]))

    def test_sem_dtp_ou_rcl_vira_none(self):
        self.assertIsNone(pes.extrair([]))
        self.assertIsNone(pes.extrair([rgf("DespesaComPessoalTotal", "Valor", 5.0)]))

    def test_tenta_semestral_quando_nao_ha_quadrimestral(self):
        chamadas = []
        def falso(endpoint, params):
            chamadas.append((params["in_periodicidade"], params["nr_periodo"]))
            return ITENS_RGF if params["in_periodicidade"] == "S" else []
        with mock.patch.object(pes, "pedir", falso):
            self.assertTrue(pes.pedir_ente(3205309, 2025))
        self.assertEqual(chamadas, [("Q", 3), ("S", 2)])

class TesteComum(unittest.TestCase):
    def test_ufs_padrao_e_brasil(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("UFS", None)
            self.assertEqual(sc.ufs_do_ambiente(), ["ES", "TO", "PA", "PE"])
        with mock.patch.dict(os.environ, {"UFS": "BR"}):
            self.assertEqual(len(sc.ufs_do_ambiente()), 27)
        with mock.patch.dict(os.environ, {"UFS": "XX"}):
            with self.assertRaises(ValueError):
                sc.ufs_do_ambiente()

    def test_estados_do_piloto_tem_codigo_ibge_correto(self):
        self.assertEqual([sc.UF_COD[u] for u in ("ES", "TO", "PA", "PE")], [32, 17, 15, 26])

    def test_paginacao_junta_paginas(self):
        paginas = iter([{"items": [1, 2], "hasMore": True, "limit": 2}, {"items": [3], "hasMore": False}])
        with mock.patch.object(sc, "baixar_json", lambda *a, **k: next(paginas)):
            self.assertEqual(sc.pedir("rreo", {}), [1, 2, 3])

class TesteFluxo(unittest.TestCase):
    def test_montar_entes_filtra_ufs_e_inclui_estados(self):
        terr = {"municipios": [{"cod": 3205309, "uf": "ES"}, {"cod": 3550308, "uf": "SP"}]}
        muni, est = rec.montar_entes(terr, ["ES"])
        self.assertEqual(muni, [{"cod": 3205309, "uf": "ES"}])
        self.assertEqual(est, [{"cod": 32, "uf": "ES"}])

if __name__ == "__main__":
    unittest.main()
