# PRD v2.0 — Sistema de Monitoramento e Comparação de Preços

**Status:** Proposta de correção da v1.0
**Base:** [`REVIEW_PRD_PRECOS.md`](./REVIEW_PRD_PRECOS.md)
**Stack:** Python 3.10+ / SQLite (mantido da v1.0)

Este documento reescreve as partes da v1.0 que a revisão apontou como quebradas. O que não aparece
aqui permanece como estava.

---

## 1. Mudanças de conceito em relação à v1.0

| v1.0 | v2.0 | Por quê |
|------|------|---------|
| Preço de referência é uma coluna digitada na planilha | Preço de referência é **derivado do histórico** (mediana / p25 dos últimos 90 dias); a planilha vira uma fonte a mais | Régua estática envelhece em dias |
| Tabela por fonte (`ofertas_ifood`) | `fontes` + `lojas` + `ofertas` genéricas | A v1 já nasce precisando de 2 fontes |
| Oferta e pareamento na mesma linha | Coleta bruta imutável + `matches` separado | Permite re-rodar o matcher sobre dados já coletados |
| Corte único de similaridade em 85 | Três faixas + **portão de unidade** + aliases aprendidos | Fuzzy sozinho casa 200g com 500g |
| Alerta sem regra definida | Regra explícita com 4 condições e cooldown | O F05 da v1 estava em branco |
| Preços em `REAL` | Inteiro em centavos | Erro de ponto flutuante em agregações |

---

## 2. Esquema de banco de dados

> Validado: este DDL foi executado sem erros em **SQLite 3.45.1**, e as constraints abaixo foram
> testadas — o índice único parcial aceita múltiplos produtos sem EAN, rejeita EAN duplicado, e a
> FK é efetivamente aplicada com `PRAGMA foreign_keys = ON`.

```sql
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
```

### 2.1 Preço de referência derivado

Substitui a coluna `preco_referencia` da v1. Mediana e p25 dos últimos 90 dias, via window function
(testado — o SQLite não tem `MEDIAN` nativo):

```sql
WITH r AS (
  SELECT preco_centavos,
         PERCENT_RANK() OVER (ORDER BY preco_centavos) AS pr
  FROM precos_coletados
  WHERE produto_id = :produto_id
    AND coletado_em >= datetime('now', '-90 days')
)
SELECT MAX(CASE WHEN pr <= 0.50 THEN preco_centavos END) AS mediana_centavos,
       MAX(CASE WHEN pr <= 0.25 THEN preco_centavos END) AS p25_centavos
FROM r;
```

**Regra de referência:** use a mediana como régua principal. Se houver menos de 5 amostras nos 90
dias, caia para o preço da planilha do usuário — e marque o alerta como "referência fraca".

---

## 3. Motor de pareamento (F04 revisado)

### 3.1 Pipeline em 5 estágios

```
título bruto da fonte
   │
   ├─ 1. NORMALIZAR ──────► minúsculas, sem acentos, abreviações expandidas
   │                        ("int"→integral, "ref"→refrigerante), ruído removido
   │
   ├─ 2. EXTRAIR ─────────► marca | quantidade | unidade viram campos
   │                        "Leite Italac Integral 1L" → {italac, 1000, ml}
   │
   ├─ 3. ALIAS ───────────► produto_aliases[fonte, titulo_norm] → HIT? fim (determinístico)
   │
   ├─ 4. EAN ─────────────► ean_informado casa em produtos.ean → HIT? fim
   │
   └─ 5. FUZZY ───────────► candidatos = produtos da MESMA MARCA (blocking)
                            score = fuzz.token_set_ratio(nome_sem_quantidade)
                            ⛔ PORTÃO: quantidade convertida DEVE bater — senão rejeita,
                               por mais alto que seja o score
```

**O portão de unidade é uma regra dura, não um peso.** É ele — e não o threshold — que resolve o
falso positivo 200g × 500g apontado na seção 6 da v1. Um score de 97 entre "Leite Italac 1L" e
"Leite Italac 200ml" é rejeitado sem apelação.

