import { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import api from '../../services/api.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Legend);

function fmt(value) {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function toDateInput(isoDate) {
  return isoDate.slice(0, 10);
}

function defaultRange() {
  const end = new Date();
  const start = new Date(Date.now() - 29 * 24 * 60 * 60 * 1000);
  return {
    dataInicio: toDateInput(start.toISOString()),
    dataFim: toDateInput(end.toISOString()),
  };
}

export function BillingChart() {
  const [range, setRange] = useState(defaultRange());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  function fetchBilling(dataInicio, dataFim) {
    setLoading(true);
    setError(null);
    api
      .get('/reports/billing', { params: { dataInicio, dataFim } })
      .then(({ data: res }) => setData(res))
      .catch((err) => setError(err.response?.data?.error || 'Erro ao carregar faturamento.'))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchBilling(range.dataInicio, range.dataFim);
  }, []);

  function handleApply() {
    fetchBilling(range.dataInicio, range.dataFim);
  }

  const chartData = {
    labels: (data?.daily || []).map((d) =>
      new Date(d.date + 'T12:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
    ),
    datasets: [
      {
        label: 'Faturamento (R$)',
        data: (data?.daily || []).map((d) => d.total),
        backgroundColor: '#2563eb',
        borderRadius: 4,
        borderSkipped: false,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => ` ${fmt(ctx.parsed.y)}`,
          afterLabel: (ctx) => {
            const day = data?.daily?.[ctx.dataIndex];
            return day ? ` ${day.count} pedidos · TM: ${fmt(day.ticketMedio)}` : '';
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          callback: (v) => `R$ ${v.toLocaleString('pt-BR')}`,
        },
      },
    },
  };

  return (
    <div className="space-y-6">
      {/* Filtro de período */}
      <div className="card flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Data início</label>
          <input
            type="date"
            value={range.dataInicio}
            max={range.dataFim}
            onChange={(e) => setRange((r) => ({ ...r, dataInicio: e.target.value }))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Data fim</label>
          <input
            type="date"
            value={range.dataFim}
            min={range.dataInicio}
            max={toDateInput(new Date().toISOString())}
            onChange={(e) => setRange((r) => ({ ...r, dataFim: e.target.value }))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <button
          onClick={handleApply}
          disabled={loading}
          className="btn-primary text-sm px-5 py-2"
        >
          {loading ? 'Carregando...' : 'Aplicar'}
        </button>
      </div>

      {/* KPIs */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Total Faturado" value={fmt(data.kpis.totalFaturado)} color="text-blue-700" />
          <KpiCard label="Cupons Emitidos" value={(data.kpis.totalCupons ?? data.kpis.totalPedidos ?? 0).toLocaleString('pt-BR')} />
          <KpiCard label="Ticket Médio" value={fmt(data.kpis.ticketMedio)} color="text-green-600" />
          <KpiCard label="Dias com Venda" value={data.kpis.diasComVenda.toString()} color="text-purple-600" />
        </div>
      )}

      {/* Gráfico */}
      <div className="card">
        <h4 className="font-medium text-gray-700 mb-4">Faturamento Diário</h4>
        {loading && <div className="text-gray-400 text-sm text-center py-12">Carregando...</div>}
        {error && <div className="text-red-500 text-sm text-center py-12">{error}</div>}
        {!loading && !error && data?.daily?.length === 0 && (
          <div className="text-gray-400 text-sm text-center py-12">Nenhum pedido encontrado no período.</div>
        )}
        {!loading && !error && data?.daily?.length > 0 && (
          <Bar data={chartData} options={chartOptions} />
        )}
      </div>

      {/* Tabela diária */}
      {!loading && data?.daily?.length > 0 && (
        <div className="card overflow-x-auto">
          <h4 className="font-medium text-gray-700 mb-4">Detalhamento por Dia</h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-gray-500">
                <th className="pb-2 font-medium">Data</th>
                <th className="pb-2 font-medium text-right">Pedidos</th>
                <th className="pb-2 font-medium text-right">Ticket Médio</th>
                <th className="pb-2 font-medium text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.daily.map((d) => (
                <tr key={d.date} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 text-gray-700">
                    {new Date(d.date + 'T12:00:00').toLocaleDateString('pt-BR')}
                  </td>
                  <td className="py-2 text-right text-gray-600">{d.count} cupons</td>
                  <td className="py-2 text-right text-gray-600">{fmt(d.ticketMedio)}</td>
                  <td className="py-2 text-right font-semibold text-blue-700">{fmt(d.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value, color = 'text-primary-700' }) {
  return (
    <div className="card text-center">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}
