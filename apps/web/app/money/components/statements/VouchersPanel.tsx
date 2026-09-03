'use client';

import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, type Party } from '@/lib/api';
import { businessToday } from '@/lib/businessDate';
import {
  createVoucher,
  fetchVouchers,
  reverseVoucher,
  type SettlementVoucher,
  type VoucherCreateBody,
} from '@/lib/money';
import { isMoneyValid, isPositive, normalizeDecimal } from '@/lib/posMoney';
import { mapMoneyError, moneyErrorMessage } from '../moneyErrors';

function str(v: unknown): string {
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  return '—';
}

function voucherId(v: SettlementVoucher): number {
  return typeof v.id === 'number' ? v.id : Number(v.id);
}

function partyName(v: SettlementVoucher): string {
  const p = v.party;
  if (p && typeof p === 'object') {
    const party = p as Record<string, unknown>;
    const ar = str(party.name_ar);
    if (ar && ar !== '—') return ar;
    const en = str(party.namee);
    return en && en !== '—' ? en : '—';
  }
  return '—';
}

function typeLabel(t: unknown): string {
  return t === 'payment' ? 'سند صرف' : 'سند قبض';
}

function methodLabel(m: unknown): string {
  if (m === 'cash') return 'نقدي';
  if (m === 'card') return 'بطاقة';
  if (m === 'network') return 'شبكة';
  return '—';
}

