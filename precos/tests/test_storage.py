"""Schema e repositórios — os defeitos do banco da v1, agora como teste."""

import tempfile
import unittest
from pathlib import Path

from ..storage import db
from ..storage import repositories as repo


class BaseComBanco(unittest.TestCase):
    def setUp(self):
        self.conn = db.conectar(":memory:")
        db.migrar(self.conn)
        self.fonte_id = repo.obter_ou_criar_fonte(self.conn, "mambo", "Mambo", "varejo_online")
        self.loja_id = repo.obter_ou_criar_loja(self.conn, self.fonte_id, "principal", "Mambo")

    def tearDown(self):
        self.conn.close()


class TestSchema(BaseComBanco):
    def test_foreign_keys_ligadas(self):
        """Sem o PRAGMA, as FKs do schema são decorativas (defeito §2.4 da revisão)."""
        ativo = self.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(ativo, 1)

    def test_fk_realmente_barra(self):
        import sqlite3

        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO lojas (fonte_id, nome) VALUES (99999, 'fantasma')"
            )

    def test_migrar_e_idempotente(self):
        db.migrar(self.conn)
        db.migrar(self.conn)
        self.assertEqual(repo.contar_produtos(self.conn), 0)

    def test_varios_produtos_sem_ean(self):
        """A PRIMARY KEY em `ean` da v1 excluía hortifruti, açougue e granel."""
        repo.upsert_produto(self.conn, nome="Banana Prata kg")
        repo.upsert_produto(self.conn, nome="Tomate Italiano kg")
        self.assertEqual(repo.contar_produtos(self.conn), 2)

    def test_ean_duplicado_barrado(self):
        a, criado_a = repo.upsert_produto(self.conn, nome="Leite 1L", ean="7891234567895")
        b, criado_b = repo.upsert_produto(self.conn, nome="Leite Italac 1L", ean="7891234567895")
        self.assertEqual(a, b)
        self.assertTrue(criado_a)
        self.assertFalse(criado_b)
        self.assertEqual(repo.contar_produtos(self.conn), 1)

    def test_preco_nao_positivo_barrado(self):
        import sqlite3

        produto_id, _ = repo.upsert_produto(self.conn, nome="Leite 1L")
        with self.assertRaises(sqlite3.IntegrityError):
            repo.registrar_preco(
                self.conn, produto_id=produto_id, loja_id=self.loja_id, preco_centavos=0
            )


class TestOfertas(BaseComBanco):
    def test_oferta_sem_produto_conhecido_e_gravada(self):
        """A FK da v1 descartava exatamente o caso interessante: produto novo."""
        execucao_id = repo.iniciar_execucao(self.conn, self.fonte_id, "catalogo")
        gravadas = repo.inserir_ofertas(
            self.conn,
            execucao_id,
            [
                repo.OfertaPersistivel(
                    loja_id=self.loja_id,
                    titulo_original="Produto Nunca Visto 500g",
                    preco_centavos=1290,
                    ean_informado="9999999999994",
                )
            ],
        )
        self.assertEqual(gravadas, 1)
        self.assertEqual(repo.contar_ofertas(self.conn, execucao_id), 1)

    def test_lote_vazio(self):
        execucao_id = repo.iniciar_execucao(self.conn, self.fonte_id, "catalogo")
        self.assertEqual(repo.inserir_ofertas(self.conn, execucao_id, []), 0)


class TestExecucoes(BaseComBanco):
    def test_ciclo_de_vida(self):
        execucao_id = repo.iniciar_execucao(self.conn, self.fonte_id, "catalogo")
        repo.concluir_execucao(self.conn, execucao_id, 42)
        linha = repo.ultimas_execucoes(self.conn, 1)[0]
        self.assertEqual(linha["status"], "completed")
        self.assertEqual(linha["itens_coletados"], 42)
        self.assertIsNotNone(linha["concluida_em"])

    def test_falha_registra_motivo(self):
        execucao_id = repo.iniciar_execucao(self.conn, self.fonte_id, "catalogo")
        repo.falhar_execucao(self.conn, execucao_id, "coleta anômala: 0 itens")
        linha = repo.ultimas_execucoes(self.conn, 1)[0]
        self.assertEqual(linha["status"], "failed")
        self.assertIn("anômala", linha["erro"])


class TestPrecoReferencia(BaseComBanco):
    def test_derivado_do_historico(self):
        """Substitui a coluna `preco_referencia` sobrescrita da v1."""
        produto_id, _ = repo.upsert_produto(self.conn, nome="Leite 1L", ean="7891234567895")
        for centavos in (599, 649, 629, 579, 899, 619):
            repo.registrar_preco(
                self.conn, produto_id=produto_id, loja_id=self.loja_id, preco_centavos=centavos
            )

        dados = repo.preco_referencia(self.conn, produto_id)
        self.assertEqual(dados["amostras"], 6)
        self.assertEqual(dados["minimo"], 579)
        self.assertEqual(dados["mediana"], 619)
        self.assertEqual(dados["p25"], 599)

    def test_sem_historico(self):
        produto_id, _ = repo.upsert_produto(self.conn, nome="Item novo")
        dados = repo.preco_referencia(self.conn, produto_id)
        self.assertEqual(dados["amostras"], 0)
        self.assertIsNone(dados["mediana"])

    def test_historico_preserva_todas_as_observacoes(self):
        """O INSERT OR REPLACE da v1 descartava o preço anterior a cada import."""
        produto_id, _ = repo.upsert_produto(self.conn, nome="Leite 1L", ean="7891234567895")
        for centavos in (599, 649, 579):
            repo.registrar_preco(
                self.conn, produto_id=produto_id, loja_id=self.loja_id, preco_centavos=centavos
            )
        total = self.conn.execute(
            "SELECT COUNT(*) FROM precos_coletados WHERE produto_id = ?", (produto_id,)
        ).fetchone()[0]
        self.assertEqual(total, 3)


class TestBackup(unittest.TestCase):
    def test_backup_gera_copia_utilizavel(self):
        with tempfile.TemporaryDirectory() as pasta:
            origem = Path(pasta) / "origem.db"
            destino = Path(pasta) / "backup" / "copia.db"

            conn = db.conectar(origem)
            db.migrar(conn)
            repo.upsert_produto(conn, nome="Leite 1L", ean="7891234567895")
            conn.commit()
            db.backup(conn, destino)
            conn.close()

            self.assertTrue(destino.exists())
            copia = db.conectar(destino)
            self.assertEqual(repo.contar_produtos(copia), 1)
            copia.close()


if __name__ == "__main__":
    unittest.main()
