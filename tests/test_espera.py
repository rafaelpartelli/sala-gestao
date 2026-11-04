import io, unittest, urllib.error
from unittest import mock
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import comum


def erro(codigo, retry_after=None):
    h = {"Retry-After": retry_after} if retry_after else {}
    import email.message
    m = email.message.Message()
    for k, v in h.items():
        m[k] = v
    return urllib.error.HTTPError("http://x", codigo, "x", m, io.BytesIO(b""))


class Resposta:
    def __init__(self, corpo): self.corpo = corpo
    def read(self, n=None): return self.corpo
    def __enter__(self): return self
    def __exit__(self, *a): return False


class TesteEspera(unittest.TestCase):
    def test_exponencial_cresce_e_respeita_teto(self):
        e = RuntimeError("x")
        a, b, c = (comum.espera_para(e, i, 3) for i in (0, 1, 2))
        self.assertTrue(3 <= a <= 3.75 and 6 <= b <= 7.5 and 12 <= c <= 15)
        self.assertEqual(comum.espera_para(e, 20, 3), comum.ESPERA_MAXIMA)

    def test_retry_after_numerico(self):
        self.assertEqual(comum.espera_para(erro(429, "17"), 0, 3), 17)
        self.assertEqual(comum.espera_para(erro(429, "9999"), 0, 3), comum.ESPERA_MAXIMA)

    def test_429_sem_cabecalho_usa_exponencial(self):
        self.assertGreaterEqual(comum.espera_para(erro(429), 1, 3), 6)

    def test_repete_429_e_depois_funciona(self):
        with mock.patch("urllib.request.urlopen", side_effect=[erro(429, "1"), Resposta(b"ok")]), \
             mock.patch("time.sleep") as dorme:
            self.assertEqual(comum.baixar("http://x", tentativas=3), b"ok")
            dorme.assert_called_once_with(1)

    def test_nao_repete_403(self):
        with mock.patch("urllib.request.urlopen", side_effect=erro(403)) as u, mock.patch("time.sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                comum.baixar("http://x", tentativas=3)
            self.assertEqual(u.call_count, 1)

    def test_nao_dorme_apos_ultima_tentativa(self):
        with mock.patch("urllib.request.urlopen", side_effect=erro(500)), mock.patch("time.sleep") as dorme:
            with self.assertRaises(urllib.error.HTTPError):
                comum.baixar("http://x", tentativas=3)
            self.assertEqual(dorme.call_count, 2)


if __name__ == "__main__":
    unittest.main()
