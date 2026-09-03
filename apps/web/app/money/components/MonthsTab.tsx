'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '@/lib/api';
import {
  closeMonth,
  fetchMonth,
  fetchMonths,
  fetchOpenBalances,
  fetchOpeningBalances,
  type MonthClose,
  type OpeningPayload,
  reopenMonth,
} from '@/lib/money';
import { mapMoneyError, moneyErrorMessage } from './moneyErrors';

function str(v: unknown): string {
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  return '—';
}

function num(v: unknown): number {
  return typeof v === 'number' ? v : Number(v);
}

function monthKey(m: MonthClose): string {
  return `${str(m.year)}-${str(m.month)}`;
}

/** Content-addressed keys for balance rows (dupes get a #n suffix). */
function keyedBalanceRows(raw: unknown): { key: string; cells: string[] }[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Map<string, number>();
  return (raw as Record<string, unknown>[]).map((r) => {
    const cells = [
      str(r.code ?? r.account_code),
      str(r.name_ar ?? r.account_name),
      str(r.debit),
      str(r.credit),
    ];
    const base = cells.join(' ');
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    return { key: n === 0 ? base : `${base}#${n}`, cells };
  });
}

export default function MonthsTab({
  token,
  onAuthFail,
}: {
  token: string;
  onAuthFail: () => void;
}) {
  const [months, setMonths] = useState<MonthClose[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const [year, setYear] = useState('');
  const [month, setMonth] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  const [reopeningKey, setReopeningKey] = useState<string | null>(null);
  const [actionsForbidden, setActionsForbidden] = useState(false);

  const [balances, setBalances] = useState<Record<string, unknown> | null>(null);
  const [balancesTitle, setBalancesTitle] = useState('');
  const [balancesLoading, setBalancesLoading] = useState(false);
  const [opening, setOpening] = useState<OpeningPayload | null>(null);
  const [openingLoading, setOpeningLoading] = useState(false);

  const seqRef = useRef(0);
  const actionLock = useRef(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const seq = ++seqRef.current;
      setLoading(true);
      setError(null);
      try {
        const res = await fetchMonths(token, signal);
        if (seq !== seqRef.current) return;
        setMonths(res.months);
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        if (seq !== seqRef.current) return;
        if (err instanceof ApiError && err.status === 401) {
          onAuthFail();
          return;
        }
        setMonths([]);
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
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  function parseYearMonth(): { y: number; m: number } | null {
    const y = Number.parseInt(year, 10);
    const m = Number.parseInt(month, 10);
    if (Number.isNaN(y) || Number.isNaN(m) || m < 1 || m > 12) {
      setFormError('أدخل سنة وشهراً صحيحين (الشهر 1-12)');
      return null;
    }
    return { y, m };
  }

  function upsert(closed: MonthClose) {
    setMonths((prev) => {
      if (!prev) return [closed];
      const key = monthKey(closed);
      const idx = prev.findIndex((c) => monthKey(c) === key);
      if (idx === -1) return [closed, ...prev];
      return prev.map((c, i) => (i === idx ? closed : c));
    });
  }

  async function close() {
    if (actionLock.current) return;
    const ym = parseYearMonth();
    if (!ym) return;
    actionLock.current = true;
    setBusy(true);
    setClosing(true);
    setFormError(null);
    setFormSuccess(null);
    try {
      upsert(await closeMonth(token, ym.y, ym.m));
      setActionsForbidden(false);
      setFormSuccess('تم تقفيل الشهر');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onAuthFail();
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setForbidden(true);
        setFormError(moneyErrorMessage(err.status, err.detail));
        return;
      }
      setFormError(
        err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
      );
    } finally {
      actionLock.current = false;
      setBusy(false);
      setClosing(false);
    }
  }

  async function reopen(y: number, m: number) {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    const key = `${y}-${m}`;
    setReopeningKey(key);
    setFormError(null);
    setFormSuccess(null);
    try {
      upsert(await reopenMonth(token, y, m));
      setActionsForbidden(false);
      setFormSuccess('تمت إعادة فتح الشهر');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onAuthFail();
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setActionsForbidden(true);
      }
      setFormError(
        err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
      );
    } finally {
      actionLock.current = false;
      setBusy(false);
      setReopeningKey(null);
    }
  }

  const balancesSeqRef = useRef(0);
  const balancesAbortRef = useRef<AbortController | null>(null);
  const openingSeqRef = useRef(0);
  const openingAbortRef = useRef<AbortController | null>(null);

  async function showBalances(y: number, m: number) {
    const seq = ++balancesSeqRef.current;
    balancesAbortRef.current?.abort();
    const controller = new AbortController();
    balancesAbortRef.current = controller;
    setBalancesLoading(true);
    setBalances(null);
    setFormError(null);
    try {
      // Prefer the month detail (carries next_open_balances); fall back to the
      // archival open-balances view when the month has no close row yet.
      let payload: Record<string, unknown>;
      try {
        const detail = (await fetchMonth(token, y, m, controller.signal)) as Record<
          string,
          unknown
        >;
        const next = detail.next_open_balances;
        if (next && typeof next === 'object') {
          payload = next as Record<string, unknown>;
        } else {
          payload = (await fetchOpenBalances(token, y, m, controller.signal)) as Record<
            string,
            unknown
          >;
        }
      } catch (inner: unknown) {
        // Fall back only when the month was never closed (404). Any other
        // failure (403/400/500) is the real answer — surface it, and never
        // show a different period's rows under this month's title.
        if (inner instanceof ApiError && inner.status === 404) {
          if (controller.signal.aborted) return;
          payload = (await fetchOpenBalances(token, y, m, controller.signal)) as Record<
            string,
            unknown
          >;
        } else {
          throw inner;
        }
      }
      if (seq !== balancesSeqRef.current) return;
      setBalances(payload);
      setBalancesTitle(`أرصدة ${y}/${m}`);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return;
      if (seq !== balancesSeqRef.current) return;
      if (err instanceof ApiError && err.status === 401) {
        onAuthFail();
        return;
      }
      setFormError(
        err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
      );
    } finally {
      if (seq === balancesSeqRef.current) {
        if (balancesAbortRef.current === controller) balancesAbortRef.current = null;
        setBalancesLoading(false);
      }
    }
  }

  async function showOpening() {
    const ym = parseYearMonth();
    if (!ym) return;
    const seq = ++openingSeqRef.current;
    openingAbortRef.current?.abort();
    const controller = new AbortController();
    openingAbortRef.current = controller;
    setOpeningLoading(true);
    setOpening(null);
    setFormError(null);
    try {
      const res = await fetchOpeningBalances(token, ym.y, ym.m, controller.signal);
      if (seq !== openingSeqRef.current) return;
      setOpening(res);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return;
      if (seq !== openingSeqRef.current) return;
      if (err instanceof ApiError && err.status === 401) {
        onAuthFail();
        return;
      }
      setFormError(
        err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
      );
    } finally {
      if (seq === openingSeqRef.current) {
        if (openingAbortRef.current === controller) openingAbortRef.current = null;
        setOpeningLoading(false);
      }
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="pt-title text-lg">تقفيل الشهور والأرصدة الافتتاحية</h2>

      {error && (
        <p className="pt-caption text-red-600" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <p className="pt-caption" role="status" aria-live="polite">
          جارٍ التحميل…
        </p>
      ) : months !== null && months.length === 0 ? (
        <p className="pt-caption">لا توجد شهور مقفلة</p>
      ) : months ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-start text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="pt-caption px-3 py-2 text-start">السنة</th>
                <th className="pt-caption px-3 py-2 text-start">الشهر</th>
                <th className="pt-caption px-3 py-2 text-start">الحالة</th>
                <th className="pt-caption px-3 py-2 text-start">إجراء</th>
              </tr>
            </thead>
            <tbody>
              {months.map((c) => {
                const y = num(c.year);
                const m = num(c.month);
                const key = monthKey(c);
                return (
                  <tr key={key} className="border-b border-border">
                    <td className="pt-mono break-all px-3 py-2">{str(c.year)}</td>
                    <td className="pt-mono break-all px-3 py-2">{str(c.month)}</td>
                    <td className="px-3 py-2">{str(c.status)}</td>
                    <td className="flex gap-2 px-3 py-2">
                      <button
                        type="button"
                        onClick={() => showBalances(y, m)}
                        className="rounded border border-border px-2 py-1 text-xs"
                      >
                        عرض الأرصدة
                      </button>
                      {str(c.status) === 'closed' && (
                        <button
                          type="button"
                          disabled={actionsForbidden || busy || reopeningKey === key}
                          onClick={() => reopen(y, m)}
                          className="rounded border border-border px-2 py-1 text-xs disabled:opacity-50"
                        >
                          {reopeningKey === key ? 'جارٍ الفتح…' : 'إعادة فتح الشهر'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {balancesLoading ? (
        <p className="pt-caption" role="status">
          جارٍ التحميل…
        </p>
      ) : balances ? (
        <div className="flex flex-col gap-2">
          <h3 className="pt-title">{balancesTitle}</h3>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-start text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="pt-caption px-3 py-2 text-start">الكود</th>
                  <th className="pt-caption px-3 py-2 text-start">الاسم</th>
                  <th className="pt-caption px-3 py-2 text-start">مدين</th>
                  <th className="pt-caption px-3 py-2 text-start">دائن</th>
                </tr>
              </thead>
              <tbody>
                {keyedBalanceRows(balances.rows).map(({ key, cells }) => (
                  <tr key={key} className="border-b border-border">
                    <td className="pt-mono break-all px-3 py-2">{cells[0]}</td>
                    <td className="px-3 py-2">{cells[1]}</td>
                    <td className="pt-mono break-all px-3 py-2">{cells[2]}</td>
                    <td className="pt-mono break-all px-3 py-2">{cells[3]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="pt-caption text-muted">
            إجمالي مدين <span className="pt-mono">{str(balances.total_debit)}</span> · إجمالي دائن{' '}
            <span className="pt-mono">{str(balances.total_credit)}</span>
          </p>
        </div>
      ) : null}

      {openingLoading ? (
        <p className="pt-caption" role="status">
          جارٍ التحميل…
        </p>
      ) : opening ? (
        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <h3 className="pt-title">
            أرصدة الافتتاح {str(opening.year)}/{str(opening.month)} —{' '}
            <span className="pt-mono">{str(opening.entry_no)}</span>
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-start text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="pt-caption px-3 py-2 text-start">الكود</th>
                  <th className="pt-caption px-3 py-2 text-start">الاسم</th>
                  <th className="pt-caption px-3 py-2 text-start">مدين</th>
                  <th className="pt-caption px-3 py-2 text-start">دائن</th>
                </tr>
              </thead>
              <tbody>
                {keyedBalanceRows(opening.rows).map(({ key, cells }) => (
                  <tr key={key} className="border-b border-border">
                    <td className="pt-mono break-all px-3 py-2">{cells[0]}</td>
                    <td className="px-3 py-2">{cells[1]}</td>
                    <td className="pt-mono break-all px-3 py-2">{cells[2]}</td>
                    <td className="pt-mono break-all px-3 py-2">{cells[3]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="pt-caption text-muted">
            إجمالي مدين <span className="pt-mono">{str(opening.total_debit)}</span> · إجمالي دائن{' '}
            <span className="pt-mono">{str(opening.total_credit)}</span>
            {opening.balanced ? ' · متوازن' : ' · غير متوازن'}
          </p>
        </div>
      ) : null}

      {formError && (
        <p className="pt-caption text-red-600" role="alert">
          {formError}
        </p>
      )}
      {formSuccess && (
        <p className="pt-caption text-green-600" role="status">
          {formSuccess}
        </p>
      )}

      {forbidden ? (
        <p className="pt-caption text-red-600" role="alert">
          ليس لديك صلاحية — تحقق من دورك (months.close)
        </p>
      ) : (
        <div className="pt-card flex flex-col gap-3">
          <p className="pt-title">تقفيل / قراءة شهر</p>
          <div className="flex flex-wrap items-end gap-2">
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
            <button
              type="button"
              onClick={close}
              disabled={busy || closing}
              className="rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
            >
              {closing ? 'جارٍ التقفيل…' : 'تقفيل الشهر'}
            </button>
            <button
              type="button"
              onClick={showOpening}
              disabled={openingLoading}
              className="rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
            >
              {openingLoading ? 'جارٍ التحميل…' : 'عرض أرصدة الافتتاح'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
