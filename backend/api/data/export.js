import 'dotenv/config';
import { requireAuth } from '../../middleware/auth.js';
import { supabase } from '../../lib/supabase.js';
import { rowsToCsv } from '../../lib/excelParser.js';
import { errorResponse, corsHeaders } from '../../lib/utils.js';

export default async function handler(req, res) {
  Object.entries(corsHeaders()).forEach(([k, v]) => res.setHeader(k, v));

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'GET') return errorResponse(res, 405, 'Método não permitido.');

  const user = await requireAuth(req, res);
  if (!user) return;

  const { upload_id, source } = req.query;

  let query = supabase
    .from('raw_data')
    .select('row_index, data, source, created_at')
    .eq('user_id', user.id)
    .order('row_index', { ascending: true })
    .limit(10000); // limite de segurança

  if (upload_id) query = query.eq('upload_id', upload_id);
  if (source) query = query.eq('source', source);

  const { data, error } = await query;

  if (error) return errorResponse(res, 500, 'Erro ao exportar dados.', error.message);
  if (!data || data.length === 0) return errorResponse(res, 404, 'Nenhum dado encontrado para exportar.');

  // Extrai dados do JSONB para o CSV
  const rows = data.map((r) => ({ ...r.data, _source: r.source, _created_at: r.created_at }));
  const csv = rowsToCsv(rows);

  const filename = `export_${new Date().toISOString().slice(0, 10)}.csv`;

  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  return res.status(200).send('\uFEFF' + csv); // BOM para Excel reconhecer UTF-8
}
