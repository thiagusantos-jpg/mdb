# Revisão Técnica — PRD "Monitoramento e Comparação de Preços (iFood & Varejo)" v1.0

**Documento revisado:** PRD v1.0 — Sistema de Monitoramento e Comparação de Preços de Supermercado
**Premissa mantida:** Python 3.10+ / SQLite standalone, conforme decisão do autor
**PRD corrigido:** [`PRD_PRECOS_V2.md`](./PRD_PRECOS_V2.md)

---

## Resumo executivo

A ideia é boa e o problema é real: preço de mercearia varia diariamente e ninguém compara à mão.
A arquitetura proposta é razoável em espírito — coletar, normalizar, parear, alertar — e as escolhas
de stack são defensáveis.

Mas o PRD tem **um bloqueio de origem** e **um defeito estrutural** que, sozinho, inviabiliza o
objetivo declarado:

1. **O bloqueio:** o item 1 da seção 6 pede estratégia de contorno da proteção antibot do iFood.
   Não vou desenhar isso — detalhes e alternativas na seção 5 abaixo.
2. **O defeito estrutural:** *o banco não guarda histórico de preços.* `produtos_base` tem uma única
   coluna `preco_referencia`, sobrescrita a cada importação. Sem série temporal não existe "preço
   médio", nem percentil, nem "menor preço dos últimos 90 dias" — e é exatamente isso que distingue
   uma oferta real de um preço normal. O sistema como está descrito só sabe responder "está abaixo
   da planilha que eu digitei", que é uma régua estática e envelhece em dias.

O resto desta revisão detalha esses e outros pontos, em ordem de impacto.

---

## 1. Veredito por feature

| Feature | Veredito | Razão em uma linha |
|---------|----------|--------------------|
| **F01** — Base de referência (planilha) | ✅ Viável | Simples; mas o código do PRD lê `row['Preco']` enquanto a spec define `Preco_Referencia`, e `.xlsx` é prometido e não implementado. |
| **F02** — Extrator de varejo | ✅ Viável, com abordagem trocada | Mambo e Pão de Açúcar rodam VTEX: existe JSON público estruturado. Raspar DOM com seletores versionados é a pior das opções disponíveis. |
| **F03** — Extrator do iFood | ⛔ Bloqueado | Depende de contornar proteção de acesso. Ver seção 5.1. |
| **F04** — Motor de pareamento | ⚠️ Viável, mas inseguro como especificado | `WRatio` + corte em 85 casa "Leite 1L" com "Leite 200ml". Falta portão de unidade e curadoria. |
| **F05** — Motor de alertas | ⚠️ Incompleto | **A regra de alerta está literalmente em branco no PRD** ("Regra de Alerta:" seguido de nada). |

---

## 2. Banco de dados — 9 defeitos no schema da seção 4

### 2.1 `ean TEXT PRIMARY KEY` — chave errada

Três problemas de uma vez:

- **Exclui produtos sem EAN.** Hortifruti, açougue, padaria e granel não têm código de barras de
  produto (têm PLU interno ou etiqueta de balança). Como `PRIMARY KEY` implica `NOT NULL`, esses
  itens simplesmente não cabem na tabela — e são justamente onde a variação de preço é maior.
- **Impede cadastrar antes de conhecer o EAN.** Você não pode registrar "quero monitorar arroz
  Tio João 5kg" e descobrir o código depois.
- **Amarra a identidade do produto ao código.** Quando o mesmo produto aparece com EAN da caixa
  (DUN-14) em uma fonte e EAN da unidade (EAN-13) em outra, viram dois produtos distintos.

**Correção:** `id INTEGER PRIMARY KEY` surrogate + índice único parcial em `ean`
(`CREATE UNIQUE INDEX ... WHERE ean IS NOT NULL`), permitindo múltiplos produtos sem EAN.

### 2.2 Sem histórico de preços — o defeito mais grave

`importar_csv` usa `INSERT OR REPLACE`, que **descarta o preço anterior**. Consequências:

- Impossível calcular preço médio, mediana ou percentil.
- Impossível detectar o padrão "sobe 20% na terça e volta na quinta", que é como boa parte das
  'promoções' de varejo funciona.
