import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import sondar_r4 as r4

SWAGGER = '''<script>window.ui = SwaggerUIBundle({ url: "/fundoafundo/swagger.json", dom_id: "#swagger-ui" });</script>
<a href="docs/openapi.json">x</a>'''

class T(unittest.TestCase):
    def test_achar_specs(self):
        c = r4.achar_specs(SWAGGER, "https://api.exemplo.gov.br/fundoafundo/")
        self.assertIn("https://api.exemplo.gov.br/fundoafundo/swagger.json", c)
        self.assertTrue(any(u.endswith("openapi.json") for u in c))

    def test_caminhos_openapi(self):
        self.assertEqual(r4.caminhos_openapi({"paths": {"/b": {}, "/a": {}}}), ["/a", "/b"])
        self.assertEqual(r4.caminhos_openapi({"x": 1}), [])
        self.assertEqual(r4.caminhos_openapi([]), [])

    def test_texto_sem_corpo(self):
        self.assertEqual(r4.texto({}), "")

if __name__ == "__main__":
    unittest.main()
