'use client';

import { useEffect, useState } from 'react';
import { Shell } from '@/components/shell';
import { clearToken, loadToken } from '@/lib/api';
import {
  ApiError,
  downloadReportExport,
  enqueuePrintJob,
  fetchPrintQueue,
  fetchReportGrid,
  fetchReportsCatalog,
  markPrintJobDone,
  type PrintJob,
  paramLabel,
  printReport,
  type ReportCatalogEntry,
  type ReportGrid,
} from '@/lib/reports';

const CATEGORY_LABELS: Record<string, string> = {
  money: 'المال',
  stock: 'المخزون',
  sales: 'المبيعات',
  purchases: 'المشتريات',
  accounting: 'الحسابات',
};

function categoryLabel(key: string): string {
  return CATEGORY_LABELS[key] ?? key;
}

/** Content-addressed React keys for static report rows (dupes get a #n suffix). */
function keyedRows(rows: string[][]): { key: string; cells: string[] }[] {
  const seen = new Map<string, number>();
  return rows.map((cells) => {
    const base = cells.join('\u0001');
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    return { key: n === 0 ? base : `${base}#${n}`, cells };
  });
}

function keyedCells(rowKey: string, cells: string[]): { key: string; cell: string }[] {
  const seen = new Map<string, number>();
  return cells.map((cell) => {
    const base = `${rowKey}:${cell}`;
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    return { key: n === 0 ? base : `${base}#${n}`, cell };
  });
}

type LoadState = 'boot' | 'login-required' | 'ready' | 'error';

