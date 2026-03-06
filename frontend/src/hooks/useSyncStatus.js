import { useState, useEffect, useCallback } from 'react';
import { mobneSync } from '../services/mobneSync.js';

export function useSyncStatus(pollInterval = 30000) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const { data } = await mobneSync.getStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.error || 'Erro ao buscar status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, pollInterval);
    return () => clearInterval(interval);
  }, [fetchStatus, pollInterval]);

  return { status, loading, error, refetch: fetchStatus };
}