### 3.2 Três faixas em vez de um corte

| Faixa | Ação | `matches.status` |
|-------|------|------------------|
| score ≥ `LIMITE_AUTO` **e** unidade bate | aceita e pode alertar | `auto` |
| `LIMITE_REVISAR` ≤ score < `LIMITE_AUTO` | entra na fila de revisão manual, **não alerta** | `revisar` |
| score < `LIMITE_REVISAR` | descarta | `rejeitado` |

Toda confirmação na fila de revisão grava um registro em `produto_aliases` — o título nunca mais
passa pelo fuzzy. Com o tempo, o estágio 3 absorve a maior parte do tráfego e o sistema fica
determinístico onde importa.

### 3.3 Como calibrar os limites (não chute)

O `85` da v1 é um número escolhido a priori. O procedimento mínimo:

1. Colete ~200 pares reais (título da fonte × produto da base), variados: mesma marca com gramaturas
   diferentes, marcas concorrentes do mesmo item, sabores/variantes.
2. Rotule à mão: match / não-match.
3. Rode a pipeline variando o limite e meça **precisão** e **recall** em cada ponto.
4. Escolha `LIMITE_AUTO` pelo alvo de precisão, não pelo de recall.

**Alvo sugerido: precisão ≥ 98% no aceite automático.** Em alerta de compra, falso positivo custa
muito mais que falso negativo — perder uma oferta é chato; mandar o usuário comprar a coisa errada
destrói a confiança no sistema inteiro. Guarde o conjunto rotulado no repositório e rode-o como
teste de regressão sempre que mexer no matcher.

---

## 4. Motor de alertas (F05 — a regra que faltava)

Um alerta é disparado quando **todas** as condições valem:

| # | Condição | Motivo |
|---|----------|--------|
| 1 | `preco ≤ referencia × (1 − DESCONTO_MIN_PCT)` | o desconto percentual que importa |
| 2 | `economia_centavos ≥ ECONOMIA_MIN_CENTAVOS` | evita alertar R$ 0,30 num item de R$ 3,00 |
| 3 | `preco ≥ referencia × PISO_SANIDADE` | queda de 95% é erro de parsing, não oferta |
| 4 | `match.status IN ('auto','confirmado')` | nunca alerta sobre pareamento não verificado |
| 5 | nenhum alerta com o mesmo `alert_key` na janela de cooldown | impede repetir a cada execução |
| 6 | `oferta.disponivel = 1` | não alerta produto esgotado |

```python
alert_key = sha256(f"{produto_id}|{loja_id}|{preco_centavos // 50}")  # faixas de R$ 0,50
```

Agrupar o preço em faixas no `alert_key` evita que uma oscilação de um centavo seja tratada como
oferta nova.

**Parâmetros iniciais sugeridos** (todos em arquivo de config, para ajuste sem deploy):

| Parâmetro | Valor inicial |
|-----------|---------------|
| `DESCONTO_MIN_PCT` | 15% |
| `ECONOMIA_MIN_CENTAVOS` | 200 (R$ 2,00) |
| `PISO_SANIDADE` | 0,30 (rejeita quedas > 70%) |
| `COOLDOWN_HORAS` | 48 |
| `MAX_ALERTAS_DIA` | 10 |

`MAX_ALERTAS_DIA` é um teto rígido: se estourar, envie um resumo único em vez de mensagens
separadas. Fadiga de alerta mata este produto mais rápido que scraper quebrado.

### 4.1 Frete e pedido mínimo

Comparar preço de item entre um marketplace com entrega e um supermercado é comparação incompleta:
R$ 2,00 de economia com R$ 9,99 de taxa é prejuízo de R$ 7,99. Duas saídas, em ordem de esforço:

- **Mínimo:** a mensagem de alerta declara a taxa de entrega e o pedido mínimo da loja, e diz
  explicitamente "vale se você já for pedir outros itens".
- **Correto:** avaliar no nível de **cesta** — acumular ofertas por loja e só alertar quando a soma
  das economias superar a taxa de entrega.

