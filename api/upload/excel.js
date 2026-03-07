import 'dotenv/config';
import { requireAuth } from '../../middleware/auth.js';
import { supabase } from '../../lib/supabase.js';
import { parseExcel } from '../../lib/excelParser.js';
import { errorResponse, successResponse, corsHeaders } from '../../lib/utils.js';

export const config = { api: { bodyParser: false } };

async function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

export default async function handler(req, res) {
  Object.entries(corsHeaders()).forEach(([k, v]) => res.setHeader(k, v));

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return errorResponse(res, 405, 'Método não permitido.');

  const user = await requireAuth(req, res);
  if (!user) return;

  const contentType = req.headers['content-type'] || '';
  if (!contentType.includes('application/octet-stream') && !contentType.includes('multipart/form-data')) {
    // Aceita qualquer body como buffer
  }

  let buffer;
  try {
    buffer = await readBody(req);
  } catch {
    return errorResponse(res, 400, 'Erro ao ler o arquivo.');
  }

  if (!buffer || buffer.length === 0) return errorResponse(res, 400, 'Arquivo vazio.');

  const filename = req.headers['x-filename'] || `upload_${Date.now()}.xlsx`;
  const originalName = req.headers['x-original-name'] || filename;

  // Cria registro de upload
  const { data: upload, error: uploadError } = await supabase
    .from('data_uploads')
    .insert({ user_id: user.id, filename, original_name: originalName, status: 'processing' })
    .select()
    .single();

  if (uploadError) return errorResponse(res, 500, 'Erro ao registrar upload.', uploadError.message);

  try {
    const { rows, headers, sheetName } = parseExcel(buffer);

    if (rows.length === 0) {
      await supabase.from('data_uploads').update({ status: 'failed', error_message: 'Arquivo sem dados.' }).eq('id', upload.id);
      return errorResponse(res, 422, 'Arquivo Excel não contém dados.');
    }

    // Insere dados em lotes de 500
    const batchSize = 500;
    for (let i = 0; i < rows.length; i += batchSize) {
      const batch = rows.slice(i, i + batchSize).map((row, idx) => ({
        upload_id: upload.id,
        user_id: user.id,
        row_index: i + idx,
        data: row,
        source: 'upload',
      }));
      const { error: insertError } = await supabase.from('raw_data').insert(batch);
      if (insertError) throw new Error(insertError.message);
    }

    await supabase.from('data_uploads').update({
      status: 'completed',
      row_count: rows.length,
    }).eq('id', upload.id);

    return successResponse(res, {
      upload: { id: upload.id, filename, originalName, rowCount: rows.length, sheetName },
      preview: rows.slice(0, 5),
      headers,
    }, 201);
  } catch (err) {
    await supabase.from('data_uploads').update({
      status: 'failed',
      error_message: err.message,
    }).eq('id', upload.id);
    return errorResponse(res, 500, 'Erro ao processar arquivo.', err.message);
  }
}
