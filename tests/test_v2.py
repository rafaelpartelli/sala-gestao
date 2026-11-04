import io, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "robo"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cnes_ftp, coletar_profissionais as pf, coletar_equipes as eq, coletar_cauc as cc, coletar_transferencias as tr
import coletar_leitos as lt, coletar_ans as an, coletar_despesa as dp, dbc
from dbc_codificador import montar_dbc
from datetime import datetime

MAPA6 = {"320530": "3205309", "320500": "3205002"}


class FTP(unittest.TestCase):
    def test_competencia_completa(self):
        ufs = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
        nomes = [f"/x/PF{u}2608.dbc" for u in ufs] + [f"/x/PF{u}2609.dbc" for u in ufs[:20]] + ["/x/leia.txt"]
        por = cnes_ftp.agrupar(nomes, "PF")
        self.assertEqual(cnes_ftp.competencia_completa(por), "2608")
        self.assertIsNone(cnes_ftp.competencia_completa(cnes_ftp.agrupar(nomes[27:], "PF")))

    def test_prefixo_nao_confunde(self):
        self.assertEqual(cnes_ftp.agrupar(["/x/EPES2608.dbc"], "EQ"), {})


class Profissionais(unittest.TestCase):
    def test_grupo_cbo(self):
        for cbo, g in (("225125", "Médicos"), ("223505", "Enfermeiros"), ("322205", "Técnicos e auxiliares de enfermagem"), ("515105", "Agentes comunitários de saúde"),
                       ("223293", "Cirurgiões-dentistas"), ("515120", "Outros"), ("", "Outros")):
            self.assertEqual(pf.grupo_cbo(cbo), g, cbo)

    def test_agregar_conta_vinculos_sus_e_horas(self):
        regs = [{"CODUFMUN": "320530", "CBO": "225125", "PROF_SUS": "1", "HORA_AMB": "20", "HORAOUTR": "0", "HORAHOSP": "10"},
                {"CODUFMUN": "320530", "CBO": "225125", "PROF_SUS": "0", "HORA_AMB": "10", "HORAOUTR": "", "HORAHOSP": "0"},
                {"CODUFMUN": "999999", "CBO": "225125", "PROF_SUS": "1", "HORA_AMB": "1", "HORAOUTR": "0", "HORAHOSP": "0"}]
        por, lidos, sem = pf.agregar(regs, MAPA6)
        self.assertEqual((lidos, sem), (3, 1))
        self.assertEqual(por["3205309"]["Médicos"], [2, 1, 40])
        self.assertEqual(por["3205309"]["Total"], [2, 1, 40])

    def test_arquivo_dbc_de_ponta_a_ponta(self):
        campos = [("CODUFMUN", "C", 6), ("CBO", "C", 6), ("PROF_SUS", "C", 1), ("HORA_AMB", "N", 3), ("HORAOUTR", "N", 3), ("HORAHOSP", "N", 3), ("NOMEPROF", "C", 60)]
        regs = [["320530", "225125", "1", 20, 0, 0, "NOME QUE NUNCA DEVE SAIR"]] * 50
        por, lidos, sem = pf.agregar(dbc.registros(montar_dbc(campos, regs), pf.CAMPOS), MAPA6)
        self.assertEqual(por["3205309"]["Total"], [50, 50, 1000])
        self.assertNotIn("NOMEPROF", pf.CAMPOS)

    def test_somar_uf(self):
        t = pf.somar_uf({"1": {"Médicos": [2, 1, 40]}, "2": {"Médicos": [1, 1, 20], "Total": [1, 1, 20]}})
        self.assertEqual(t["Médicos"], [3, 2, 60])


