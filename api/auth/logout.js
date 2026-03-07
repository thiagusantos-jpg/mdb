import 'dotenv/config';
import { successResponse, corsHeaders } from '../../lib/utils.js';

// Logout é client-side (remoção do token do localStorage).
// Este endpoint existe para compatibilidade e futuro blacklist.
export default async function handler(req, res) {
  Object.entries(corsHeaders()).forEach(([k, v]) => res.setHeader(k, v));

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Método não permitido.' });
  }

  return successResponse(res, { message: 'Logout realizado com sucesso.' });
}
