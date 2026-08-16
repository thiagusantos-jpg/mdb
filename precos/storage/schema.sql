PRAGMA foreign_keys = ON;   -- OBRIGATÓRIO em toda conexão: no SQLite vem desligado por padrão
PRAGMA journal_mode = WAL;

-- ============================================================
-- DIMENSÕES
-- ============================================================

CREATE TABLE IF NOT EXISTS fontes (
    id            INTEGER PRIMARY KEY,
    slug          TEXT NOT NULL UNIQUE,
    nome          TEXT NOT NULL,
    tipo          TEXT NOT NULL CHECK (tipo IN ('marketplace', 'varejo_online', 'planilha', 'orgao_publico')),
    ativa         INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0, 1)),
    criada_em     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Preço é sempre um fato de (produto, LOJA, momento) — nunca um atributo do produto.
CREATE TABLE IF NOT EXISTS lojas (
    id             INTEGER PRIMARY KEY,
    fonte_id       INTEGER NOT NULL REFERENCES fontes(id) ON DELETE CASCADE,
    codigo_externo TEXT,
    nome           TEXT NOT NULL,
    cidade         TEXT,
    uf             TEXT CHECK (uf IS NULL OR length(uf) = 2),
    latitude       REAL,
    longitude      REAL,
    criada_em      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (fonte_id, codigo_externo)
);

