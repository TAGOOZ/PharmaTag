'use client';

import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '@/lib/api';
import { businessToday } from '@/lib/businessDate';
import {
  createManualJournal,
  fetchManualJournal,
  fetchManualJournals,
  type ManualJournalEntry,
  reverseManualJournal,
} from '@/lib/money';
import { isMoneyValid, isPositive, normalizeDecimal } from '@/lib/posMoney';
import { mapMoneyError, moneyErrorMessage } from './moneyErrors';

function str(v: unknown): string {
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  return '—';
}

function entryId(e: ManualJournalEntry): number {
  return typeof e.id === 'number' ? e.id : Number(e.id);
}

/** Content-addressed React keys for journal lines (dupes get a #n suffix). */
function keyedLines(raw: unknown): { key: string; line: Record<string, unknown> }[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Map<string, number>();
  return (raw as Record<string, unknown>[]).map((line) => {
    const base = `${str(line.account_code)}:${str(line.debit)}:${str(line.credit)}:${str(line.note ?? '')}`;
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    return { key: n === 0 ? base : `${base}#${n}`, line };
  });
}

interface FormLine {
  key: string;
  account: string;
  debit: string;
  credit: string;
}

let lineSeq = 0;
function blankLine(): FormLine {
  lineSeq += 1;
  return { key: `line-${lineSeq}`, account: '', debit: '', credit: '' };
}

