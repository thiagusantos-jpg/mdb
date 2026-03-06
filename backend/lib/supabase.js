import { createClient } from '@supabase/supabase-js';

// Configura proxy HTTP quando disponível (necessário em ambientes containerizados)
if (process.env.https_proxy || process.env.HTTPS_PROXY) {
  const { ProxyAgent, setGlobalDispatcher } = await import('undici');
  const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY;
  setGlobalDispatcher(new ProxyAgent(proxyUrl));
}

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseServiceKey) {
  throw new Error('SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar definidos');
}

// Client com service role key para operações no backend
export const supabase = createClient(supabaseUrl, supabaseServiceKey, {
  auth: { autoRefreshToken: false, persistSession: false },
});
