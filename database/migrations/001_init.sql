-- ============================================================
-- DUBAIRRO MVP — Schema Inicial
-- Migration: 001_init.sql
-- ============================================================

-- Tabela de usuários (auth simples em dev, migra para Supabase Auth em prod)
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  nome TEXT,
  role TEXT DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Tabela de uploads de Excel
CREATE TABLE IF NOT EXISTS data_uploads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  original_name TEXT NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  row_count INTEGER DEFAULT 0,
  error_message TEXT,
  uploaded_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Tabela de dados brutos (JSONB flexível para Excel)
CREATE TABLE IF NOT EXISTS raw_data (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  upload_id UUID REFERENCES data_uploads(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  row_index INTEGER NOT NULL,
  data JSONB NOT NULL,
  synced_to_mobne BOOLEAN DEFAULT false,
  synced_at TIMESTAMPTZ,
  source TEXT DEFAULT 'upload' CHECK (source IN ('upload', 'mobne')),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Tabela de logs de sincronização com Mobne
CREATE TABLE IF NOT EXISTS sync_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sync_type TEXT NOT NULL CHECK (sync_type IN ('manual', 'automatic')),
  status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
  entity TEXT,  -- 'Produto', 'Nota', 'Empresa', etc.
  records_synced INTEGER DEFAULT 0,
  last_sync TIMESTAMPTZ,
  next_sync TIMESTAMPTZ,
  details JSONB,
  error_message TEXT,
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);

-- Indexes para performance
CREATE INDEX IF NOT EXISTS idx_raw_data_user_id ON raw_data(user_id);
CREATE INDEX IF NOT EXISTS idx_raw_data_upload_id ON raw_data(upload_id);
CREATE INDEX IF NOT EXISTS idx_raw_data_synced ON raw_data(synced_to_mobne);
CREATE INDEX IF NOT EXISTS idx_raw_data_source ON raw_data(source);
CREATE INDEX IF NOT EXISTS idx_data_uploads_user_id ON data_uploads(user_id);
CREATE INDEX IF NOT EXISTS idx_data_uploads_status ON data_uploads(status);
CREATE INDEX IF NOT EXISTS idx_sync_logs_status ON sync_logs(status);

-- Trigger para atualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE TRIGGER data_uploads_updated_at
  BEFORE UPDATE ON data_uploads
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
