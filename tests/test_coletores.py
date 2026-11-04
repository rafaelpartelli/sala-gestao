import io, json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import comum, coletar_dengue as dg, coletar_rede as rd, coletar_emendas as em
import coletar_financiamento as fn, coletar_aps as ap, coletar_notas as nt

class Comum(unittest.TestCase):
    def test_numero_br(self):
        self.assertEqual(comum.numero_br("1.234,56"), 1234.56)
        self.assertEqual(comum.numero_br("1234,5"), 1234.5)
        self.assertEqual(comum.numero_br("1234.5"), 1234.5)
        self.assertEqual(comum.numero_br(None), 0.0)
        self.assertEqual(comum.numero_br(""), 0.0)
        self.assertEqual(comum.numero_br("abc"), 0.0)
    def test_sem_acento(self):
        self.assertEqual(comum.sem_acento(" Vitória - ES "), "VITORIA - ES")

class Dengue(unittest.TestCase):
    REG = [{"SE": 202543, "data_iniSE": 1, "nivel": 1, "casos": 3, "casos_est": 4.2, "p_inc100k": 5.55, "Rt": 0.912},
           {"SE": 202544, "data_iniSE": 2, "nivel": 2, "casos": 9, "casos_est": 10.4, "p_inc100k": 12.3, "Rt": 1.2}]
    def test_resumir_pega_ultima_semana(self):
        r = dg.resumir(self.REG)
        self.assertEqual((r["se"], r["nivel"], r["casos"], r["casos_est"]), (202544, 2, 9, 10))
        self.assertEqual(r["serie"], [4, 10])
    def test_resumir_vazio(self):
        self.assertIsNone(dg.resumir([]))
        self.assertIsNone(dg.resumir([{"x": 1}]))
    def test_resumir_serie_limita_8(self):
        reg = [{"SE": i, "data_iniSE": i, "nivel": 1, "casos": 1, "casos_est": i} for i in range(1, 20)]
        self.assertEqual(len(dg.resumir(reg)["serie"]), 8)
    def test_agregar_uf(self):
        a = dg.agregar_uf([("1", "A", {"nivel": 1, "casos_est": 5}), ("2", "B", {"nivel": 4, "casos_est": 7}), ("3", "C", None), ("4", "D", {"nivel": None})])
        self.assertEqual(a["niveis"], {"1": 1, "2": 0, "3": 0, "4": 1, "sem_dado": 2})
        self.assertEqual(a["casos_est_semana"], 12)

def _cnes(n, cod="320530", tp="02", esf="MUNICIPAL", desab=""):
    return {"CO_CNES": str(n), "CO_IBGE": cod, "TP_UNIDADE": tp, "DS_ESFERA_ADMINISTRATIVA": esf, "CO_MOTIVO_DESAB": desab, "NO_FANTASIA": "Posto {x}"}

class Rede(unittest.TestCase):
    MAPA = {"320530": ("3205309", "ES")}
    def _texto(self, regs, envelope=False):
        corpo = json.dumps(regs)
        return json.dumps({"estabelecimentos": regs}) if envelope else corpo
    def test_fluxo_em_blocos_pequenos(self):
        regs = [_cnes(i, tp="05" if i % 3 == 0 else "02") for i in range(500)]
        for env in (False, True):
            fluxo = io.BytesIO(self._texto(regs, env).encode())
            lidos = list(rd.iter_registros(fluxo, tamanho=97))
            self.assertEqual(len(lidos), 500, f"envelope={env}")
            self.assertEqual(json.loads(lidos[-1])["CO_CNES"], "499")
    def test_agregar_conta_ativos_tipos_esfera(self):
        regs = [_cnes(1, tp="05"), _cnes(2, tp="02", esf="PRIVADA"), _cnes(3, tp="02", desab="12"), _cnes(4, cod="999999")]
        por, lidos, erros, sem = rd.agregar([json.dumps(r) for r in regs], self.MAPA)
        d = por["3205309"]
        self.assertEqual((lidos, erros, sem), (4, 0, 1))
        self.assertEqual((d["total"], d["ativos"]), (3, 2))
        self.assertEqual(d["grupos"], {"Hospitais": 1, "Atencao basica": 1})
        self.assertEqual(d["esfera"], {"Municipal": 1, "Privada": 1})
    def test_json_invalido_conta_erro(self):
        por, lidos, erros, sem = rd.agregar(["{nao e json}", json.dumps(_cnes(1))], self.MAPA)
        self.assertEqual((lidos, erros), (1, 1))
    def test_cod6_e_inativo(self):
        self.assertEqual(rd.cod6("3205309"), "320530")
        self.assertEqual(rd.cod6("320530"), "320530")
        self.assertIsNone(rd.cod6("12"))
        self.assertFalse(rd.inativo("")); self.assertFalse(rd.inativo("0")); self.assertTrue(rd.inativo("07"))
    def test_esfera_curta(self):
        self.assertEqual(rd.esfera_curta("ESTADUAL"), "Estadual")
        self.assertEqual(rd.esfera_curta("PRIVADA"), "Privada")
        self.assertEqual(rd.esfera_curta(None), "Outra")

