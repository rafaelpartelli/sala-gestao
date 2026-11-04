import io, json, os, struct, sys, unittest, zlib
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import sondar_r5 as r5


def zip_local(nome, conteudo, metodo=8):
    corpo = zlib.compressobj(wbits=-15).compress(conteudo) if metodo == 8 else conteudo
    if metodo == 8:
        c = zlib.compressobj(wbits=-15)
        corpo = c.compress(conteudo) + c.flush()
    n = nome.encode()
    cab = b"PK\x03\x04" + struct.pack("<HHHHHIIIHH", 20, 0, metodo, 0, 0, 0, len(corpo), len(conteudo), len(n), 0)
    return cab + n + corpo


class Zip(unittest.TestCase):
    def test_zip_completo_e_truncado(self):
        conteudo = b"A;B;C\n" + b"".join(b"%d;%d;%d\n" % (i, i * 7919 % 10007, i * 104729 % 99991) for i in range(20000))
        z = zip_local("x.csv", conteudo)
        self.assertEqual(r5.primeiro_arquivo_zip(z)["bytes"], conteudo)
        corte = r5.primeiro_arquivo_zip(z[:len(z) // 2])
        self.assertTrue(corte["bytes"] and conteudo.startswith(corte["bytes"]))

    def test_zip_sem_compressao_e_invalido(self):
        self.assertEqual(r5.primeiro_arquivo_zip(zip_local("a.txt", b"ola", metodo=0))["bytes"], b"ola")
        self.assertIsNone(r5.primeiro_arquivo_zip(b"<html>"))
        self.assertIsNone(r5.primeiro_arquivo_zip(b""))


class Csv(unittest.TestCase):
    def test_cabecalho_descarta_ultima_linha_cortada(self):
        c = r5.cabecalho_csv("ano;municipio;valor\n2024;Vitória;10\n2024;Serra;20\n2024;Vi".encode("utf-8"), linhas=2)
        self.assertEqual(c["colunas"], ["ano", "municipio", "valor"])
        self.assertEqual(c["separador"], ";")
        self.assertEqual(len(c["amostra"]), 2)

    def test_latin1(self):
        c = r5.cabecalho_csv("nome,valor\nSão,1\nX,2\n".encode("latin-1"))
        self.assertEqual(c["codificacao"], "latin-1")

    def test_vazio(self):
        self.assertEqual(r5.cabecalho_csv(b""), {})


SPEC = {"paths": {
    "/api-de-dados/convenios": {"get": {"parameters": [
        {"name": "dataInicial", "in": "query", "required": True}, {"name": "dataFinal", "in": "query", "required": True},
        {"name": "pagina", "in": "query", "required": True}, {"name": "uf", "in": "query", "required": False}]}},
    "/api-de-dados/convenios/{id}": {"get": {"parameters": [{"name": "id", "in": "path", "required": True}]}},
    "/api-de-dados/bolsa": {"get": {"parameters": []}},
    "/api-de-dados/transferencias": {"post": {}}}}


class Spec(unittest.TestCase):
    def test_rotas_e_parametros(self):
        r = r5.params_openapi(SPEC, r"convenio|transferenc")
        self.assertEqual([x["path"] for x in r], ["/api-de-dados/convenios", "/api-de-dados/convenios/{id}"])
        self.assertTrue(any(p["name"] == "dataInicial" and p["required"] for p in r[0]["params"]))

    def test_montar_parametros(self):
        r = r5.params_openapi(SPEC, r"/convenios$")[0]
        q, faltam = r5.montar_parametros(r["params"], datetime(2026, 11, 4))
        self.assertEqual(q, {"dataInicial": "05/10/2026", "dataFinal": "04/11/2026", "pagina": 1})
        self.assertEqual(faltam, [])
        q2, f2 = r5.montar_parametros([{"name": "codigoMisterio", "in": "query", "required": True}], datetime(2026, 11, 4))
        self.assertEqual((q2, f2), ({}, ["codigoMisterio"]))


XML = ('<ListBucketResult><CommonPrefixes><Prefix>SIOPS/</Prefix></CommonPrefixes><CommonPrefixes><Prefix>CNES/</Prefix></CommonPrefixes>'
       '<Contents><Key>CNES/a.zip</Key><LastModified>2026-10-01T10:00:00.000Z</LastModified><ETag>"x"</ETag><Size>2048</Size></Contents></ListBucketResult>')


class S3(unittest.TestCase):
    def test_parse(self):
        pastas, arqs = r5.s3_parse(XML)
        self.assertEqual(pastas, ["SIOPS/", "CNES/"])
        self.assertEqual(arqs, [{"chave": "CNES/a.zip", "modificado": "2026-10-01", "bytes": 2048}])


class Cnes(unittest.TestCase):
    def test_analise(self):
        regs = [json.dumps({"CO_UF": "32", "CO_IBGE": "320530", "TP_UNIDADE": 5, "DS_TIPO_UNIDADE": "HOSPITAL GERAL",
                            "DS_ESFERA_ADMINISTRATIVA": "MUNICIPAL", "CO_MOTIVO_DESAB": ""}),
                json.dumps({"CO_UF": "32", "CO_IBGE": "3205309", "TP_UNIDADE": "01", "DS_TIPO_UNIDADE": "CENTRO DE SAUDE",
                            "DS_ESFERA_ADMINISTRATIVA": "ESTADUAL", "CO_MOTIVO_DESAB": "3"}), "{quebrado"]
        a = r5.analisar_cnes(regs)
        self.assertEqual((a["lidos"], a["erros_leitura"]), (2, 1))
        self.assertEqual(a["tipos_unidade"], {"05": 1, "01": 1})
        self.assertEqual(a["descricao_do_tipo"]["05"], {"DS_TIPO_UNIDADE": "HOSPITAL GERAL"})
        self.assertEqual(a["tamanho_co_ibge"], {6: 1, 7: 1})

    def test_leitor_real_da_v1_com_zip_truncado(self):
        import coletar_rede
        corpo = "[" + ",".join(json.dumps({"CO_IBGE": "320530", "TP_UNIDADE": "01", "I": i}) for i in range(3000)) + "]"
        z = zip_local("cnes.json", corpo.encode())
        saida = r5.primeiro_arquivo_zip(z[:len(z) * 2 // 3])["bytes"]
        textos = list(coletar_rede.iter_registros(io.BytesIO(saida), tamanho=1000))
        self.assertGreater(len(textos), 1000)
        self.assertEqual(r5.analisar_cnes(textos[:-1])["erros_leitura"], 0)


class Volume(unittest.TestCase):
    def test_resumir(self):
        r = r5.resumir_pedidos([(200, 100, None)] * 8 + [(429, 50, "30"), (0, 10, "Timeout")])
        self.assertEqual((r["pedidos"], r["ok"], r["taxa_erro"]), (10, 8, 0.2))
        self.assertEqual(r["retry_after"], ["30"])
        self.assertEqual(r["mediana_ms"], 100)


class Fundo(unittest.TestCase):
    def mk(self, **o):
        d = dict(mun=78, pop=4e6, fb=100.0, fbEst=20.0, s=50.0, sEst=10.0, ep=30.0, ee=20.0, eg=10.0, eq=3, nIdx=78)
        d.update(o)
        return d

    def test_hipoteses(self):
        ufs = {c: self.mk() for c in ["ES", "SP", "AC", "RJ", "MG", "BA", "PA", "PE", "TO", "GO", "MT", "MS", "PR", "SC", "RS", "AM", "AP", "RO", "RR", "CE", "MA", "PB", "PI", "RN", "SE", "AL", "DF"]}
        ufs["SP"] = self.mk(fbEst=300.0)
        for env in (ufs, {"meta": {}, "ufs": ufs}, [dict(d, uf=k) for k, d in ufs.items()]):
            h = r5.hipoteses_fundo(env)
            self.assertEqual(h["ufs"], 27)
            self.assertEqual(h["fbEst <= fb"], 26)
            self.assertEqual(h["nIdx == mun"], 27)
            self.assertEqual(h["ep >= ee >= eg"], 27)
            self.assertIn("ES", h["amostra"])

    def test_sem_ufs(self):
        self.assertEqual(r5.hipoteses_fundo({"x": 1})["ufs"], 0)


class Js(unittest.TestCase):
    def test_trechos(self):
        js = 'a("/relatorio/competencia/ultima");b("outra coisa");c("baixar arquivo csv");d("x")'
        self.assertEqual(r5.trechos_js(js, r"competencia|csv"), ["/relatorio/competencia/ultima", "baixar arquivo csv"])


class Seguro(unittest.TestCase):
    def test_falha_vira_linha(self):
        def quebra():
            raise ValueError("boom")
        r = r5.seguro("x", quebra)
        self.assertEqual((r[0]["ok"], r[0]["id"]), (False, "x"))
        self.assertIn("ValueError", r[0]["erro"])
        self.assertEqual(r5.seguro("y", lambda: {"id": "y", "ok": True}), [{"id": "y", "ok": True}])


if __name__ == "__main__":
    unittest.main()
