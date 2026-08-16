"""Casos de quantidade listados no PRD v2 §5, mais o portão de unidade."""

import unittest

from ..normalize.quantidades import extrair_do_titulo, parse_quantidade, preco_por_unidade


class TestParseQuantidade(unittest.TestCase):
    def test_litro(self):
        self.assertEqual(parse_quantidade("1L"), (1000.0, "ml"))

    def test_grama(self):
        self.assertEqual(parse_quantidade("200g"), (200.0, "g"))

    def test_multiplo(self):
        # 2x500ml = 1000ml no total: é o que permite comparar preço por litro
        self.assertEqual(parse_quantidade("2x500ml"), (1000.0, "ml"))
        self.assertEqual(parse_quantidade("6 x 1L"), (6000.0, "ml"))

    def test_decimal_com_virgula(self):
        self.assertEqual(parse_quantidade("1,5 L"), (1500.0, "ml"))

    def test_unidade_nua(self):
        self.assertEqual(parse_quantidade("kg"), (1000.0, "g"))

    def test_conversoes(self):
        self.assertEqual(parse_quantidade("2kg"), (2000.0, "g"))
        self.assertEqual(parse_quantidade("500 MG"), (0.5, "g"))
        self.assertEqual(parse_quantidade("12 un"), (12.0, "un"))
        self.assertEqual(parse_quantidade("1 dz"), (12.0, "un"))

    def test_sem_quantidade(self):
        for entrada in (None, "", "leite", "promoção"):
            with self.subTest(entrada=entrada):
                self.assertIsNone(parse_quantidade(entrada))


class TestExtrairDoTitulo(unittest.TestCase):
    def test_separa_quantidade_do_nome(self):
        self.assertEqual(
            extrair_do_titulo("Leite Italac Integral 1L"),
            (1000.0, "ml", "Leite Italac Integral"),
        )

    def test_quantidade_no_meio(self):
        qtd, unidade, resto = extrair_do_titulo("Arroz Tio João 5kg Tipo 1")
        self.assertEqual((qtd, unidade), (5000.0, "g"))
        self.assertEqual(resto, "Arroz Tio João Tipo 1")

    def test_produto_a_peso(self):
        self.assertEqual(
            extrair_do_titulo("Banana Prata kg"), (1000.0, "g", "Banana Prata")
        )

    def test_sem_quantidade_preserva_titulo(self):
        self.assertEqual(extrair_do_titulo("Detergente Ypê"), (None, None, "Detergente Ypê"))

    def test_o_falso_positivo_do_prd(self):
        """200g × 500g: o par que o WRatio da v1 aceitava.

        Com quantidade extraída como campo, o portão do matcher (fase 4) tem
        como recusar: os títulos residuais são idênticos, as quantidades não.
        """
        a = extrair_do_titulo("Leite Italac Integral 1L")
        b = extrair_do_titulo("Leite Italac Integral 200ml")
        self.assertEqual(a[2], b[2])          # mesmo texto residual
        self.assertNotEqual(a[0], b[0])       # quantidades diferentes
        self.assertEqual(a[1], b[1])          # mesma unidade base


class TestPrecoPorUnidade(unittest.TestCase):
    def test_por_litro(self):
        # R$ 5,99 por 1000ml -> R$ 5,99/L
        self.assertAlmostEqual(preco_por_unidade(599, 1000.0, "ml"), 599.0)

    def test_embalagens_diferentes_ficam_comparaveis(self):
        grande = preco_por_unidade(1000, 2000.0, "g")   # R$10,00 / 2kg
        pequena = preco_por_unidade(600, 1000.0, "g")   # R$ 6,00 / 1kg
        self.assertLess(grande, pequena)

    def test_sem_quantidade(self):
        self.assertIsNone(preco_por_unidade(599, None, None))
        self.assertIsNone(preco_por_unidade(599, 0, "g"))


if __name__ == "__main__":
    unittest.main()
