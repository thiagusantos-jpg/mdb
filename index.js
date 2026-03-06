import { supabase } from './src/lib/supabase.js';

async function main() {
  console.log('Testando conexão com o Supabase...');

  const { error } = await supabase.from('_health_check_').select('*').limit(1);

  // Conexão OK se a tabela não existe (erro esperado em banco novo)
  // ou se a query executou sem problemas de rede/autenticação
  const isConnected =
    !error ||
    error.code === '42P01' ||
    error.message?.includes('does not exist') ||
    error.message?.includes('Could not find the table');

  if (isConnected) {
    console.log('Conexão com Supabase OK');
    console.log(`URL: ${process.env.SUPABASE_URL}`);
  } else {
    console.error('Erro ao conectar:', error.message);
    process.exit(1);
  }
}

main();