export default function JournalsTab({
  token,
  onAuthFail,
}: {
  token: string;
  onAuthFail: () => void;
}) {
  const [entries, setEntries] = useState<ManualJournalEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ManualJournalEntry | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [datee, setDatee] = useState('');
  const [description, setDescription] = useState('');
  const [lines, setLines] = useState<FormLine[]>([blankLine(), blankLine()]);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reversing, setReversing] = useState(false);
  const [actionsForbidden, setActionsForbidden] = useState(false);

  const seqRef = useRef(0);
  const detailSeqRef = useRef(0);
  const detailAbortRef = useRef<AbortController | null>(null);
  const savingLock = useRef(false);
  const reverseLock = useRef(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const seq = ++seqRef.current;
      setLoading(true);
      setError(null);
      try {
        const res = await fetchManualJournals(token, {}, signal);
        if (seq !== seqRef.current) return;
        setEntries(res.entries);
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        if (seq !== seqRef.current) return;
        if (err instanceof ApiError && err.status === 401) {
          onAuthFail();
          return;
        }
        setEntries([]);
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

  async function showDetail(id: number) {
    if (expandedId === id) {
      detailSeqRef.current++;
      detailAbortRef.current?.abort();
      detailAbortRef.current = null;
      setExpandedId(null);
      setDetail(null);
      return;
    }
    const seq = ++detailSeqRef.current;
    detailAbortRef.current?.abort();
    const controller = new AbortController();
    detailAbortRef.current = controller;
    setExpandedId(id);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      const res = await fetchManualJournal(token, id, controller.signal);
      if (seq !== detailSeqRef.current) return;
      setDetail(res);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return;
      if (seq !== detailSeqRef.current) return;
      if (err instanceof ApiError && err.status === 401) {
        onAuthFail();
        return;
      }
      setDetailError(
        err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
      );
    } finally {
      if (seq === detailSeqRef.current) {
        if (detailAbortRef.current === controller) detailAbortRef.current = null;
        setDetailLoading(false);
      }
    }
  }

  function setLine(i: number, patch: Partial<FormLine>) {
    setLines((prev) => prev.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  }

  function validate(): string | null {
    if (!description.trim()) return 'البيان مطلوب — أدخل وصفاً للقيد';
    if (lines.length < 2) return 'القيد يحتاج سطرين على الأقل';
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i] as FormLine;
      if (!l.account.trim()) return `سطر ${i + 1}: كود الحساب مطلوب`;
      const d = l.debit.trim() ? normalizeDecimal(l.debit) : '';
      const c = l.credit.trim() ? normalizeDecimal(l.credit) : '';
      if (d && !isMoneyValid(d)) return `سطر ${i + 1}: المدين غير صالح`;
      if (c && !isMoneyValid(c)) return `سطر ${i + 1}: الدائن غير صالح`;
      if (!d && !c) return `سطر ${i + 1}: أدخل مبلغاً مديناً أو دائناً`;
      if (d && c) return `سطر ${i + 1}: السطر مدين أو دائن — وليس الاثنين`;
      if ((d && !isPositive(d)) || (c && !isPositive(c)))
        return `سطر ${i + 1}: المبلغ يجب أن يكون أكبر من الصفر`;
    }
    return null;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (savingLock.current) return;
    const clientError = validate();
    if (clientError) {
      setFormError(clientError);
      return;
    }
    savingLock.current = true;
    setSaving(true);
    setFormError(null);
    setFormSuccess(null);
    try {
      const created = await createManualJournal(token, {
        datee: datee || businessToday(),
        description: description.trim(),
        lines: lines.map((l) => {
          const out: { account_code: string; debit?: string; credit?: string } = {
            account_code: l.account.trim(),
          };
          if (l.debit.trim()) out.debit = normalizeDecimal(l.debit);
          if (l.credit.trim()) out.credit = normalizeDecimal(l.credit);
          return out;
        }),
      });
      setEntries((prev) => (prev ? [created, ...prev] : [created]));
      setFormSuccess('تم إنشاء القيد');
      setDescription('');
      setLines([blankLine(), blankLine()]);
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
    setReversing(true);
    setFormError(null);
    setFormSuccess(null);
    try {
      const created = await reverseManualJournal(token, id);
      setEntries((prev) => (prev ? [created, ...prev] : [created]));
      setFormSuccess('تم عكس القيد');
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
      reverseLock.current = false;
      setReversing(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="pt-title text-lg">القيود اليومية</h2>

      {error && (
        <p className="pt-caption text-red-600" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <p className="pt-caption" role="status" aria-live="polite">
          جارٍ التحميل…
        </p>
      ) : entries !== null && entries.length === 0 ? (
        <p className="pt-caption">لا توجد قيود يدوية</p>
      ) : entries ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-start text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="pt-caption px-3 py-2 text-start">رقم القيد</th>
                <th className="pt-caption px-3 py-2 text-start">التاريخ</th>
                <th className="pt-caption px-3 py-2 text-start">البيان</th>
                <th className="pt-caption px-3 py-2 text-start">الإجمالي</th>
                <th className="pt-caption px-3 py-2 text-start">إجراء</th>
              </tr>
            </thead>
            <tbody>
              {entries.flatMap((en) => {
                const id = entryId(en);
                const rows: React.ReactNode[] = [
                  <tr key={id} className="border-b border-border">
                    <td className="pt-mono break-all px-3 py-2">{str(en.entry_no)}</td>
                    <td className="px-3 py-2">{str(en.datee)}</td>
                    <td className="px-3 py-2">{str(en.description)}</td>
                    <td className="pt-mono break-all px-3 py-2">{str(en.total)}</td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        onClick={() => showDetail(id)}
                        className="rounded border border-border px-2 py-1 text-xs"
                      >
                        {expandedId === id ? 'إخفاء' : 'عرض'}
                      </button>
                    </td>
                  </tr>,
                ];
                if (expandedId === id) {
                  rows.push(
                    <tr key={`${id}-detail`}>
                      <td colSpan={5} className="bg-[var(--background-secondary)] px-3 py-2">
                        {detailLoading ? (
                          <p className="pt-caption" role="status">
                            جارٍ التحميل…
                          </p>
                        ) : detailError ? (
                          <p className="pt-caption text-red-600" role="alert">
                            {detailError}
                          </p>
                        ) : detail ? (
                          <div className="flex flex-col gap-2">
                            <table className="w-full border-collapse text-start text-xs">
                              <thead>
                                <tr className="border-b border-border">
                                  <th className="pt-caption px-2 py-1 text-start">الحساب</th>
                                  <th className="pt-caption px-2 py-1 text-start">الاسم</th>
                                  <th className="pt-caption px-2 py-1 text-start">مدين</th>
                                  <th className="pt-caption px-2 py-1 text-start">دائن</th>
                                </tr>
                              </thead>
                              <tbody>
                                {keyedLines(detail.lines).map(({ key, line }) => (
                                  <tr key={key} className="border-b border-border">
                                    <td className="pt-mono break-all px-2 py-1">
                                      {str(line.account_code)}
                                    </td>
                                    <td className="px-2 py-1">{str(line.account_name)}</td>
                                    <td className="pt-mono break-all px-2 py-1">
                                      {str(line.debit)}
                                    </td>
                                    <td className="pt-mono break-all px-2 py-1">
                                      {str(line.credit)}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            <button
                              type="button"
                              disabled={actionsForbidden || reversing}
                              onClick={() => reverse(id)}
                              className="w-fit rounded border border-border px-3 py-1 text-xs disabled:opacity-50"
                            >
                              {reversing ? 'جارٍ العكس…' : 'عكس القيد'}
                            </button>
                          </div>
                        ) : null}
                      </td>
                    </tr>,
                  );
                }
                return rows;
              })}
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
          ليس لديك صلاحية — تحقق من دورك (journals.manage)
        </p>
      ) : (
        <form className="pt-card flex flex-col gap-3" onSubmit={submit}>
          <p className="pt-title">قيد يدوي جديد</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="pt-caption flex flex-col gap-1">
              التاريخ
              <input
                aria-label="التاريخ"
                type="date"
                className="rounded border border-border px-2 py-1"
                value={datee}
                onChange={(e) => setDatee(e.target.value)}
              />
            </label>
            <label className="pt-caption flex flex-col gap-1">
              البيان
              <input
                aria-label="البيان"
                className="rounded border border-border px-2 py-1"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
              />
            </label>
          </div>
          {lines.map((l, i) => (
            <div key={l.key} className="grid gap-2 sm:grid-cols-3">
              <label className="pt-caption flex flex-col gap-1">
                الحساب
                <input
                  aria-label={`الحساب ${i + 1}`}
                  className="rounded border border-border px-2 py-1"
                  value={l.account}
                  onChange={(e) => setLine(i, { account: e.target.value })}
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                مدين
                <input
                  aria-label={`مدين ${i + 1}`}
                  inputMode="decimal"
                  className="rounded border border-border px-2 py-1"
                  value={l.debit}
                  onChange={(e) => setLine(i, { debit: e.target.value })}
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                دائن
                <input
                  aria-label={`دائن ${i + 1}`}
                  inputMode="decimal"
                  className="rounded border border-border px-2 py-1"
                  value={l.credit}
                  onChange={(e) => setLine(i, { credit: e.target.value })}
                />
              </label>
            </div>
          ))}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setLines((prev) => [...prev, blankLine()])}
              className="w-fit rounded border border-border px-3 py-1 text-sm"
            >
              + سطر
            </button>
            <button
              type="submit"
              disabled={saving}
              className="w-fit rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
            >
              {saving ? 'جارٍ الحفظ…' : 'إنشاء القيد'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
