"""Conexão e migração do banco."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .. import config

SCHEMA = Path(__file__).with_name("schema.sql")


def conectar(caminho: Path | str | None = None) -> sqlite3.Connection:
    """Abre uma conexão já configurada.

    `PRAGMA foreign_keys = ON` é obrigatório em TODA conexão: no SQLite a
    checagem vem desligada por padrão, e sem ela as foreign keys do schema são
    decorativas — foi um dos defeitos apontados na revisão do PRD v1.
    """
    destino = Path(caminho) if caminho is not None else config.DB_PATH
    if destino.parent != Path("") and str(destino) != ":memory:":
        destino.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(destino))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def migrar(conn: sqlite3.Connection) -> None:
    """Aplica o schema. Idempotente — todo objeto usa IF NOT EXISTS."""
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    # executescript faz commit implícito, mas o PRAGMA de FK é por conexão e
    # o script o redefine; garantimos o estado final.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


@contextmanager
def sessao(caminho: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Conexão migrada, com commit no sucesso e rollback no erro."""
    conn = conectar(caminho)
    try:
        migrar(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def backup(conn: sqlite3.Connection, destino: Path | str) -> None:
    """Cópia consistente com o banco em uso (PRD v2 §7).

    A série histórica leva meses para ser reconstruída, se é que pode. Isso
    aqui deve rodar desde o primeiro dia, para fora da máquina.
    """
    alvo = Path(destino)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(alvo)) as saida:
        conn.backup(saida)
