import { useState } from 'react';
import { useSyncStatus } from '../../hooks/useSyncStatus.js';
import { mobneSync } from '../../services/mobneSync.js';

export function SyncStatus() {
  const { status, loading, refetch } = useSyncStatus(30000);
  const [syncing, setSyncing] = useState(false);
  const [entity, setEntity] = useState('produtos');

  const handleSync = async () => {
    setSyncing(true);
    try {
      await mobneSync.triggerSync(entity);
      await refetch();
    } catch (err) {
      console.error('Erro ao sincronizar:', err);
    } finally {
      setSyncing(false);
    }
  };

  const lastSync = status?.lastSync;
  const isRunning = status?.isRunning;

  const statusBadge = isRunning
    ? 'bg-yellow-100 text-yellow-700'
    : lastSync?.status === 'completed'
    ? 'bg-green-100 text-green-700'
    : lastSync?.status === 'failed'
    ? 'bg-red-100 text-red-700'
    : 'bg-gray-100 text-gray-600';

  const statusLabel = isRunning
    ? 'Sincronizando...'
    : lastSync?.status === 'completed'
    ? 'Sincronizado'
    : lastSync?.status === 'failed'
    ? 'Falhou'
    : 'Nunca sincronizado';

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">Sincronização Mobne</h3>
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusBadge}`}>
          {loading ? '...' : statusLabel}
        </span>
      </div>

      {lastSync && (
        <div className="text-xs text-gray-500 mb-4 space-y-1">
          <div>Última sync: {new Date(lastSync.started_at).toLocaleString('pt-BR')}</div>
          {lastSync.records_synced > 0 && (
            <div>Registros: {lastSync.records_synced}</div>
          )}
          {lastSync.entity && <div>Entidade: {lastSync.entity}</div>}
        </div>
      )}

      <div className="flex gap-2">
        <select
          className="input flex-1 text-sm"
          value={entity}
          onChange={(e) => setEntity(e.target.value)}
          disabled={syncing || isRunning}
        >
          <option value="produtos">Produtos</option>
          <option value="notas">Notas Fiscais</option>
          <option value="empresas">Empresas</option>
        </select>
        <button
          onClick={handleSync}
          className="btn-primary px-4 text-sm whitespace-nowrap"
          disabled={syncing || isRunning}
        >
          {syncing ? 'Sincronizando...' : 'Sincronizar'}
        </button>
      </div>
    </div>
  );
}