-- id surrogate: hortifruti/granel não têm EAN e precisam existir na base.
-- quantidade+unidade são CAMPOS, não texto — é o que viabiliza o portão de unidade do matcher.
CREATE TABLE IF NOT EXISTS produtos (
    id            INTEGER PRIMARY KEY,
    ean           TEXT,
    nome          TEXT NOT NULL,
    marca         TEXT,
    categoria     TEXT,
    quantidade    REAL,                    -- sempre normalizada para a unidade base
    unidade       TEXT CHECK (unidade IS NULL OR unidade IN ('g', 'ml', 'un')),
    monitorado    INTEGER NOT NULL DEFAULT 1 CHECK (monitorado IN (0, 1)),
    criado_em     TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Índice único PARCIAL: garante EAN único quando existe, e permite N produtos sem EAN.
CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_ean
    ON produtos(ean) WHERE ean IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_produtos_marca ON produtos(marca);
CREATE INDEX IF NOT EXISTS ix_produtos_monitorado ON produtos(monitorado) WHERE monitorado = 1;

-- ============================================================
-- EXECUÇÕES — mesmo padrão de sync_logs em database/migrations/001_init.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS execucoes (
    id              INTEGER PRIMARY KEY,
    fonte_id        INTEGER REFERENCES fontes(id) ON DELETE SET NULL,
    tipo            TEXT NOT NULL CHECK (tipo IN ('watchlist', 'catalogo', 'manual', 'import')),
    status          TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    itens_coletados INTEGER NOT NULL DEFAULT 0,
    erro            TEXT,
    iniciada_em     TEXT NOT NULL DEFAULT (datetime('now')),
    concluida_em    TEXT
);

CREATE INDEX IF NOT EXISTS ix_execucoes_fonte_data ON execucoes(fonte_id, iniciada_em DESC);

-- ============================================================
-- FATO: OFERTAS BRUTAS (append-only, imutável)
-- Sem FK para produtos: a oferta é gravada SEMPRE, mesmo sem pareamento.
-- payload_bruto permite re-parsear histórico sem re-coletar.
-- ============================================================

CREATE TABLE IF NOT EXISTS ofertas (
    id                INTEGER PRIMARY KEY,
    execucao_id       INTEGER NOT NULL REFERENCES execucoes(id) ON DELETE CASCADE,
    loja_id           INTEGER NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
    titulo_original   TEXT NOT NULL,
    ean_informado     TEXT,
    preco_centavos    INTEGER NOT NULL CHECK (preco_centavos > 0),
    preco_de_centavos INTEGER CHECK (preco_de_centavos IS NULL OR preco_de_centavos > 0),
    disponivel        INTEGER NOT NULL DEFAULT 1 CHECK (disponivel IN (0, 1)),
    url               TEXT,
    payload_bruto     TEXT,
    coletada_em       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_ofertas_execucao  ON ofertas(execucao_id);
CREATE INDEX IF NOT EXISTS ix_ofertas_loja_data ON ofertas(loja_id, coletada_em DESC);
CREATE INDEX IF NOT EXISTS ix_ofertas_ean       ON ofertas(ean_informado) WHERE ean_informado IS NOT NULL;

-- ============================================================
-- PAREAMENTO
-- ============================================================

-- Cada confirmação humana vira memória permanente. É a camada que faz o sistema
-- ficar mais preciso com o uso, em vez de repetir o mesmo fuzzy para sempre.
CREATE TABLE IF NOT EXISTS produto_aliases (
    id             INTEGER PRIMARY KEY,
    produto_id     INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
    fonte_id       INTEGER NOT NULL REFERENCES fontes(id) ON DELETE CASCADE,
    titulo_norm    TEXT NOT NULL,
    confirmado_por TEXT NOT NULL DEFAULT 'humano',
    criado_em      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (fonte_id, titulo_norm)
);

CREATE TABLE IF NOT EXISTS matches (
    id         INTEGER PRIMARY KEY,
    oferta_id  INTEGER NOT NULL REFERENCES ofertas(id) ON DELETE CASCADE,
    produto_id INTEGER REFERENCES produtos(id) ON DELETE SET NULL,
    metodo     TEXT NOT NULL CHECK (metodo IN ('alias', 'ean', 'fuzzy')),
    score      REAL CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
    status     TEXT NOT NULL CHECK (status IN ('auto', 'revisar', 'confirmado', 'rejeitado')),
    criado_em  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (oferta_id)
);

CREATE INDEX IF NOT EXISTS ix_matches_produto ON matches(produto_id);
CREATE INDEX IF NOT EXISTS ix_matches_revisar ON matches(status) WHERE status = 'revisar';

-- ============================================================
-- FATO: SÉRIE HISTÓRICA — o ativo do projeto
-- ============================================================

CREATE TABLE IF NOT EXISTS precos_coletados (
    id                INTEGER PRIMARY KEY,
    produto_id        INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
    loja_id           INTEGER NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
    oferta_id         INTEGER REFERENCES ofertas(id) ON DELETE SET NULL,
    preco_centavos    INTEGER NOT NULL CHECK (preco_centavos > 0),
    preco_por_unidade REAL,               -- R$/kg ou R$/L: torna embalagens comparáveis
    coletado_em       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_precos_produto_data ON precos_coletados(produto_id, coletado_em DESC);
CREATE INDEX IF NOT EXISTS ix_precos_loja_data    ON precos_coletados(loja_id, coletado_em DESC);

-- ============================================================
-- ALERTAS — alert_key UNIQUE é o que impede spam
-- ============================================================

CREATE TABLE IF NOT EXISTS alertas (
    id                  INTEGER PRIMARY KEY,
    alert_key           TEXT NOT NULL UNIQUE,
    produto_id          INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
    loja_id             INTEGER NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
    oferta_id           INTEGER REFERENCES ofertas(id) ON DELETE SET NULL,
    preco_centavos      INTEGER NOT NULL,
    referencia_centavos INTEGER NOT NULL,
    economia_pct        REAL NOT NULL,
    economia_centavos   INTEGER NOT NULL,
    enviado_em          TEXT NOT NULL DEFAULT (datetime('now')),
    feedback            TEXT CHECK (feedback IS NULL OR feedback IN ('util', 'irrelevante', 'errado'))
);

CREATE INDEX IF NOT EXISTS ix_alertas_produto_data ON alertas(produto_id, enviado_em DESC);
