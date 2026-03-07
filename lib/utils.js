/**
 * Resposta de erro padronizada
 */
export function errorResponse(res, status, message, details = null) {
  return res.status(status).json({ error: message, ...(details && { details }) });
}

/**
 * Resposta de sucesso padronizada
 */
export function successResponse(res, data, status = 200) {
  return res.status(status).json({ success: true, ...data });
}

/**
 * Extrai parâmetros de paginação da query string
 */
export function getPagination(query) {
  const page = Math.max(1, parseInt(query.page || '1', 10));
  const limit = Math.min(100, Math.max(1, parseInt(query.limit || '20', 10)));
  const offset = (page - 1) * limit;
  return { page, limit, offset };
}

/**
 * Valida se um email tem formato válido
 */
export function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * Gera CORS headers para respostas de API
 */
export function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': process.env.CORS_ORIGIN || '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
}
