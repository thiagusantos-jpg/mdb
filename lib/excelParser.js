import * as XLSX from 'xlsx';

/**
 * Parseia um buffer de arquivo Excel e retorna array de objetos.
 * @param {Buffer} buffer - conteúdo do arquivo .xlsx/.xls
 * @param {object} options
 * @param {number} options.headerRow - linha do cabeçalho (default: 1)
 * @param {string} options.sheetName - nome da aba (default: primeira aba)
 * @returns {{ headers: string[], rows: object[], sheetName: string }}
 */
export function parseExcel(buffer, options = {}) {
  const workbook = XLSX.read(buffer, { type: 'buffer', cellDates: true });

  const sheetName = options.sheetName || workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];

  if (!sheet) {
    throw new Error(`Aba "${sheetName}" não encontrada no arquivo.`);
  }

  // Converte para array de objetos com cabeçalhos da primeira linha
  const rows = XLSX.utils.sheet_to_json(sheet, {
    defval: null,
    raw: false,
    dateNF: 'yyyy-mm-dd',
  });

  if (rows.length === 0) {
    return { headers: [], rows: [], sheetName };
  }

  const headers = Object.keys(rows[0]);

  return { headers, rows, sheetName };
}

/**
 * Converte array de objetos para CSV.
 * @param {object[]} rows
 * @returns {string}
 */
export function rowsToCsv(rows) {
  if (rows.length === 0) return '';

  const headers = Object.keys(rows[0]);
  const escape = (v) => {
    const str = v === null || v === undefined ? '' : String(v);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const lines = [
    headers.map(escape).join(','),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(',')),
  ];

  return lines.join('\n');
}
