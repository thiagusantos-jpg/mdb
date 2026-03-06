import 'dotenv/config';
import { requireAuth } from '../../middleware/auth.js';
import { successResponse, corsHeaders } from '../../lib/utils.js';

export default async function handler(req, res) {
  Object.entries(corsHeaders()).forEach(([k, v]) => res.setHeader(k, v));

  if (req.method === 'OPTIONS') return res.status(200).end();

  const user = await requireAuth(req, res);
  if (!user) return;

  return successResponse(res, { user });
}
