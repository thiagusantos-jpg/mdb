"""F02 — coletor de lojas VTEX via catálogo público.

Por que JSON e não DOM: os seletores do PRD v1
(`vtex-product-summary-2-x-container`) carregam a versão do componente no nome.
Uma atualização de tema muda o número e o scraper passa a devolver lista vazia
sem erro. O endpoint de busca pública devolve produto, SKU, EAN e oferta por
seller — mais estável, mais rápido e mais rico.

    GET /api/catalog_system/pub/products/search?_from=0&_to=49
    GET /api/catalog_system/pub/products/search?fq=C:/<id-categoria>/
    GET /api/catalog_system/pub/products/search?fq=alternateIds_Ean:<ean>

Cuidados que fazem parte de usar um endpoint público de terceiro: volume baixo,
pausa entre requisições, backoff em erro e User-Agent honesto. Leia o
robots.txt e os Termos de Uso do varejista antes de rodar isso em rotina.
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol
from urllib.parse import urljoin

from .. import config
from ..normalize.precos import parse_preco_brl
from ..normalize.texto import normalizar_ean
from .base import ColetaAnomala, Coletor, ErroDeColeta, OfertaBruta

CAMINHO_BUSCA = "/api/catalog_system/pub/products/search"


class Resposta(Protocol):  # pragma: no cover - contrato
    status_code: int
    text: str

    def json(self) -> Any: ...


class Sessao(Protocol):  # pragma: no cover - contrato
    def get(self, url: str, **kwargs: Any) -> Resposta: ...


def _sessao_padrao() -> Sessao:
    import requests  # importado aqui para o pacote não exigir rede em testes

    sessao = requests.Session()
    sessao.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json"})
    return sessao


class ColetorVtex(Coletor):
    """Varre o catálogo público de uma loja VTEX."""

    def __init__(
        self,
        fonte: config.FonteVtex,
        *,
        sessao: Sessao | None = None,
        limite: int | None = None,
        pausa_s: float | None = None,
        dormir=time.sleep,
    ) -> None:
        self.fonte = fonte
        self.slug = fonte.slug
        self._sessao = sessao
        self.limite = limite
        self.pausa_s = config.PAUSA_ENTRE_REQUISICOES_S if pausa_s is None else pausa_s
        self._dormir = dormir

    # -- HTTP ------------------------------------------------------------

    @property
    def sessao(self) -> Sessao:
        if self._sessao is None:
            self._sessao = _sessao_padrao()
        return self._sessao

    def _buscar(self, params: dict[str, Any]) -> list[dict]:
        url = urljoin(self.fonte.base_url, CAMINHO_BUSCA)
        ultimo_erro = ""

        for tentativa in range(1, config.MAX_TENTATIVAS + 1):
            try:
                resposta = self.sessao.get(
                    url,
                    params=params,
                    headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"},
                    timeout=config.TIMEOUT_S,
                )
            except Exception as erro:  # rede instável
                ultimo_erro = f"{type(erro).__name__}: {erro}"
                self._recuar(tentativa)
                continue

            # 206 Partial Content é a resposta normal de busca paginada na VTEX.
            if resposta.status_code in (200, 206):
                try:
                    dados = resposta.json()
                except (ValueError, json.JSONDecodeError) as erro:
                    raise ErroDeColeta(f"resposta não-JSON de {url}: {erro}") from erro
                if not isinstance(dados, list):
                    raise ErroDeColeta(f"formato inesperado em {url}: {type(dados).__name__}")
                return dados

            if resposta.status_code == 429 or resposta.status_code >= 500:
                ultimo_erro = f"HTTP {resposta.status_code}"
                self._recuar(tentativa)
                continue

            # 4xx que não seja 429 não melhora com repetição.
            raise ErroDeColeta(
                f"HTTP {resposta.status_code} em {url} (params={params}). "
                "Confirme o host e se a loja expõe o catálogo público."
            )

        raise ErroDeColeta(f"falhou após {config.MAX_TENTATIVAS} tentativas: {ultimo_erro}")

    def _recuar(self, tentativa: int) -> None:
        if tentativa < config.MAX_TENTATIVAS:
            self._dormir(config.BACKOFF_BASE_S ** tentativa)

    # -- Coleta ----------------------------------------------------------

    def coletar(self) -> list[OfertaBruta]:
        ofertas: list[OfertaBruta] = []
        vistos: set[str] = set()

        consultas: list[dict[str, Any]] = (
            [{"fq": f"C:/{c}/"} for c in self.fonte.categorias]
            if self.fonte.categorias
            else [{}]
        )

        for base_params in consultas:
            ofertas.extend(self._varrer(base_params, vistos, restante=self._restante(ofertas)))
            if self._atingiu_limite(ofertas):
                break

        if len(ofertas) < self.fonte.piso_esperado:
            raise ColetaAnomala(
                f"coleta anômala em '{self.slug}': {len(ofertas)} itens, "
                f"piso esperado {self.fonte.piso_esperado}. "
                "Provável mudança de contrato da API ou bloqueio — não é 'não teve produto hoje'."
            )

        return ofertas

    def _restante(self, ofertas: list[OfertaBruta]) -> int | None:
        return None if self.limite is None else max(0, self.limite - len(ofertas))

    def _atingiu_limite(self, ofertas: list[OfertaBruta]) -> bool:
        return self.limite is not None and len(ofertas) >= self.limite

    def _varrer(
        self, base_params: dict[str, Any], vistos: set[str], restante: int | None
    ) -> list[OfertaBruta]:
        coletadas: list[OfertaBruta] = []
        inicio = 0
        passo = config.VTEX_TAMANHO_PAGINA

        while restante is None or len(coletadas) < restante:
            if inicio > config.VTEX_OFFSET_MAXIMO:
                # A plataforma recusa deslocamentos grandes. Para varrer um
                # catálogo inteiro, fatie por categoria em vez de paginar sem fim.
                break

            params = dict(base_params)
            params["_from"] = inicio
            params["_to"] = inicio + passo - 1  # janela inclusiva

            pagina = self._buscar(params)
            if not pagina:
                break

            for produto in pagina:
                for oferta in self._extrair(produto):
                    chave = f"{oferta.ean_informado or ''}|{oferta.titulo_original}|{oferta.url or ''}"
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    coletadas.append(oferta)
                    if restante is not None and len(coletadas) >= restante:
                        return coletadas

            if len(pagina) < passo:
                break  # última página

            inicio += passo
            if self.pausa_s:
                self._dormir(self.pausa_s)

        return coletadas

    # -- Extração --------------------------------------------------------

    def _extrair(self, produto: dict) -> list[OfertaBruta]:
        """Um produto VTEX vira uma oferta por SKU disponível.

        SKUs distintos do mesmo produto são embalagens distintas (500g e 1kg
        convivem sob o mesmo productId) e precisam virar linhas separadas —
        colapsar aqui reintroduziria a confusão de gramatura pelo outro lado.
        """
        titulo_base = (produto.get("productName") or "").strip()
        marca = (produto.get("brand") or "").strip() or None
        link = produto.get("link") or None

        ofertas: list[OfertaBruta] = []
        for item in produto.get("items") or []:
            titulo = (item.get("name") or titulo_base).strip() or titulo_base
            if not titulo:
                continue

            ean = normalizar_ean(item.get("ean"))

            for vendedor in item.get("sellers") or []:
                comercial = vendedor.get("commertialOffer") or {}

                preco = parse_preco_brl(comercial.get("Price"))
                if preco is None or preco <= 0:
                    continue

                de = parse_preco_brl(comercial.get("ListPrice"))
                if de is not None and de <= preco:
                    de = None  # "de/por" sem desconto real não é preço-de

                disponivel = bool(
                    comercial.get("IsAvailable", (comercial.get("AvailableQuantity") or 0) > 0)
                )

                ofertas.append(
                    OfertaBruta(
                        titulo_original=titulo,
                        preco_centavos=preco,
                        ean_informado=ean,
                        preco_de_centavos=de,
                        disponivel=disponivel,
                        url=link,
                        marca=marca,
                        payload_bruto=json.dumps(
                            {
                                "productId": produto.get("productId"),
                                "itemId": item.get("itemId"),
                                "sellerId": vendedor.get("sellerId"),
                                "commertialOffer": {
                                    k: comercial.get(k)
                                    for k in ("Price", "ListPrice", "AvailableQuantity", "IsAvailable")
                                },
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
                break  # basta o seller principal

        return ofertas