- Impossível responder "esse é o menor preço do trimestre?", que é a pergunta que justifica comprar.
- Impossível medir volatilidade por categoria — e sem isso não dá para calibrar a frequência de
  coleta que o próprio item 4 da seção 6 pergunta.

**Correção:** tabela fato append-only `precos_coletados (produto_id, loja_id, preco_centavos,
coletado_em)`. A "referência" deixa de ser um campo digitado e passa a ser derivada: mediana ou p25
móvel dos últimos N dias. A planilha do usuário vira *uma fonte a mais*, não a verdade absoluta.

### 2.3 `ofertas_ifood` amarrada a uma única fonte

O nome da tabela e a coluna `loja_nome TEXT` fixam a modelagem em um marketplace. Mas o próprio PRD
já lista Mambo e Pão de Açúcar no F02 — ou seja, a v1 nasce precisando de uma segunda tabela quase
idêntica, e toda query de comparação vira `UNION`.

**Correção:** `fontes` (iFood, Mambo, planilha, …) + `lojas` (com `fonte_id`, endereço, lat/lon) +
uma tabela de ofertas única com `loja_id`. `loja_nome TEXT` repetido em cada linha também é
denormalização que garante grafias divergentes do mesmo estabelecimento.

### 2.4 A foreign key `ean_identificado REFERENCES produtos_base(ean)` faz mal e não faz o que promete

- **Faz mal:** impede gravar uma oferta cujo EAN ainda não está na base. O dado bruto coletado —
  que custou uma requisição — é perdido justamente no caso mais interessante (produto novo).
- **Não faz o que promete:** no SQLite, a checagem de FK é **desligada por padrão**. Sem
  `PRAGMA foreign_keys = ON` em toda conexão, essa constraint é decorativa. O `db_manager.py` do
  PRD não a liga.

**Correção:** separar coleta de pareamento. A oferta bruta é imutável e sempre gravada; o vínculo
vive em `matches (oferta_id, produto_id, score, metodo, status)`. Isso também permite **rodar o
matcher de novo com algoritmo melhor, sobre dados já coletados**, sem re-raspar nada — o que é o
maior ganho prático dessa mudança.

### 2.5 Sem quantidade e unidade normalizadas

Não existe campo para `quantidade`, `unidade` ou `preco_por_unidade`. Isso é a causa raiz do falso
positivo 200g × 500g citado na própria seção 6 — não dá para resolver no matcher se o dado não
existe no modelo. E sem `R$/kg` e `R$/L`, "mais barato" é uma comparação sem sentido entre embalagens
diferentes.

### 2.6 `REAL` para dinheiro

`preco_referencia REAL`, `preco_promocional REAL`. Ponto flutuante binário não representa `0,10`
exatamente; somas e comparações de igualdade acumulam erro, e `percentual_economia` calculado sobre
isso produz valores como `19.999999999999996%`.

**Correção:** inteiro em centavos (`preco_centavos INTEGER`), formatando só na apresentação.

### 2.7 `historico_alertas` sem chave de deduplicação

A tabela registra o que foi enviado, mas nada impede reenviar. Como a oferta continua ativa na
próxima varredura, **o mesmo alerta dispara a cada execução**. Com coleta de hora em hora, um único
produto em promoção de fim de semana gera algo como 48 mensagens no Telegram. O usuário silencia o
bot no segundo dia e o produto morre aí.

**Correção:** `alert_key TEXT UNIQUE` (hash de produto + loja + faixa de preço) e janela de cooldown
consultada antes do envio.

### 2.8 Zero índices

Nenhum `CREATE INDEX` no schema. As consultas quentes são "ofertas coletadas na última execução",
"histórico de um produto" e "já alertei isso?" — todas viram full scan conforme a tabela fato cresce
(e ela cresce rápido: 10k SKUs × 4 coletas/dia = 14,6M linhas/ano).

### 2.9 Sem tabela de execuções

