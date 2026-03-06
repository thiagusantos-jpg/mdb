-- ============================================================
-- DUBAIRRO MVP — Seed Data (desenvolvimento)
-- Usuário de teste: admin@dubairro.com / admin123
-- ============================================================

-- Usuário admin de teste
-- Senha: admin123 (bcrypt hash gerado com salt 12)
INSERT INTO users (id, email, password_hash, nome, role)
VALUES (
  'a0000000-0000-0000-0000-000000000001',
  'admin@dubairro.com',
  '$2b$12$quD0e3CZV//0FGYJ42KtB.W42qUgT6Nr0DDGXfReCdXNyYMwfxr7W',
  'Administrador',
  'admin'
) ON CONFLICT (email) DO NOTHING;

-- Usuário comum de teste
-- Senha: user123
INSERT INTO users (id, email, password_hash, nome, role)
VALUES (
  'a0000000-0000-0000-0000-000000000002',
  'user@dubairro.com',
  '$2b$12$KnkQfSgwxsK7FJdBtSfUG.WYBd3YQMp8AJLuPu5BDlrxbH7ugYn3q',
  'Usuário Teste',
  'user'
) ON CONFLICT (email) DO NOTHING;