export default function ReportsPage() {
  const [view, setView] = useState<LoadState>('boot');
  const [catalog, setCatalog] = useState<ReportCatalogEntry[]>([]);
  const [selected, setSelected] = useState<ReportCatalogEntry | null>(null);
  const [paramValues, setParamValues] = useState<Record<string, string>>({});
  const [paper, setPaper] = useState<'A4' | 'A5'>('A4');
  const [grid, setGrid] = useState<ReportGrid | null>(null);
  const [jobs, setJobs] = useState<PrintJob[]>([]);
  const [busy, setBusy] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    (async () => {
      const token = loadToken();
      if (!token) {
        if (!cancelled) setView('login-required');
        return;
      }
      try {
        const reports = await fetchReportsCatalog(token, controller.signal);
        if (cancelled) return;
        setCatalog(reports);
        setJobs(await fetchPrintQueue(token, controller.signal));
        if (!cancelled) setView('ready');
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          setView('login-required');
          return;
        }
        setErrorText('تعذّر الاتصال بالـ API');
        setView('error');
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  function selectReport(entry: ReportCatalogEntry) {
    setSelected(entry);
    setGrid(null);
    setErrorText(null);
    setPaper(entry.paper);
    const initial: Record<string, string> = {};
    for (const name of entry.params) initial[name] = '';
    setParamValues(initial);
  }

  async function requireToken(): Promise<string> {
    const token = loadToken();
    if (!token) throw new ApiError(401);
    return token;
  }

  function withBusy(fn: (entry: ReportCatalogEntry) => Promise<void>): () => Promise<void> {
    return async () => {
      if (busy || !selected) return;
      setBusy(true);
      setErrorText(null);
      try {
        await fn(selected);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          setView('login-required');
          return;
        }
        if (err instanceof ApiError && err.status === 400) {
          setErrorText('تحقّق من التواريخ المدخلة (من تاريخ بعد إلى تاريخ؟)');
          return;
        }
        setErrorText('تعذّر تنفيذ العملية — حاول مرة أخرى');
      } finally {
        setBusy(false);
      }
    };
  }

  const showGrid = grid !== null;

  const runShow = withBusy(async (entry) => {
    const token = await requireToken();
    setGrid(await fetchReportGrid(token, entry.code, paramValues));
  });

  const runPrint = withBusy(async (entry) => {
    const token = await requireToken();
    await printReport(token, entry.code, paramValues, paper);
  });

  const runExport = (format: 'xlsx' | 'pdf') =>
    withBusy(async (entry) => {
      const token = await requireToken();
      await downloadReportExport(token, entry.code, format, paramValues, paper);
    });

  const runEnqueue = withBusy(async (entry) => {
    const token = await requireToken();
    await enqueuePrintJob(token, entry.code, paramValues, paper);
    setJobs(await fetchPrintQueue(token));
  });

  /** Queue actions run without a selected report — only a busy guard. */
  function withQueueBusy<A>(fn: (args: A) => Promise<void>): (args: A) => Promise<void> {
    return async (args: A) => {
      if (busy) return;
      setBusy(true);
      setErrorText(null);
      try {
        await fn(args);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          setView('login-required');
          return;
        }
        setErrorText('تعذّر تنفيذ العملية — حاول مرة أخرى');
      } finally {
        setBusy(false);
      }
    };
  }

  const runMarkDone = withQueueBusy<number>(async (jobId) => {
    const token = await requireToken();
    await markPrintJobDone(token, jobId);
    setJobs(await fetchPrintQueue(token));
  });

  if (view === 'boot') {
    return (
      <Shell>
        <p className="pt-caption">جارٍ التحميل…</p>
      </Shell>
    );
  }

  if (view === 'login-required') {
    return (
      <Shell>
        <section className="flex h-full flex-col items-start gap-3">
          <h1 className="pt-title text-2xl">التقارير</h1>
          <p className="pt-caption">سجّل الدخول أولاً من شاشة الأدوية لعرض التقارير.</p>
        </section>
      </Shell>
    );
  }

  if (view === 'error') {
    return (
      <Shell>
        <section className="flex h-full flex-col items-start gap-3">
          <h1 className="pt-title text-2xl">التقارير</h1>
          <p className="pt-caption text-red-600">{errorText}</p>
        </section>
      </Shell>
    );
  }

  const grouped = new Map<string, ReportCatalogEntry[]>();
  for (const entry of catalog) {
    const list = grouped.get(entry.category) ?? [];
    list.push(entry);
    grouped.set(entry.category, list);
  }

  return (
    <Shell>
      <section className="flex h-full flex-col gap-4">
        <h1 className="pt-title text-2xl">التقارير</h1>

        <div className="flex flex-wrap gap-6">
          {[...grouped.entries()].map(([category, entries]) => (
            <div key={category} className="flex flex-col gap-1">
              <h2 className="pt-caption font-bold">{categoryLabel(category)}</h2>
              {entries.map((entry) => (
                <button
                  key={entry.code}
                  type="button"
                  onClick={() => selectReport(entry)}
                  className={
                    'rounded px-3 py-1.5 text-start transition-colors ' +
                    (selected?.code === entry.code
                      ? 'bg-[var(--accent-color)] text-white'
                      : 'hover:bg-[var(--background-secondary)]')
                  }
                >
                  {entry.title_ar}
                </button>
              ))}
            </div>
          ))}
        </div>

        {selected && (
          <div className="flex flex-wrap items-end gap-3 border-t border-[var(--border-primary)] pt-3">
            {selected.params.map((name) => (
              <label key={name} className="flex flex-col gap-1 text-sm">
                <span className="pt-caption">{paramLabel(name)}</span>
                <input
                  type="date"
                  value={paramValues[name] ?? ''}
                  onChange={(e) => setParamValues((prev) => ({ ...prev, [name]: e.target.value }))}
                  className="rounded border border-[var(--border-primary)] bg-transparent px-2 py-1"
                />
              </label>
            ))}
            <label className="flex flex-col gap-1 text-sm">
              <span className="pt-caption">الورق</span>
              <select
                value={paper}
                onChange={(e) => setPaper(e.target.value === 'A5' ? 'A5' : 'A4')}
                className="rounded border border-[var(--border-primary)] bg-transparent px-2 py-1"
              >
                <option value="A4">A4</option>
                <option value="A5">A5</option>
              </select>
            </label>
            <button type="button" onClick={runShow} disabled={busy} className="pt-button">
              عرض
            </button>
            <button type="button" onClick={runPrint} disabled={busy} className="pt-button">
              طباعة
            </button>
            <button type="button" onClick={runExport('pdf')} disabled={busy} className="pt-button">
              PDF
            </button>
            <button type="button" onClick={runExport('xlsx')} disabled={busy} className="pt-button">
              Excel
            </button>
            <button type="button" onClick={runEnqueue} disabled={busy} className="pt-button">
              إضافة لقائمة الطباعة
            </button>
          </div>
        )}

        {errorText && <p className="text-sm text-red-600">{errorText}</p>}

        {showGrid && grid && (
          <article className="flex flex-col gap-2">
            <header className="text-center">
              <h2 className="pt-title font-bold">{grid.title_ar}</h2>
              <p className="pt-caption">{grid.title_en}</p>
            </header>
            {grid.meta.length > 0 && (
              <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                {grid.meta.map((m) => (
                  <div key={m.label} className="flex gap-2">
                    <dt className="pt-caption">{m.label}:</dt>
                    <dd>{m.value}</dd>
                  </div>
                ))}
              </dl>
            )}
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr>
                    {grid.columns.map((col) => (
                      <th
                        key={col}
                        className="border border-[var(--border-primary)] px-2 py-1 text-start"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {keyedRows(grid.rows).map(({ key, cells }) => (
                    <tr key={key}>
                      {keyedCells(key, cells).map(({ key: cellKey, cell }) => (
                        <td
                          key={cellKey}
                          className="border border-[var(--border-primary)] px-2 py-1"
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
                {grid.foot && (
                  <tfoot>
                    <tr className="font-bold">
                      {grid.foot.map((cell, j) => (
                        <td
                          key={`${grid.columns[j] ?? j}:${cell}`}
                          className="border border-[var(--border-primary)] px-2 py-1"
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
            {grid.note && <p className="pt-caption">{grid.note}</p>}
          </article>
        )}

        <details className="border-t border-[var(--border-primary)] pt-3">
          <summary className="cursor-pointer pt-caption">
            قائمة الطباعة ({jobs.filter((j) => j.status === 'queued').length} في الانتظار)
          </summary>
          <ul className="mt-2 flex flex-col gap-1 text-sm">
            {jobs.length === 0 && <li className="pt-caption">لا توجد مهام طباعة.</li>}
            {jobs.map((job) => (
              <li key={job.id} className="flex items-center gap-3">
                <span>{job.report_code}</span>
                <span className="pt-caption">
                  {job.paper} · {job.status === 'queued' ? 'في الانتظار' : 'تمت'}
                </span>
                {job.status === 'queued' && (
                  <button
                    type="button"
                    onClick={() => runMarkDone(job.id)}
                    disabled={busy}
                    className="pt-button"
                  >
                    تم الطباعة
                  </button>
                )}
              </li>
            ))}
          </ul>
        </details>
      </section>
    </Shell>
  );
}