class Emendas(unittest.TestCase):
    SIG = {"ES", "SP"}; NOMES = {"ESPIRITO SANTO": "ES", "SAO PAULO": "SP"}
    def test_uf_do_local(self):
        f = lambda t: em.uf_do_local(t, self.NOMES, self.SIG)
        self.assertEqual(f("VITÓRIA - ES"), "ES")
        self.assertEqual(f("ESPÍRITO SANTO (UF)"), "ES")
        self.assertEqual(f("São Paulo (UF)"), "SP")
        self.assertIsNone(f("MULTIPLO"))
        self.assertIsNone(f("NACIONAL"))
    def test_agregar(self):
        regs = [{"localidadeDoGasto": "VITÓRIA - ES", "tipoEmenda": "Emenda Individual", "subfuncao": "Atenção Básica", "valorEmpenhado": "1.000,00", "valorLiquidado": "500,00", "valorPago": "250,50"},
                {"localidadeDoGasto": "MULTI", "tipoEmenda": "Emenda de Bancada", "subfuncao": "Atenção Básica", "valorEmpenhado": "10,00", "valorLiquidado": "0", "valorPago": "0"}]
        a = em.agregar(regs, self.NOMES, self.SIG)
        self.assertEqual(a["total"], {"empenhado": 1010.0, "liquidado": 500.0, "pago": 250.5, "n": 2})
        self.assertEqual(a["por_uf"]["ES"]["pago"], 250.5)
        self.assertEqual(a["por_uf"]["ND"]["n"], 1)
        self.assertEqual(a["por_subfuncao"]["Atenção Básica"]["n"], 2)

class Financiamento(unittest.TestCase):
    def _uf(self):
        return {c: 1 for c in fn.CAMPOS} | {"fb": 10, "mun": 5}
    def test_valido(self):
        obj = {"uf": {f"U{i:02d}": self._uf() for i in range(27)}}
        self.assertEqual(fn.validar_financiamento(obj), [])
    def test_numero_de_ufs_errado(self):
        self.assertTrue(fn.validar_financiamento({"uf": {"ES": self._uf()}}))
        self.assertTrue(fn.validar_financiamento({}))
    def test_campo_faltando_e_zero(self):
        obj = {"uf": {f"U{i:02d}": self._uf() for i in range(27)}}
        del obj["uf"]["U00"]["s"]; obj["uf"]["U01"]["fb"] = 0
        self.assertEqual(len(fn.validar_financiamento(obj)), 2)
    def test_portarias(self):
        self.assertTrue(fn.validar_portarias({"portarias": []}))
        self.assertEqual(fn.validar_portarias({"portarias": [{"titulo": "x"}]}), [])

class Aps(unittest.TestCase):
    def test_estrutura_ponto_e_virgula(self):
        cols, n, sep = ap.estrutura("a;b;c\n1;2;3\n4;5;6\n")
        self.assertEqual((cols, n, sep), (["a", "b", "c"], 2, ";"))
    def test_ler_zip_csv(self):
        import zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("leia.txt", "x")
            z.writestr("sisab_2024Q1.csv", "\ufeffa;b\n1;2\n")
        nome, txt = ap.ler_zip_csv(b.getvalue())
        self.assertEqual(nome, "sisab_2024Q1.csv")
        self.assertEqual(ap.estrutura(txt)[0], ["a", "b"])
        self.assertEqual(ap.ler_zip_csv(b"a;b\n1;2\n")[0], "(csv sem zip)")

    def test_url_do_sisab_e_zip(self):
        self.assertTrue(ap.BASE.endswith(".csv.zip"))

    def test_estrutura_virgula(self):
        cols, n, sep = ap.estrutura("a,b\n1,2\n")
        self.assertEqual((cols, n, sep), (["a", "b"], 1, ","))

class Notas(unittest.TestCase):
    def test_tema(self):
        self.assertEqual(nt.tema("Portaria altera o custeio da Atenção Primária"), "Atencao primaria")
        self.assertEqual(nt.tema("Nota sobre emendas parlamentares"), "Financiamento")
        self.assertEqual(nt.tema("Campanha de vacinação"), "Vigilancia")
        self.assertEqual(nt.tema("Assunto qualquer"), "Outros")
    def test_conass(self):
        i = nt.itens_conass([{"date": "2026-09-30T09:56:14", "link": "https://x/a", "title": {"rendered": "Conass Informa n. 191/2026 &#8211; Publicada"}}, {"date": "x", "title": {}}])
        self.assertEqual(len(i), 1)
        self.assertEqual(i[0]["data"], "2026-09-30")
        self.assertIn("191/2026", i[0]["titulo"])
    def test_ms(self):
        html = '<a href="/saude/notas-tecnicas/nota-tecnica-10">Nota técnica 10 sobre algo importante</a><a href="/x">Curto</a><a href="/saude/notas-tecnicas/nota-tecnica-10">Repetido nota técnica</a>'
        i = nt.itens_ms(html, "https://www.gov.br/saude/pt-br/centrais-de-conteudo/publicacoes/notas-tecnicas")
        self.assertEqual(len(i), 1)
        self.assertTrue(i[0]["link"].startswith("https://www.gov.br/"))

if __name__ == "__main__":
    unittest.main()
