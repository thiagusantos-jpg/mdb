"""Coletor VTEX (F02) — testado offline, sem tocar a rede."""

import json
import unittest

from .. import config
from ..collectors.base import ColetaAnomala, ErroDeColeta
from ..collectors.vtex import ColetorVtex


def produto(
    nome="Leite Italac Integral 1L",
    ean="7891234567895",
    preco=5.99,
    de=None,
    disponivel=True,
    product_id="1",
):
    return {
        "productId": product_id,
        "productName": nome,
        "brand": "Italac",
        "link": f"https://loja.exemplo/{product_id}",
        "items": [
            {
                "itemId": f"sku-{product_id}",
                "name": nome,
                "ean": ean,
                "sellers": [
                    {
                        "sellerId": "1",
                        "commertialOffer": {
                            "Price": preco,
                            "ListPrice": de,
                            "AvailableQuantity": 10 if disponivel else 0,
                            "IsAvailable": disponivel,
                        },
                    }
                ],
            }
        ],
    }


class RespostaFake:
    def __init__(self, dados, status_code=200):
        self._dados = dados
        self.status_code = status_code
        self.text = json.dumps(dados) if dados is not None else ""

    def json(self):
        if self._dados is None:
            raise ValueError("sem JSON")
        return self._dados


class SessaoFake:
    """Devolve páginas pré-definidas e registra o que foi pedido."""

    def __init__(self, paginas, status=200):
        self.paginas = list(paginas)
        self.status = status
        self.chamadas = []

    def get(self, url, **kwargs):
        self.chamadas.append((url, kwargs.get("params", {})))
        dados = self.paginas.pop(0) if self.paginas else []
        status = self.status if callable(self.status) is False else self.status
        return RespostaFake(dados, status)


def fonte(**kwargs):
    padrao = dict(
        slug="teste",
        nome="Loja Teste",
        base_url="https://loja.exemplo",
        nome_loja="Loja Teste",
        piso_esperado=1,
    )
    padrao.update(kwargs)
    return config.FonteVtex(**padrao)


class TestExtracao(unittest.TestCase):
    def coletar(self, paginas, **kwargs):
        sessao = SessaoFake(paginas)
        coletor = ColetorVtex(
            fonte(**kwargs.pop("fonte_kwargs", {})),
            sessao=sessao,
            pausa_s=0,
            dormir=lambda _: None,
            **kwargs,
        )
        return coletor.coletar(), sessao

    def test_extrai_campos(self):
        ofertas, _ = self.coletar([[produto()]])
        self.assertEqual(len(ofertas), 1)
        oferta = ofertas[0]
        self.assertEqual(oferta.titulo_original, "Leite Italac Integral 1L")
        self.assertEqual(oferta.preco_centavos, 599)
        self.assertEqual(oferta.ean_informado, "7891234567895")
        self.assertEqual(oferta.marca, "Italac")
        self.assertTrue(oferta.disponivel)

    def test_preco_de_maior_vira_preco_de(self):
        ofertas, _ = self.coletar([[produto(preco=5.99, de=7.49)]])
        self.assertEqual(ofertas[0].preco_de_centavos, 749)

    def test_preco_de_sem_desconto_e_ignorado(self):
        """'De R$5,99 por R$5,99' não é preço-de; virava desconto fantasma."""
        ofertas, _ = self.coletar([[produto(preco=5.99, de=5.99)]])
        self.assertIsNone(ofertas[0].preco_de_centavos)

    def test_indisponivel_e_marcado(self):
        ofertas, _ = self.coletar([[produto(disponivel=False)]])
        self.assertFalse(ofertas[0].disponivel)

    def test_preco_zero_e_ignorado(self):
        with self.assertRaises(ColetaAnomala):
            self.coletar([[produto(preco=0)]])

    def test_ean_ausente_nao_impede_coleta(self):
        ofertas, _ = self.coletar([[produto(ean=None)]])
        self.assertIsNone(ofertas[0].ean_informado)
        self.assertEqual(ofertas[0].preco_centavos, 599)

    def test_payload_bruto_permite_reprocessar(self):
        ofertas, _ = self.coletar([[produto()]])
        payload = json.loads(ofertas[0].payload_bruto)
        self.assertEqual(payload["commertialOffer"]["Price"], 5.99)

    def test_skus_distintos_viram_ofertas_distintas(self):
        p = produto()
        p["items"].append(
            {
                "itemId": "sku-2",
                "name": "Leite Italac Integral 200ml",
                "ean": "7891234567901",
                "sellers": [
                    {"sellerId": "1", "commertialOffer": {"Price": 2.49, "IsAvailable": True}}
                ],
            }
        )
        ofertas, _ = self.coletar([[p]])
        self.assertEqual(len(ofertas), 2)
        self.assertEqual({o.preco_centavos for o in ofertas}, {599, 249})


