import { API_URL } from './api';

export interface ReportCatalogEntry {
  code: string;
  category: string;
  title_ar: string;
  title_en: string;
  params: string[];
  paper: 'A4' | 'A5';
}

export interface ReportGrid {
  title_ar: string;
  title_en: string;
  meta: { label: string; value: string }[];
  columns: string[];
  rows: string[][];
  foot: string[] | null;
  note: string | null;
}

export interface PrintJob {
  id: number;
  report_code: string;
  params: Record<string, string>;
  paper: 'A4' | 'A5';
  status: 'queued' | 'done' | 'failed';
  created_at: string | null;
  done_at: string | null;
}

/** Arabic labels for the known report params (date inputs). */
export const PARAM_LABELS: Record<string, string> = {
  datee: 'التاريخ',
  date_from: 'من تاريخ',
  date_to: 'إلى تاريخ',
};

export function paramLabel(name: string): string {
  return PARAM_LABELS[name] ?? name;
}

function queryString(params: Record<string, string>): string {
  const pairs = Object.entries(params)
    .filter(([, v]) => v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`);
  return pairs.length ? `&${pairs.join('&')}` : '';
}

export async function fetchReportsCatalog(
  token: string,
  signal?: AbortSignal,
): Promise<ReportCatalogEntry[]> {
  const res = await fetch(`${API_URL}/api/v1/reports`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  const body = (await res.json()) as { reports: ReportCatalogEntry[] };
  return body.reports;
}

export async function fetchReportGrid(
  token: string,
  code: string,
  params: Record<string, string>,
  signal?: AbortSignal,
): Promise<ReportGrid> {
  const res = await fetch(
    `${API_URL}/api/v1/reports/${encodeURIComponent(code)}?format=grid${queryString(params)}`,
    { headers: { Authorization: `Bearer ${token}` }, signal },
  );
  await throwForStatus(res);
  return (await res.json()) as ReportGrid;
}

export async function fetchPrintQueue(token: string, signal?: AbortSignal): Promise<PrintJob[]> {
  const res = await fetch(`${API_URL}/api/v1/reports/print-queue`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  const body = (await res.json()) as { jobs: PrintJob[] };
  return body.jobs;
}

export async function enqueuePrintJob(
  token: string,
  code: string,
  params: Record<string, string>,
  paper: 'A4' | 'A5',
): Promise<PrintJob> {
  const res = await fetch(`${API_URL}/api/v1/reports/${encodeURIComponent(code)}/print-queue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ params, paper }),
  });
  await throwForStatus(res);
  return (await res.json()) as PrintJob;
}

export async function markPrintJobDone(token: string, jobId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/reports/print-queue/${jobId}/done`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  await throwForStatus(res);
}

/** Download an export (xlsx/pdf) as a file via a blob anchor. */
export async function downloadReportExport(
  token: string,
  code: string,
  format: 'xlsx' | 'pdf',
  params: Record<string, string>,
  paper: 'A4' | 'A5',
): Promise<void> {
  const res = await fetch(
    `${API_URL}/api/v1/reports/${encodeURIComponent(code)}/export?format=${format}` +
      `&paper=${paper}${queryString(params)}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  await throwForStatus(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${code}.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/** Open the black-on-white printable page in a new tab (browser print → PDF). */
export async function printReport(
  token: string,
  code: string,
  params: Record<string, string>,
  paper: 'A4' | 'A5',
): Promise<void> {
  const res = await fetch(
    `${API_URL}/api/v1/reports/${encodeURIComponent(code)}?format=html` +
      `&paper=${paper}${queryString(params)}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  await throwForStatus(res);
  const html = await res.text();
  const blobUrl = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
  window.open(blobUrl, '_blank', 'noopener');
}

async function throwForStatus(res: Response): Promise<void> {
  if (!res.ok) throw new ApiError(res.status);
}

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number) {
    super(`API returned ${status}`);
    this.name = 'ApiError';
    this.status = status;
  }
}