class Equipes(unittest.TestCase):
    def test_conta_distintas_ativas_por_tipo(self):
        regs = [{"CNES": "1", "CODUFMUN": "320530", "TIPO_EQP": "70", "IDEQUIPE": "0000000001", "ID_AREA": "", "DT_DESAT": ""},
                {"CNES": "1", "CODUFMUN": "320530", "TIPO_EQP": "70", "IDEQUIPE": "0000000001", "ID_AREA": "", "DT_DESAT": ""},   # repetida
                {"CNES": "1", "CODUFMUN": "320530", "TIPO_EQP": "71", "IDEQUIPE": "0000000002", "ID_AREA": "", "DT_DESAT": "      "},
                {"CNES": "1", "CODUFMUN": "320530", "TIPO_EQP": "70", "IDEQUIPE": "0000000003", "ID_AREA": "", "DT_DESAT": "202501"},  # desativada
                {"CNES": "9", "CODUFMUN": "320530", "TIPO_EQP": "76", "IDEQUIPE": "", "ID_AREA": "A1", "DT_DESAT": ""},
                {"CNES": "9", "CODUFMUN": "888888", "TIPO_EQP": "70", "IDEQUIPE": "5", "ID_AREA": "", "DT_DESAT": ""}]
        por, lidos, sem, inat = eq.agregar(regs, MAPA6)
        self.assertEqual(por, {"3205309": {"70": 1, "71": 1, "76": 1}})
        self.assertEqual((lidos, sem, inat), (6, 1, 1))


class Cauc(unittest.TestCase):
    TXT = ('"Data da Pesquisa: 30/10/2026"\n"Tipo de Ente: Municípios"\n"Abrangência: CNPJ principal dos Entes Federados"\n'
           '"UF";"Nome do Ente Federado";"Código IBGE";"Código SIAFI";"Região";"População";"Fonte";"1.1";"3.2.4";"5.2"\n'
           '"ES";"Vitória";"3205309";"5701";"SE";"350000";;"30/10/26";"!";"30/10/26"\n'
           '"ES";"Montanha";"3203700";"5619";"SE";"18000";;"!";"Desabilitado";"30/10/26"\n'
           '"XX";"Linha de rodape";"1";"1";"X";"1";;"";"";""\n')

    def test_interpretar(self):
        r = cc.interpretar(self.TXT)
        self.assertEqual((r["data_pesquisa"], r["municipios"], r["itens"]), ("2026-10-30", 2, ["1.1", "3.2.4", "5.2"]))
        self.assertEqual(r["pendencias"], {"3205309": ["3.2.4"], "3203700": ["1.1"]})
        self.assertEqual(r["siafi"]["5701"], "3205309")

    def test_resumir(self):
        nac, uf = cc.resumir(cc.interpretar(self.TXT))
        self.assertEqual(nac["3.2.4"], {"pendentes": 1, "pct": 50.0})
        self.assertEqual(uf["ES"], {"com_pendencia": 2, "municipios": 2})

    def test_sem_cabecalho(self):
        with self.assertRaises(ValueError):
            cc.interpretar("a;b\n1;2\n")


class Transferencias(unittest.TestCase):
    CSV = ('ANO;MÊS;UF;CÓDIGO MUNICÍPIO SIAFI;NOME MUNICÍPIO;CÓDIGO FUNÇÃO;VALOR TRANSFERIDO;TIPO FAVORECIDO\n'
           '2026;10;ES;5701;VITORIA;10;"1.000,50";Administração Pública\n'
           '2026;10;ES;5701;VITORIA;10;"500,00";Administração Pública\n'
           '2026;10;ES;5701;VITORIA;12;"9.999,00";Administração Pública\n'
           '2026;10;ES;0000;MUNICIPIO NOVO;10;"200,00";X\n'
           '2026;10;ES;;;10;"300,00";X\n')

    def test_agregar(self):
        mun, uf, sem, total, nao = tr.agregar(io.StringIO(self.CSV), {"5701": "3205309"}, {})
        self.assertEqual(mun, {"3205309": 1500.5})
        self.assertAlmostEqual(total, 2000.5)
        self.assertAlmostEqual(sem, 500.0)
        self.assertEqual(nao, {"MUNICIPIO NOVO-ES"})
        self.assertAlmostEqual(uf["ES"], 2000.5)

    def test_casa_por_nome_quando_siafi_nao_esta_no_mapa(self):
        mun, *_ = tr.agregar(io.StringIO(self.CSV), {}, {("VITORIA", "ES"): "3205309"})
        self.assertAlmostEqual(mun["3205309"], 1500.5)

    def test_colunas_ausentes(self):
        with self.assertRaises(ValueError):
            tr.agregar(io.StringIO("A;B\n1;2\n"), {}, {})

    def test_meses_candidatos(self):
        self.assertEqual(tr.meses_candidatos(datetime(2026, 1, 15), 3), ["202512", "202511", "202510"])


