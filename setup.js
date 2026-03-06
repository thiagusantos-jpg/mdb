#!/usr/bin/env node
/**
 * Setup script: cria um novo projeto no Supabase via Management API
 * e gera o arquivo .env com as credenciais.
 *
 * Uso: node setup.js
 */

import { writeFileSync } from 'fs';
import { spawnSync } from 'child_process';

const SUPABASE_ACCESS_TOKEN = 'sbp_v0_7a922af1edee1e1a196ba2fe947e2a5ad39cc947';
const API_BASE = 'https://api.supabase.com/v1';

function apiFetch(path, options = {}) {
  const { method = 'GET', body } = options;
  const args = [
    '-s', '-f',
    '-H', `Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}`,
    '-H', 'Content-Type: application/json',
    '-X', method,
  ];
  if (body) {
    args.push('-d', body);
  }
  args.push(`${API_BASE}${path}`);

  const result = spawnSync('curl', args, { encoding: 'utf8' });
  if (result.status !== 0) {
    throw new Error(`curl falhou [${result.status}]: ${result.stderr}`);
  }
  return JSON.parse(result.stdout);
}

async function waitForActive(ref, maxWaitMs = 5 * 60 * 1000) {
  const start = Date.now();
  process.stdout.write('Aguardando projeto ficar ativo');
  while (Date.now() - start < maxWaitMs) {
    const project = apiFetch(`/projects/${ref}`);
    if (project.status === 'ACTIVE_HEALTHY') {
      process.stdout.write(' OK\n');
      return;
    }
    process.stdout.write('.');
    await new Promise((r) => setTimeout(r, 5000));
  }
  throw new Error('Timeout aguardando projeto ficar ativo.');
}

async function main() {
  // 1. Listar organizações
  console.log('Buscando organizações...');
  const orgs = apiFetch('/organizations');
  if (!orgs.length) throw new Error('Nenhuma organização encontrada.');
  const orgId = orgs[0].id;
  console.log(`Organização: ${orgs[0].name} (${orgId})`);

  // 2. Criar projeto
  const dbPass = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2).toUpperCase() + '!9';
  console.log('Criando projeto "mdb" no Supabase...');
  const project = apiFetch('/projects', {
    method: 'POST',
    body: JSON.stringify({
      name: 'mdb',
      organization_id: orgId,
      db_pass: dbPass,
      region: 'sa-east-1',
      plan: 'free',
    }),
  });
  const ref = project.id;
  console.log(`Projeto criado! Ref: ${ref}`);

  // 3. Aguardar projeto ficar ativo
  await waitForActive(ref);

  // 4. Obter API keys
  console.log('Obtendo credenciais...');
  const keys = apiFetch(`/projects/${ref}/api-keys`);
  const anonKey = keys.find((k) => k.name === 'anon')?.api_key;
  const serviceKey = keys.find((k) => k.name === 'service_role')?.api_key;

  if (!anonKey || !serviceKey) throw new Error('Não foi possível obter as API keys.');

  const supabaseUrl = `https://${ref}.supabase.co`;

  // 5. Gerar .env
  const envContent = `SUPABASE_URL=${supabaseUrl}
SUPABASE_ANON_KEY=${anonKey}
SUPABASE_SERVICE_ROLE_KEY=${serviceKey}
SUPABASE_DB_PASS=${dbPass}
`;
  writeFileSync('.env', envContent);

  console.log('\n✓ Arquivo .env gerado com sucesso!');
  console.log(`  URL: ${supabaseUrl}`);
  console.log('\nExecute agora:');
  console.log('  npm install');
  console.log('  node index.js');
}

main().catch((err) => {
  console.error('Erro:', err.message);
  process.exit(1);
});
