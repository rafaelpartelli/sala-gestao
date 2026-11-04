import io, os, sys, unittest, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import sondar_r6 as r6

CAUC = ('"Data da Pesquisa: 30/10/2026"\n"Tipo de Ente: Municípios"\n"Abrangência: CNPJ principal dos Entes Federados"\n'
        '"UF";"Nome do Ente Federado";"Código IBGE";"Código SIAFI";"Região";"População";"Fonte";"3.2.4";"5.1";"5.2"\n'
        '"AC";"Acrelândia";"1200013";"0643";"N";"12538";;"!";"30/10/26";"Desabilitado"\n'
        '"ES";"Vitória";"3205309";"5705";"SE";"322869";;"30/11/26";"30/10/26";"30/10/26"\n'
        '"ES";"Montanha";"3203304";"5701";"SE";"18000";;"!";"";"!"\n'
        '"ES";"Serra";"3205002";"5703";"SE";"520000";;"30/11/26";"30/10/26";"30/10/26"\n')


class Cauc(unittest.TestCase):
    def test_classe(self):
        self.assertEqual([r6.classe_cauc(x) for x in ("", "!", "Desabilitado", "30/10/26", "30/10/2026", "x")],
                         ["vazio", "pendente (!)", "desabilitado", "data", "data", "outro"])

    def test_analisar(self):
        r = r6.analisar_cauc(CAUC)
        self.assertEqual((r["municipios"], r["colunas"]), (4, 10))
        self.assertEqual(r["data_da_pesquisa"], "Data da Pesquisa: 30/10/2026")
        self.assertEqual(r["situacao"]["5.2"], {"desabilitado": 1, "data": 2, "pendente (!)": 1})
        self.assertEqual(r["situacao"]["3.2.4"]["data"], 2)
        self.assertEqual(r["por_uf_5_2"]["ES"], {"data": 2, "pendente (!)": 1})
        self.assertEqual(r["datas_item_5_2"], {"30/10/26": 2})
        self.assertEqual(set(r["exemplos"]), {"Vitória", "Montanha"})
        self.assertEqual(r["exemplos"]["Montanha"]["5.2"], "!")

    def test_sem_cabecalho(self):
        self.assertIn("erro", r6.analisar_cauc("a;b\n1;2\n"))


class Apache(unittest.TestCase):
    def test_lista(self):
        html = ('<a href="?C=N;O=D">Name</a><a href="/FTP/PDA/">Parent Directory</a><a href="sub/">sub/</a>'
                '<a href="tx_2025.zip">x</a><a href="tx_2026.csv">y</a>')
        self.assertEqual(r6.lista_apache(html, "https://d.ans.gov.br/FTP/PDA/x/"),
                         ["https://d.ans.gov.br/FTP/PDA/x/tx_2025.zip", "https://d.ans.gov.br/FTP/PDA/x/tx_2026.csv"])


EM = ("Código da Emenda;Ano da Emenda;Tipo de Emenda;Localidade de aplicação do recurso;Código Município IBGE;UF;Código Função;Valor Pago\n"
      "1;2026;Individual;VITÓRIA - ES;3205309;ES;10;1.000,00\n"
      "2;2026;Individual;Nacional;;;10;9.000,00\n"
      "3;2026;Bancada;ESPÍRITO SANTO (UF);;ES;10;500,00\n"
      "4;2026;Individual;Nacional;;;12;7.000,00\n"
      "5;2025;Individual;Nacional;;Sem informação;10;100,00\n")


class Emendas(unittest.TestCase):
    def test_resumo(self):
        r = r6.resumir_emendas_csv(io.StringIO(EM))
        a = r["anos"]["2026"]
        self.assertEqual((a["linhas"], a["pago"], a["pago_com_uf"], a["pago_com_municipio"]), (3, 10500, 1500, 1000))
        self.assertEqual(a["pct_valor_com_uf"], 14.3)
        self.assertEqual(a["sem_uf_localidades"], {"Nacional": 9000})
        self.assertEqual(r["anos"]["2025"]["linhas_sem_uf"], 1)

    def test_colunas_ausentes(self):
        self.assertIn("erro", r6.resumir_emendas_csv(io.StringIO("a;b\n1;2\n")))


TR = ("TIPO TRANSFERÊNCIA;TIPO FAVORECIDO;UF;CÓDIGO MUNICÍPIO SIAFI;NOME MUNICÍPIO;CÓDIGO FUNÇÃO;VALOR TRANSFERIDO\n"
      "Fundo a Fundo;Fundo;ES;5705;VITÓRIA;10;1.000,00\n"
      "Fundo a Fundo;Fundo;ES;5701;MONTANHA;10;500,00\n"
      "Fundo a Fundo;Fundo;ES;9999;CIDADE NOVA;10;100,00\n"
      "Convênio;Prefeitura;ES;5705;VITÓRIA;12;5.000,00\n")


class Transf(unittest.TestCase):
    def test_resumo(self):
        r = r6.resumir_transferencias_csv(io.StringIO(TR), {("VITORIA", "ES"), ("MONTANHA", "ES")})
        self.assertEqual((r["linhas_saude"], r["total_saude"], r["municipios_distintos"], r["municipios_casados_com_ibge"]), (3, 1600, 3, 2))
        self.assertEqual(r["pct_casados"], 66.7)
        self.assertEqual(r["nao_casados_amostra"], ["CIDADE NOVA-ES"])


class Xlsx(unittest.TestCase):
    def test_textos(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("xl/workbook.xml", '<workbook><sheets><sheet name="Dicionário" sheetId="1"/></sheets></workbook>')
            z.writestr("xl/sharedStrings.xml", "<sst><si><t>co_tipo_indicador</t></si><si><r><t>Indicador </t></r><r><t>1 &amp; 2</t></r></si></sst>")
        abas, t = r6.textos_xlsx(b.getvalue())
        self.assertEqual(abas, ["Dicionário"])
        self.assertEqual(t, ["co_tipo_indicador", "Indicador 1 & 2"])


class Dca(unittest.TestCase):
    def test_saude(self):
        its = [{"conta": "10 - Saúde", "coluna": "Despesas Empenhadas", "valor": 5}, {"conta": "10 - Saúde", "coluna": "Despesas Pagas", "valor": 3}]
        self.assertEqual(r6.saude_do_dca(its), 3)
        self.assertIsNone(r6.saude_do_dca([{"conta": "12 - Educação", "coluna": "Despesas Pagas", "valor": 1}]))
        self.assertIsNone(r6.saude_do_dca([]))


if __name__ == "__main__":
    unittest.main()
