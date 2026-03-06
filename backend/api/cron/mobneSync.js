import 'dotenv/config';
import { supabase } from '../../lib/supabase.js';
import { fetchPage, MOBNE_ENDPOINTS } from '../../lib/mobneClient.js';

const CRON_SECRET = process.env.CRON_SECRET;

// Usuário sistema para registrar os dados do cron
const SYSTEM_USER_ID = process.env.SYSTEM_USER_ID;

async function syncEntity(entity) {
  const response = fetchPage(entity, 1, 100);
  const items = response?.Data?.Items || [];
  const paging = response?.Data?.Paging || {};

  if (items.length === 0) return { entity, synced: 0 };

  const rows = items.map((item, idx) => ({
    user_id: SYSTEM_USER_ID,
    row_index: idx,
    data: item,
    source: 'mobne',
    synced_to_mobne: true,
    synced_at: new Date().toISOString(),
  }));

  const { error } = await supabase.from('raw_data').insert(rows);
  if (error) throw new Error(`Erro ao inserir ${entity}: ${error.message}`);

  return { entity, synced: items.length, paging };
}

export default async function handler(req, res) {
  // Verifica segredo do cron
  const authHeader = req.headers.authorization;
  if (!CRON_SECRET || authHeader !== `Bearer ${CRON_SECRET}`) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const startedAt = new Date();
  const results = [];
  let totalSynced = 0;

  const { data: syncLog } = await supabase
    .from('sync_logs')
    .insert({
      sync_type: 'automatic',
      status: 'running',
      entity: 'all',
      started_at: startedAt.toISOString(),
    })
    .select()
    .single();

  try {
    for (const entity of Object.keys(MOBNE_ENDPOINTS)) {
      try {
        const result = await syncEntity(entity);
        results.push(result);
        totalSynced += result.synced;
      } catch (err) {
        results.push({ entity, error: err.message });
      }
    }

    await supabase.from('sync_logs').update({
      status: 'completed',
      records_synced: totalSynced,
      last_sync: startedAt.toISOString(),
      next_sync: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
      completed_at: new Date().toISOString(),
      details: { results },
    }).eq('id', syncLog.id);

    return res.status(200).json({ success: true, totalSynced, results, timestamp: new Date() });
  } catch (err) {
    await supabase.from('sync_logs').update({
      status: 'failed',
      error_message: err.message,
      completed_at: new Date().toISOString(),
    }).eq('id', syncLog.id);

    return res.status(500).json({ error: err.message });
  }
}
