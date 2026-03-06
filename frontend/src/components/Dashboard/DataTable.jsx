import { useState, useEffect, useCallback } from 'react';
import api from '../../services/api.js';

export function DataTable({ uploadId, source }) {
  const [data, setData] = useState([]);
  const [headers, setHeaders] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, total: 0, totalPages: 1 });
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const fetchData = useCallback(async (page = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page, limit: 20 });
      if (uploadId) params.set('upload_id', uploadId);
      if (source) params.set('source', source);

      const endpoint = searchTerm
        ? `/data/search?q=${encodeURIComponent(searchTerm)}&${params}`
        : `/data/list?${params}`;

      const { data: res } = await api.get(endpoint);
      const rows = res.data || [];
      setData(rows);
      setPagination(res.pagination || { page, total: 0, totalPages: 1 });
      if (rows.length > 0 && rows[0].data) {
        setHeaders(Object.keys(rows[0].data).slice(0, 10));
      }
    } catch (err) {
      console.error('Erro ao buscar dados:', err);
    } finally {
      setLoading(false);
    }
  }, [uploadId, source, searchTerm]);

  useEffect(() => { fetchData(1); }, [fetchData]);

  const handleSearch = (e) => {
    e.preventDefault();
    setSearchTerm(search);
  };

  const handleExport = async () => {
    const params = new URLSearchParams();
    if (uploadId) params.set('upload_id', uploadId);
    if (source) params.set('source', source);
    const token = localStorage.getItem('accessToken');
    const url = `/api/data/export?${params}`;
    const a = document.createElement('a');
    a.href = url;
    a.setAttribute('download', '');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <form onSubmit={handleSearch} className="flex-1 flex gap-2">
          <input
            className="input flex-1"
            placeholder="Buscar nos dados..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="btn-primary px-4">Buscar</button>
          {searchTerm && (
            <button
              type="button"
              className="btn-secondary px-3"
              onClick={() => { setSearch(''); setSearchTerm(''); }}
            >
              Limpar
            </button>
          )}
        </form>
        <button onClick={handleExport} className="btn-secondary">
          Exportar CSV
        </button>
      </div>

      {/* Tabela */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">#</th>
              {headers.map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase truncate max-w-32">
                  {h}
                </th>
              ))}
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fonte</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={headers.length + 2} className="px-4 py-8 text-center text-gray-400">Carregando...</td></tr>
            ) : data.length === 0 ? (
              <tr><td colSpan={headers.length + 2} className="px-4 py-8 text-center text-gray-400">Nenhum dado encontrado.</td></tr>
            ) : (
              data.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-400 text-xs">{row.row_index}</td>
                  {headers.map((h) => (
                    <td key={h} className="px-4 py-3 text-gray-700 max-w-32 truncate">
                      {row.data?.[h] != null ? String(row.data[h]) : '—'}
                    </td>
                  ))}
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                      row.source === 'mobne'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-green-100 text-green-700'
                    }`}>
                      {row.source}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Paginação */}
      {pagination.totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>{pagination.total} registros no total</span>
          <div className="flex gap-2">
            <button
              className="btn-secondary px-3 py-1 text-xs"
              disabled={pagination.page <= 1}
              onClick={() => fetchData(pagination.page - 1)}
            >
              Anterior
            </button>
            <span className="px-3 py-1 text-xs">
              {pagination.page} / {pagination.totalPages}
            </span>
            <button
              className="btn-secondary px-3 py-1 text-xs"
              disabled={pagination.page >= pagination.totalPages}
              onClick={() => fetchData(pagination.page + 1)}
            >
              Próxima
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
