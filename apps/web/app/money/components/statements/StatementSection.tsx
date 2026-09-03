'use client';

import { useRef, useState } from 'react';
import { ApiError, type Party } from '@/lib/api';
import { fetchStatement, type PartyStatement } from '@/lib/money';
import { mapMoneyError, moneyErrorMessage } from '../moneyErrors';

function str(v: unknown): string {
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  return '—';
}

interface Row {
  key: string;
  cells: string[];
}

/** Content-addressed keys for statement movement rows (dupes get a #n suffix). */
function keyedMovements(raw: unknown): Row[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Map<string, number>();
  return (raw as Record<string, unknown>[]).map((m) => {
    const cells = [
      str(m.datee),
      str(m.description),
      str(m.account_code),
      str(m.debit),
      str(m.credit),
      str(m.running_balance),
    ];
    const base = cells.join('');
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    return { key: n === 0 ? base : `${base}#${n}`, cells };
  });
}

export default function StatementSection({
  token,
  onAuthFail,
  parties,
}: {
  token: string;
  onAuthFail: () => void;
  parties: Party[] | null;
}) {
  const [partyId, setPartyId] = useState('');
  const [month, setMonth] = useState('');
  const [year, setYear] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [statement, setStatement] = useState<PartyStatement | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const seqRef = useRef(0);

  async function show() {
    const id = Number.parseInt(partyId, 10);
    if (!partyId || Number.isNaN(id)) {
      setError('اختر طرفاً لعرض الكشف');
      return;
    }
    if ((month || year) && (dateFrom || dateTo)) {
      setError('اختر الشهر والسنة أو المدى الزمني — وليس الاثنين معاً');
      return;
    }
    const seq = ++seqRef.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchStatement(token, id, {
        month: month || undefined,
        year: year || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      if (seq !== seqRef.current) return;
      setStatement(res);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return;
      if (seq !== seqRef.current) return;
      if (err instanceof ApiError && err.status === 401) {
        onAuthFail();
        return;
      }
      setStatement(null);
      setError(
        err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
      );
    } finally {
      if (seq === seqRef.current) setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <h3 className="pt-title">كشف حساب</h3>

      {parties === null ? (
        <p className="pt-caption" role="status">
          جارٍ تحميل الأطراف…
        </p>
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <label className="pt-caption flex flex-col gap-1">
            الطرف
            <select
              aria-label="الطرف"
              className="rounded border border-border px-2 py-1"
              value={partyId}
              onChange={(e) => setPartyId(e.target.value)}
            >
              <option value="">— اختر —</option>
              {(parties ?? []).map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.name_ar || p.namee} ({p.kind})
                </option>
              ))}
            </select>
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
            من تاريخ
            <input
              aria-label="من تاريخ"
              type="date"
              className="rounded border border-border px-2 py-1"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </label>
          <label className="pt-caption flex flex-col gap-1">
            إلى تاريخ
            <input
              aria-label="إلى تاريخ"
              type="date"
              className="rounded border border-border px-2 py-1"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </label>
          <button
            type="button"
            onClick={show}
            disabled={loading}
            className="rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
          >
            {loading ? 'جارٍ التحميل…' : 'عرض الكشف'}
          </button>
        </div>
      )}

      {error && (
        <p className="pt-caption text-red-600" role="alert">
          {error}
        </p>
      )}

      {statement && (
        <div className="flex flex-col gap-2">
          <p className="pt-caption">
            الرصيد الافتتاحي: <span className="pt-mono">{str(statement.opening_balance)}</span>
            {' · '}
            الرصيد الختامي: <span className="pt-mono">{str(statement.closing_balance)}</span>
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-start text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="pt-caption px-3 py-2 text-start">التاريخ</th>
                  <th className="pt-caption px-3 py-2 text-start">البيان</th>
                  <th className="pt-caption px-3 py-2 text-start">الحساب</th>
                  <th className="pt-caption px-3 py-2 text-start">مدين</th>
                  <th className="pt-caption px-3 py-2 text-start">دائن</th>
                  <th className="pt-caption px-3 py-2 text-start">الرصيد</th>
                </tr>
              </thead>
              <tbody>
                {keyedMovements(statement.movements).map(({ key, cells }) => (
                  <tr key={key} className="border-b border-border">
                    <td className="px-3 py-2">{cells[0]}</td>
                    <td className="px-3 py-2">{cells[1]}</td>
                    <td className="pt-mono break-all px-3 py-2">{cells[2]}</td>
                    <td className="pt-mono break-all px-3 py-2">{cells[3]}</td>
                    <td className="pt-mono break-all px-3 py-2">{cells[4]}</td>
                    <td className="pt-mono break-all px-3 py-2">{cells[5]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="pt-caption text-muted">
            إجمالي مدين <span className="pt-mono">{str(statement.debit_total)}</span> · إجمالي دائن{' '}
            <span className="pt-mono">{str(statement.credit_total)}</span>
          </p>
        </div>
      )}
    </div>
  );
}
