"""Queries nomeadas. É o único lugar do sistema que escreve SQL."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable, Sequence


# --------------------------------------------------------------------------
# Fontes e lojas
# --------------------------------------------------------------------------


def obter_ou_criar_fonte(conn: sqlite3.Connection, slug: str, nome: str, tipo: str) -> int:
    linha = conn.execute("SELECT id FROM fontes WHERE slug = ?", (slug,)).fetchone()
    if linha:
        return int(linha["id"])
    cursor = conn.execute(
        "INSERT INTO fontes (slug, nome, tipo) VALUES (?, ?, ?)", (slug, nome, tipo)
    )
    return int(cursor.lastrowid)


def obter_ou_criar_loja(
    conn: sqlite3.Connection,
    fonte_id: int,
    codigo_externo: str,
    nome: str,
    *,
    cidade: str | None = None,
    uf: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> int:
    linha = conn.execute(
        "SELECT id FROM lojas WHERE fonte_id = ? AND codigo_externo = ?",
        (fonte_id, codigo_externo),
    ).fetchone()
    if linha:
        return int(linha["id"])
    cursor = conn.execute(
        """INSERT INTO lojas (fonte_id, codigo_externo, nome, cidade, uf, latitude, longitude)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (fonte_id, codigo_externo, nome, cidade, uf, latitude, longitude),
    )
    return int(cursor.lastrowid)


# --------------------------------------------------------------------------
# Produtos
# --------------------------------------------------------------------------


def upsert_produto(
    conn: sqlite3.Connection,
    *,
    nome: str,
    ean: str | None = None,
    marca: str | None = None,
    categoria: str | None = None,
    quantidade: float | None = None,
    unidade: str | None = None,
) -> tuple[int, bool]:
    """Insere ou atualiza um produto. Devolve (id, foi_criado).

    Chaveia por EAN quando existe. Sem EAN (hortifruti, açougue, granel) o
    produto continua tendo lugar na base — era o que a PRIMARY KEY em `ean` da
    v1 impedia — e a deduplicação passa a ser por nome.
    """
    if ean:
        linha = conn.execute("SELECT id FROM produtos WHERE ean = ?", (ean,)).fetchone()
    else:
        linha = conn.execute(
            "SELECT id FROM produtos WHERE ean IS NULL AND lower(nome) = lower(?)", (nome,)
        ).fetchone()

    if linha:
        produto_id = int(linha["id"])
        conn.execute(
            """UPDATE produtos
                  SET nome = ?,
                      marca = COALESCE(?, marca),
                      categoria = COALESCE(?, categoria),
                      quantidade = COALESCE(?, quantidade),
                      unidade = COALESCE(?, unidade),
                      atualizado_em = datetime('now')
                WHERE id = ?""",
            (nome, marca, categoria, quantidade, unidade, produto_id),
        )
        return produto_id, False

    cursor = conn.execute(
        """INSERT INTO produtos (ean, nome, marca, categoria, quantidade, unidade)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ean, nome, marca, categoria, quantidade, unidade),
    )
    return int(cursor.lastrowid), True


def contar_produtos(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) AS n FROM produtos").fetchone()["n"])


# --------------------------------------------------------------------------
# Execuções
# --------------------------------------------------------------------------


def iniciar_execucao(conn: sqlite3.Connection, fonte_id: int | None, tipo: str) -> int:
    cursor = conn.execute(
        "INSERT INTO execucoes (fonte_id, tipo, status) VALUES (?, ?, 'running')",
        (fonte_id, tipo),
    )
    conn.commit()
    return int(cursor.lastrowid)


def concluir_execucao(conn: sqlite3.Connection, execucao_id: int, itens: int) -> None:
    conn.execute(
        """UPDATE execucoes
              SET status = 'completed', itens_coletados = ?, concluida_em = datetime('now')
            WHERE id = ?""",
        (itens, execucao_id),
    )
    conn.commit()


def falhar_execucao(conn: sqlite3.Connection, execucao_id: int, erro: str, itens: int = 0) -> None:
    conn.execute(
        """UPDATE execucoes
              SET status = 'failed', erro = ?, itens_coletados = ?, concluida_em = datetime('now')
            WHERE id = ?""",
        (erro[:2000], itens, execucao_id),
    )
    conn.commit()


def ultimas_execucoes(conn: sqlite3.Connection, limite: int = 10) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT e.id, e.tipo, e.status, e.itens_coletados, e.erro,
                  e.iniciada_em, e.concluida_em, f.slug AS fonte
             FROM execucoes e
             LEFT JOIN fontes f ON f.id = e.fonte_id
            ORDER BY e.iniciada_em DESC
            LIMIT ?""",
        (limite,),
    ).fetchall()