export default function VouchersPanel({
  token,
  onAuthFail,
  parties,
}: {
  token: string;
  onAuthFail: () => void;
  parties: Party[];
}) {
  const [vouchers, setVouchers] = useState<SettlementVoucher[] | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const [vtype, setVtype] = useState<VoucherCreateBody['voucher_type']>('receipt');
  const [partyId, setPartyId] = useState('');
  const [datee, setDatee] = useState('');
  const [method, setMethod] = useState<VoucherCreateBody['method']>('cash');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reversingId, setReversingId] = useState<number | null>(null);
  const [actionsForbidden, setActionsForbidden] = useState(false);

  const seqRef = useRef(0);
  const savingLock = useRef(false);
  const reverseLock = useRef(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const seq = ++seqRef.current;
      setLoading(true);
      setError(null);
      try {
        const vres = await fetchVouchers(token, {}, signal);
        if (seq !== seqRef.current) return;
        setVouchers(vres.vouchers);
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        if (seq !== seqRef.current) return;
        if (err instanceof ApiError && err.status === 401) {
          onAuthFail();
          return;
        }
        setVouchers([]);
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

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (savingLock.current) return;
    const pid = Number.parseInt(partyId, 10);
    if (!partyId || Number.isNaN(pid)) {
      setFormError('اختر الطرف أولاً');
      return;
    }
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
      const created = await createVoucher(token, {
        voucher_type: vtype,
        party_id: pid,
        datee: datee || businessToday(),
        method,
        amount: norm,
        description: description.trim() || undefined,
      });
      setVouchers((prev) => (prev ? [created, ...prev] : [created]));
      setActionsForbidden(false);
      setFormSuccess('تم إنشاء السند');
      setAmount('');
      setDescription('');
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

  async function reverse(id: number) {
    if (reverseLock.current) return;
    reverseLock.current = true;
    setReversingId(id);
    setFormError(null);
    setFormSuccess(null);
    try {
      const created = await reverseVoucher(token, id);
      setVouchers((prev) => (prev ? [created, ...prev] : [created]));
      setActionsForbidden(false);
      setFormSuccess('تم عكس السند');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onAuthFail();
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setActionsForbidden(true);
        // Same permission gates creation — hide the form too.
        setForbidden(true);
      }
      setFormError(
        err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
      );
    } finally {
      reverseLock.current = false;
      setReversingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <h3 className="pt-title">سندات القبض والصرف</h3>

      {error && (
        <p className="pt-caption text-red-600" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <p className="pt-caption" role="status">
          جارٍ التحميل…
        </p>
      ) : vouchers !== null && vouchers.length === 0 ? (
        <p className="pt-caption">لا توجد سندات</p>
      ) : vouchers ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-start text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="pt-caption px-3 py-2 text-start">الرقم</th>
                <th className="pt-caption px-3 py-2 text-start">النوع</th>
                <th className="pt-caption px-3 py-2 text-start">الطرف</th>
                <th className="pt-caption px-3 py-2 text-start">التاريخ</th>
                <th className="pt-caption px-3 py-2 text-start">الطريقة</th>
                <th className="pt-caption px-3 py-2 text-start">المبلغ</th>
                <th className="pt-caption px-3 py-2 text-start">إجراء</th>
              </tr>
            </thead>
            <tbody>
              {vouchers.map((v) => (
                <tr key={voucherId(v)} className="border-b border-border">
                  <td className="pt-mono break-all px-3 py-2">{str(v.voucher_no)}</td>
                  <td className="px-3 py-2">{typeLabel(v.voucher_type)}</td>
                  <td className="px-3 py-2">{partyName(v)}</td>
                  <td className="px-3 py-2">{str(v.datee)}</td>
                  <td className="px-3 py-2">{methodLabel(v.method)}</td>
                  <td className="pt-mono break-all px-3 py-2">{str(v.amount)}</td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      disabled={actionsForbidden || reversingId === voucherId(v)}
                      onClick={() => reverse(voucherId(v))}
                      className="rounded border border-border px-2 py-1 text-xs disabled:opacity-50"
                    >
                      {reversingId === voucherId(v) ? 'جارٍ العكس…' : 'عكس السند'}
                    </button>
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
      {formSuccess && (
        <p className="pt-caption text-green-600" role="status">
          {formSuccess}
        </p>
      )}

      {forbidden ? (
        <p className="pt-caption text-red-600" role="alert">
          ليس لديك صلاحية — تحقق من دورك (receivables.manage)
        </p>
      ) : (
        <form className="pt-card flex flex-col gap-3" onSubmit={submit}>
          <p className="pt-title">سند جديد</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="pt-caption flex flex-col gap-1">
              نوع السند
              <select
                aria-label="نوع السند"
                className="rounded border border-border px-2 py-1"
                value={vtype}
                onChange={(e) => setVtype(e.target.value === 'payment' ? 'payment' : 'receipt')}
              >
                <option value="receipt">سند قبض</option>
                <option value="payment">سند صرف</option>
              </select>
            </label>
            <label className="pt-caption flex flex-col gap-1">
              طرف السند
              <select
                aria-label="طرف السند"
                className="rounded border border-border px-2 py-1"
                value={partyId}
                onChange={(e) => setPartyId(e.target.value)}
              >
                <option value="">— اختر —</option>
                {parties.map((p) => (
                  <option key={p.id} value={String(p.id)}>
                    {p.name_ar || p.namee} ({p.kind})
                  </option>
                ))}
              </select>
            </label>
            <label className="pt-caption flex flex-col gap-1">
              تاريخ السند
              <input
                aria-label="تاريخ السند"
                type="date"
                className="rounded border border-border px-2 py-1"
                value={datee}
                onChange={(e) => setDatee(e.target.value)}
              />
            </label>
            <label className="pt-caption flex flex-col gap-1">
              طريقة الدفع
              <select
                aria-label="طريقة الدفع"
                className="rounded border border-border px-2 py-1"
                value={method}
                onChange={(e) => setMethod(e.target.value as VoucherCreateBody['method'])}
              >
                <option value="cash">نقدي</option>
                <option value="network">شبكة</option>
                <option value="card">بطاقة</option>
              </select>
            </label>
            <label className="pt-caption flex flex-col gap-1">
              مبلغ السند
              <input
                aria-label="مبلغ السند"
                inputMode="decimal"
                className="rounded border border-border px-2 py-1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
              />
            </label>
            <label className="pt-caption flex flex-col gap-1">
              بيان السند
              <input
                aria-label="بيان السند"
                className="rounded border border-border px-2 py-1"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
          </div>
          <button
            type="submit"
            disabled={saving}
            className="w-fit rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
          >
            {saving ? 'جارٍ الحفظ…' : 'إنشاء السند'}
          </button>
        </form>
      )}
    </div>
  );
}
