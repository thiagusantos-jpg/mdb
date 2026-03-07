import 'dotenv/config';
import { requireAuth } from '../../middleware/auth.js';
import { supabase } from '../../lib/supabase.js';
import { errorResponse, successResponse, corsHeaders } from '../../lib/utils.js';

export default async function handler(req, res) {
  Object.entries(corsHeaders()).forEach(([k, v]) => res.setHeader(k, v));

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'GET') return errorResponse(res, 405, 'Método não permitido.');

  const user = await requireAuth(req, res);
  if (!user) return;

  const { data: logs, error } = await supabase
    .from('sync_logs')
    .select('*')
    .order('started_at', { ascending: false })
    .limit(10);

  if (error) return errorResponse(res, 500, 'Erro ao buscar status de sync.', error.message);

  const lastSync = logs?.[0] || null;
  const isRunning = lastSync?.status === 'running';

  return successResponse(res, {
    lastSync,
    isRunning,
    recentLogs: logs,
  });
}
