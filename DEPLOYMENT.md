# DEPLOYMENT — DuBairro MVP

Guia completo para colocar o projeto em produção no **Vercel** + **Supabase**.

---

## Pré-requisitos

- Conta no [Vercel](https://vercel.com) (gratuita serve)
- Conta no [Supabase](https://supabase.com) (gratuita serve)
- Node.js 18+ instalado localmente
- Vercel CLI: `npm i -g vercel`

---

## 1. Configurar o Supabase

### 1.1 Criar o projeto
1. Acesse [supabase.com](https://supabase.com) → **New Project**
2. Escolha organização, nome e senha do banco → **Create Project**
3. Aguarde a criação (~2 minutos)

### 1.2 Executar o schema
1. Vá em **SQL Editor** no painel do Supabase
2. Cole e execute o conteúdo de `database/schema.sql`
3. (Opcional) Cole e execute `database/seed.sql` para dados iniciais

### 1.3 Criar usuário sistema (para o cron)
```sql
INSERT INTO users (id, email, password_hash, name, role)
VALUES (
  gen_random_uuid(),
  'sistema@dubairro.internal',
  'x', -- sem login real
  'Sistema Cron',
  'admin'
)
RETURNING id; -- copie este UUID para SYSTEM_USER_ID
```

### 1.4 Coletar as credenciais
Vá em **Project Settings → API**:
- `SUPABASE_URL` → Project URL
- `SUPABASE_ANON_KEY` → anon / public key
- `SUPABASE_SERVICE_ROLE_KEY` → service_role key (mantenha secreto!)

Vá em **Project Settings → Database**:
- `SUPABASE_DB_PASS` → a senha que você definiu na criação

---

## 2. Configurar variáveis de ambiente

Copie o arquivo de exemplo e preencha:

```bash
cp .env.example .env
```

Preencha todos os valores em `.env`:

```env
# Supabase
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_DB_PASS=sua-senha

# JWT (gere secrets aleatórios)
JWT_SECRET=$(openssl rand -base64 32)
JWT_REFRESH_SECRET=$(openssl rand -base64 32)

# Mobne
MOBNE_API_URL=https://apiexternal.mobne.com.br/api/v1
MOBNE_API_KEY=zikBlcp7B/R2HyKAs+y/Qrz1KeihAmGI8yNdKHDblssMBMrJSZjY8pJC5qFO59MIz7ohVFJ4UAQNcQc0t96qLQ==

# Cron
CRON_SECRET=$(openssl rand -base64 32)
SYSTEM_USER_ID=uuid-copiado-do-passo-1.3

# CORS
CORS_ORIGIN=*

# Frontend (Vite)
VITE_API_URL=/api
VITE_SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

---

## 3. Testar localmente

### Backend
```bash
cd backend
npm install
node ../index.js
# servidor em http://localhost:3000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# app em http://localhost:5173
```

### Fluxo de teste
1. Acesse `http://localhost:5173`
2. Login com um usuário cadastrado no Supabase
3. Upload de arquivo Excel na aba **Dados**
4. Verifique os dados na tabela
5. Exporte como CSV
6. Dispare sincronização com Mobne
7. Acesse a aba **Relatórios** e verifique métricas

---

## 4. Deploy no Vercel

### 4.1 Via CLI (recomendado)
```bash
# Na raiz do projeto
vercel login
vercel --prod
```

O Vercel detecta automaticamente o `vercel.json` e configura:
- Build do frontend via Vite
- Funções serverless do backend
- Cron job a cada hora (`0 * * * *`)
- Rewrites de `/api/*` para o backend

### 4.2 Via painel web
1. Acesse [vercel.com/new](https://vercel.com/new)
2. Importe o repositório do GitHub
3. O Vercel usa o `vercel.json` automaticamente — sem configuração adicional

### 4.3 Configurar variáveis de ambiente no Vercel
1. Vá em **Project Settings → Environment Variables**
2. Adicione **todas** as variáveis do `.env` (exceto as `VITE_*` que são do build)
3. Para as variáveis `VITE_*`, adicione também — o Vercel as injeta no build

> **Atenção:** `SUPABASE_SERVICE_ROLE_KEY` e `JWT_SECRET` devem ser marcadas como **Secret** no Vercel.

---

## 5. Pós-deploy

### 5.1 Verificar o cron
- Vá em **Project → Functions → Cron Jobs** no painel Vercel
- O job `/api/cron/mobneSync` deve aparecer com schedule `0 * * * *`
- Clique em **Trigger** para testar manualmente

### 5.2 Configurar domínio customizado (opcional)
1. **Project Settings → Domains**
2. Adicione seu domínio e siga as instruções de DNS

### 5.3 Monitoramento
- **Vercel Analytics**: ative em Project Settings → Analytics
- **Supabase Logs**: acompanhe queries em Database → Logs
- **Function Logs**: visualize erros em Vercel → Deployments → Functions

---

## 6. Estrutura do Projeto

```
mdb/
├── vercel.json          # Configuração do Vercel (rewrites, crons, headers)
├── index.js             # Entry point (desenvolvimento local)
├── frontend/            # React + Vite
│   ├── src/
│   │   ├── pages/       # LoginPage, DashboardPage, ReportsPage
│   │   └── components/  # Upload, DataTable, Reports, etc.
│   └── vite.config.js
├── backend/
│   └── api/             # Serverless functions
│       ├── auth/        # login, validate, logout
│       ├── upload/      # excel
│       ├── data/        # list, search, export
│       ├── sync/        # mobne, status
│       ├── reports/     # sales, metrics
│       └── cron/        # mobneSync
└── database/
    ├── schema.sql       # Estrutura do banco
    └── seed.sql         # Dados iniciais (opcional)
```

---

## 7. Variáveis de Ambiente — Referência Rápida

| Variável | Onde obter | Obrigatória |
|---|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API | Sim |
| `SUPABASE_ANON_KEY` | Supabase → Project Settings → API | Sim |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API | Sim |
| `SUPABASE_DB_PASS` | Senha definida na criação do projeto | Sim |
| `JWT_SECRET` | Gerar: `openssl rand -base64 32` | Sim |
| `JWT_REFRESH_SECRET` | Gerar: `openssl rand -base64 32` | Sim |
| `MOBNE_API_KEY` | Já fornecida no `.env.example` | Sim |
| `CRON_SECRET` | Gerar: `openssl rand -base64 32` | Sim |
| `SYSTEM_USER_ID` | UUID do usuário sistema criado no banco | Sim |
| `VITE_API_URL` | Valor fixo: `/api` | Sim |
| `VITE_SUPABASE_URL` | Mesmo valor de `SUPABASE_URL` | Sim |
| `VITE_SUPABASE_ANON_KEY` | Mesmo valor de `SUPABASE_ANON_KEY` | Sim |

---

## Suporte

Problemas? Abra uma issue no repositório ou consulte:
- [Vercel Docs](https://vercel.com/docs)
- [Supabase Docs](https://supabase.com/docs)
