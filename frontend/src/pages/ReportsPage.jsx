import { useState } from 'react';
import { DashboardLayout } from '../components/Dashboard/DashboardLayout.jsx';
import { SalesReport } from '../components/Reports/SalesReport.jsx';
import { MetricsChart } from '../components/Reports/MetricsChart.jsx';
import { BillingChart } from '../components/Reports/BillingChart.jsx';

export default function ReportsPage() {
  const [tab, setTab] = useState('billing');

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Relatórios</h2>
          <p className="text-gray-500 mt-1">Análises e KPIs dos dados sincronizados.</p>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <div className="flex gap-4">
            {[
              { key: 'billing', label: 'Faturamento Diário' },
              { key: 'metrics', label: 'Métricas e Gráficos' },
              { key: 'sales', label: 'Relatório de Dados' },
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                  tab === key
                    ? 'border-primary-600 text-primary-700'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {tab === 'billing' && <BillingChart />}
        {tab === 'metrics' && <MetricsChart />}
        {tab === 'sales' && <SalesReport />}
      </div>
    </DashboardLayout>
  );
}
