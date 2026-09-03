'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '@/lib/api';
import {
  fetchBalanceSheet,
  fetchBalanceSheetHtml,
  fetchTrialBalance,
  type MizanParams,
} from '@/lib/money';
import { mapMoneyError, moneyErrorMessage } from './moneyErrors';

function str(v: unknown): string {
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  return '—';
}

type TbRow = Record<string, unknown>;
type BsSection = { total: string; accounts: Record<string, unknown>[] };

function asRows(raw: unknown): TbRow[] {
  return Array.isArray(raw) ? (raw as TbRow[]) : [];
}

function asSection(raw: unknown): BsSection {
  if (raw && typeof raw === 'object') {
    const s = raw as Record<string, unknown>;
    return {
      total: str(s.total),
      accounts: asRows(s.accounts),
    };
  }
  return { total: '0.00', accounts: [] };
}

/** Content-addressed keys for trial-balance rows (dupes get a #n suffix). */
function keyedTb(rows: TbRow[]): { key: string; row: TbRow }[] {
  const seen = new Map<string, number>();
  return rows.map((row) => {
    const base = `${str(row.code)}`;
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    return { key: n === 0 ? base : `${base}#${n}`, row };
  });
}

function keyedBs(
  accounts: Record<string, unknown>[],
): { key: string; acc: Record<string, unknown> }[] {
  const seen = new Map<string, number>();
  return accounts.map((acc) => {
    const base = `${str(acc.code)}:${str(acc.amount)}`;
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    return { key: n === 0 ? base : `${base}#${n}`, acc };
  });
}