class Leitos(unittest.TestCase):
    CAB = '"COMP";"UF";"CO_IBGE";"NOME_ESTABELECIMENTO";"NU_TELEFONE";"NO_EMAIL";"LEITOS_EXISTENTES";"LEITOS_SUS";"UTI_TOTAL_EXIST";"UTI_TOTAL_SUS";"UTI_ADULTO_SUS";"UTI_PEDIATRICO_SUS";"UTI_NEONATAL_SUS"\n'

    def test_usa_so_a_competencia_mais_recente_e_soma(self):
        csv_ = (self.CAB + '"202601";"ES";"320530";"HOSPITAL A";"(27)1";"a@b";"10";"8";"2";"2";"1";"1";"0"\n'
                '"202602";"ES";"320530";"HOSPITAL A";"(27)1";"a@b";"12";"9";"2";"2";"1";"1";"0"\n'
                '"202602";"ES";"320530";"HOSPITAL B";"(27)2";"c@d";"5";"0";"0";"0";"0";"0";"0"\n'
                '"202602";"ES";"999999";"FORA";"";"";"7";"7";"0";"0";"0";"0";"0"\n')
        comp, mun, lidas, sem = lt.agregar(io.StringIO(csv_), MAPA6)
        self.assertEqual(comp, "202602")
        self.assertEqual(mun["3205309"], [2, 17, 9, 2, 2, 1, 1, 0])
        self.assertEqual((lidas, sem), (4, 1))

    def test_saida_nao_tem_dado_de_contato(self):
        self.assertEqual(lt.CAMPOS, ["EST", "EXIST", "SUS", "UTI_EXIST", "UTI_SUS", "UTI_AD_SUS", "UTI_PED_SUS", "UTI_NEO_SUS"])


class ANS(unittest.TestCase):
    CSV = ('"PERIODO";"CD_MUNICIPIO";"NM_MUNICIPIO";"CD_UF";"SG_UF";"CD_RM";"NM_RM";"SEXO";"FAIXA_ETARIA";"BENEF_ASSISTENCIA_MEDICA";"BENEF_EXCLUS_ODONTOLOGICO";"BENEF_TOTAL";"POPULACAO"\n'
           '"2025";"320530";"Vitória";"32";"ES";"0";"x";"FEMININO";"Até 1 ano";"10";"0";"10";"100"\n'
           '"2026";"320530";"Vitória";"32";"ES";"0";"x";"FEMININO";"Até 1 ano";"20";"0";"20";"100"\n'
           '"2026";"320530";"Vitória";"32";"ES";"0";"x";"MASCULINO";"1 a 4 anos";"30";"0";"30";"150"\n'
           '"2026";"320530";"Vitória";"32";"ES";"0";"x";"TOTAL";"Total";"999";"0";"999";"999"\n')

    def test_agregar_por_periodo_e_ignora_totais(self):
        por, sexos, faixas, totais = an.agregar(io.StringIO(self.CSV))
        self.assertEqual(por["2026"]["320530"], [50, 250])
        self.assertEqual(por["2025"]["320530"], [10, 100])
        self.assertEqual(totais, 1)
        self.assertIn("TOTAL", sexos)

    def test_colunas_ausentes(self):
        with self.assertRaises(ValueError):
            an.agregar(io.StringIO("A;B\n1;2\n"))


class Despesa(unittest.TestCase):
    ITENS = [{"conta": "10 - Saúde", "coluna": "Despesas Empenhadas", "valor": 1000.4, "populacao": "35000"},
             {"conta": "10 - Saúde", "coluna": "Despesas Liquidadas", "valor": 900},
             {"conta": "10 - Saúde", "coluna": "Despesas Pagas", "valor": 800.6},
             {"conta": "10.301 - Atenção Básica", "coluna": "Despesas Pagas", "valor": 1},
             {"conta": "10 - Saúde", "coluna": "Inscrição de Restos a Pagar Não Processados", "valor": 5}]

    def test_extrair(self):
        self.assertEqual(dp.extrair(self.ITENS), [1000, 900, 801, 35000])

    def test_sem_entrega(self):
        self.assertIsNone(dp.extrair([]))
        self.assertIsNone(dp.extrair([{"conta": "04 - Administração", "coluna": "Despesas Pagas", "valor": 1}]))


if __name__ == "__main__":
    unittest.main()
