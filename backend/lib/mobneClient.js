import { spawnSync } from 'child_process';

const MOBNE_BASE_URL = process.env.MOBNE_API_URL || 'https://apiexternal.mobne.com.br/api/v1';
const MOBNE_API_KEY = process.env.MOBNE_API_KEY;

// Endpoints disponíveis na API Mobne
export const MOBNE_ENDPOINTS = {
  produtos: 'Produto/consulta-cadastro-produto',
  notas: 'Nota/consulta',
  empresas: 'Empresa/consulta-cadastro-empresa',
};

/**
 * Retorna dados mock quando MOBNE_API_KEY não está configurada.
 */
function mockResponse(path, params) {
  const page = Number(params.PageNumber) || 1;
  const size = Number(params.PageSize) || 10;
  const mockItems = Array.from({ length: size }, (_, i) => ({
    Id: `mock-${page}-${i + 1}`,
    Nome: `Item Mock ${(page - 1) * size + i + 1}`,
    Codigo: `MOCK-${String((page - 1) * size + i + 1).padStart(4, '0')}`,
    _mock: true,
  }));

  return {
    Data: {
      Items: mockItems,
      Paging: { TotalPages: 1, PageNumber: page, PageSize: size, TotalItems: size },
    },
  };
}

/**
 * Faz uma chamada à API Mobne usando curl (necessário por limitação de DNS no ambiente).
 * Em produção (Vercel), fetch funciona normalmente — substituir por fetch padrão.
 * Retorna dados mock se MOBNE_API_KEY não estiver configurada.
 */
function mobneRequest(path, params = {}) {
  if (!MOBNE_API_KEY) {
    return mockResponse(path, params);
  }

  const query = new URLSearchParams(params).toString();
  const url = `${MOBNE_BASE_URL}/${path}${query ? `?${query}` : ''}`;

  const result = spawnSync('curl', [
    '-s', '-f',
    '-H', `Authorization: ApiKey ${MOBNE_API_KEY}`,
    url,
  ], { encoding: 'utf8', timeout: 30000 });

  if (result.status !== 0) {
    throw new Error(`Mobne API request failed: ${result.stderr}`);
  }

  return JSON.parse(result.stdout);
}

/**
 * Busca todos os itens de um endpoint paginado do Mobne.
 * @param {string} endpoint - chave de MOBNE_ENDPOINTS
 * @param {object} extraParams - parâmetros adicionais
 * @param {number} maxPages - limite de páginas (0 = todas)
 */
export async function fetchAllPages(endpoint, extraParams = {}, maxPages = 0) {
  const path = MOBNE_ENDPOINTS[endpoint];
  if (!path) throw new Error(`Endpoint Mobne desconhecido: ${endpoint}`);

  const items = [];
  let page = 1;
  let totalPages = 1;
  const pageSize = 100;

  do {
    const response = mobneRequest(path, { PageSize: pageSize, PageNumber: page, ...extraParams });
    const data = response?.Data;

    if (!data?.Items) break;

    items.push(...data.Items);
    totalPages = data.Paging?.TotalPages ?? 1;
    page++;

    if (maxPages > 0 && page > maxPages) break;
  } while (page <= totalPages);

  return items;
}

/**
 * Busca uma página específica de um endpoint Mobne.
 */
export function fetchPage(endpoint, pageNumber = 1, pageSize = 100, extraParams = {}) {
  const path = MOBNE_ENDPOINTS[endpoint];
  if (!path) throw new Error(`Endpoint Mobne desconhecido: ${endpoint}`);
  return mobneRequest(path, { PageSize: pageSize, PageNumber: pageNumber, ...extraParams });
}
