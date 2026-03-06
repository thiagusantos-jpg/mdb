import 'dotenv/config';
import { requireAuth } from '../../middleware/auth.js';
import { supabase } from '../../lib/supabase.js';
import { errorResponse, successResponse, getPagination, corsHeaders } from '../../lib/utils.js';

export default async function handler(req, res) {
  Object.entries(corsHeaders()).forEach(([k, v]) => res.setHeader(k, v));

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'GET') return errorResponse(res, 405, 'Método não permitido.');

  const user = await requireAuth(req, res);
  if (!user) return;

  const { page, limit, offset } = getPagination(req.query);
  const { upload_id, source } = req.query;

  let query = supabase
    .from('raw_data')
    .select('id, row_index, data, source, synced_to_mobne, created_at, upload_id', { count: 'exact' })
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1);

  if (upload_id) query = query.eq('upload_id', upload_id);
  if (source) query = query.eq('source', source);

  const { data, error, count } = await query;

  if (error) return errorResponse(res, 500, 'Erro ao buscar dados.', error.message);

  return successResponse(res, {
    data,
    pagination: { page, limit, total: count, totalPages: Math.ceil(count / limit) },
  });
}
