"""Normalização de título e de EAN."""

import unittest

from ..normalize.texto import (
    expandir_abreviacoes,
    normalizar_ean,
    normalizar_titulo,
    remover_acentos,
    validar_ean,
)


class TestNormalizarTitulo(unittest.TestCase):
    def test_minusculas_sem_acento_sem_pontuacao(self):
        self.assertEqual(normalizar_titulo("Café Torrado & Moído"), "cafe torrado moido")

    def test_colapsa_espacos(self):
        self.assertEqual(normalizar_titulo("  Leite   Integral  "), "leite integral")

    def test_expande_abreviacoes(self):
        self.assertEqual(normalizar_titulo("Leite Int"), "leite integral")
        self.assertEqual(normalizar_titulo("Biscoito c/ Recheio"), "biscoito com recheio")

    def test_grafias_diferentes_convergem(self):
        self.assertEqual(
            normalizar_titulo("Leite INT. Italac"), normalizar_titulo("leite integral italac")
        )

    def test_vazio(self):
        self.assertEqual(normalizar_titulo(None), "")
        self.assertEqual(normalizar_titulo(""), "")

    def test_remover_acentos(self):
        self.assertEqual(remover_acentos("Ação Ñandú"), "Acao Nandu")

    def test_expandir_preserva_desconhecidas(self):
        self.assertEqual(expandir_abreviacoes("Leite Italac"), "Leite Italac")


class TestNormalizarEan(unittest.TestCase):
    def test_texto_simples(self):
        self.assertEqual(normalizar_ean("7891234567895"), "7891234567895")

    def test_float_do_excel(self):
        # O caso concreto: pandas/Excel transformam o código em número
        self.assertEqual(normalizar_ean(7891234567895.0), "7891234567895")
        self.assertEqual(normalizar_ean("7891234567895.0"), "7891234567895")

    def test_notacao_cientifica(self):
        self.assertEqual(normalizar_ean("7.891234567895E+12"), "7891234567895")

    def test_zero_a_esquerda_perdido(self):
        # 12 dígitos que não são UPC viram EAN-13 com zero à esquerda
        self.assertEqual(normalizar_ean("789123456789"), "789123456789")
        self.assertEqual(len(normalizar_ean("78912345678")), 12)

    def test_com_separadores(self):
        self.assertEqual(normalizar_ean("789-1234-567895"), "7891234567895")

    def test_descarta_lixo(self):
        for entrada in (None, "", "   ", "SEM EAN", "123", float("nan")):
            with self.subTest(entrada=entrada):
                self.assertIsNone(normalizar_ean(entrada))


class TestValidarEan(unittest.TestCase):
    def test_ean13_valido(self):
        # dígito verificador calculado: 7891234567895
        self.assertTrue(validar_ean("7891234567895"))

    def test_ean13_invalido(self):
        self.assertFalse(validar_ean("7891234567890"))

    def test_ean8(self):
        self.assertTrue(validar_ean("96385074"))

    def test_formato_errado(self):
        for entrada in (None, "", "abc", "123", "789123456789012345"):
            with self.subTest(entrada=entrada):
                self.assertFalse(validar_ean(entrada))


if __name__ == "__main__":
    unittest.main()
