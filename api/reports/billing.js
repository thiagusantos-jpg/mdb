import 'dotenv/config';
import { requireAuth } from '../../middleware/auth.js';
import { errorResponse, successResponse, corsHeaders } from '../../lib/utils.js';

const MOBNE_BASE_URL = process.env.MOBNE_API_URL || 'https://apiexternal.mobne.com.br/api/v1';
const MOBNE_API_KEY = process.env.MOBNE_API_KEY;
const EMPRESA_ID = '218';

function generateMockBilling(dataInicio, dataFim) {
  const start = new Date(dataInicio);
  const end = new Date(dataFim);
  const items = [];
  let id = 1;

  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const cuponsNoDia = Math.floor(Math.random() * 20) + 5;
    for (let i = 0; i < cuponsNoDia; i++) {
      items.push({
        Id: `mock-${id++}`,
        dataEmissao: d.toISOString().slice(0, 10),
        valorTotal: parseFloat((Math.random() * 300 + 20).toFixed(2)),
        _mock: true,
      });
    }
  }

  return { Data: { Items: items, Paging: { TotalPages: 1, PageNumber: 1, TotalItems: items.length } } };
}

async function fetchCuponsFiscais(dataInicio, dataFim) {
  if (!MOBNE_API_KEY) {
    return generateMockBilling(dataInicio, dataFim);
  }

  const allItems = [];
  let page = 1;
  let totalPages = 1;

  do {
    const params = new URLSearchParams({
      PageSize: 500,
      PageNumber: page,
      DataInicio: dataInicio,
      DataFim: dataFim,
    });

    const response = await fetch(`${MOBNE_BASE_URL}/CupomFiscal/consulta?${params}`, {
      headers: {
        Authorization: `ApiKey ${MOBNE_API_KEY}`,
        empresaId: EMPRESA_ID,
      },
    });

    if (!response.ok) throw new Error(`Mobne API error: ${response.status} ${response.statusText}`);

    const json = await response.json();
    const items = json?.Data?.Items || [];
    totalPages = json?.Data?.Paging?.TotalPages ?? 1;

    allItems.push(...items);
    page++;
  } while (page <= totalPages && page <= 20); // cap at 20 pages for safety

  return { Data: { Items: allItems } };
}

function groupByDay(items) {
  const map = {};

  for (const item of items) {
    // Filtra apenas Cupom Fiscal emitido (exclui Nota Fiscal PDV e cancelados)
    const tipo     = (item.tipo      || item.Tipo      || '').toUpperCase();
    const situacao = (item.situacao  || item.Situacao  || item.situação || item.Situação || '').toUpperCase();

    if (tipo     && tipo     !== 'CUPOM FISCAL') continue;
    if (situacao && situacao !== 'EMITIDO')      continue;

    const date = (
      item.dataEmissao || item.DataEmissao ||
      item.dataCupom   || item.DataCupom   ||
      item.dataVenda   || item.DataVenda   || ''
    ).slice(0, 10);
    if (!date) continue;

    // Vlr. Líquido é o valor correto (bruto menos descontos, mais acréscimos)
    const valor = parseFloat(
      item.valorLiquido || item.ValorLiquido ||
      item.vlrLiquido   || item.VlrLiquido   ||
      item.valorTotal   || item.ValorTotal   ||
      item.valorCupom   || item.ValorCupom   || 0
    );

    if (!map[date]) map[date] = { total: 0, count: 0 };
    map[date].total += valor;
    map[date].count += 1;
  }

  return Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, { total, count }]) => ({
      date,
      total: parseFloat(total.toFixed(2)),
      count,
      ticketMedio: count > 0 ? parseFloat((total / count).toFixed(2)) : 0,
    }));
}

export default async function handler(req, res) {
  Object.entries(corsHeaders()).forEach(([k, v]) => res.setHeader(k, v));

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'GET') return errorResponse(res, 405, 'Método não permitido.');

  const user = await requireAuth(req, res);
  if (!user) return;

  const hoje = new Date().toISOString().slice(0, 10);
  const trintaDiasAtras = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

  const dataInicio = req.query.dataInicio || trintaDiasAtras;
  const dataFim = req.query.dataFim || hoje;

  try {
    const { Data } = await fetchCuponsFiscais(dataInicio, dataFim);
    const items = Data?.Items || [];
    const daily = groupByDay(items);

    const totalFaturado = daily.reduce((sum, d) => sum + d.total, 0);
    const totalCupons = daily.reduce((sum, d) => sum + d.count, 0);
    const ticketMedioGeral = totalCupons > 0 ? parseFloat((totalFaturado / totalCupons).toFixed(2)) : 0;

    return successResponse(res, {
      dataInicio,
      dataFim,
      daily,
      kpis: {
        totalFaturado: parseFloat(totalFaturado.toFixed(2)),
        totalCupons,
        ticketMedio: ticketMedioGeral,
        diasComVenda: daily.length,
      },
    });
  } catch (err) {
    return errorResponse(res, 502, 'Erro ao buscar faturamento na Mobne.', err.message);
  }
}
