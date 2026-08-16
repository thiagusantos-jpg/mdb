"""Orquestração: liga coletores ao banco.

Fica fora do `cli.py` para poder ser testado sem simular linha de comando, e
fora dos coletores para manter a regra de que coletor não escreve no banco.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import config
from .collectors.base import ColetaAnomala, ErroDeColeta, OfertaBruta
from .collectors.planilha import ler_planilha
from .collectors.vtex import ColetorVtex
from .normalize.quantidades import extrair_do_titulo, preco_por_unidade
from .storage import repositories as repo

SLUG_PLANILHA = "planilha"


@dataclass
class ResultadoImportacao:
    execucao_id: int
    produtos_novos: int
    produtos_atualizados: int
    precos_registrados: int
    descartadas: list[tuple[int, str]]
    ean_sem_digito_valido: int
    colunas_detectadas: dict[str, str]


@dataclass
class ResultadoColeta:
    execucao_id: int
    fonte: str
    ofertas: int
    com_ean: int


def importar_planilha(conn: sqlite3.Connection, caminho: Path | str) -> ResultadoImportacao:
    """F01 — carrega a planilha de referência.

    Diferença central em relação à v1: o preço da planilha não é gravado como
    uma coluna sobrescrevível em `produtos`. Ele entra na série histórica como
    mais uma observação, de uma fonte chamada 'planilha'. A referência passa a
    ser derivada do histórico (repositories.preco_referencia).
    """
    leitura = ler_planilha(caminho)

    fonte_id = repo.obter_ou_criar_fonte(
        conn, SLUG_PLANILHA, "Planilha de referência", "planilha"
    )
    loja_id = repo.obter_ou_criar_loja(conn, fonte_id, "referencia", "Planilha de referência")
    execucao_id = repo.iniciar_execucao(conn, fonte_id, "import")

    novos = atualizados = 0
    registros: list[tuple] = []

    try:
        for linha in leitura.linhas:
            produto_id, criado = repo.upsert_produto(
                conn,
                nome=linha.nome,
                ean=linha.ean,
                marca=linha.marca,
                categoria=linha.categoria,
                quantidade=linha.quantidade,
                unidade=linha.unidade,
            )
            if criado:
                novos += 1
            else:
                atualizados += 1

            registros.append(
                (
                    produto_id,
                    loja_id,
                    None,
                    linha.preco_centavos,
                    preco_por_unidade(linha.preco_centavos, linha.quantidade, linha.unidade),
                )
            )

        gravados = repo.registrar_precos(conn, registros)
        conn.commit()
        repo.concluir_execucao(conn, execucao_id, gravados)
    except Exception as erro:
        conn.rollback()
        repo.falhar_execucao(conn, execucao_id, f"{type(erro).__name__}: {erro}")
        raise

    return ResultadoImportacao(
        execucao_id=execucao_id,
        produtos_novos=novos,
        produtos_atualizados=atualizados,
        precos_registrados=gravados,
        descartadas=leitura.descartadas,
        ean_sem_digito_valido=leitura.ean_sem_digito_valido,
        colunas_detectadas=leitura.colunas_detectadas,
    )


def coletar_vtex(
    conn: sqlite3.Connection,
    slug: str,
    *,
    limite: int | None = None,
    sessao=None,
) -> ResultadoColeta:
    """F02 — coleta uma loja VTEX e grava as ofertas brutas.

    Nada de pareamento aqui: a oferta é gravada como veio. O vínculo com a base
    é responsabilidade da fase 4, e mantê-lo separado é o que permite rodar um
    matcher melhor sobre dados já coletados, sem repetir a coleta.
    """
    if slug not in config.FONTES_VTEX:
        conhecidas = ", ".join(sorted(config.FONTES_VTEX)) or "(nenhuma)"
        raise ValueError(f"fonte VTEX desconhecida: {slug}. Configuradas: {conhecidas}")

    fonte_cfg = config.FONTES_VTEX[slug]
    fonte_id = repo.obter_ou_criar_fonte(conn, fonte_cfg.slug, fonte_cfg.nome, "varejo_online")
    loja_id = repo.obter_ou_criar_loja(
        conn, fonte_id, fonte_cfg.codigo_loja, fonte_cfg.nome_loja
    )
    execucao_id = repo.iniciar_execucao(conn, fonte_id, "catalogo")

    try:
        coletor = ColetorVtex(fonte_cfg, sessao=sessao, limite=limite)
        ofertas = coletor.coletar()
    except ColetaAnomala as erro:
        # Health check do PRD §5.1: falha ALTO, não grava vazio em silêncio.
        repo.falhar_execucao(conn, execucao_id, str(erro))
        raise
    except ErroDeColeta as erro:
        repo.falhar_execucao(conn, execucao_id, f"{type(erro).__name__}: {erro}")
        raise

    try:
        persistiveis = [
            repo.OfertaPersistivel(
                loja_id=loja_id,
                titulo_original=o.titulo_original,
                preco_centavos=o.preco_centavos,
                ean_informado=o.ean_informado,
                preco_de_centavos=o.preco_de_centavos,
                disponivel=o.disponivel,
                url=o.url,
                payload_bruto=o.payload_bruto,
            )
            for o in ofertas
        ]
        gravadas = repo.inserir_ofertas(conn, execucao_id, persistiveis)
        conn.commit()
        repo.concluir_execucao(conn, execucao_id, gravadas)
    except Exception as erro:
        conn.rollback()
        repo.falhar_execucao(conn, execucao_id, f"{type(erro).__name__}: {erro}")
        raise

    return ResultadoColeta(
        execucao_id=execucao_id,
        fonte=slug,
        ofertas=gravadas,
        com_ean=sum(1 for o in ofertas if o.ean_informado),
    )


def resumo_oferta(oferta: OfertaBruta) -> str:
    """Linha legível de uma oferta — usada pelo CLI."""
    quantidade, unidade, _ = extrair_do_titulo(oferta.titulo_original)
    medida = f" [{quantidade:g}{unidade}]" if quantidade and unidade else ""
    return f"{oferta.titulo_original}{medida}"