Não há como saber se a última varredura rodou, quantos itens trouxe ou por que falhou. Quando um
seletor VTEX mudar, o sistema vai coletar zero produtos **em silêncio** e simplesmente parar de
alertar — o modo de falha mais perigoso, porque parece "não teve oferta hoje".

Vale notar que este repositório já resolve esse problema em `database/migrations/001_init.sql`, com
a tabela `sync_logs` (status, `records_synced`, `error_message`, `started_at`/`completed_at`). É o
mesmo padrão, e vale copiar.

---

## 3. Código — análise dos 3 módulos

### 3.1 `db_manager.py`

| Problema | Detalhe |
|----------|---------|
| **Spec × código divergem** | F01 define a coluna `Preco_Referencia`; o código lê `row['Preco']`. Um dos dois está errado — e como está, o import quebra com `KeyError` na planilha que a própria spec descreve. |
| `iterrows()` + execute linha a linha | Lento e sem controle transacional por lote. `executemany` com uma lista de tuplas resolve. |
| Sem validação de EAN | `str(row['EAN'])` aceita qualquer coisa. Excel converte EAN para float (`7891234567890.0`) e para notação científica em códigos longos — corrupção silenciosa. Falta normalizar (strip, zero-padding) e validar dígito verificador GTIN. |
| Sem tratamento de `NaN` | Linha com preço vazio vira `float('nan')`, é gravada, e depois compara `False` em qualquer `<`, sumindo dos alertas sem erro. |
| `.xlsx` prometido, não implementado | F01 diz `.csv` **ou** `.xlsx`; só há `pd.read_csv`. |
| Sem `PRAGMA foreign_keys = ON` | Ver 2.4. |

### 3.2 `scraper_mambo.py`

| Problema | Detalhe |
|----------|---------|
| **Abordagem** | Mambo roda em VTEX (confirmado: a loja responde em `mambo.myvtex.com`). Existe JSON estruturado público em `/api/catalog_system/pub/products/search`, com EAN e preço. Raspar HTML renderizado é mais lento, mais frágil e traz menos dados que a alternativa. Ver 5.1. |
| `wait_for_timeout(4000)` | Espera cega: desperdiça 4s quando carrega em 800ms e falha silenciosamente quando demora 5s. Usar `wait_for_selector` ou aguardar a resposta de rede. |
| Seletores versionados | `vtex-product-summary-2-x-container` carrega a versão do componente no nome. Uma atualização do tema muda o número e o scraper passa a retornar `[]` — sem erro. Obrigatório: se a contagem cair a zero (ou abaixo de um piso), **falhar alto**, não gravar vazio. |
| `productBrand` não é o nome | Essa classe VTEX corresponde à marca, não ao título completo do produto. O nome que alimenta o fuzzy matching sai truncado ou errado. |
| Parsing de preço frágil | `.replace(".", "").replace(",", ".")` funciona em `R$ 1.234,56` e em `R$ 12,34`, mas quebra em variações com espaço não separável (`\xa0`), centavos em `<sup>` separado (padrão comum em temas VTEX) ou preço por peso ("R$ 9,90 /kg"). Precisa ser uma função única e testada. |
| Sem paginação | Coleta só o primeiro lote da categoria. Um supermercado tem milhares de SKUs. |
| Sem rate limiting / retry / User-Agent | Nenhum backoff, nenhum tratamento de erro de rede, nenhuma identificação. |

### 3.3 `matcher.py`

| Problema | Detalhe |
|----------|---------|
| **`WRatio` é quase cego à quantidade** | O núcleo do risco 2 da seção 6. "Leite Integral Italac 1L" × "Leite Integral Italac 200ml" compartilham quase todos os tokens; o score fica bem acima de 85. O algoritmo está funcionando corretamente — a especificação é que está errada ao confiar só nele. |
| Threshold 85 sem medição | Número escolhido a priori. Sem um conjunto rotulado, não há como afirmar se produz 2% ou 30% de falso positivo. |
| Acoplamento silencioso do índice | `resultado` traz o índice dentro de `self.nomes_base`, e o código indexa `self.base[index]`. Só funciona porque as duas listas são construídas na mesma ordem — qualquer filtro futuro em uma delas corrompe o pareamento **sem lançar exceção**. |
| Sem *blocking* | `extractOne` compara contra a base inteira a cada consulta. Com 10k produtos × 10k ofertas são 100M comparações por execução. Filtrar candidatos por marca ou categoria antes reduz isso em ordens de grandeza. |
| Nada é aprendido | Toda execução repete o mesmo fuzzy sobre os mesmos títulos. Uma decisão humana ("esse título é esse produto") deveria ser gravada e reutilizada para sempre. |
| Descarta o score de saída | Retorna `None` para tudo abaixo do corte. Os casos na faixa 70–85 são os mais valiosos para revisão manual e são simplesmente jogados fora. |

