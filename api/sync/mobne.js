import 'dotenv/config';
import { requireAuth } from '../../middleware/auth.js';
import { supabase } from '../../lib/supabase.js';
import { fetchPage, MOBNE_ENDPOINTS } from '../../lib/mobneClient.js';
import { errorResponse, successResponse, corsHeaders } from '../../lib/utils.js';

export default async function handler(req, res) {
  Object.entries(corsHeaders()).forEach(([k, v]) => res.setHeader(k, v));

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return errorResponse(res, 405, 'Método não permitido.');

  const user = await requireAuth(req, res);
  if (!user) return;

  const { entity = 'produtos', page = 1, pageSize = 100 } = req.body || {};

  if (!MOBNE_ENDPOINTS[entity]) {
    return errorResponse(res, 400, `Entidade inválida. Use: ${Object.keys(MOBNE_ENDPOINTS).join(', ')}`);
  }

  // Registra início da sync
  const { data: syncLog } = await supabase
    .from('sync_logs')
    .insert({
      sync_type: 'manual',
      status: 'running',
      entity,
      started_at: new Date().toISOString(),
    })
    .select()
    .single();

  try {
    const response = fetchPage(entity, parseInt(page), parseInt(pageSize));
    const items = response?.Data?.Items || [];
    const paging = response?.Data?.Paging || {};

    if (items.length > 0) {
      const rows = items.map((item, idx) => ({
        user_id: user.id,
        row_index: (parseInt(page) - 1) * parseInt(pageSize) + idx,
        data: item,
        source: 'mobne',
        synced_to_mobne: true,
        synced_at: new Date().toISOString(),
      }));

      await supabase.from('raw_data').insert(rows);
    }

    await supabase.from('sync_logs').update({
      status: 'completed',
      records_synced: items.length,
      last_sync: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      details: { paging, entity, page, pageSize },
    }).eq('id', syncLog.id);

    return successResponse(res, {
      entity,
      recordsSynced: items.length,
      paging,
      syncLogId: syncLog.id,
    });
  } catch (err) {
    await supabase.from('sync_logs').update({
      status: 'failed',
      error_message: err.message,
      completed_at: new Date().toISOString(),
    }).eq('id', syncLog.id);

    return errorResponse(res, 502, 'Erro ao sincronizar com Mobne.', err.message);
  }
}
