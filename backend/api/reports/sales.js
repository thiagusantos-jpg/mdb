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

  // Total de registros por fonte
  const { data: bySource, error: e1 } = await supabase
    .from('raw_data')
    .select('source')
    .eq('user_id', user.id);

  if (e1) return errorResponse(res, 500, 'Erro ao gerar relatório.', e1.message);

  const sourceCounts = (bySource || []).reduce((acc, r) => {
    acc[r.source] = (acc[r.source] || 0) + 1;
    return acc;
  }, {});

  // Total de uploads por status
  const { data: uploads, error: e2 } = await supabase
    .from('data_uploads')
    .select('status, row_count, uploaded_at')
    .eq('user_id', user.id)
    .order('uploaded_at', { ascending: false });

  if (e2) return errorResponse(res, 500, 'Erro ao buscar uploads.', e2.message);

  const uploadSummary = (uploads || []).reduce((acc, u) => {
    acc[u.status] = (acc[u.status] || 0) + 1;
    return acc;
  }, {});

  const totalRows = (uploads || []).reduce((sum, u) => sum + (u.row_count || 0), 0);

  // Uploads dos últimos 7 dias (por dia)
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const recentUploads = (uploads || [])
    .filter((u) => new Date(u.uploaded_at) >= sevenDaysAgo)
    .map((u) => ({
      date: u.uploaded_at.slice(0, 10),
      rows: u.row_count,
      status: u.status,
    }));

  return successResponse(res, {
    totalRecords: (bySource || []).length,
    bySource: sourceCounts,
    uploads: {
      total: (uploads || []).length,
      byStatus: uploadSummary,
      totalRows,
      recent: recentUploads,
    },
  });
}
