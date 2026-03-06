import { useState, useEffect } from 'react';
import api from '../../services/api.js';

export function SalesReport() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/reports/sales')
      .then(({ data: d }) => setData(d))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400 text-sm">Carregando...</div>;
  if (!data) return null;

  const { totalRecords, bySource, uploads } = data;

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total de Registros" value={totalRecords?.toLocaleString('pt-BR')} />
        <KpiCard label="Via Upload" value={(bySource?.upload || 0).toLocaleString('pt-BR')} />
        <KpiCard label="Via Mobne" value={(bySource?.mobne || 0).toLocaleString('pt-BR')} />
        <KpiCard label="Total de Linhas" value={(uploads?.totalRows || 0).toLocaleString('pt-BR')} />
      </div>

      {/* Uploads recentes */}
      {uploads?.recent?.length > 0 && (
        <div>
          <h4 className="font-medium text-gray-700 mb-3">Uploads Recentes (7 dias)</h4>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Data</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Linhas</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {uploads.recent.map((u, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2">{u.date}</td>
                    <td className="px-4 py-2">{u.rows}</td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {u.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value }) {
  return (
    <div className="card text-center">
      <div className="text-2xl font-bold text-primary-700">{value ?? '—'}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}
