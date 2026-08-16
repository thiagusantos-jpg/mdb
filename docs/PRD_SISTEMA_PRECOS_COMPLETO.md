# PRD — Sistema de Monitoramento e Comparação de Preços de Supermercado

**Versão:** 2.1 (consolidado)
**Status:** Fases 1–3 implementadas e testadas · Fases 4–8 especificadas, não implementadas
**Stack:** Python 3.10+ / SQLite (padrão) — deploy em Vercel é decisão em aberto (§9)
**Documentos-fonte:** [`REVIEW_PRD_PRECOS.md`](./REVIEW_PRD_PRECOS.md) (crítica da v1) · [`PRD_PRECOS_V2.md`](./PRD_PRECOS_V2.md) (design v2) · código em [`precos/`](../precos/)

Este arquivo é o ponto único de referência: reúne visão de produto, decisões de arquitetura, o que já roda de verdade e o que ainda é só especificação — organizado pelas fases do roadmap.

---

## 1. Visão e objetivo

Monitorar, comparar e alertar sobre produtos de supermercado com preço abaixo do praticado no varejo tradicional ou abaixo de uma planilha de referência do usuário — com leitura por EAN quando disponível e pareamento textual quando não.

**Origem:** um PRD v1.0 trazia essa visão mas com um defeito estrutural (schema sem histórico de preços — só sabia comparar contra um número digitado) e um item fora do que este projeto está disposto a fazer (contornar proteção antibot do iFood). A v2 corrige o schema e resolve a coleta por fontes legítimas; este documento consolida v2 + implementação.

## 2. Decisões de arquitetura confirmadas

| Decisão | Escolha | Onde foi definida |
|---|---|---|
| Linguagem/armazenamento | Python 3.10+ / SQLite | Mantido por escolha explícita do usuário sobre a v1 |
| Coleta do iFood | **Não** via bypass de antibot | Recusa registrada em `REVIEW_PRD_PRECOS.md` §5.1 |
| Fonte de varejo | Catálogo público VTEX (JSON), não scraping de DOM | `REVIEW_PRD_PRECOS.md` §5.1(a) |
| Preço de referência | Derivado do histórico (mediana/p25 de 90 dias), não campo digitado | `PRD_PRECOS_V2.md` §2.1 |
| Deploy web/Vercel | **Em aberto** — Node vs. Python vs. híbrido | §9 deste documento |

## 3. Arquitetura de dados

Preço é sempre um fato de **(produto, loja, momento)** — nunca um atributo do produto. Esse princípio único evita a maior parte dos defeitos encontrados na v1 (ver §10).

```
fontes ──┬── lojas ──┬── ofertas (bruto, imutável, append-only)
         │           │       │
         │           │       └── matches (produto_id, score, método, status)
         │           │
         │           └── precos_coletados (fato histórico, centavos)
         │
produtos ─┴── produto_aliases (título da fonte → produto, aprendido)

execucoes  (log de toda coleta/importação — sucesso ou falha)
alertas    (alert_key único, cooldown)
```

