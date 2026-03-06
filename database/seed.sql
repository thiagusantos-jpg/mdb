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
  '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMqJqhcanFp8.e5bLJiX/VH.am',
  'Administrador',
  'admin'
) ON CONFLICT (email) DO NOTHING;

-- Usuário comum de teste
-- Senha: user123
INSERT INTO users (id, email, password_hash, nome, role)
VALUES (
  'a0000000-0000-0000-0000-000000000002',
  'user@dubairro.com',
  '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uAnc/W6Ca',
  'Usuário Teste',
  'user'
) ON CONFLICT (email) DO NOTHING;
