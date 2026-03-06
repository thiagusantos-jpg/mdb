# DUBAIRRO MVP — Guia de Deploy

## Pré-requisitos

- Conta Vercel
- Projeto Supabase criado (já configurado: `jsqkbcnmwdjpygawnhlw`)
- Node.js 18+

## 1. Configurar variáveis de ambiente na Vercel

No painel Vercel → Settings → Environment Variables, adicionar todas as vars do `.env.example`:

| Variável | Onde obter |
|----------|-----------|
| `SUPABASE_URL` | Supabase → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API |
| `JWT_SECRET` | Gerar com `openssl rand -base64 32` |
| `JWT_REFRESH_SECRET` | Gerar com `openssl rand -base64 32` |
| `MOBNE_API_KEY` | Fornecido pelo Mobne |
| `CRON_SECRET` | Gerar com `openssl rand -base64 32` |
| `SYSTEM_USER_ID` | UUID do usuário "sistema" no banco |

## 2. Conectar repositório ao Vercel

```bash
# Via Vercel CLI
npm install -g vercel
vercel --prod
```

Ou conectar via GitHub no painel da Vercel.

## 3. Configurar branches

- `main` → produção
- `staging` → preview
- `claude/connect-supabase-Ygxl6` → desenvolvimento atual

## 4. Verificar deploy

1. Acessar a URL gerada pela Vercel
2. Fazer login com `admin@dubairro.com` / `admin123`
3. Testar upload de Excel
4. Testar sync manual com Mobne
5. Verificar relatórios

## 5. Migrar para Supabase Auth (Fase 5)

Quando pronto para produção, migrar de JWT manual para Supabase Auth:

1. Criar usuários no Supabase Auth Dashboard
2. Substituir `backend/api/auth/login.js` para usar `supabase.auth.signInWithPassword()`
3. Substituir `backend/middleware/auth.js` para usar `supabase.auth.getUser(token)`
4. Remover tabela `users` e usar `auth.users` do Supabase

## Cron Jobs (Vercel)

O cron é configurado em `vercel.json` para rodar a cada 1h:
```json
{
  "crons": [{ "path": "/api/cron/mobneSync", "schedule": "0 * * * *" }]
}
```

O endpoint é protegido pelo `CRON_SECRET` via header `Authorization: Bearer <secret>`.