class TestPaginacao(unittest.TestCase):
    def test_para_na_pagina_incompleta(self):
        pagina_cheia = [produto(product_id=str(i), ean=None) for i in range(50)]
        sessao = SessaoFake([pagina_cheia, [produto(product_id="x", ean=None)]])
        coletor = ColetorVtex(
            fonte(), sessao=sessao, pausa_s=0, dormir=lambda _: None
        )
        ofertas = coletor.coletar()
        self.assertEqual(len(ofertas), 51)
        self.assertEqual(len(sessao.chamadas), 2)

    def test_janela_inclusiva(self):
        sessao = SessaoFake([[produto()]])
        ColetorVtex(fonte(), sessao=sessao, pausa_s=0, dormir=lambda _: None).coletar()
        _, params = sessao.chamadas[0]
        self.assertEqual(params["_from"], 0)
        self.assertEqual(params["_to"], config.VTEX_TAMANHO_PAGINA - 1)

    def test_limite_respeitado(self):
        pagina = [produto(product_id=str(i), ean=None) for i in range(50)]
        sessao = SessaoFake([pagina, pagina])
        coletor = ColetorVtex(
            fonte(), sessao=sessao, limite=10, pausa_s=0, dormir=lambda _: None
        )
        self.assertEqual(len(coletor.coletar()), 10)

    def test_duplicatas_entre_paginas(self):
        mesmo = produto(product_id="1")
        sessao = SessaoFake([[mesmo], [mesmo]])
        coletor = ColetorVtex(fonte(), sessao=sessao, pausa_s=0, dormir=lambda _: None)
        self.assertEqual(len(coletor.coletar()), 1)

    def test_categorias_geram_consultas_separadas(self):
        sessao = SessaoFake([[produto(product_id="1")], [produto(product_id="2", ean=None)]])
        coletor = ColetorVtex(
            fonte(categorias=("10", "20")), sessao=sessao, pausa_s=0, dormir=lambda _: None
        )
        coletor.coletar()
        self.assertEqual(sessao.chamadas[0][1]["fq"], "C:/10/")
        self.assertEqual(sessao.chamadas[1][1]["fq"], "C:/20/")


class TestHealthCheck(unittest.TestCase):
    def test_coleta_vazia_falha_alto(self):
        """O modo de falha mais perigoso: 0 itens parecendo 'não teve oferta hoje'."""
        sessao = SessaoFake([[]])
        coletor = ColetorVtex(
            fonte(piso_esperado=20), sessao=sessao, pausa_s=0, dormir=lambda _: None
        )
        with self.assertRaises(ColetaAnomala) as ctx:
            coletor.coletar()
        self.assertIn("anômala", str(ctx.exception))

    def test_coleta_abaixo_do_piso_falha(self):
        sessao = SessaoFake([[produto()]])
        coletor = ColetorVtex(
            fonte(piso_esperado=100), sessao=sessao, pausa_s=0, dormir=lambda _: None
        )
        with self.assertRaises(ColetaAnomala):
            coletor.coletar()


class TestErrosHttp(unittest.TestCase):
    def test_404_nao_repete(self):
        sessao = SessaoFake([[]], status=404)
        coletor = ColetorVtex(fonte(), sessao=sessao, pausa_s=0, dormir=lambda _: None)
        with self.assertRaises(ErroDeColeta):
            coletor.coletar()
        self.assertEqual(len(sessao.chamadas), 1)

    def test_500_repete_e_desiste(self):
        sessao = SessaoFake([[]] * 10, status=500)
        coletor = ColetorVtex(fonte(), sessao=sessao, pausa_s=0, dormir=lambda _: None)
        with self.assertRaises(ErroDeColeta):
            coletor.coletar()
        self.assertEqual(len(sessao.chamadas), config.MAX_TENTATIVAS)

    def test_206_e_sucesso(self):
        """206 Partial Content é a resposta normal da busca paginada VTEX."""
        sessao = SessaoFake([[produto()]], status=206)
        coletor = ColetorVtex(fonte(), sessao=sessao, pausa_s=0, dormir=lambda _: None)
        self.assertEqual(len(coletor.coletar()), 1)

    def test_resposta_nao_json(self):
        class SessaoQuebrada:
            def get(self, url, **kwargs):
                return RespostaFake(None, 200)

        coletor = ColetorVtex(fonte(), sessao=SessaoQuebrada(), pausa_s=0, dormir=lambda _: None)
        with self.assertRaises(ErroDeColeta):
            coletor.coletar()

    def test_formato_inesperado(self):
        class SessaoDict:
            def get(self, url, **kwargs):
                return RespostaFake({"erro": "acesso negado"}, 200)

        coletor = ColetorVtex(fonte(), sessao=SessaoDict(), pausa_s=0, dormir=lambda _: None)
        with self.assertRaises(ErroDeColeta) as ctx:
            coletor.coletar()
        self.assertIn("formato inesperado", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
