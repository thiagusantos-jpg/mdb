import { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
} from 'chart.js';
import { Doughnut, Bar } from 'react-chartjs-2';
import api from '../../services/api.js';

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement);

export function MetricsChart() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/reports/metrics')
      .then(({ data }) => setMetrics(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400 text-sm">Carregando métricas...</div>;
  if (!metrics) return null;

  const { kpis, syncHealth, lastSync, recentUploads } = metrics;

  const donutData = {
    labels: ['Sincronizados', 'Pendentes'],
    datasets: [{
      data: [kpis.syncedRecords, kpis.pendingSyncs],
      backgroundColor: ['#2563eb', '#e5e7eb'],
      borderWidth: 0,
    }],
  };

  const uploadsBarData = {
    labels: (recentUploads || []).map((u) => u.filename?.slice(0, 12) || 'Upload'),
    datasets: [{
      label: 'Linhas por Upload',
      data: (recentUploads || []).map((u) => u.row_count || 0),
      backgroundColor: '#3b82f6',
      borderRadius: 4,
    }],
  };

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total Registros" value={kpis.totalRecords.toLocaleString('pt-BR')} />
        <KpiCard label="Sincronizados" value={kpis.syncedRecords.toLocaleString('pt-BR')} color="text-green-600" />
        <KpiCard label="Pendentes" value={kpis.pendingSyncs.toLocaleString('pt-BR')} color="text-yellow-600" />
        <KpiCard label="Taxa de Sync" value={`${kpis.syncRate}%`} color="text-blue-600" />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Donut chart */}
        <div className="card">
          <h4 className="font-medium text-gray-700 mb-4">Status de Sincronização</h4>
          <div className="flex justify-center">
            <div style={{ width: 220, height: 220 }}>
              <Doughnut data={donutData} options={{ cutout: '65%', plugins: { legend: { position: 'bottom' } } }} />
            </div>
          </div>
        </div>

        {/* Bar chart */}
        <div className="card">
          <h4 className="font-medium text-gray-700 mb-4">Uploads Recentes</h4>
          {recentUploads?.length > 0 ? (
            <Bar
              data={uploadsBarData}
              options={{
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } },
              }}
            />
          ) : (
            <div className="text-gray-400 text-sm text-center py-8">Nenhum upload ainda.</div>
          )}
        </div>
      </div>

      {/* Sync health */}
      {lastSync && (
        <div className="card">
          <h4 className="font-medium text-gray-700 mb-2">Última Sincronização</h4>
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <span>Status: <strong>{lastSync.status}</strong></span>
            <span>Registros: <strong>{lastSync.recordsSynced}</strong></span>
            <span>Em: <strong>{new Date(lastSync.at).toLocaleString('pt-BR')}</strong></span>
            {lastSync.durationMs && (
              <span>Duração: <strong>{(lastSync.durationMs / 1000).toFixed(1)}s</strong></span>
            )}
          </div>
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
