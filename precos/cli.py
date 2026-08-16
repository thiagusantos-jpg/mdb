"""Linha de comando.

    python -m precos.cli migrar
    python -m precos.cli importar planilha.csv
    python -m precos.cli coletar mambo --limite 200
    python -m precos.cli status
    python -m precos.cli referencia --produto 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, servicos
from .collectors.base import ColetaAnomala, ErroDeColeta
from .collectors.planilha import ErroDePlanilha
from .normalize.precos import formatar_brl
from .storage import db
from .storage import repositories as repo


def _cmd_migrar(args: argparse.Namespace) -> int:
    conn = db.conectar(args.banco)
    try:
        db.migrar(conn)
        tabelas = [
            linha["name"]
            for linha in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        print(f"Banco pronto em {args.banco or config.DB_PATH}")
        print(f"Tabelas: {', '.join(tabelas)}")
    finally:
        conn.close()
    return 0


def _cmd_importar(args: argparse.Namespace) -> int:
    with db.sessao(args.banco) as conn:
        try:
            resultado = servicos.importar_planilha(conn, args.arquivo)
        except ErroDePlanilha as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 2

    print(f"Colunas detectadas: {resultado.colunas_detectadas}")
    print(
        f"Produtos: {resultado.produtos_novos} novos, "
        f"{resultado.produtos_atualizados} atualizados"
    )
    print(f"Preços registrados no histórico: {resultado.precos_registrados}")

    if resultado.ean_sem_digito_valido:
        print(
            f"aviso: {resultado.ean_sem_digito_valido} EAN(s) com dígito verificador "
            "inválido — importados, mas confira a planilha"
        )
    if resultado.descartadas:
        print(f"\n{len(resultado.descartadas)} linha(s) descartada(s):")
        for numero, motivo in resultado.descartadas[:20]:
            print(f"  linha {numero}: {motivo}")
        if len(resultado.descartadas) > 20:
            print(f"  ... e mais {len(resultado.descartadas) - 20}")
    return 0


def _cmd_coletar(args: argparse.Namespace) -> int:
    with db.sessao(args.banco) as conn:
        try:
            resultado = servicos.coletar_vtex(conn, args.fonte, limite=args.limite)
        except ColetaAnomala as erro:
            # Falha alto de propósito: coletar quase nada é sintoma, não resultado.
            print(f"COLETA ANÔMALA: {erro}", file=sys.stderr)
            return 3
        except ErroDeColeta as erro:
            print(f"erro de coleta: {erro}", file=sys.stderr)
            return 2
        except ValueError as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 2

    print(f"Fonte {resultado.fonte}: {resultado.ofertas} ofertas gravadas")
    print(f"Com EAN: {resultado.com_ean} ({resultado.com_ean * 100 // max(resultado.ofertas, 1)}%)")
    print(f"Execução #{resultado.execucao_id}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    with db.sessao(args.banco) as conn:
        produtos = repo.contar_produtos(conn)
        ofertas = repo.contar_ofertas(conn)
        execucoes = repo.ultimas_execucoes(conn, args.limite)

    print(f"Produtos na base: {produtos}")
    print(f"Ofertas coletadas: {ofertas}\n")

    if not execucoes:
        print("Nenhuma execução registrada.")
        return 0

    print(f"{'#':>4}  {'FONTE':<12} {'TIPO':<10} {'STATUS':<10} {'ITENS':>6}  INÍCIO")
    for linha in execucoes:
        print(
            f"{linha['id']:>4}  {(linha['fonte'] or '—'):<12} {linha['tipo']:<10} "
            f"{linha['status']:<10} {linha['itens_coletados']:>6}  {linha['iniciada_em']}"
        )
        if linha["erro"]:
            print(f"        erro: {linha['erro'][:160]}")
    return 0


def _cmd_referencia(args: argparse.Namespace) -> int:
    with db.sessao(args.banco) as conn:
        dados = repo.preco_referencia(conn, args.produto, dias=args.dias)

    if not dados["amostras"]:
        print(f"Produto {args.produto}: sem amostras nos últimos {args.dias} dias.")
        return 1

    print(f"Produto {args.produto} — últimos {args.dias} dias")
    print(f"  amostras: {dados['amostras']}")
    print(f"  mínimo:   {formatar_brl(dados['minimo'])}")
    print(f"  mediana:  {formatar_brl(dados['mediana'])}")
    print(f"  p25:      {formatar_brl(dados['p25'])}")
    if dados["amostras"] < 5:
        print("  aviso: menos de 5 amostras — referência fraca (PRD v2 §2.1)")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="precos", description="Monitor de preços de supermercado (fases 1 e 2)"
    )
    parser.add_argument("--banco", type=Path, default=None, help="caminho do arquivo SQLite")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("migrar", help="cria/atualiza o schema").set_defaults(func=_cmd_migrar)

    p_importar = sub.add_parser("importar", help="importa planilha de referência (.csv/.xlsx)")
    p_importar.add_argument("arquivo", type=Path)
    p_importar.set_defaults(func=_cmd_importar)

    p_coletar = sub.add_parser("coletar", help="coleta o catálogo público de uma loja VTEX")
    p_coletar.add_argument("fonte", choices=sorted(config.FONTES_VTEX) or None)
    p_coletar.add_argument("--limite", type=int, default=None, help="máximo de ofertas")
    p_coletar.set_defaults(func=_cmd_coletar)

    p_status = sub.add_parser("status", help="últimas execuções e totais")
    p_status.add_argument("--limite", type=int, default=10)
    p_status.set_defaults(func=_cmd_status)

    p_ref = sub.add_parser("referencia", help="preço de referência derivado do histórico")
    p_ref.add_argument("--produto", type=int, required=True)
    p_ref.add_argument("--dias", type=int, default=90)
    p_ref.set_defaults(func=_cmd_referencia)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
