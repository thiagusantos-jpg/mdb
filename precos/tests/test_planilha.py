"""Importação de planilha (F01) — inclusive os defeitos da v1."""

import tempfile
import unittest
from pathlib import Path

from ..collectors.planilha import ErroDePlanilha, ler_planilha


def escrever(conteudo: str, sufixo: str = ".csv") -> Path:
    arquivo = tempfile.NamedTemporaryFile("w", suffix=sufixo, delete=False, encoding="utf-8")
    arquivo.write(conteudo)
    arquivo.close()
    return Path(arquivo.name)


class TestLerPlanilha(unittest.TestCase):
    def test_colunas_da_spec_do_prd(self):
        caminho = escrever(
            "EAN,Nome,Preco_Referencia\n7891234567895,Leite Italac Integral 1L,5.99\n"
        )
        resultado = ler_planilha(caminho)
        self.assertEqual(len(resultado.linhas), 1)
        linha = resultado.linhas[0]
        self.assertEqual(linha.ean, "7891234567895")
        self.assertEqual(linha.preco_centavos, 599)
        self.assertEqual((linha.quantidade, linha.unidade), (1000.0, "ml"))

    def test_coluna_preco_do_codigo_do_prd(self):
        """A v1 divergia de si mesma: spec dizia Preco_Referencia, código lia Preco."""
        caminho = escrever("EAN,Nome,Preco\n7891234567895,Leite 1L,5.99\n")
        resultado = ler_planilha(caminho)
        self.assertEqual(len(resultado.linhas), 1)
        self.assertEqual(resultado.colunas_detectadas["preco"], "Preco")

    def test_separador_ponto_e_virgula(self):
        caminho = escrever("EAN;Nome;Preco\n7891234567895;Arroz 5kg;R$ 24,90\n")
        resultado = ler_planilha(caminho)
        self.assertEqual(resultado.linhas[0].preco_centavos, 2490)

    def test_bom_do_excel(self):
        caminho = escrever("﻿EAN,Nome,Preco\n7891234567895,Leite 1L,5.99\n")
        self.assertEqual(len(ler_planilha(caminho).linhas), 1)

    def test_preco_em_reais_com_simbolo(self):
        caminho = escrever("EAN,Nome,Preco\n7891234567895,Leite 1L,\"R$ 1.234,56\"\n")
        self.assertEqual(ler_planilha(caminho).linhas[0].preco_centavos, 123456)

    def test_preco_vazio_e_descartado_com_motivo(self):
        """Na v1 isso virava NaN, era gravado e sumia dos alertas em silêncio."""
        caminho = escrever(
            "EAN,Nome,Preco\n"
            "7891234567895,Leite 1L,\n"
            "7891234567895,Arroz 5kg,24.90\n"
        )
        resultado = ler_planilha(caminho)
        self.assertEqual(len(resultado.linhas), 1)
        self.assertEqual(len(resultado.descartadas), 1)
        self.assertIn("preço ilegível", resultado.descartadas[0][1])
        self.assertEqual(resultado.descartadas[0][0], 2)  # número da linha

    def test_preco_zero_descartado(self):
        caminho = escrever("EAN,Nome,Preco\n7891234567895,Leite 1L,0\n")
        resultado = ler_planilha(caminho)
        self.assertEqual(resultado.linhas, [])
        self.assertIn("não positivo", resultado.descartadas[0][1])

    def test_nome_vazio_descartado(self):
        caminho = escrever("EAN,Nome,Preco\n7891234567895,,5.99\n")
        self.assertIn("nome vazio", ler_planilha(caminho).descartadas[0][1])

    def test_produto_sem_ean_e_aceito(self):
        """Hortifruti não tem código de barras — a PK em `ean` da v1 o excluía."""
        caminho = escrever("EAN,Nome,Preco\n,Banana Prata kg,7.90\n")
        resultado = ler_planilha(caminho)
        self.assertEqual(len(resultado.linhas), 1)
        self.assertIsNone(resultado.linhas[0].ean)
        self.assertEqual(resultado.linhas[0].quantidade, 1000.0)

    def test_ean_corrompido_pelo_excel(self):
        caminho = escrever("EAN,Nome,Preco\n7891234567895.0,Leite 1L,5.99\n")
        self.assertEqual(ler_planilha(caminho).linhas[0].ean, "7891234567895")

    def test_ean_com_digito_invalido_e_contado(self):
        caminho = escrever("EAN,Nome,Preco\n7891234567890,Leite 1L,5.99\n")
        resultado = ler_planilha(caminho)
        self.assertEqual(resultado.ean_sem_digito_valido, 1)
        self.assertTrue(resultado.linhas[0].ean_invalido)
        self.assertEqual(len(resultado.linhas), 1)  # importado mesmo assim

    def test_colunas_opcionais(self):
        caminho = escrever(
            "EAN,Nome,Preco,Marca,Categoria\n7891234567895,Leite 1L,5.99,Italac,Laticínios\n"
        )
        linha = ler_planilha(caminho).linhas[0]
        self.assertEqual(linha.marca, "Italac")
        self.assertEqual(linha.categoria, "Laticínios")

    def test_cabecalho_acentuado(self):
        caminho = escrever("Código,Descrição,Valor\n7891234567895,Leite 1L,5.99\n")
        self.assertEqual(len(ler_planilha(caminho).linhas), 1)

    def test_coluna_obrigatoria_ausente(self):
        caminho = escrever("EAN,Observacao\n7891234567895,nada\n")
        with self.assertRaises(ErroDePlanilha) as ctx:
            ler_planilha(caminho)
        self.assertIn("nome", str(ctx.exception))

    def test_arquivo_inexistente(self):
        with self.assertRaises(ErroDePlanilha):
            ler_planilha(Path("/tmp/nao-existe-mesmo-12345.csv"))

    def test_formato_nao_suportado(self):
        caminho = escrever("qualquer coisa", sufixo=".pdf")
        with self.assertRaises(ErroDePlanilha):
            ler_planilha(caminho)


if __name__ == "__main__":
    unittest.main()
