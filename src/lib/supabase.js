import { createClient } from '@supabase/supabase-js';
import 'dotenv/config';

// Configura proxy HTTP quando disponível (necessário em ambientes containerizados)
if (process.env.https_proxy || process.env.HTTPS_PROXY) {
  const { ProxyAgent, setGlobalDispatcher } = await import('undici');
  const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY;
  setGlobalDispatcher(new ProxyAgent(proxyUrl));
}

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('SUPABASE_URL e SUPABASE_ANON_KEY devem estar definidos no .env');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