# --------------------------------------------------------------------------
# Ofertas brutas
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OfertaPersistivel:
    loja_id: int
    titulo_original: str
    preco_centavos: int
    ean_informado: str | None = None
    preco_de_centavos: int | None = None
    disponivel: bool = True
    url: str | None = None
    payload_bruto: str | None = None


def inserir_ofertas(
    conn: sqlite3.Connection, execucao_id: int, ofertas: Sequence[OfertaPersistivel]
) -> int:
    """Grava as ofertas brutas em lote.

    A oferta é sempre gravada, mesmo sem pareamento com um produto conhecido —
    inclusive quando o EAN é desconhecido. Perder o dado bruto justamente no
    caso de produto novo era o efeito da foreign key da v1.
    """
    if not ofertas:
        return 0
    conn.executemany(
        """INSERT INTO ofertas (execucao_id, loja_id, titulo_original, ean_informado,
                                preco_centavos, preco_de_centavos, disponivel, url, payload_bruto)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                execucao_id,
                o.loja_id,
                o.titulo_original,
                o.ean_informado,
                o.preco_centavos,
                o.preco_de_centavos,
                1 if o.disponivel else 0,
                o.url,
                o.payload_bruto,
            )
            for o in ofertas
        ],
    )
    return len(ofertas)


def contar_ofertas(conn: sqlite3.Connection, execucao_id: int | None = None) -> int:
    if execucao_id is None:
        linha = conn.execute("SELECT COUNT(*) AS n FROM ofertas").fetchone()
    else:
        linha = conn.execute(
            "SELECT COUNT(*) AS n FROM ofertas WHERE execucao_id = ?", (execucao_id,)
        ).fetchone()
    return int(linha["n"])


# --------------------------------------------------------------------------
# Série histórica
# --------------------------------------------------------------------------


def registrar_preco(
    conn: sqlite3.Connection,
    *,
    produto_id: int,
    loja_id: int,
    preco_centavos: int,
    preco_por_unidade: float | None = None,
    oferta_id: int | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO precos_coletados
               (produto_id, loja_id, oferta_id, preco_centavos, preco_por_unidade)
           VALUES (?, ?, ?, ?, ?)""",
        (produto_id, loja_id, oferta_id, preco_centavos, preco_por_unidade),
    )
    return int(cursor.lastrowid)


def registrar_precos(conn: sqlite3.Connection, registros: Iterable[tuple]) -> int:
    """Lote de (produto_id, loja_id, oferta_id, preco_centavos, preco_por_unidade)."""
    linhas = list(registros)
    if not linhas:
        return 0
    conn.executemany(
        """INSERT INTO precos_coletados
               (produto_id, loja_id, oferta_id, preco_centavos, preco_por_unidade)
           VALUES (?, ?, ?, ?, ?)""",
        linhas,
    )
    return len(linhas)


# Mediana e p25 dos últimos 90 dias. O SQLite não tem MEDIAN nativo; a janela
# resolve. Substitui a coluna `preco_referencia` fixa da v1.
_SQL_REFERENCIA = """
WITH r AS (
  SELECT preco_centavos,
         PERCENT_RANK() OVER (ORDER BY preco_centavos) AS pr
  FROM precos_coletados
  WHERE produto_id = :produto_id
    AND coletado_em >= datetime('now', :janela)
)
SELECT COUNT(*) AS amostras,
       MIN(preco_centavos) AS minimo,
       MAX(CASE WHEN pr <= 0.50 THEN preco_centavos END) AS mediana,
       MAX(CASE WHEN pr <= 0.25 THEN preco_centavos END) AS p25
FROM r
"""


def preco_referencia(
    conn: sqlite3.Connection, produto_id: int, dias: int = 90
) -> dict[str, int | None]:
    linha = conn.execute(
        _SQL_REFERENCIA, {"produto_id": produto_id, "janela": f"-{dias} days"}
    ).fetchone()
    return {
        "amostras": int(linha["amostras"] or 0),
        "minimo": linha["minimo"],
        "mediana": linha["mediana"],
        "p25": linha["p25"],
    }
