"""Contrato comum dos coletores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ErroDeColeta(RuntimeError):
    """Falha irrecuperável de coleta (rede, formato inesperado, bloqueio)."""


class ColetaAnomala(ErroDeColeta):
    """Coleta abaixo do piso esperado.

    Existe como erro próprio porque o modo de falha mais perigoso do sistema é
    coletar zero item em silêncio e parecer 'não teve oferta hoje'. Quando um
    seletor ou um contrato de API muda, isso aqui precisa falhar alto.
    """


@dataclass(frozen=True)
class OfertaBruta:
    """Um item observado numa fonte, ainda sem pareamento com a base."""

    titulo_original: str
    preco_centavos: int
    ean_informado: str | None = None
    preco_de_centavos: int | None = None
    disponivel: bool = True
    url: str | None = None
    marca: str | None = None
    payload_bruto: str | None = None

    def __post_init__(self) -> None:
        if not self.titulo_original or not self.titulo_original.strip():
            raise ValueError("oferta sem título")
        if self.preco_centavos <= 0:
            raise ValueError(f"preço inválido: {self.preco_centavos}")


class Coletor(ABC):
    """Interface comum. Uma implementação por fonte."""

    slug: str

    @abstractmethod
    def coletar(self) -> list[OfertaBruta]:
        """Devolve as ofertas observadas. Não toca no banco."""
        raise NotImplementedError
