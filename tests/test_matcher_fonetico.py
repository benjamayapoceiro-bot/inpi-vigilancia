import unittest

from matcher import similitud, similitud_fonetica_tokens, normalizar_fonetico, buscar_coincidencias, distancia_logo_combinada


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

    def test_no_colapsa_ch_con_y(self):
        self.assertNotEqual(normalizar_fonetico("CHICO"), normalizar_fonetico("YICO"))
        resultado = similitud("CHICO", "YICO")
        self.assertLess(resultado["score"], 0.60)

    def test_penaliza_inicio_fonetico_distinto_en_palabra_unica(self):
        resultado = similitud("GUERRA", "JERRA")
        self.assertLess(resultado["score"], 0.60)

    def test_no_colapsa_enie_con_n(self):
        self.assertNotEqual(normalizar_fonetico("PEÑA"), normalizar_fonetico("PENA"))
        resultado = similitud("PEÑA", "PENA")
        self.assertLess(resultado["score"], 0.60)

    def test_no_colapsa_w_con_b(self):
        self.assertNotEqual(normalizar_fonetico("WAKA"), normalizar_fonetico("BAKA"))
        resultado = similitud("WAKA", "BAKA")
        self.assertLess(resultado["score"], 0.60)

    def test_gue_gui_conservan_sonido_de_g_dura(self):
        self.assertTrue(normalizar_fonetico("GUERRA").startswith("G"))
        self.assertTrue(normalizar_fonetico("JERRA").startswith("J"))
        self.assertNotEqual(normalizar_fonetico("GUERRA"), normalizar_fonetico("JERRA"))

    def test_logo_con_un_solo_hash_se_penaliza(self):
        score = distancia_logo_combinada(
            {"logo_phash": "ffffffffffffffff"},
            {"logo_phash": "ffffffffffffffff"},
        )
        self.assertEqual(score, 0.90)


if __name__ == "__main__":
    unittest.main()
