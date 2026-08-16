"""Parâmetros do sistema.

Regra do PRD v2 (§5): nenhum limiar hardcoded pelo código. Tudo vive aqui e é
sobrescrevível por variável de ambiente, porque a calibração da fase 5 vai
mudar esses números.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Banco
# --------------------------------------------------------------------------

DB_PATH = Path(os.environ.get("PRECOS_DB", "sistema_precos.db"))


# --------------------------------------------------------------------------
# Coleta
# --------------------------------------------------------------------------

# Identificação honesta. Não se passe por navegador.
USER_AGENT = os.environ.get(
    "PRECOS_USER_AGENT",
    "monitor-precos/0.2 (uso pessoal; contato: configure PRECOS_USER_AGENT)",
)

TIMEOUT_S = float(os.environ.get("PRECOS_TIMEOUT_S", "20"))

# Pausa entre requisições. Volume baixo é parte do trato de usar um endpoint
# público: não transforme a coleta em carga para o varejista.
PAUSA_ENTRE_REQUISICOES_S = float(os.environ.get("PRECOS_PAUSA_S", "1.0"))

MAX_TENTATIVAS = int(os.environ.get("PRECOS_MAX_TENTATIVAS", "4"))
BACKOFF_BASE_S = float(os.environ.get("PRECOS_BACKOFF_BASE_S", "2.0"))

# A busca pública da VTEX devolve no máximo 50 itens por requisição
# (janela _from.._to inclusiva) e recusa deslocamentos muito grandes.
VTEX_TAMANHO_PAGINA = 50
VTEX_OFFSET_MAXIMO = 2500


@dataclass(frozen=True)
class FonteVtex:
    """Uma loja VTEX monitorada."""

    slug: str
    nome: str
    base_url: str
    nome_loja: str
    codigo_loja: str = "principal"
    # Health check (§5.1 do PRD): abaixo disso a coleta é tratada como falha,
    # não como "não teve produto hoje".
    piso_esperado: int = 20
    # Categorias a varrer (fq=C:/<id>/). Vazio = busca geral.
    categorias: tuple[str, ...] = field(default_factory=tuple)


# Mambo roda em VTEX — confirmado na revisão (docs/REVIEW_PRD_PRECOS.md §5.1).
# Confirme o host e o comportamento do endpoint com uma requisição manual antes
# de rodar em volume, e leia o robots.txt e os Termos de Uso do varejista.
FONTES_VTEX: dict[str, FonteVtex] = {
    "mambo": FonteVtex(
        slug="mambo",
        nome="Mambo Supermercados",
        base_url=os.environ.get("PRECOS_MAMBO_URL", "https://www.mambo.com.br"),
        nome_loja="Mambo (loja online)",
    ),
}


# --------------------------------------------------------------------------
# Importação de planilha
# --------------------------------------------------------------------------

# O PRD v1 divergia de si mesmo: a spec do F01 definia "Preco_Referencia" e o
# código lia "Preco". Aceitamos os dois, além das variações óbvias.
COLUNAS_EAN = ("ean", "codigo_barras", "gtin", "codigo")
COLUNAS_NOME = ("nome", "produto", "descricao", "titulo")
COLUNAS_PRECO = ("preco_referencia", "preco", "valor", "preco_venda")
COLUNAS_MARCA = ("marca", "fabricante")
COLUNAS_CATEGORIA = ("categoria", "secao", "departamento")