export default function MizanTab({ token, onAuthFail }: { token: string; onAuthFail: () => void }) {
  const [month, setMonth] = useState('');
  const [year, setYear] = useState('');
  const [tb, setTb] = useState<Record<string, unknown> | null>(null);
  const [bs, setBs] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [printing, setPrinting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const seqRef = useRef(0);

  const load = useCallback(
    async (params: MizanParams, signal?: AbortSignal) => {
      const seq = ++seqRef.current;
      setLoading(true);
      setError(null);
      try {
        const [tbRes, bsRes] = await Promise.all([
          fetchTrialBalance(token, params, signal),
          fetchBalanceSheet(token, params, signal),
        ]);
        if (seq !== seqRef.current) return;
        setTb(tbRes as Record<string, unknown>);
        setBs(bsRes as Record<string, unknown>);
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        if (seq !== seqRef.current) return;
        if (err instanceof ApiError && err.status === 401) {
          onAuthFail();
          return;
        }
        setTb(null);
        setBs(null);
        setError(
          err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
        );
      } finally {
        if (seq === seqRef.current) setLoading(false);
      }
    },
    [token, onAuthFail],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load({}, controller.signal);
    return () => controller.abort();
  }, [load]);

  function params(): MizanParams {
    return {
      month: month || undefined,
      year: year || undefined,
    };
  }

  async function print() {
    if (printing) return;
    setPrinting(true);
    setError(null);
    try {
      const html = await fetchBalanceSheetHtml(token, params());
      const blobUrl = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
      window.open(blobUrl, '_blank', 'noopener');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onAuthFail();
        return;
      }
      setError(
        err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
      );
    } finally {
      setPrinting(false);
    }
  }

  const tbAccounts = tb ? asRows(tb.accounts) : null;
  const tbTotals = tb && typeof tb.totals === 'object' ? (tb.totals as TbRow) : null;

  const sections: { title: string; section: BsSection }[] = bs
    ? [
        { title: 'الأصول', section: asSection(bs.assets) },
        { title: 'الخصوم', section: asSection(bs.liabilities) },
        { title: 'حقوق الملكية', section: asSection(bs.equity) },
      ]
    : [];

  return (
    <div className="flex flex-col gap-4">
      <h2 className="pt-title text-lg">ميزان المراجعة والميزانية</h2>

      <div className="flex flex-wrap items-end gap-2">
        <label className="pt-caption flex flex-col gap-1">
          الشهر
          <input
            aria-label="الشهر"
            inputMode="numeric"
            className="rounded border border-border px-2 py-1"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
        </label>
        <label className="pt-caption flex flex-col gap-1">
          السنة
          <input
            aria-label="السنة"
            inputMode="numeric"
            className="rounded border border-border px-2 py-1"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />
        </label>
        <button
          type="button"
          onClick={() => load(params())}
          disabled={loading}
          className="rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
        >
          {loading ? 'جارٍ التحميل…' : 'عرض'}
        </button>
        <button
          type="button"
          onClick={print}
          disabled={printing}
          className="rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
        >
          {printing ? 'جارٍ التجهيز…' : 'نسخة للطباعة'}
        </button>
      </div>

      {error && (
        <p className="pt-caption text-red-600" role="alert">
          {error}
        </p>
      )}

      {loading && tb === null ? (
        <p className="pt-caption" role="status" aria-live="polite">
          جارٍ التحميل…
        </p>
      ) : (
        <>
          <div className="flex flex-col gap-2">
            <h3 className="pt-title">ميزان المراجعة</h3>
            {tbAccounts !== null && tbAccounts.length === 0 ? (
              <p className="pt-caption">لا توجد حسابات لهذه الفترة</p>
            ) : tbAccounts ? (
              <>
                <p className="pt-caption" role="status">
                  {tb?.balanced ? 'الميزان متوازن' : 'الميزان غير متوازن'}
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-start text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="pt-caption px-3 py-2 text-start">الكود</th>
                        <th className="pt-caption px-3 py-2 text-start">الاسم</th>
                        <th className="pt-caption px-3 py-2 text-start">افتتاحي مدين</th>
                        <th className="pt-caption px-3 py-2 text-start">افتتاحي دائن</th>
                        <th className="pt-caption px-3 py-2 text-start">مدين</th>
                        <th className="pt-caption px-3 py-2 text-start">دائن</th>
                        <th className="pt-caption px-3 py-2 text-start">ختامي مدين</th>
                        <th className="pt-caption px-3 py-2 text-start">ختامي دائن</th>
                      </tr>
                    </thead>
                    <tbody>
                      {keyedTb(tbAccounts).map(({ key, row }) => (
                        <tr key={key} className="border-b border-border">
                          <td className="pt-mono px-3 py-2">{str(row.code)}</td>
                          <td className="px-3 py-2">{str(row.name_ar)}</td>
                          <td className="pt-mono px-3 py-2">{str(row.opening_debit)}</td>
                          <td className="pt-mono px-3 py-2">{str(row.opening_credit)}</td>
                          <td className="pt-mono px-3 py-2">{str(row.debit)}</td>
                          <td className="pt-mono px-3 py-2">{str(row.credit)}</td>
                          <td className="pt-mono px-3 py-2">{str(row.closing_debit)}</td>
                          <td className="pt-mono px-3 py-2">{str(row.closing_credit)}</td>
                        </tr>
                      ))}
                    </tbody>
                    {tbTotals && (
                      <tfoot>
                        <tr className="font-bold">
                          <td colSpan={2} className="px-3 py-2">
                            الإجمالي
                          </td>
                          <td className="pt-mono px-3 py-2">{str(tbTotals.opening_debit)}</td>
                          <td className="pt-mono px-3 py-2">{str(tbTotals.opening_credit)}</td>
                          <td className="pt-mono px-3 py-2">{str(tbTotals.debit)}</td>
                          <td className="pt-mono px-3 py-2">{str(tbTotals.credit)}</td>
                          <td className="pt-mono px-3 py-2">{str(tbTotals.closing_debit)}</td>
                          <td className="pt-mono px-3 py-2">{str(tbTotals.closing_credit)}</td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              </>
            ) : null}
          </div>

          {bs && (
            <div className="flex flex-col gap-3 border-t border-border pt-4">
              <h3 className="pt-title">الميزانية العمومية</h3>
              <p className="pt-caption" role="status">
                {bs.balanced ? 'الميزانية متوازنة' : 'الميزانية غير متوازنة'}
              </p>
              <p className="pt-caption">
                الأصول = الخصوم + حقوق الملكية:{' '}
                <span className="pt-mono">{str(bs.total_assets)}</span> ={' '}
                <span className="pt-mono">{str(bs.total_liabilities_equity)}</span>
              </p>
              {sections.map(({ title, section }) => (
                <div key={title} className="flex flex-col gap-1">
                  <h4 className="pt-caption font-bold">
                    {title} — الإجمالي <span className="pt-mono">{section.total}</span>
                  </h4>
                  {section.accounts.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse text-start text-sm">
                        <tbody>
                          {keyedBs(section.accounts).map(({ key, acc }) => (
                            <tr key={key} className="border-b border-border">
                              <td className="pt-mono px-3 py-2">{str(acc.code)}</td>
                              <td className="px-3 py-2">{str(acc.name_ar)}</td>
                              <td className="pt-mono px-3 py-2">{str(acc.amount)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
