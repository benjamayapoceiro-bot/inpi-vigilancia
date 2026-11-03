import unittest

from matcher import similitud, similitud_fonetica_tokens


class MatchingFoneticoTests(unittest.TestCase):
    def test_equivalencias_foneticas_espanol(self):
        # B/V y C/K deben aproximarse aunque la escritura sea distinta.
        resultado = similitud("BACA", "VAKA")
        self.assertGreaterEqual(resultado["fonetica"], 0.95)
        self.assertGreaterEqual(resultado["score"], 0.95)

    def test_compara_tokens_en_marcas_compuestas(self):
        # Una palabra distintiva coincidente debe sobrevivir a palabras adicionales.
        score = similitud_fonetica_tokens("CASA CUMBRE", "CASA KUMBRE PATAGONIA")
        self.assertGreaterEqual(score, 0.60)

    def test_ll_y_se_normalizan_para_busqueda_fonetica(self):
        resultado = similitud("YERBA", "LLERBA")
        self.assertGreaterEqual(resultado["fonetica"], 0.95)


if __name__ == "__main__":
    unittest.main()