---

## 4. Lacunas de produto (não estão no PRD, mas decidem se o sistema serve)

- **A regra de alerta não existe.** O F05 tem o título "Regra de Alerta:" e nenhuma regra abaixo.
  É o coração do produto e ficou em branco.
- **Frete e pedido mínimo não entram na conta.** Um item R$ 2,00 mais barato no iFood com R$ 9,99 de
  taxa de entrega não é economia — é prejuízo de R$ 7,99. Comparação honesta acontece no nível de
  **cesta**, ou o alerta precisa dizer "vale se você já for pedir mais coisas".
- **Nenhuma métrica de sucesso.** Sem alvo de precisão do matching e sem teto de alertas por dia,
  não há como dizer se o sistema está funcionando. Fadiga de alerta mata este produto mais rápido
  que scraper quebrado.
- **Nenhuma checagem de sanidade de preço.** Queda de 95% quase nunca é oferta; quase sempre é erro
  de parsing (pegou centavos como reais, ou o preço do item de 100g no lugar do de 1kg).

---

## 5. Respostas aos 4 riscos da seção 6

### 5.1 Bloqueios antibot no iFood

**Não vou desenhar estratégia de contorno de proteção de acesso** — proxies residenciais rotativos,
emulação de sessão ou quebra de desafio de CDN. É o único ponto deste PRD em que não posso ajudar
como pedido.

Vale registrar também o argumento de engenharia, porque ele é independente do resto: uma coleta que
depende de vencer uma proteção ativa é uma dependência que se degrada sozinha, sem aviso e sem
correlação com o seu deploy. Você passa a manter um sistema cujo modo de falha é "parou de funcionar
na madrugada de domingo e ninguém sabe por quê" — em cima do qual você quer construir decisão de
compra.

**As alternativas legítimas, em ordem de custo-benefício:**

**a) Catálogo público VTEX dos varejistas — o caminho mais forte hoje**

Mambo é VTEX (confirmado). Pão de Açúcar e boa parte do varejo alimentar brasileiro também. Lojas
VTEX expõem um endpoint de busca público:

```
/api/catalog_system/pub/products/search?fq=alternateIds_Ean:7898526205947
/api/catalog_system/pub/products/search?fq=C:/<id-categoria>/&_from=0&_to=49
```

Retorna JSON estruturado com produto, SKUs, EAN e ofertas por seller (preço, preço de lista,
disponibilidade). É **mais estável, mais rápido e mais rico** que raspar DOM, e substitui boa parte
do módulo F02.

> ⚠️ **Confirmar antes de codar.** Não consegui alcançar esses hosts do ambiente onde esta revisão
> foi escrita (egress restrito), então o formato acima vem da documentação da VTEX e não de uma
> chamada real ao Mambo. Valide com uma requisição manual, confira `robots.txt` e os Termos de Uso
> de cada varejista, use `_from`/`_to` respeitando o limite de paginação da plataforma, identifique-se
> num `User-Agent` honesto e mantenha volume baixo.

**b) Dados públicos de preço originados de NFC-e (SEFAZ / Menor Preço Brasil)**

Existe um programa nacional — **Menor Preço Brasil**, do CONFAZ, com origem no Preço da Hora da
SEFAZ-BA — que publica preços praticados extraídos de NFC-e e NF-e reais, com busca por descrição,
marca ou **código de barras**, e ordenação por proximidade geográfica. Em conteúdo, é *exatamente*
o dado que este projeto quer: EAN + preço + estabelecimento + geolocalização, resolvendo de uma vez
os riscos 2 e 3 desta seção.

