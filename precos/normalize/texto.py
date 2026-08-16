"""Normalização de texto e de códigos EAN/GTIN."""

from __future__ import annotations

import re
import unicodedata

# Abreviações comuns em título de produto de supermercado.
ABREVIACOES = {
    "int": "integral",
    "desn": "desnatado",
    "semi": "semidesnatado",
    "ref": "refrigerante",
    "refri": "refrigerante",
    "achoc": "achocolatado",
    "choc": "chocolate",
    "past": "pasteurizado",
    "cong": "congelado",
    "trad": "tradicional",
    "sab": "sabor",
    "c/": "com",
    "s/": "sem",
    "p/": "para",
    "pc": "pacote",
    "pct": "pacote",
    "cx": "caixa",
    "gf": "garrafa",
    "lt": "lata",
    "und": "unidade",
    "un": "unidade",
    "unid": "unidade",
}

_ESPACOS = re.compile(r"\s+")
_PONTUACAO = re.compile(r"[^\w\s%]", re.UNICODE)


def remover_acentos(texto: str) -> str:
    """'Café Torrado' -> 'Cafe Torrado'."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def expandir_abreviacoes(texto: str) -> str:
    """Troca abreviações por palavras inteiras, token a token.

    Feito antes de remover pontuação, porque abreviações como 'c/' dependem
    da barra para serem reconhecidas.
    """
    tokens = texto.split()
    saida = []
    for token in tokens:
        chave = token.lower().rstrip(".")
        saida.append(ABREVIACOES.get(chave, token))
    return " ".join(saida)


def normalizar_titulo(texto: str | None) -> str:
    """Forma canônica de um título, usada como chave de alias.

    Minúsculas, sem acentos, sem pontuação, abreviações expandidas e espaços
    colapsados. Duas grafias do mesmo produto devem convergir para a mesma
    string.
    """
    if not texto:
        return ""
    resultado = expandir_abreviacoes(str(texto).strip())
    resultado = remover_acentos(resultado).lower()
    resultado = _PONTUACAO.sub(" ", resultado)
    return _ESPACOS.sub(" ", resultado).strip()


# --------------------------------------------------------------------------
# EAN / GTIN
# --------------------------------------------------------------------------

_COMPRIMENTOS_VALIDOS = (8, 12, 13, 14)


def normalizar_ean(valor: object) -> str | None:
    """Devolve o EAN como string de dígitos, ou None se não der para aproveitar.

    Existe por causa de um problema concreto de planilha: o Excel trata código
    de barras como número, e o que chega aqui é '7891234567890.0' ou
    '7.89123E+12'. Gravar isso cru corrompe a base em silêncio.
    """
    if valor is None:
        return None

    if isinstance(valor, float):
        # 7891234567890.0 -> "7891234567890"; notação científica também resolve
        if valor != valor or valor in (float("inf"), float("-inf")):  # NaN/inf
            return None
        texto = f"{valor:.0f}"
    elif isinstance(valor, int) and not isinstance(valor, bool):
        texto = str(valor)
    else:
        texto = str(valor).strip()
        if not texto:
            return None
        # "7.89123E+12" vindo de planilha
        if re.fullmatch(r"\d+(?:\.\d+)?[eE][+-]?\d+", texto):
            try:
                texto = f"{float(texto):.0f}"
            except (ValueError, OverflowError):
                return None
        # "7891234567890.0"
        elif re.fullmatch(r"\d+\.0+", texto):
            texto = texto.split(".")[0]

    digitos = re.sub(r"\D", "", texto)
    if not digitos:
        return None

    # Códigos internos de balança e afins são curtos demais para ser GTIN.
    if len(digitos) < 8:
        return None
    if len(digitos) > 14:
        return None

    # EAN-13 exportado sem o zero à esquerda é o caso mais comum de "quase lá".
    if len(digitos) not in _COMPRIMENTOS_VALIDOS:
        alvo = next((c for c in _COMPRIMENTOS_VALIDOS if c > len(digitos)), None)
        if alvo is None:
            return None
        digitos = digitos.zfill(alvo)

    return digitos


def validar_ean(ean: str | None) -> bool:
    """Confere o dígito verificador do GTIN (EAN-8/12/13/14)."""
    if not ean or not ean.isdigit() or len(ean) not in _COMPRIMENTOS_VALIDOS:
        return False

    corpo, verificador = ean[:-1], int(ean[-1])
    # Da direita para a esquerda no corpo, pesos alternam 3 e 1.
    soma = 0
    for posicao, digito in enumerate(reversed(corpo)):
        peso = 3 if posicao % 2 == 0 else 1
        soma += int(digito) * peso

    esperado = (10 - (soma % 10)) % 10
    return esperado == verificador
