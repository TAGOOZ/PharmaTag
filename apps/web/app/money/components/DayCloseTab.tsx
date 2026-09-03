'use client';

import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '@/lib/api';
import { closeDay, type DayClose, fetchDayCloses, reopenDay } from '@/lib/money';
import { isMoneyValid, normalizeDecimal } from '@/lib/posMoney';
import { mapMoneyError, moneyErrorMessage } from './moneyErrors';

function str(v: unknown): string {
  return typeof v === 'string' ? v : (v ?? '—').toString();
}

function closeId(c: DayClose): number {
  return typeof c.id === 'number' ? c.id : Number(c.id);
}

export default function DayCloseTab({
  token,
  onAuthFail,
}: {
  token: string;
  onAuthFail: () => void;
}) {
  const [closes, setCloses] = useState<DayClose[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const [counted, setCounted] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reopeningId, setReopeningId] = useState<number | null>(null);

  const seqRef = useRef(0);
  const savingLock = useRef(false);
  const reopenLock = useRef(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const seq = ++seqRef.current;
      setLoading(true);
      setError(null);
      try {
        const res = await fetchDayCloses(token, {}, signal);
        if (seq !== seqRef.current) return;
        setCloses(res.day_closes);
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        if (seq !== seqRef.current) return;
        if (err instanceof ApiError && err.status === 401) {
          onAuthFail();
          return;
        }
        setCloses([]);
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

  async function submitClose(e: FormEvent) {
    e.preventDefault();
    if (savingLock.current) return;
    const norm = normalizeDecimal(counted);
    if (!isMoneyValid(norm)) {
      setFormError('المبلغ غير صالح — أدخل مبلغاً موجباً برقمين عشريين على الأكثر');
      return;
    }
    savingLock.current = true;
    setSaving(true);
    setFormError(null);
    setFormSuccess(null);
    try {
      const created = await closeDay(token, { counted_cash: norm });
      setCloses((prev) => (prev ? [created, ...prev] : [created]));
      setFormSuccess('تم تقفيل اليوم');
      setCounted('');
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
      if (err instanceof ApiError) {
        setFormError(moneyErrorMessage(err.status, err.detail));
        return;
      }
      setFormError(mapMoneyError(err));
    } finally {
      savingLock.current = false;
      setSaving(false);
    }
  }

  async function reopen(id: number) {
    if (reopenLock.current) return;
    reopenLock.current = true;
    setReopeningId(id);
    setFormError(null);
    try {
      const updated = await reopenDay(token, id);
      setCloses((prev) => (prev ? prev.map((c) => (closeId(c) === id ? updated : c)) : prev));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onAuthFail();
        return;
      }
      setFormError(
        err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
      );
    } finally {
      reopenLock.current = false;
      setReopeningId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="pt-title text-lg">تقفيل اليوم</h2>

      {error && (
        <p className="pt-caption text-red-600" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <p className="pt-caption" role="status" aria-live="polite">
          جارٍ التحميل…
        </p>
      ) : closes !== null && closes.length === 0 ? (
        <p className="pt-caption">لا يوجد تقفيل لهذا اليوم</p>
      ) : closes ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-start text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="pt-caption px-3 py-2 text-start">التاريخ</th>
                <th className="pt-caption px-3 py-2 text-start">المتوقع</th>
                <th className="pt-caption px-3 py-2 text-start">المعدود</th>
                <th className="pt-caption px-3 py-2 text-start">الفرق</th>
                <th className="pt-caption px-3 py-2 text-start">الحالة</th>
                <th className="pt-caption px-3 py-2 text-start">إجراء</th>
              </tr>
            </thead>
            <tbody>
              {closes.map((c) => (
                <tr key={String(c.id)} className="border-b border-border">
                  <td className="px-3 py-2">{str(c.datee)}</td>
                  <td className="pt-mono px-3 py-2">{str(c.expected_cash)}</td>
                  <td className="pt-mono px-3 py-2">{str(c.counted_cash)}</td>
                  <td className="pt-mono px-3 py-2">{str(c.difference)}</td>
                  <td className="px-3 py-2">{str(c.status)}</td>
                  <td className="px-3 py-2">
                    {str(c.status) === 'closed' && (
                      <button
                        type="button"
                        disabled={reopeningId === closeId(c)}
                        onClick={() => reopen(closeId(c))}
                        className="rounded border border-border px-2 py-1 text-xs disabled:opacity-50"
                      >
                        {reopeningId === closeId(c) ? 'جارٍ الفتح…' : 'إعادة فتح'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {formError && (
        <p className="pt-caption text-red-600" role="alert">
          {formError}
        </p>
      )}
      {formSuccess && <p className="pt-caption text-green-600">{formSuccess}</p>}

      {forbidden ? (
        <p className="pt-caption text-red-600" role="alert">
          ليس لديك صلاحية — تحقق من دورك (day.close)
        </p>
      ) : (
        <form className="pt-card flex flex-col gap-3" onSubmit={submitClose}>
          <p className="pt-title">تقفيل اليوم</p>
          <label className="pt-caption flex flex-col gap-1">
            المبلغ المعدود
            <input
              aria-label="المبلغ المعدود"
              inputMode="decimal"
              className="rounded border border-border px-2 py-1"
              value={counted}
              onChange={(e) => setCounted(e.target.value)}
              required
            />
          </label>
          <button
            type="submit"
            disabled={saving}
            className="w-fit rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
          >
            {saving ? 'جارٍ التقفيل…' : 'تقفيل اليوم'}
          </button>
        </form>
      )}
    </div>
  );
}
