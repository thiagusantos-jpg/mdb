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

  const [
    { count: totalRecords },
    { count: syncedRecords },
    { count: pendingSyncs },
    { data: lastUploads },
    { data: syncLogs },
  ] = await Promise.all([
    supabase.from('raw_data').select('id', { count: 'exact', head: true }).eq('user_id', user.id),
    supabase.from('raw_data').select('id', { count: 'exact', head: true }).eq('user_id', user.id).eq('synced_to_mobne', true),
    supabase.from('raw_data').select('id', { count: 'exact', head: true }).eq('user_id', user.id).eq('synced_to_mobne', false),
    supabase.from('data_uploads').select('id, filename, row_count, status, uploaded_at').eq('user_id', user.id).order('uploaded_at', { ascending: false }).limit(5),
    supabase.from('sync_logs').select('status, records_synced, started_at, completed_at').order('started_at', { ascending: false }).limit(5),
  ]);

  const lastSync = syncLogs?.[0] || null;
  const successSyncs = (syncLogs || []).filter((s) => s.status === 'completed').length;

  return successResponse(res, {
    kpis: {
      totalRecords: totalRecords || 0,
      syncedRecords: syncedRecords || 0,
      pendingSyncs: pendingSyncs || 0,
      syncRate: totalRecords ? Math.round(((syncedRecords || 0) / totalRecords) * 100) : 0,
    },
    lastSync: lastSync
      ? {
          status: lastSync.status,
          recordsSynced: lastSync.records_synced,
          at: lastSync.started_at,
          durationMs: lastSync.completed_at
            ? new Date(lastSync.completed_at) - new Date(lastSync.started_at)
            : null,
        }
      : null,
    syncHealth: {
      total: (syncLogs || []).length,
      successful: successSyncs,
      successRate: syncLogs?.length ? Math.round((successSyncs / syncLogs.length) * 100) : 0,
    },
    recentUploads: lastUploads || [],
  });
}
