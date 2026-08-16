# Monitor de preços — fases 1 e 2

Implementação do [PRD v2](../docs/PRD_PRECOS_V2.md). Cobre os dois primeiros
passos do roadmap:

| Fase | Entrega | Status |
|------|---------|--------|
| 1 | Schema + importador de planilha (F01) | ✅ |
| 2 | Coletor VTEX via JSON público (F02) | ✅ |
| 3 | Série histórica + referência derivada | ✅ (veio junto: a planilha já entra como observação) |
| 4 | Matching com portão de unidade | ⬜ |
| 5 | Calibração do threshold | ⬜ |
| 6 | Alertas | ⬜ |

## Instalação

```bash
pip install -r precos/requirements.txt      # requests; openpyxl só para .xlsx
```

O CSV é lido com a biblioteca padrão — sem nenhuma dependência.

## Uso

```bash
python -m precos.cli migrar                                   # cria o banco
python -m precos.cli importar precos/exemplos/planilha_exemplo.csv
python -m precos.cli coletar mambo --limite 200
python -m precos.cli status
python -m precos.cli referencia --produto 1 --dias 90
```

O caminho do banco vem de `PRECOS_DB` (padrão: `sistema_precos.db`) ou de `--banco`.

## Formato da planilha

Obrigatórias: uma coluna de **nome** e uma de **preço**. As demais são opcionais.

```csv
EAN,Nome,Preco_Referencia,Marca,Categoria
7891234567895,Leite Italac Integral 1L,5.99,Italac,Laticínios
,Banana Prata kg,7.90,,Hortifruti
```

O nome da coluna de preço aceita `Preco_Referencia` **e** `Preco` — o PRD v1
divergia de si mesmo nesse ponto, então as duas planilhas existem por aí.
Cabeçalhos acentuados (`Código`, `Descrição`, `Valor`) também são reconhecidos.

Linha com preço ilegível é **descartada com motivo registrado**, nunca gravada.

## Decisões que divergem do PRD v1

**Sem pandas.** `pd.read_csv` infere tipos, e é essa inferência que transforma
o EAN `7891234567890` no float `7891234567890.0` e códigos longos em notação
científica. O módulo `csv` lê tudo como texto, que é o que se quer aqui, e
evita ~50 MB de dependência para ler alguns milhares de linhas. `normalizar_ean`
ainda assim conserta os dois formatos, porque planilha vinda de Excel chega
corrompida de qualquer jeito.

**Sem Playwright/BeautifulSoup na fase 2.** Lojas VTEX expõem
`/api/catalog_system/pub/products/search`, com produto, SKU, EAN e oferta por
seller. Os seletores da v1 (`vtex-product-summary-2-x-container`) carregam a
versão do componente no nome: uma atualização de tema muda o número e o scraper
passa a devolver lista vazia sem erro.

**O preço da planilha não é uma coluna sobrescrevível.** Ele entra na série
histórica como mais uma observação, de uma fonte chamada `planilha`. A
referência é derivada (mediana/p25 de 90 dias) — reimportar acumula histórico
em vez de destruí-lo.

## Health check

Coleta abaixo de `piso_esperado` levanta `ColetaAnomala`, a execução é marcada
como `failed` e o CLI sai com código 3. É deliberado: o modo de falha mais
perigoso do sistema é coletar zero item em silêncio e parecer "não teve oferta
hoje".

## Antes de rodar contra um varejista

O host padrão e o comportamento do endpoint **não foram verificados contra a
loja real** — o ambiente onde isso foi escrito não tem saída de rede para esses
domínios. Antes de usar em rotina:

1. Confirme o endpoint com uma requisição manual.
2. Leia o `robots.txt` e os Termos de Uso do varejista.
3. Ajuste `PRECOS_USER_AGENT` para algo que identifique você de verdade.
4. Mantenha `PRECOS_PAUSA_S` alto e o volume baixo.

## Testes

```bash
python -m unittest discover -s precos -t .
```

95 testes, biblioteca padrão apenas, sem rede — o coletor recebe a sessão HTTP
por injeção e os testes usam respostas fixas.
