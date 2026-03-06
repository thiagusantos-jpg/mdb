import { useState } from 'react';
import { DashboardLayout } from '../components/Dashboard/DashboardLayout.jsx';
import { ExcelUploader } from '../components/Upload/ExcelUploader.jsx';
import { DataTable } from '../components/Dashboard/DataTable.jsx';

export default function UploadPage() {
  const [lastUpload, setLastUpload] = useState(null);

  const handleSuccess = (data) => {
    setLastUpload(data);
  };

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Upload de Arquivo</h2>
          <p className="text-gray-500 mt-1">Faça upload de arquivos Excel para importar dados.</p>
        </div>

        <div className="card">
          <ExcelUploader onUploadSuccess={handleSuccess} />
        </div>

        {lastUpload && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <span className="text-green-500 text-xl">✓</span>
              <div>
                <p className="text-green-800 font-medium">Upload realizado com sucesso!</p>
                <p className="text-green-600 text-sm mt-1">
                  {lastUpload.upload?.rowCount?.toLocaleString('pt-BR')} linhas importadas
                  {lastUpload.upload?.sheetName && ` (aba: ${lastUpload.upload.sheetName})`}
                </p>
              </div>
            </div>
          </div>
        )}

        {lastUpload?.upload?.id && (
          <div className="card">
            <h3 className="font-semibold text-gray-800 mb-4">Dados importados</h3>
            <DataTable uploadId={lastUpload.upload.id} />
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
