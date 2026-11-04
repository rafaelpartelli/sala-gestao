import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import sondar_r3 as r3

HTML = b'''<html><head><title> Notas  Tecnicas </title></head><body>
<a href="/a/nota-tecnica-12.pdf">Nota T\xc3\xa9cnica 12/2026</a><a href="/b">Outro</a>
<a href="/a/nota-tecnica-12.pdf">Repetido</a><a href="https://x.gov.br/portaria-10994">Portaria 10.994</a></body></html>'''

class T(unittest.TestCase):
    def test_links_filtra_e_remove_repetidos(self):
        l = r3.links(HTML, "https://www.gov.br/saude/", r"nota-tecnica|portaria")
        self.assertEqual(len(l), 2)
        self.assertTrue(l[0]["url"].startswith("https://www.gov.br/a/"))

    def test_links_sem_filtro(self):
        self.assertEqual(len(r3.links(HTML, "https://x/", None)), 3)

    def test_limite_n(self):
        self.assertEqual(len(r3.links(HTML, "https://x/", None, n=1)), 1)

if __name__ == "__main__":
    unittest.main()

class T2(unittest.TestCase):
    def test_mes_anterior_formato(self):
        m = r3.mes_anterior()
        self.assertRegex(m, r"^20\d{2}(0[1-9]|1[0-2])$")
