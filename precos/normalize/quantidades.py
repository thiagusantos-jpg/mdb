"""Extração e normalização de quantidade/unidade.

É o dado que faltava no PRD v1 e a causa raiz do falso positivo 200g × 500g:
sem quantidade como campo, o matcher não tem como recusar o par, por mais alto
que seja o score textual.

Unidades base: 'g' (massa), 'ml' (volume), 'un' (contagem).
"""

from __future__ import annotations

import re

# fator de conversão para a unidade base
_UNIDADES = {
    "kg": (1000.0, "g"),
    "quilo": (1000.0, "g"),
    "quilos": (1000.0, "g"),
    "k": (1000.0, "g"),
    "g": (1.0, "g"),
    "gr": (1.0, "g"),
    "grama": (1.0, "g"),
    "gramas": (1.0, "g"),
    "mg": (0.001, "g"),
    "l": (1000.0, "ml"),
    "lt": (1000.0, "ml"),
    "lts": (1000.0, "ml"),
    "litro": (1000.0, "ml"),
    "litros": (1000.0, "ml"),
    "ml": (1.0, "ml"),
    "un": (1.0, "un"),
    "und": (1.0, "un"),
    "unid": (1.0, "un"),
    "unidade": (1.0, "un"),
    "unidades": (1.0, "un"),
    "dz": (12.0, "un"),
    "duzia": (12.0, "un"),
    "dúzia": (12.0, "un"),
}

_ALTERNATIVAS = "|".join(sorted(_UNIDADES, key=len, reverse=True))

# "2x500ml", "2 x 500 ml", "6x1L"
_MULTIPLO = re.compile(
    rf"(?<![\w,.])(\d+)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*({_ALTERNATIVAS})(?![a-zA-Z])",
    re.IGNORECASE,
)
# "1L", "200 g", "1,5 L"
_SIMPLES = re.compile(
    rf"(?<![\w,.])(\d+(?:[.,]\d+)?)\s*({_ALTERNATIVAS})(?![a-zA-Z])",
    re.IGNORECASE,
)
# "kg" sozinho: produto vendido a peso ("Banana Prata kg") -> 1 kg
_NUA = re.compile(rf"(?<![\w])({_ALTERNATIVAS})(?![a-zA-Z])", re.IGNORECASE)


def _para_float(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", ".")) if "," in texto else float(texto)


def parse_quantidade(texto: str | None) -> tuple[float, str] | None:
    """Converte uma expressão de quantidade para (valor, unidade base).

        >>> parse_quantidade("1L")
        (1000.0, 'ml')
        >>> parse_quantidade("2x500ml")
        (1000.0, 'ml')
        >>> parse_quantidade("kg")
        (1000.0, 'g')

    O multiplicador é resolvido no total ('2x500ml' = 1000ml), que é o que
    permite comparar preço por litro entre embalagens diferentes.
    """
    if not texto:
        return None
    alvo = str(texto).strip()
    if not alvo:
        return None

    casado = _MULTIPLO.search(alvo)
    if casado:
        fator, base = _UNIDADES[casado.group(3).lower()]
        return int(casado.group(1)) * _para_float(casado.group(2)) * fator, base

    casado = _SIMPLES.search(alvo)
    if casado:
        fator, base = _UNIDADES[casado.group(2).lower()]
        return _para_float(casado.group(1)) * fator, base

    casado = _NUA.fullmatch(alvo.strip().lower())
    if casado:
        fator, base = _UNIDADES[casado.group(1).lower()]
        return fator, base

    return None


def extrair_do_titulo(titulo: str | None) -> tuple[float | None, str | None, str]:
    """Separa a quantidade do resto do título.

    Devolve (quantidade, unidade, titulo_sem_quantidade). O terceiro item é o
    que deve alimentar a comparação textual na fase 4 — comparar títulos com a
    gramatura dentro é justamente o que faz 'Leite 1L' pontuar alto contra
    'Leite 200ml'.

        >>> extrair_do_titulo("Leite Italac Integral 1L")
        (1000.0, 'ml', 'Leite Italac Integral')
    """
    if not titulo:
        return None, None, ""

    alvo = str(titulo).strip()

    for padrao in (_MULTIPLO, _SIMPLES):
        casado = padrao.search(alvo)
        if not casado:
            continue
        resultado = parse_quantidade(casado.group(0))
        if resultado is None:
            continue
        restante = (alvo[: casado.start()] + " " + alvo[casado.end() :]).strip()
        restante = re.sub(r"\s{2,}", " ", restante).strip(" -–—,")
        return resultado[0], resultado[1], restante

    # Título terminando em unidade nua: "Banana Prata kg"
    tokens = alvo.split()
    if tokens and tokens[-1].lower() in _UNIDADES:
        fator, base = _UNIDADES[tokens[-1].lower()]
        return fator, base, " ".join(tokens[:-1]).strip(" -–—,")

    return None, None, alvo


def preco_por_unidade(preco_centavos: int, quantidade: float | None, unidade: str | None) -> float | None:
    """Preço por kg, litro ou unidade — em centavos.

    É o que torna embalagens de tamanhos diferentes comparáveis entre si.
    """
    if not quantidade or quantidade <= 0 or not unidade:
        return None
    if unidade in ("g", "ml"):
        return preco_centavos * 1000.0 / quantidade
    return preco_centavos / quantidade
