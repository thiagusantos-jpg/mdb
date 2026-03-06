import { verifyAccessToken, extractBearerToken } from '../lib/auth.js';
import { errorResponse } from '../lib/utils.js';

/**
 * Middleware de autenticação JWT para Vercel Serverless Functions.
 * Uso: const user = await requireAuth(req, res); if (!user) return;
 */
export async function requireAuth(req, res) {
  const token = extractBearerToken(req.headers.authorization);

  if (!token) {
    errorResponse(res, 401, 'Token de autenticação não fornecido.');
    return null;
  }

  try {
    const payload = verifyAccessToken(token);
    return payload;
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      errorResponse(res, 401, 'Token expirado. Faça login novamente.');
    } else {
      errorResponse(res, 401, 'Token inválido.');
    }
    return null;
  }
}

/**
 * Middleware que exige role de admin.
 */
export async function requireAdmin(req, res) {
  const user = await requireAuth(req, res);
  if (!user) return null;

  if (user.role !== 'admin') {
    errorResponse(res, 403, 'Acesso restrito a administradores.');
    return null;
  }

  return user;
}
