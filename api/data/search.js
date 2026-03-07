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

  const { q } = req.query;
  if (!q || q.trim().length < 2) return errorResponse(res, 400, 'Termo de busca deve ter pelo menos 2 caracteres.');

  const { page, limit, offset } = getPagination(req.query);

  // Busca full-text no JSONB usando operador @>  e casting
  const { data, error, count } = await supabase
    .from('raw_data')
    .select('id, row_index, data, source, created_at', { count: 'exact' })
    .eq('user_id', user.id)
    .textSearch('data::text', q, { type: 'plain' })
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1);

  if (error) {
    // Fallback: busca via ilike no JSON stringificado
    const { data: fallback, error: err2, count: cnt2 } = await supabase
      .from('raw_data')
      .select('id, row_index, data, source, created_at', { count: 'exact' })
      .eq('user_id', user.id)
      .filter('data::text', 'ilike', `%${q}%`)
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (err2) return errorResponse(res, 500, 'Erro na busca.', err2.message);

    return successResponse(res, {
      data: fallback,
      pagination: { page, limit, total: cnt2, totalPages: Math.ceil(cnt2 / limit) },
      query: q,
    });
  }

  return successResponse(res, {
    data,
    pagination: { page, limit, total: count, totalPages: Math.ceil(count / limit) },
    query: q,
  });
}
