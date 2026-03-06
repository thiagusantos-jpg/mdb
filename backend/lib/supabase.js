import { createClient } from '@supabase/supabase-js';
import fetch from 'node-fetch';
import httpsProxyAgentPkg from 'https-proxy-agent';
const { HttpsProxyAgent } = httpsProxyAgentPkg;

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseServiceKey) {
  throw new Error('SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar definidos');
}

// Configura proxy quando disponível (necessário em ambientes containerizados)
const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;
const fetchWithProxy = agent
  ? (url, options) => fetch(url, { ...options, agent })
  : fetch;

// Client com service role key para operações no backend
export const supabase = createClient(supabaseUrl, supabaseServiceKey, {
  auth: { autoRefreshToken: false, persistSession: false },
  global: { fetch: fetchWithProxy },
});