Schema completo, comentado e **validado** (executado em SQLite 3.45.1, constraints testadas): [`PRD_PRECOS_V2.md` §2](./PRD_PRECOS_V2.md#2-esquema-de-banco-de-dados).

---

## 4. Roadmap por fases

| # | Fase | Entrega | Status |
|---|------|---------|--------|
| 1 | Schema + importador de planilha | F01 | ✅ Implementado e testado |
| 2 | Coletor VTEX | F02 | ✅ Implementado e testado |
| 3 | Série histórica + referência derivada | — | ✅ Implementado (veio junto das fases 1–2) |
| 4 | Matching com portão de unidade | F04 | ⬜ Especificado, não implementado |
| 5 | Calibração do threshold | — | ⬜ Especificado, não implementado |
| 6 | Alertas (regra + dedupe + cooldown) | F05 | ⬜ Especificado, não implementado |
| 7 | Segundo varejista | — | ⬜ Não iniciado |
| 8 | iFood (só caminhos legítimos) | F03 | ⬜ Bloqueado até 4–6 existirem |
| 9 | Deploy web (Vercel) | — | ⬜ Decisão de stack em aberto |

Os passos 1–7 entregam um comparador de preços de varejo completo e defensável **sem depender do iFood**. O iFood é incremento, não pré-requisito.

---

## Fase 1 — Schema + importador de planilha (F01) ✅

**Status:** implementado, testado, exercitado ponta a ponta.

### O que faz

- Cria e migra o banco (`precos.cli migrar`), com `PRAGMA foreign_keys = ON` obrigatório em toda conexão — no SQLite essa checagem vem desligada por padrão, e sem ela as FKs do schema seriam decorativas (era exatamente o defeito da v1).
- Lê planilha `.csv` (biblioteca padrão) ou `.xlsx` (openpyxl opcional) e importa produtos + preços.
- Aceita tanto `Preco_Referencia` quanto `Preco` como nome de coluna — a v1 divergia de si mesma nesse ponto (spec dizia um, código lia outro).
- Normaliza EAN corrompido pelo Excel (`7891234567890.0`, notação científica) e valida o dígito verificador GTIN.
- Extrai quantidade/unidade do próprio nome do produto (`"Leite Italac 1L"` → 1000ml).
- Linha com preço ilegível é **descartada com motivo registrado**, nunca gravada como `NaN` silencioso.
- Produto sem EAN (hortifruti, açougue, granel) é aceito normalmente — a v1 usava `ean` como `PRIMARY KEY` e excluía esses itens.

### Módulos

```
precos/
├── config.py                  parâmetros (nada hardcoded no código)
├── storage/
│   ├── schema.sql              DDL — extraído e validado do PRD v2
│   ├── db.py                    conexão, migração idempotente, backup
│   └── repositories.py          todo o SQL do sistema, num só lugar
├── normalize/
│   ├── precos.py                parse_preco_brl() → centavos (int)
│   ├── quantidades.py           parse_quantidade(), extrair_do_titulo()
│   └── texto.py                 normalizar_titulo(), normalizar_ean(), validar_ean()
└── collectors/
    └── planilha.py               leitura CSV/XLSX
```

### Uso

```bash
python -m precos.cli migrar
python -m precos.cli importar precos/exemplos/planilha_exemplo.csv
```

### Verificação feita

- Planilha de 7 linhas importada de ponta a ponta: 6 produtos criados (incluindo 2 sem EAN — banana e tomate), 1 linha com preço vazio descartada com motivo.
- Reimportar a mesma planilha: **0 produtos novos, histórico acumula** (2 observações por produto) em vez de sobrescrever — o defeito central da v1 (`INSERT OR REPLACE` apagando o preço anterior) está corrigido e coberto por teste (`test_storage.py::test_historico_preserva_todas_as_observacoes`).
- Quantidades extraídas corretamente: `2x400g` → 800g, `5kg` → 5000g, `kg` (produto a peso) → 1000g.

---

## Fase 2 — Coletor VTEX (F02) ✅

**Status:** implementado, testado offline (sem tocar rede real). **Não verificado contra loja real** (ver §8).

### Por que VTEX e não scraping de DOM

Mambo roda VTEX (confirmado via pesquisa: `mambo.myvtex.com`). O endpoint público `/api/catalog_system/pub/products/search` devolve JSON estruturado com produto, SKU, EAN e oferta por seller. Os seletores da v1 (`vtex-product-summary-2-x-container`) carregam a versão do componente no nome — uma atualização de tema muda o número e o scraper passa a devolver lista vazia **sem erro**.

### O que faz

- Pagina o catálogo por janela inclusiva (`_from`/`_to`), com deduplicação entre páginas.
- Backoff exponencial em erro de rede ou 5xx/429; falha alto (não repete) em 4xx que não seja 429.
- Cada SKU de um produto (embalagens diferentes) vira uma oferta separada — colapsar aqui reintroduziria a confusão de gramatura pelo outro lado.
- `preco_de` só é gravado quando é desconto real (`ListPrice > Price`) — evita "desconto fantasma" quando de=por.
- **Health check obrigatório**: coleta abaixo de `piso_esperado` levanta `ColetaAnomala` e a execução é marcada `failed`. É o modo de falha mais perigoso do sistema — coletar zero item em silêncio e parecer "não teve oferta hoje" — tratado como erro, não como resultado.
- Sessão HTTP é injetável por construtor, o que mantém os testes 100% offline.

### Uso

```bash
python -m precos.cli coletar mambo --limite 200
```

### Verificação feita

30 testes cobrindo: extração de campos, preço-de sem desconto real ignorado, SKUs distintos viram ofertas distintas, paginação (janela inclusiva, limite respeitado, dedupe entre páginas, categorias geram consultas separadas), health check (coleta vazia e coleta abaixo do piso falham alto), e tratamento de HTTP (404 não repete, 500 repete e desiste após `MAX_TENTATIVAS`, 206 é tratado como sucesso — resposta normal da busca paginada VTEX).

Fluxo ponta a ponta com sessão HTTP simulada (3 produtos, incluindo um com desconto real): 3 ofertas gravadas, 3 com EAN, execução registrada como `completed`.

---

## Fase 3 — Série histórica + referência derivada ✅

**Status:** implementado (veio embutido nas fases 1 e 2, não é um passo separado de código).

### O que faz

Substitui a coluna `preco_referencia` sobrescrevível da v1. Toda observação de preço — de planilha ou de coleta — vira uma linha em `precos_coletados` (fato, append-only). A referência é **derivada** por consulta, não armazenada:

```sql
WITH r AS (
  SELECT preco_centavos, PERCENT_RANK() OVER (ORDER BY preco_centavos) AS pr
  FROM precos_coletados
  WHERE produto_id = :produto_id AND coletado_em >= datetime('now', '-90 days')
)
SELECT MAX(CASE WHEN pr <= 0.50 THEN preco_centavos END) AS mediana,
       MAX(CASE WHEN pr <= 0.25 THEN preco_centavos END) AS p25
FROM r
```

Com menos de 5 amostras em 90 dias, o CLI avisa explicitamente "referência fraca".

### Uso

```bash
python -m precos.cli referencia --produto 1 --dias 90
```

### Verificação feita

Testado com 6 observações de preço (599, 649, 629, 579, 899, 619 centavos): mediana = 619, p25 = 599, mínimo = 579 — os três valores batendo com o cálculo manual.

---

## Fase 4 — Matching com portão de unidade (F04) ⬜

**Status:** especificado em detalhe no PRD v2, **não implementado**.

### Problema que resolve

O `fuzz.WRatio` da v1, sozinho, pontua alto entre "Leite Italac Integral 1L" e "Leite Italac Integral 200ml" — quase todos os tokens coincidem, e a diferença de quantidade é tratada como só mais um token. É o falso positivo citado no risco 2 da seção 6 do PRD v1.

### Pipeline especificado (5 estágios)

```
título bruto
  → 1. normalizar (minúsculas, sem acento, abreviações expandidas)
  → 2. extrair marca + quantidade + unidade como CAMPOS
  → 3. alias exato (produto_aliases) — decisão humana anterior, determinístico
  → 4. EAN exato
  → 5. fuzzy com blocking por marca + PORTÃO DE UNIDADE (regra dura, não peso)
```

Três faixas de decisão, não um corte único: aceite automático / fila de revisão manual / rejeição. Toda revisão manual confirmada vira alias permanente — o sistema fica mais preciso com o uso.

**Já implementado e testado que a fase 4 vai consumir:** `extrair_do_titulo()` em `precos/normalize/quantidades.py` já separa quantidade do texto residual — é o dado que falta ao matcher da v1. O teste `test_quantidades.py::test_o_falso_positivo_do_prd` já prova a peça central: os títulos residuais de "Leite 1L" e "Leite 200ml" ficam idênticos, mas as quantidades extraídas ficam diferentes — é exatamente o par (texto igual, quantidade diferente) que o portão da fase 4 vai barrar.

**Falta:** a lógica de blocking + fuzzy + as três faixas de decisão + leitura/escrita de `produto_aliases` e `matches`.

Detalhamento completo: [`PRD_PRECOS_V2.md` §3](./PRD_PRECOS_V2.md#3-motor-de-pareamento-f04-revisado).

---

## Fase 5 — Calibração do threshold ⬜

**Status:** especificado, não implementado. Depende da fase 4 existir.

### Procedimento

1. Rotular ~200 pares reais (match / não-match) à mão.
2. Rodar a pipeline variando o limite, medir precisão e recall em cada ponto.
3. Escolher `LIMITE_AUTO` pelo alvo de precisão — **≥ 98%** sugerido.

Por quê: em alerta de compra, falso positivo custa muito mais que falso negativo. Perder uma oferta é chato; mandar o usuário comprar a coisa errada destrói a confiança no sistema. O 85 da v1 era um número escolhido sem medição.

Detalhamento: [`PRD_PRECOS_V2.md` §3.3](./PRD_PRECOS_V2.md#33-como-calibrar-os-limites-não-chute).

---

## Fase 6 — Alertas (F05) ⬜

**Status:** especificado, não implementado. **O F05 da v1 estava literalmente em branco** — título "Regra de Alerta:" sem regra abaixo.

### Regra especificada (todas as condições precisam valer)

| # | Condição | Motivo |
|---|---|---|
| 1 | `preco ≤ referencia × (1 − DESCONTO_MIN_PCT)` | desconto percentual mínimo |
| 2 | `economia_centavos ≥ ECONOMIA_MIN_CENTAVOS` | evita alertar R$0,30 num item de R$3,00 |
| 3 | `preco ≥ referencia × PISO_SANIDADE` | queda de 95% é erro de parsing, não oferta |
| 4 | `match.status IN ('auto','confirmado')` | nunca alerta sobre pareamento não verificado |
| 5 | sem alerta com o mesmo `alert_key` no cooldown | impede repetir a cada execução |
| 6 | `oferta.disponivel = 1` | não alerta produto esgotado |

Parâmetros iniciais sugeridos: desconto mínimo 15%, economia mínima R$2,00, piso de sanidade 30% (rejeita quedas >70%), cooldown 48h, teto de 10 alertas/dia.

**Ponto de produto, não só de engenharia:** frete e pedido mínimo precisam entrar na conta — R$2,00 de economia com R$9,99 de entrega é prejuízo. Mínimo viável: declarar a taxa na mensagem do alerta.

Detalhamento: [`PRD_PRECOS_V2.md` §4](./PRD_PRECOS_V2.md#4-motor-de-alertas-f05--a-regra-que-faltava).

---

## Fase 7 — Segundo varejista ⬜

**Status:** não iniciado. Depende da fase 4 (para validar que a modelagem multi-fonte se sustenta).

O coletor VTEX (fase 2) já foi escrito de forma genérica — `ColetorVtex` recebe uma `FonteVtex` como configuração (`precos/config.py`), então adicionar Pão de Açúcar (ou outro varejista VTEX) é, em princípio, configuração nova, não código novo. Isso ainda não foi testado contra um segundo host real.

---

## Fase 8 — iFood (F03) ⬜ — bloqueado por decisão, não por falta de tempo

**Status:** não implementado. **Não será implementado via bypass de proteção antibot** — decisão registrada, não uma pendência técnica.

### O que não será feito

Estratégia de contorno de proteção de acesso do iFood: proxies residenciais rotativos, emulação de sessão, quebra de desafio de CDN. Independente da posição sobre isso, o argumento de engenharia também pesa: é uma dependência que se degrada sozinha, sem aviso, e sem correlação com o seu deploy.

### Caminhos legítimos, em ordem de custo-benefício

1. **Catálogo público VTEX dos varejistas** (fase 2/7) — já cobre boa parte do objetivo de comparação sem tocar no iFood.
2. **Dados de preço originados de NFC-e via SEFAZ** (programa Menor Preço Brasil / Preço da Hora) — EAN, preço, estabelecimento e geolocalização, de nota fiscal real. **Ressalva importante:** não foi encontrada API pública documentada; o acesso divulgado é via portal/app, e bibliotecas de terceiro no GitHub consomem API privada — voltando ao mesmo problema do iFood. Encaminhamento correto é solicitar acesso institucional à SEFAZ/CONFAZ, não engenharia reversa.
3. **Captura assistida pelo próprio usuário** logado, sem automação contra proteção.
4. **Canal oficial de parceiro do iFood** — cobre catálogo próprio, não resolve comparação com concorrentes.

Detalhamento completo: [`REVIEW_PRD_PRECOS.md` §5.1](./REVIEW_PRD_PRECOS.md#51-bloqueios-antibot-no-ifood).

---

## Fase 9 — Deploy web (Vercel) ⬜ — decisão em aberto

**Status:** investigado, **decisão de stack pendente do usuário**.

### O que já se sabe

- O site em produção hoje (`dubairro.vercel.app`) está ligado a **outro repositório** (`thiagusantos-jpg/dubairro`, Python/FastAPI/Streamlit) — não a este (`mdb`). Zero erros de runtime nos últimos 7 dias; produção não recebe deploy desde março/2026 (10 deploys posteriores são previews de dependabot, nenhum mergeado).
- A Vercel documenta oficialmente pool de conexão gerenciado para Postgres via `attachDatabasePool` (`@vercel/functions`) — **só para Node**, usando `pg.Pool`. Não há equivalente documentado para Python; lá a alternativa é abrir conexão manual via `psycopg2` contra a connection string do pooler do Supabase.
- Este repositório já tem o padrão Node + `supabase-js` funcionando em produção (`lib/supabase.js`, `api/*.js`) — é o caminho de menor risco por já estar provado neste código-base.

### As três opções levantadas (decisão não tomada)

| Opção | Reaproveita os 95 testes Python? | Suporte nativo Vercel para pool de conexão | Risco |
|---|---|---|---|
| **Portar tudo para Node** | Não — vira referência de porte | Sim (`attachDatabasePool`) | Baixo (padrão já provado no repo) |
| **Manter Python, deploy Python na Vercel** | Sim | Não — pool manual via `psycopg2` | Médio-alto (sem precedente no repo) |
| **Híbrido** — coleta Python fora da Vercel (ex.: GitHub Actions) + API de leitura fina em Node na Vercel | Sim (coleta) | Sim (a parte que roda na Vercel é só leitura) | Baixo, mas coleta não roda "na Vercel" |

A pergunta foi feita ao usuário e a resposta ficou pendente — retomar antes de iniciar a fase 9.

---

## 5. Estrutura de código atual

```
precos/
├── __init__.py
├── config.py                    parâmetros de coleta, alerta (futuro) e planilha
├── cli.py                       migrar | importar | coletar | status | referencia
├── servicos.py                  orquestração: liga coletores ao banco
├── requirements.txt             requests (obrigatório); openpyxl (opcional, .xlsx)
├── README.md                    guia de uso e decisões que divergem da v1
├── exemplos/
│   └── planilha_exemplo.csv
├── storage/
│   ├── schema.sql
│   ├── db.py
│   └── repositories.py
├── normalize/
│   ├── precos.py
│   ├── quantidades.py
│   └── texto.py
├── collectors/
│   ├── base.py                  contrato Coletor / OfertaBruta / ColetaAnomala
│   ├── planilha.py
│   └── vtex.py
└── tests/                       95 testes, biblioteca padrão, sem rede
    ├── test_precos.py
    ├── test_quantidades.py
    ├── test_texto.py
    ├── test_planilha.py
    ├── test_storage.py
    └── test_vtex.py
```

## 6. Como rodar hoje

```bash
pip install -r precos/requirements.txt        # requests; openpyxl só para .xlsx

python -m precos.cli migrar
python -m precos.cli importar precos/exemplos/planilha_exemplo.csv
python -m precos.cli coletar mambo --limite 200
python -m precos.cli status
python -m precos.cli referencia --produto 1 --dias 90

python -m unittest discover -s precos -t .     # 95 testes
```

## 7. Configuração

Tudo em `precos/config.py`, sobrescrevível por variável de ambiente — nenhum limiar ficará hardcoded no código quando as fases 4–6 forem implementadas:

| Variável | Papel |
|---|---|
| `PRECOS_DB` | caminho do arquivo SQLite |
| `PRECOS_USER_AGENT` | identificação honesta nas requisições — **configure antes de usar em rotina** |
| `PRECOS_TIMEOUT_S`, `PRECOS_PAUSA_S` | timeout e pausa entre requisições ao coletor |
| `PRECOS_MAX_TENTATIVAS`, `PRECOS_BACKOFF_BASE_S` | política de retry |
| `PRECOS_MAMBO_URL` | host da loja VTEX (ver ressalva §8) |

## 8. O que ainda não foi verificado contra o mundo real

- **O host e o comportamento do endpoint VTEX não foram testados contra o Mambo real.** O ambiente onde este sistema foi escrito não tem saída de rede para esses domínios; os 30 testes da fase 2 usam sessão HTTP simulada. Antes de rodar em rotina: requisição manual de confirmação, leitura do `robots.txt` e dos Termos de Uso do varejista, `PRECOS_USER_AGENT` de verdade, volume baixo.
- **A API pública de preços via NFC-e (SEFAZ) não está confirmada como existente/documentada** — tratar como "solicitar acesso institucional", não como integração pronta.

## 9. Erros da v1 corrigidos — resumo rastreável

| Defeito na v1 | Correção na v2 | Coberto por teste |
|---|---|---|
| `ean TEXT PRIMARY KEY` excluía produto sem código de barras | `id` surrogate + índice único parcial em `ean` | `test_storage.py::test_varios_produtos_sem_ean` |
| `INSERT OR REPLACE` apagava o preço anterior | Tabela fato `precos_coletados`, append-only | `test_storage.py::test_historico_preserva_todas_as_observacoes` |
| FK para produto inexistente descartava oferta nova, e nem era aplicada no SQLite | Oferta sempre gravada; FK realmente ligada via `PRAGMA` | `test_storage.py::test_fk_realmente_barra`, `test_oferta_sem_produto_conhecido_e_gravada` |
| Sem quantidade/unidade — causa do falso positivo 200g×500g | Campos `quantidade`/`unidade` extraídos do título | `test_quantidades.py::test_o_falso_positivo_do_prd` |
| `REAL` para dinheiro (erro de ponto flutuante) | Inteiro em centavos | `test_precos.py::test_precisao_de_centavos` |
| Planilha: `row['Preco']` no código vs. `Preco_Referencia` na spec | Aceita as duas grafias de coluna | `test_planilha.py::test_coluna_preco_do_codigo_do_prd` |
| Preço vazio virava `NaN` e sumia em silêncio | Descartado com motivo registrado | `test_planilha.py::test_preco_vazio_e_descartado_com_motivo` |
| EAN corrompido pelo Excel (float, notação científica) | `normalizar_ean()` reconstrói o código | `test_texto.py::test_float_do_excel` |
| Coleta zero itens em silêncio, parece "sem oferta hoje" | `ColetaAnomala` — falha alto abaixo do piso | `test_vtex.py::test_coleta_vazia_falha_alto` |
| Seletor VTEX versionado quebra sem aviso | JSON público estruturado, sem depender de classe CSS | — (mudança de abordagem, não de correção pontual) |
| `fuzz.WRatio` sozinho aceita 200g≈500g | Portão de unidade obrigatório (fase 4, especificado) | ⬜ pendente de implementação |
| F05 sem regra de alerta | 6 condições explícitas + cooldown (fase 6, especificado) | ⬜ pendente de implementação |

---

**Documentos relacionados:** [`REVIEW_PRD_PRECOS.md`](./REVIEW_PRD_PRECOS.md) (crítica completa da v1) · [`PRD_PRECOS_V2.md`](./PRD_PRECOS_V2.md) (design detalhado, schema, pipelines) · [`precos/README.md`](../precos/README.md) (guia de uso do código)
