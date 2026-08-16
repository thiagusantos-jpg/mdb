"""Parsing e formatação de preços em Real.

Dinheiro trafega e é gravado em CENTAVOS (inteiro). Float para dinheiro foi um
dos defeitos apontados na revisão do PRD v1: 0,10 não tem representação binária
exata e o erro se acumula em agregações.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Espaços que aparecem em HTML de e-commerce e quebram um split ingênuo.
_ESPACOS_ESPECIAIS = dict.fromkeys(map(ord, "    ​"), " ")

# Alguns temas VTEX renderizam os centavos em um elemento separado:
# "R$ 12<sup>90</sup>". O texto extraído do DOM vira "R$ 1290" se você só
# arrancar as tags — um erro de 100x, silencioso.
_CENTAVOS_SUP = re.compile(
    # Os centavos podem estar em outro elemento, e o elemento dos reais pode
    # fechar antes: "R$ 12<sup>90</sup>" e "<span>R$ 5</span><sup>,49</sup>".
    r"(\d[\d.,]*)\s*(?:<\s*/\s*[a-z]+\s*>\s*)*"
    r"<\s*(sup|small|span)[^>]*>\s*,?\s*(\d{2})\s*<\s*/\s*\2\s*>",
    re.IGNORECASE,
)
_TAGS = re.compile(r"<[^>]+>")

# Sufixo de preço por medida: "R$ 9,90 /kg", "R$ 4,50 a unidade"
_SUFIXO_MEDIDA = re.compile(
    r"\s*(?:/|por\s+|a\s+)\s*(kg|quilo|g|l|litro|ml|un|und|unid|unidade)\.?\s*$",
    re.IGNORECASE,
)

_NUMERO = re.compile(r"\d[\d.,]*")


def parse_preco_brl(valor: object) -> int | None:
    """Converte um preço em centavos.

    Aceita número (interpretado como reais, que é o formato dos JSONs de API)
    ou texto em português. Devolve None quando não há preço reconhecível —
    nunca zero por engano, e nunca NaN.

        >>> parse_preco_brl("R$ 1.234,56")
        123456
        >>> parse_preco_brl("R$ 12,34")
        1234
        >>> parse_preco_brl(12.9)
        1290
    """
    if valor is None:
        return None

    # Números: já vêm em reais (VTEX devolve Price: 12.9).
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float, Decimal)):
        if isinstance(valor, float) and valor != valor:  # NaN
            return None
        try:
            return int((Decimal(str(valor)) * 100).quantize(Decimal("1")))
        except (InvalidOperation, OverflowError, ValueError):
            return None

    texto = str(valor).translate(_ESPACOS_ESPECIAIS).strip()
    if not texto:
        return None

    # Centavos em elemento separado, antes de qualquer limpeza de tags.
    casado = _CENTAVOS_SUP.search(texto)
    if casado:
        reais = casado.group(1).replace(".", "").replace(",", "")
        return int(reais) * 100 + int(casado.group(3))

    texto = _TAGS.sub(" ", texto)
    texto = _SUFIXO_MEDIDA.sub("", texto.strip())

    encontrado = _NUMERO.search(texto)
    if not encontrado:
        return None

    numero = encontrado.group(0).rstrip(".,")
    if not numero:
        return None

    tem_virgula = "," in numero
    tem_ponto = "." in numero

    if tem_virgula and tem_ponto:
        # O separador decimal é o que aparece por último: "1.234,56" ou "1,234.56"
        if numero.rfind(",") > numero.rfind("."):
            numero = numero.replace(".", "").replace(",", ".")
        else:
            numero = numero.replace(",", "")
    elif tem_virgula:
        # Em pt-BR a vírgula é sempre decimal.
        numero = numero.replace(",", ".", 1).replace(",", "")
    elif tem_ponto:
        casas = len(numero.split(".")[-1])
        if numero.count(".") == 1 and casas in (1, 2):
            pass  # "12.90" / "1.5" — ponto decimal, formato de API
        else:
            numero = numero.replace(".", "")  # "1.234" / "1.234.567" — milhar

    try:
        return int((Decimal(numero) * 100).quantize(Decimal("1")))
    except (InvalidOperation, OverflowError, ValueError):
        return None


def formatar_brl(centavos: int | None) -> str:
    """1234 -> 'R$ 12,34'. Só para apresentação."""
    if centavos is None:
        return "—"
    sinal = "-" if centavos < 0 else ""
    inteiro, resto = divmod(abs(centavos), 100)
    return f"{sinal}R$ {inteiro:,.0f}".replace(",", ".") + f",{resto:02d}"
