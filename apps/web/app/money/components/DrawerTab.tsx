'use client';

import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '@/lib/api';
import {
  createMovement,
  type DrawerMovement,
  fetchDrawerMovements,
  type MovementCreateBody,
} from '@/lib/money';
import { isMoneyValid, isPositive, normalizeDecimal } from '@/lib/posMoney';
import { mapMoneyError, moneyErrorMessage } from './moneyErrors';

const REASON_LABELS: Record<MovementCreateBody['reason'], string> = {
  cash_sale: 'بيع نقدي',
  cash_return: 'مرتجع نقدي',
  supplier_pay: 'سداد مورد',
  customer_settlement: 'تسوية عميل',
  expense: 'مصروف',
  transfer: 'تحويل',
  opening: 'افتتاحي',
  correction: 'تصحيح',
};

function methodLabel(method: string): string {
  return method === 'network' ? 'شبكة' : 'نقدي';
}

function directionLabel(direction: string): string {
  return direction === 'out' ? 'منصرف' : 'وارد';
}

export default function DrawerTab({
  token,
  onAuthFail,
}: {
  token: string;
  onAuthFail: () => void;
}) {
  const [movements, setMovements] = useState<DrawerMovement[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const [amount, setAmount] = useState('');
  const [direction, setDirection] = useState<'in' | 'out'>('in');
  const [reason, setReason] = useState<MovementCreateBody['reason']>('opening');
  const [method, setMethod] = useState<'cash' | 'network'>('cash');
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const seqRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const savingLock = useRef(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const seq = ++seqRef.current;
      setLoading(true);
      setError(null);
      try {
        const res = await fetchDrawerMovements(token, {}, signal);
        if (seq !== seqRef.current) return;
        setMovements(res.movements);
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        if (seq !== seqRef.current) return;
        if (err instanceof ApiError && err.status === 401) {
          onAuthFail();
          return;
        }
        if (err instanceof ApiError && err.status === 403) {
          setForbidden(true);
          setMovements([]);
          setError(moneyErrorMessage(err.status, err.detail));
          return;
        }
        setMovements([]);
        setError(mapMoneyError(err));
      } finally {
        if (seq === seqRef.current) setLoading(false);
      }
    },
    [token, onAuthFail],
  );

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    void load(controller.signal);
    return () => {
      controller.abort();
      if (abortRef.current === controller) abortRef.current = null;
    };
  }, [load]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (savingLock.current) return;
    const norm = normalizeDecimal(amount);
    if (!isMoneyValid(norm)) {
      setFormError('المبلغ غير صالح — أدخل مبلغاً موجباً برقمين عشريين على الأكثر');
      return;
    }
    if (!isPositive(norm)) {
      setFormError('المبلغ يجب أن يكون أكبر من الصفر');
      return;
    }
    savingLock.current = true;
    setSaving(true);
    setFormError(null);
    setFormSuccess(null);
    try {
      const created = await createMovement(token, {
        direction,
        reason,
        method,
        amount: norm,
      });
      setMovements((prev) => (prev ? [created, ...prev] : [created]));
      setFormSuccess('تم تسجيل الحركة');
      setAmount('');
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

  return (
    <div className="flex flex-col gap-4">
      <h2 className="pt-title text-lg">حركة الدرج</h2>

      {error && (
        <p className="pt-caption text-red-600" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <p className="pt-caption" role="status" aria-live="polite">
          جارٍ التحميل…
        </p>
      ) : movements !== null && movements.length === 0 ? (
        <p className="pt-caption">لا توجد حركات لهذا اليوم</p>
      ) : movements ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-start text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="pt-caption px-3 py-2 text-start">التاريخ</th>
                <th className="pt-caption px-3 py-2 text-start">الاتجاه</th>
                <th className="pt-caption px-3 py-2 text-start">السبب</th>
                <th className="pt-caption px-3 py-2 text-start">الطريقة</th>
                <th className="pt-caption px-3 py-2 text-start">المبلغ</th>
              </tr>
            </thead>
            <tbody>
              {movements.map((m) => (
                <tr key={m.id} className="border-b border-border">
                  <td className="px-3 py-2">{m.datee}</td>
                  <td className="px-3 py-2">{directionLabel(m.direction)}</td>
                  <td className="px-3 py-2">
                    {(REASON_LABELS as Record<string, string>)[m.reason] ?? m.reason}
                  </td>
                  <td className="px-3 py-2">{methodLabel(m.method)}</td>
                  <td className="pt-mono break-all px-3 py-2">{m.amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {forbidden ? (
        <p className="pt-caption text-red-600" role="alert">
          ليس لديك صلاحية — تحقق من دورك (drawer.manage)
        </p>
      ) : (
        <form className="pt-card flex flex-col gap-3" onSubmit={submit}>
          <p className="pt-title">حركة يدوية</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="pt-caption flex flex-col gap-1">
              المبلغ
              <input
                aria-label="المبلغ"
                inputMode="decimal"
                className="rounded border border-border px-2 py-1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
              />
            </label>
            <label className="pt-caption flex flex-col gap-1">
              الاتجاه
              <select
                aria-label="الاتجاه"
                className="rounded border border-border px-2 py-1"
                value={direction}
                onChange={(e) => setDirection(e.target.value === 'out' ? 'out' : 'in')}
              >
                <option value="in">وارد</option>
                <option value="out">منصرف</option>
              </select>
            </label>
            <label className="pt-caption flex flex-col gap-1">
              السبب
              <select
                aria-label="السبب"
                className="rounded border border-border px-2 py-1"
                value={reason}
                onChange={(e) => setReason(e.target.value as MovementCreateBody['reason'])}
              >
                {Object.entries(REASON_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="pt-caption flex flex-col gap-1">
              الطريقة
              <select
                aria-label="الطريقة"
                className="rounded border border-border px-2 py-1"
                value={method}
                onChange={(e) => setMethod(e.target.value === 'network' ? 'network' : 'cash')}
              >
                <option value="cash">نقدي</option>
                <option value="network">شبكة</option>
              </select>
            </label>
          </div>
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
          <button
            type="submit"
            disabled={saving}
            className="w-fit rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
          >
            {saving ? 'جارٍ الحفظ…' : 'تسجيل الحركة'}
          </button>
        </form>
      )}
    </div>
  );
}
