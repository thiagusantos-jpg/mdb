# DUBAIRRO MVP — API Reference

## Autenticação

Todos os endpoints protegidos requerem o header:
```
Authorization: Bearer <access_token>
```

---

## Auth

### POST /api/auth/login
Login com email e senha. Retorna JWT tokens.

**Body:** `{ email, password }`

**Response:** `{ success, accessToken, refreshToken, user }`

### GET /api/auth/validate
Valida o token JWT atual.

**Response:** `{ success, user }`

### POST /api/auth/logout
Realiza logout (client-side token removal).

---

## Upload

### POST /api/upload/excel
Faz upload de arquivo Excel (.xlsx, .xls, .csv).

**Headers:**
- `Content-Type: application/octet-stream`
- `X-Filename: nome_do_arquivo.xlsx`
- `X-Original-Name: nome_original.xlsx`

**Body:** Buffer do arquivo

**Response:** `{ success, upload: { id, rowCount, sheetName }, preview, headers }`

---

## Data

### GET /api/data/list
Lista dados com paginação.

**Query:** `page`, `limit`, `upload_id`, `source`

**Response:** `{ success, data, pagination }`

### GET /api/data/search
Busca full-text nos dados JSONB.

**Query:** `q` (mínimo 2 caracteres), `page`, `limit`

**Response:** `{ success, data, pagination, query }`

### GET /api/data/export
Exporta dados como CSV com BOM UTF-8.

**Query:** `upload_id`, `source`

**Response:** CSV file download

---

## Sync (Mobne)

### POST /api/sync/mobne
Dispara sincronização manual com Mobne.

**Body:** `{ entity: "produtos"|"notas"|"empresas", page, pageSize }`

**Response:** `{ success, entity, recordsSynced, paging, syncLogId }`

### GET /api/sync/status
Retorna status da última sincronização e logs recentes.

**Response:** `{ success, lastSync, isRunning, recentLogs }`

---

## Reports

### GET /api/reports/sales
Relatório de dados por fonte e uploads.

**Response:** `{ success, totalRecords, bySource, uploads }`

### GET /api/reports/metrics
KPIs e métricas de sincronização.

**Response:** `{ success, kpis, lastSync, syncHealth, recentUploads }`

---

## Cron

### POST /api/cron/mobneSync
Endpoint do cron Vercel (executado a cada 1h). Requer `Authorization: Bearer <CRON_SECRET>`.

**Response:** `{ success, totalSynced, results, timestamp }`

---

## Entidades Mobne Disponíveis

| Chave | Endpoint Mobne | Descrição |
|-------|---------------|-----------|
| `produtos` | `Produto/consulta-cadastro-produto` | Cadastro de produtos |
| `notas` | `Nota/consulta` | Notas fiscais |
| `empresas` | `Empresa/consulta-cadastro-empresa` | Empresas/filiais |
