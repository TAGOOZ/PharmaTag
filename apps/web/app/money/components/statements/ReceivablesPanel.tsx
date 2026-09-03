'use client';

import { useEffect, useState } from 'react';
import { ApiError } from '@/lib/api';
import { fetchReceivables } from '@/lib/money';
import { mapMoneyError, moneyErrorMessage } from '../moneyErrors';

function str(v: unknown): string {
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  return '—';
}

interface ReceivableRow {
  party_id: number;
  namee: string;
  name_ar: string;
  kind: string;
  credit_limit: string;
  balance: string;
}

export default function ReceivablesPanel({
  token,
  onAuthFail,
}: {
  token: string;
  onAuthFail: () => void;
}) {
  const [rows, setRows] = useState<ReceivableRow[] | null>(null);
  const [total, setTotal] = useState('0.00');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchReceivables(token, controller.signal);
        if (cancelled) return;
        const list = Array.isArray(res.receivables) ? res.receivables : [];
        setRows(
          (list as Record<string, unknown>[]).map((p) => ({
            party_id: Number(p.party_id),
            namee: str(p.namee),
            name_ar: str(p.name_ar),
            kind: str(p.kind),
            credit_limit: str(p.credit_limit),
            balance: str(p.balance),
          })),
        );
        setTotal(str(res.total));
      } catch (err) {
        if (cancelled || (err as Error)?.name === 'AbortError') return;
        if (err instanceof ApiError && err.status === 401) {
          onAuthFail();
          return;
        }
        setRows([]);
        setError(
          err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [token, onAuthFail]);

  return (
    <div className="flex flex-col gap-3">
      <h3 className="pt-title">الذمم المدينة (العملاء)</h3>
      {error && (
        <p className="pt-caption text-red-600" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p className="pt-caption" role="status">
          جارٍ التحميل…
        </p>
      ) : rows !== null && rows.length === 0 ? (
        <p className="pt-caption">لا توجد ذمم مدينة</p>
      ) : rows ? (
        <div className="flex flex-col gap-2">
          <p className="pt-caption">
            الإجمالي: <span className="pt-mono break-all">{total}</span>
          </p>
          <p className="pt-caption text-muted">الرصيد الموجب مستحق لنا من العميل.</p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-start text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="pt-caption px-3 py-2 text-start">العميل</th>
                  <th className="pt-caption px-3 py-2 text-start">حد الائتمان</th>
                  <th className="pt-caption px-3 py-2 text-start">الرصيد</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={Number.isFinite(r.party_id) ? r.party_id : `row-${r.namee}-${r.balance}`}
                    className="border-b border-border"
                  >
                    <td className="px-3 py-2">
                      {r.name_ar || r.namee} ({r.kind})
                    </td>
                    <td className="pt-mono break-all px-3 py-2">{r.credit_limit}</td>
                    <td className="pt-mono break-all px-3 py-2">{r.balance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