> ⚠️ **Ressalva honesta, e ela é importante:** eu **não encontrei API pública documentada** para esse
> programa. O acesso oficial divulgado é via portal web e aplicativo; as bibliotecas que circulam no
> GitHub consomem a API *privada* do app. Usar essas bibliotecas te devolve ao mesmo problema do
> iFood, com a agravante de ser dado público que você poderia obter formalmente.
>
> **Encaminhamento recomendado:** solicitar acesso institucional à SEFAZ do seu estado / ao CONFAZ,
> invocando a Lei de Acesso à Informação e a política de dados abertos. É burocrático e leva semanas,
> mas se sair, você recebe uma fonte oficial, estável, gratuita, com EAN e georreferenciada — o que
> torna metade deste PRD desnecessária. Vale o e-mail antes de escrever qualquer scraper.

**c) Captura assistida pelo próprio usuário**

Você, logado e navegando normalmente, exportando seu histórico de pedidos ou o carrinho. Sem
automação contra a proteção. Cobre pouco volume, mas é o caminho legítimo para dados que só existem
na sua sessão.

**d) Canal oficial do iFood (Portal do Parceiro / API de desenvolvedor)**

Se você opera como parceiro, tem acesso programático ao **seu próprio** catálogo e pedidos. Sendo
direto: **isso não resolve o objetivo do PRD**, que é comparar com preços de terceiros. É útil para
o outro lado da moeda — monitorar sua própria competitividade — e não substitui (a) ou (b).

### 5.2 Ausência de EAN no iFood — fuzzy matching é suficiente?

**Não.** Não na forma especificada, e o exemplo dado na própria pergunta (200g × 500g) é a prova:
`WRatio` pontua alto justamente aí, porque quase todos os tokens coincidem e a diferença está em um
número que o algoritmo trata como mais um token.

O que torna confiável é uma pipeline em camadas, com um portão que o fuzzy não pode atravessar:

1. **Normalizar** — minúsculas, sem acentos, expandir abreviações (`int` → integral, `ref` →
   refrigerante), remover ruído de marketing.
2. **Extrair estrutura** — marca, quantidade e unidade viram *campos*, não texto. `"Leite Italac
   Integral 1L"` → `{marca: italac, qtd: 1000, un: ml}`.
3. **Alias exato** — consultar `produto_aliases`: se um humano já confirmou esse título uma vez, a
   resposta é imediata e determinística. **É a camada mais valiosa**, porque converte esforço humano
   em ativo permanente.
4. **EAN exato** — quando disponível, encerra.
5. **Fuzzy com blocking por marca — e portão obrigatório de unidade.** Só compara candidatos da mesma
   marca; e **rejeita qualquer par cuja quantidade convertida não bata**, por mais alto que seja o
   score textual. O portão é uma regra dura, não um peso.

E o corte deixa de ser um número só: **três faixas** — aceite automático, fila de revisão manual,
rejeição. Cada revisão manual vira um alias (camada 3) e nunca mais é revista.

Sobre o 85: é chute até ser medido. Rotule ~200 pares à mão, meça precisão e recall, e escolha o
corte pelo alvo de precisão. Em alerta de compra, falso positivo custa muito mais que falso negativo
— perder uma oferta é chato, mandar o usuário comprar a coisa errada destrói a confiança no sistema.

### 5.3 Dependência de geolocalização

Sem desenhar fixação de sessão no iFood. Nas fontes recomendadas o problema é bem menor:

- **VTEX:** o recorte é por loja / *sales channel* / política comercial — parâmetro documentado,
  não sessão frágil. Você fixa a loja e o preço é determinístico.
- **Dados de NFC-e:** latitude, longitude e raio são parâmetro de consulta por natureza.

O que importa é a **modelagem**, e ela vale para qualquer fonte: preço nunca é um atributo do
produto, é sempre um fato de `(produto, loja, momento)`. Modele `lojas` com coordenadas e endereço
desde o primeiro dia. Um schema que trata preço como coluna de produto — como o da v1 — não tem
conserto incremental quando a segunda região entra.

