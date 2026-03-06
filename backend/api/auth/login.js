import 'dotenv/config';
import bcrypt from 'bcrypt';
import { supabase } from '../../lib/supabase.js';
import { signAccessToken, signRefreshToken } from '../../lib/auth.js';
import { errorResponse, successResponse, isValidEmail, corsHeaders } from '../../lib/utils.js';

export default async function handler(req, res) {
  Object.entries(corsHeaders()).forEach(([k, v]) => res.setHeader(k, v));

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return errorResponse(res, 405, 'Método não permitido.');

  const { email, password } = req.body || {};

  if (!email || !password) return errorResponse(res, 400, 'Email e senha são obrigatórios.');
  if (!isValidEmail(email)) return errorResponse(res, 400, 'Email inválido.');

  const { data: user, error } = await supabase
    .from('users')
    .select('id, email, password_hash, nome, role')
    .eq('email', email.toLowerCase())
    .single();

  if (error || !user) return errorResponse(res, 401, 'Credenciais inválidas.');

  const valid = await bcrypt.compare(password, user.password_hash);
  if (!valid) return errorResponse(res, 401, 'Credenciais inválidas.');

  const payload = { id: user.id, email: user.email, nome: user.nome, role: user.role };
  const accessToken = signAccessToken(payload);
  const refreshToken = signRefreshToken({ id: user.id });

  return successResponse(res, {
    accessToken,
    refreshToken,
    user: payload,
  });
}
