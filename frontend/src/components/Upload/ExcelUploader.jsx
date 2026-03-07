import { useState, useRef } from 'react';
import api from '../../services/api.js';

export function ExcelUploader({ onUploadSuccess }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const uploadFile = async (file) => {
    if (!file) return;

    const allowed = ['.xlsx', '.xls'];
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!allowed.includes(ext)) {
      setError('Formato não suportado. Use .xlsx ou .xls');
      return;
    }

    setUploading(true);
    setError('');
    setProgress(10);

    try {
      const buffer = await file.arrayBuffer();
      setProgress(40);

      const { data } = await api.post('/upload/excel', buffer, {
        headers: {
          'Content-Type': 'application/octet-stream',
          'X-Filename': `upload_${Date.now()}${ext}`,
          'X-Original-Name': file.name,
        },
        onUploadProgress: (e) => {
          setProgress(40 + Math.round((e.loaded / e.total) * 50));
        },
      });

      setProgress(100);
      onUploadSuccess?.(data);
    } catch (err) {
      const msg = err.response?.data?.error;
      setError(typeof msg === 'string' ? msg : 'Erro ao fazer upload.');
    } finally {
      setUploading(false);
      setTimeout(() => setProgress(0), 1500);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  };

  return (
    <div className="space-y-4">
      <div
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          dragging ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="text-4xl mb-3">📄</div>
        <p className="text-gray-600 font-medium">
          Arraste um arquivo Excel aqui ou <span className="text-primary-600">clique para selecionar</span>
        </p>
        <p className="text-gray-400 text-sm mt-1">.xlsx, .xls — máx. 10MB</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={(e) => uploadFile(e.target.files[0])}
        />
      </div>

      {/* Barra de progresso */}
      {uploading && (
        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Enviando arquivo...</span>
            <span>{progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
