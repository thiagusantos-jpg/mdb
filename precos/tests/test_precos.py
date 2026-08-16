"""Casos de parsing de preço listados no PRD v2 §5."""

import unittest

from ..normalize.precos import formatar_brl, parse_preco_brl


class TestParsePrecoBrl(unittest.TestCase):
    def test_milhar_com_centavos(self):
        self.assertEqual(parse_preco_brl("R$ 1.234,56"), 123456)

    def test_valor_simples(self):
        self.assertEqual(parse_preco_brl("R$ 12,34"), 1234)

    def test_preco_por_medida(self):
        self.assertEqual(parse_preco_brl("R$ 9,90 /kg"), 990)
        self.assertEqual(parse_preco_brl("R$ 4,50 a unidade"), 450)
        self.assertEqual(parse_preco_brl("R$ 7,20 por litro"), 720)

    def test_espaco_nao_separavel(self):
        # \xa0 é o que o HTML de e-commerce costuma usar depois do "R$"
        self.assertEqual(parse_preco_brl("R$\xa012,34"), 1234)
        self.assertEqual(parse_preco_brl("R$ 1.234,56"), 123456)

    def test_centavos_em_elemento_separado(self):
        # Sem tratamento, "R$ 12<sup>90</sup>" vira 1290 reais — erro de 100x.
        self.assertEqual(parse_preco_brl("R$ 12<sup>90</sup>"), 1290)
        self.assertEqual(parse_preco_brl("<span>R$ 5</span><sup>,49</sup>"), 549)
        self.assertEqual(parse_preco_brl("R$ 1.234<small>56</small>"), 123456)

    def test_ponto_decimal_de_api(self):
        self.assertEqual(parse_preco_brl("12.90"), 1290)
        self.assertEqual(parse_preco_brl("1.5"), 150)

    def test_ponto_como_milhar(self):
        self.assertEqual(parse_preco_brl("1.234"), 123400)
        self.assertEqual(parse_preco_brl("1.234.567"), 123456700)

    def test_numeros_sao_reais(self):
        self.assertEqual(parse_preco_brl(12.9), 1290)
        self.assertEqual(parse_preco_brl(5), 500)
        self.assertEqual(parse_preco_brl(0.1), 10)

    def test_precisao_de_centavos(self):
        # O motivo de não usar float: 19.99*100 == 1998.9999999999998
        self.assertEqual(parse_preco_brl(19.99), 1999)
        self.assertEqual(parse_preco_brl("R$ 19,99"), 1999)

    def test_sem_preco(self):
        for entrada in (None, "", "   ", "grátis", "sob consulta", float("nan"), True):
            with self.subTest(entrada=entrada):
                self.assertIsNone(parse_preco_brl(entrada))

    def test_inteiro_em_texto(self):
        self.assertEqual(parse_preco_brl("R$ 15"), 1500)


class TestFormatarBrl(unittest.TestCase):
    def test_formata(self):
        self.assertEqual(formatar_brl(1234), "R$ 12,34")
        self.assertEqual(formatar_brl(123456), "R$ 1.234,56")
        self.assertEqual(formatar_brl(5), "R$ 0,05")
        self.assertEqual(formatar_brl(None), "—")

    def test_ida_e_volta(self):
        for centavos in (1, 99, 100, 1234, 123456, 100000000):
            with self.subTest(centavos=centavos):
                self.assertEqual(parse_preco_brl(formatar_brl(centavos)), centavos)


if __name__ == "__main__":
    unittest.main()
