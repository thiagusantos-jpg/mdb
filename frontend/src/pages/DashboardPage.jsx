import { DashboardLayout } from '../components/Dashboard/DashboardLayout.jsx';
import { DataTable } from '../components/Dashboard/DataTable.jsx';
import { SyncStatus } from '../components/Dashboard/SyncStatus.jsx';
import { useAuth } from '../hooks/useAuth.js';

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Dashboard</h2>
          <p className="text-gray-500 mt-1">Bem-vindo, {user?.nome || user?.email}</p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2">
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-4">Dados</h3>
              <DataTable />
            </div>
          </div>
          <div>
            <SyncStatus />
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