### 5.4 Frequência de raspagem

Não existe número único certo; existe uma estrutura em dois níveis:

- **Watchlist quente** (dezenas a poucas centenas de SKUs que você realmente compra): checagem
  frequente, poucas requisições, é aqui que ofertas-relâmpago são pegas.
- **Varredura fria** (catálogo inteiro): uma vez por dia, em janela de baixo tráfego, para manter a
  série histórica e descobrir produtos novos.

Com, em todos os casos: orçamento explícito de requisições/dia por fonte, backoff exponencial em
erro, `If-None-Match`/`If-Modified-Since` quando a fonte suportar, e jitter entre requisições.

E a resposta honesta à pergunta "qual a frequência ideal": **você ainda não pode saber.** A
frequência deve derivar da volatilidade medida por categoria — hortifruti muda em horas, mercearia
seca muda em semanas. Isso só é mensurável depois que a tabela de histórico (2.2) existir e tiver
algumas semanas de dados. Comece conservador, meça, ajuste.

---

## 6. Ordem sugerida de implementação

O que dá para entregar sem depender de nada bloqueado, e em ordem de valor por esforço:

1. **Schema corrigido + importador de planilha** (F01) — base para todo o resto.
2. **Coletor VTEX** de um varejista, via JSON público (F02) — primeira fonte real de dados.
3. **Histórico + preço de referência derivado** — a partir daqui o sistema tem memória.
4. **Pipeline de matching com portão de unidade + tabela de aliases** (F04).
5. **Conjunto rotulado e calibração do threshold** — antes de confiar em qualquer alerta.
6. **Alertas com regra explícita, dedupe e cooldown** (F05).
7. **Segundo varejista** — valida que a modelagem multi-fonte se sustenta.
8. **iFood** — somente por (a)/(b)/(c)/(d) da seção 5.1, e depois de tudo acima.

O ponto importante dessa ordem: os passos 1 a 7 entregam um comparador de preços de varejo
funcional e defensável. O iFood deixa de ser pré-requisito e vira um incremento.

---

## 7. Sobre o stack

Mantida a decisão de Python + SQLite standalone. Duas observações práticas, sem propor troca:

- **SQLite aguenta o volume** desse projeto com folga por anos, desde que os índices da seção 2.8
  existam e o modo WAL esteja ligado. Não é o gargalo.
- **O ponto de atenção é durabilidade, não desempenho.** O banco vive em uma máquina só; a série
  histórica é o ativo do projeto e leva meses para ser reconstruída, se é que pode. Backup
  automatizado do arquivo `.db` para fora da máquina, desde o primeiro dia.

---

**Continua em:** [`PRD_PRECOS_V2.md`](./PRD_PRECOS_V2.md) — schema completo, pipeline de matching,
regras de alerta e estrutura de módulos.

## Fontes consultadas

- [Catalog API — VTEX Developers](https://developers.vtex.com/docs/guides/catalog-api-overview)
- [Legacy Search API — VTEX Developers](https://developers.vtex.com/docs/api-reference/search-api)
- [Consult product search information — VTEX Developers](https://developers.vtex.com/docs/guides/consult-product-search-information)
- [Supermercado Mambo migra para VTEX](https://vtex.com/pt-br/blog/historias-de-clientes/supermercado-mambo-migra-para-vtex/)
- [CONFAZ — Aplicativo Menor Preço Brasil](https://www.confaz.fazenda.gov.br/noticias-do-confaz/confaz-lanca-aplicativo-menor-preco-brasil-destinado-a-ajudar-o-cidadao-a-encontrar-os-melhores-valores-no-comercio)
- [Preço da Hora Bahia — Sobre](https://precodahora.ba.gov.br/sobre)
- [SEFAZ-ES — Menor Preço](https://internet.sefaz.es.gov.br/informacoes/menorpreco/duvidas.php)
- [Menor Preço — Nota Fiscal Gaúcha](https://nfg.sefaz.rs.gov.br/site/MenorPreco.aspx)