Comece pelo mínimo; a cesta depende de ter várias fontes ativas.

---

## 5. Estrutura de código

```
precos/
├── cli.py                    # ponto de entrada: importar / coletar / parear / alertar / revisar
├── config.py                 # thresholds e parâmetros de alerta (sem números mágicos no código)
├── storage/
│   ├── schema.sql            # o DDL da seção 2
│   ├── db.py                 # conexão (com PRAGMA foreign_keys=ON), migrations
│   └── repositories.py       # queries nomeadas; nenhum SQL solto pelo resto do código
├── normalize/
│   ├── precos.py             # parse_preco_brl() — UMA função, com testes
│   ├── quantidades.py        # parse_quantidade() → (valor, unidade) normalizados
│   └── texto.py              # normalizar_titulo(), expandir_abreviacoes()
├── collectors/
│   ├── base.py               # interface comum: coletar() -> list[OfertaBruta]
│   ├── vtex.py               # cliente do JSON público (serve Mambo, Pão de Açúcar, …)
│   └── planilha.py           # importador CSV/XLSX
├── matching/
│   ├── pipeline.py           # os 5 estágios da seção 3.1
│   ├── aliases.py            # leitura/escrita de produto_aliases
│   └── avaliacao.py          # precisão/recall sobre o conjunto rotulado
├── alerts/
│   ├── regras.py             # as 6 condições da seção 4
│   └── telegram.py           # envio
└── tests/
    ├── test_precos.py        # "R$ 1.234,56", "R$ 12,34", "R$ 9,90/kg", NBSP, centavos em <sup>
    ├── test_quantidades.py   # "1L", "200g", "2x500ml", "1,5 L", "kg"
    └── fixtures/pares.csv    # conjunto rotulado (seção 3.3)
```

**Três regras que evitam a maior parte dos bugs da v1:**

1. **Parsing em um lugar só.** `parse_preco_brl` e `parse_quantidade` são funções únicas, testadas,
   usadas por todos os coletores. Na v1 o parsing de preço estava inline no scraper — cada nova
   fonte reescreveria (e reintroduziria) o mesmo bug.
2. **Coletor não escreve no banco.** Retorna `list[OfertaBruta]`; quem persiste é o repositório.
   Torna cada coletor testável sem banco.
3. **Nenhum limiar hardcoded.** Todos em `config.py` — porque a seção 3.3 vai mudá-los depois de
   medir.

### 5.1 Health check obrigatório do coletor

O modo de falha mais perigoso é coletar zero itens em silêncio e parecer "não teve oferta hoje":

```python
if len(ofertas) < PISO_ESPERADO[fonte]:
    registrar_execucao(status='failed', erro=f'coleta anômala: {len(ofertas)} itens')
    notificar_operador()      # falha ALTO, não grava vazio
    return
```

---

## 6. Roadmap

| # | Entrega | Depende de |
|---|---------|-----------|
| 1 | Schema + importador de planilha (F01) | — |
| 2 | Coletor VTEX de 1 varejista, via JSON público (F02) | 1 |
| 3 | Série histórica + preço de referência derivado | 2 |
| 4 | Pipeline de matching com portão de unidade + aliases (F04) | 3 |
| 5 | Conjunto rotulado + calibração dos limites | 4 |
| 6 | Alertas com regra, dedupe e cooldown (F05) | 5 |
| 7 | Segundo varejista | 4 |
| 8 | iFood — apenas pelos caminhos legítimos da revisão, §5.1 | 6 |

Os passos 1–7 entregam um comparador de preços de varejo completo e defensável. O iFood deixa de ser
pré-requisito e vira incremento.

---

## 7. Backup

A série histórica é o ativo do projeto e leva meses para ser reconstruída — se é que pode. Cópia
automatizada do arquivo `.db` para fora da máquina desde o primeiro dia, usando a API de backup
online do SQLite (`sqlite3.Connection.backup()`), que é consistente com o banco em uso.
