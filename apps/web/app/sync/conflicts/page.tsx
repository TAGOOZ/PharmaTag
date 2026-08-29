'use client';

import { useEffect, useState } from 'react';
import { Shell } from '@/components/shell';
import { API_URL, ApiError, clearToken, loadToken } from '@/lib/api';

type Conflict = {
  id: number;
  branch_id: number;
  entity: string;
  entity_id: number | null;
  created_at: string | null;
  synced_at: string | null;
  updated_at: string | null;
  skipped_reason: string;
  loser: Record<string, unknown>;
  winner: Record<string, unknown> | null;
  payload: Record<string, unknown>;
  resolved: boolean;
};

type ViewState = 'boot' | 'login-required' | 'ready' | 'error';

const ENTITY_LABELS: Record<string, string> = {
  branch_stock: 'رصيد الفرع',
  transfer: 'تحويل',
  branch: 'فرع',
  branch_identity: 'هوية فرع',
  need: 'حاجة',
  purchase_order: 'طلب شراء',
  chain_buy_order: 'طلب شراء جماعي',
  invoice: 'فاتورة',
};

function entityLabel(e: string): string {
  return ENTITY_LABELS[e] ?? e;
}

function formatJson(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

export default function SyncConflictsPage() {
  const [view, setView] = useState<ViewState>('boot');
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [entityFilter, setEntityFilter] = useState<string>('');
  const [busyId, setBusyId] = useState<number | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [successText, setSuccessText] = useState<string | null>(null);

  async function fetchConflicts(token: string, entity?: string, signal?: AbortSignal) {
    const params = new URLSearchParams();
    if (entity) params.set('entity', entity);
    // branch_id omitted → server defaults to caller's branch
    const qs = params.toString();
    const url = `${API_URL}/api/v1/sync/conflicts${qs ? `?${qs}` : ''}`;
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      signal,
    });
    if (!res.ok) throw new ApiError(res.status);
    const data = await res.json();
    // server returns {conflicts, items, count} or array
    if (Array.isArray(data)) return data as Conflict[];
    if (Array.isArray(data.conflicts)) return data.conflicts as Conflict[];
    if (Array.isArray(data.items)) return data.items as Conflict[];
    return [];
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchConflicts is stable for this effect
  // biome-ignore lint/correctness/useExhaustiveDependencies: fetchConflicts recreated each render, effect only depends on entityFilter
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
        const list = await fetchConflicts(token, entityFilter || undefined, controller.signal);
        if (cancelled) return;
        setConflicts(list);
        setView('ready');
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
  }, [entityFilter]);

  async function reload() {
    const token = loadToken();
    if (!token) {
      setView('login-required');
      return;
    }
    try {
      setErrorText(null);
      setSuccessText(null);
      const list = await fetchConflicts(token, entityFilter || undefined);
      setConflicts(list);
      setView('ready');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        setView('login-required');
        return;
      }
      setErrorText('تعذّر تحديث قائمة التعارضات');
    }
  }

  async function restore(id: number) {
    const token = loadToken();
    if (!token) {
      setView('login-required');
      return;
    }
    setBusyId(id);
    setErrorText(null);
    setSuccessText(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/sync/conflicts/${id}/restore`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new ApiError(res.status);
      await reload();
      setSuccessText('تمت استعادة التعارض بنجاح — تم إنشاء مراجعة جديدة');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          clearToken();
          setView('login-required');
          return;
        }
        if (err.status === 403) {
          setErrorText('ليس لديك صلاحية الاستعادة — يتطلب مدير (مستوى 7)');
          return;
        }
        if (err.status === 404) {
          setErrorText('التعارض غير موجود');
          return;
        }
        if (err.status === 409) {
          setErrorText('التعارض تمت استعادته سابقاً');
          return;
        }
        if (err.status === 400) {
          setErrorText('التعارض غير صالح للاستعادة');
          return;
        }
      }
      setErrorText('تعذّر استعادة التعارض — حاول مرة أخرى');
    } finally {
      setBusyId(null);
    }
  }

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
          <h1 className="pt-title text-2xl">تعارضات المزامنة</h1>
          <p className="pt-caption">سجّل الدخول أولاً من شاشة الأدوية لعرض التعارضات.</p>
        </section>
      </Shell>
    );
  }

  if (view === 'error') {
    return (
      <Shell>
        <section className="flex h-full flex-col items-start gap-3">
          <h1 className="pt-title text-2xl">تعارضات المزامنة</h1>
          <p className="pt-caption text-red-600">{errorText}</p>
        </section>
      </Shell>
    );
  }

  return (
    <Shell>
      <section className="flex h-full flex-col gap-4" dir="rtl">
        <div className="flex items-center gap-3">
          <h1 className="pt-title text-2xl">تعارضات المزامنة</h1>
          <span className="pt-caption rounded-full bg-[var(--background-secondary)] px-3 py-1 text-sm">
            LWW — المراجعة غير المدمرة
          </span>
          <button
            type="button"
            onClick={reload}
            className="ms-auto pt-caption cursor-pointer rounded-md border border-[var(--border-primary)] px-3 py-1"
          >
            تحديث
          </button>
        </div>

        <p className="pt-caption text-sm text-[var(--text-muted)]">
          يعرض هذا الجدول الخسائر التي تم حلها تلقائياً بـ Last-Write-Wins. الرابح هو الحالة الحالية
          في قاعدة البيانات، والخاسر هو الحمولة التي تم تخطيها. يمكن للمدير استعادة الخاسر كمراجعة
          جديدة — لا يتم تعديل السجل التاريخي في مكانه.
        </p>

        <div className="flex flex-wrap items-end gap-3 border-b border-[var(--border-primary)] pb-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="pt-caption">تصفية حسب الكيان</span>
            <select
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value)}
              className="rounded border border-[var(--border-primary)] bg-transparent px-2 py-1"
            >
              <option value="">الكل</option>
              <option value="branch_stock">رصيد الفرع</option>
              <option value="transfer">تحويل</option>
              <option value="branch">فرع</option>
              <option value="branch_identity">هوية فرع</option>
              <option value="need">حاجة</option>
              <option value="purchase_order">طلب شراء</option>
              <option value="chain_buy_order">طلب شراء جماعي</option>
              <option value="invoice">فاتورة</option>
            </select>
          </label>
          <span className="pt-caption text-sm">العدد: {conflicts.length}</span>
        </div>

        {errorText && <p className="text-sm text-red-600">{errorText}</p>}
        {successText && <p className="text-sm text-green-700">{successText}</p>}

        {conflicts.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border-primary)] bg-[var(--background-secondary)] p-8 text-center">
            <p className="pt-title text-lg">لا توجد تعارضات للمراجعة</p>
            <p className="pt-caption text-sm">
              عندما يقوم فرعان بتعديل نفس السجل أثناء عدم الاتصال، سيظهر الخاسر هنا للمراجعة.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-[var(--border-primary)] bg-[var(--background-secondary)]">
                  <th className="px-3 py-2 text-start font-bold">المعرف</th>
                  <th className="px-3 py-2 text-start font-bold">الكيان</th>
                  <th className="px-3 py-2 text-start font-bold">الخاسر (payload)</th>
                  <th className="px-3 py-2 text-start font-bold">الرابح (الحالة الحالية)</th>
                  <th className="px-3 py-2 text-start font-bold">تاريخ التحديث</th>
                  <th className="px-3 py-2 text-start font-bold">السبب</th>
                  <th className="px-3 py-2 text-start font-bold">إجراء</th>
                </tr>
              </thead>
              <tbody>
                {conflicts.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-[var(--border-primary)] hover:bg-[var(--background-secondary)]"
                  >
                    <td className="px-3 py-2 font-mono text-xs">{c.id}</td>
                    <td className="px-3 py-2">{entityLabel(c.entity)}</td>
                    <td className="px-3 py-2">
                      <pre className="max-h-32 max-w-[280px] overflow-auto whitespace-pre-wrap break-words rounded bg-[var(--background-primary)] p-2 text-xs">
                        {formatJson(c.loser)}
                      </pre>
                    </td>
                    <td className="px-3 py-2">
                      <pre className="max-h-32 max-w-[280px] overflow-auto whitespace-pre-wrap break-words rounded bg-[var(--background-primary)] p-2 text-xs">
                        {c.winner ? formatJson(c.winner) : '—'}
                      </pre>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{c.updated_at ?? '—'}</td>
                    <td className="px-3 py-2 text-xs">{c.skipped_reason}</td>
                    <td className="px-3 py-2">
                      {c.resolved ? (
                        <span className="pt-caption text-xs text-[var(--text-muted)]">
                          تمت الاستعادة
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => restore(c.id)}
                          disabled={busyId === c.id}
                          className="rounded bg-[var(--accent-color)] px-3 py-1 text-xs text-white disabled:opacity-50"
                        >
                          {busyId === c.id ? 'جارٍ…' : 'استعادة'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </Shell>
  );
}
