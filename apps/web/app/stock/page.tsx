'use client';

import { StatusChip } from '@pharmatag/ui';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Shell } from '@/components/shell';
import { ApiError, clearToken, loadToken } from '@/lib/api';
import {
  addDecimal,
  compareDecimal,
  errorForStatus,
  normalizeDecimal,
  toFixed4,
} from '@/lib/posMoney';
import {
  type CrossBranchResponse,
  type CurrentStockItem,
  fetchCrossBranch,
  fetchCurrentStock,
} from '@/lib/stock';

type ViewState = 'boot' | 'login' | 'ready' | 'error';
type Tab = 'current' | 'cross';

function toSafeDecimalInput(value: unknown): string {
  if (value == null) return '0';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '0';
    return String(value);
  }
  if (typeof value === 'string') return value;
  return String(value);
}

function safeNormalize(value: unknown): string {
  const raw = toSafeDecimalInput(value);
  try {
    return normalizeDecimal(raw) || '0';
  } catch {
    return '0';
  }
}

function negateDecimal(s: string): string {
  const t = s.trim();
  if (t.startsWith('-')) return t.slice(1);
  if (t.startsWith('+')) return `-${t.slice(1)}`;
  return `-${t}`;
}

function shortageOf(qty: unknown, minimum: unknown): string {
  const q = safeNormalize(qty);
  const m = safeNormalize(minimum);
  // detect non-numeric raw
  const rawQ = String(qty ?? '').trim();
  const rawM = String(minimum ?? '').trim();
  const isInvalid =
    (rawQ !== '' && q === '0' && rawQ !== '0' && !/^-?\d*\.?\d+$/.test(rawQ.replace(/,/g, ''))) ||
    (rawM !== '' && m === '0' && rawM !== '0' && !/^-?\d*\.?\d+$/.test(rawM.replace(/,/g, '')));
  if (isInvalid) return '—';
  try {
    const diff = addDecimal(m, negateDecimal(q));
    if (compareDecimal(diff, '0') <= 0) return '0.0000';
    return toFixed4(diff);
  } catch {
    return '—';
  }
}

function isValidDecimalRaw(raw: string): boolean {
  if (!raw) return true;
  const cleaned = raw
    .replace(/[\u00A0\u202F\u2009\u200A\u2002\u2003\u200C ]/g, '')
    .replace(/[٬,،]/g, '')
    .replace(/٫/g, '.')
    .replace(/[٠-٩]/g, (c) => String(c.charCodeAt(0) - 0x0660))
    .replace(/[۰-۹]/g, (c) => String(c.charCodeAt(0) - 0x06f0));
  return /^-?\d*\.?\d+$/.test(cleaned) && !/[a-zA-Z]/.test(cleaned);
}

function isOverstocked(qty: unknown, minimum: unknown): boolean {
  const rawQ = String(qty ?? '').trim();
  const rawM = String(minimum ?? '').trim();
  if (rawQ !== '' && !isValidDecimalRaw(rawQ)) return false;
  if (rawM !== '' && !isValidDecimalRaw(rawM)) return false;
  const q = safeNormalize(qty);
  const m = safeNormalize(minimum);
  try {
    return compareDecimal(q, m) >= 0;
  } catch {
    return false;
  }
}

function safeBatches(batches: unknown): CurrentStockItem['batches'] {
  if (!Array.isArray(batches)) return [];
  return batches.filter((b) => b && typeof b === 'object') as CurrentStockItem['batches'];
}

function stockErrorForStatus(status: number, detail?: string): string {
  if (status === 404) {
    const d = (detail ?? '').toLowerCase();
    if (d.includes('branch') || d.includes('drug') || d.includes('stock'))
      return 'المخزون غير موجود — تحقّق من الفرع أو الصنف';
    return 'غير موجود — تحقّق من الرابط أو الصنف';
  }
  if (status === 400 || status === 422) {
    const d = (detail ?? '').toLowerCase();
    if (d.includes('branch')) return 'المستخدم بدون فرع — تواصل مع الإدارة';
    if (d.includes('qty') || d.includes('minimum'))
      return 'بيانات غير صالحة — تحقّق من الكميات والحد الأدنى';
    return errorForStatus(status, detail);
  }
  return errorForStatus(status, detail);
}

function safeFormat4(value: unknown, fallback = '—'): string {
  const raw = toSafeDecimalInput(value);
  const norm = safeNormalize(raw);
  // if normalization produced '0' but raw was non-numeric like "N/A", treat as invalid
  const rawTrim = String(value ?? '').trim();
  if (
    rawTrim !== '' &&
    norm === '0' &&
    rawTrim !== '0' &&
    rawTrim !== '0.0000' &&
    !/^-?\d*\.?\d+$/.test(rawTrim.replace(/,/g, ''))
  ) {
    return fallback;
  }
  try {
    return toFixed4(norm);
  } catch {
    return fallback;
  }
}

function mapStockError(err: unknown): string {
  if (err instanceof SyntaxError) return 'خطأ بالخادم — حاول لاحقاً';
  if (err instanceof TypeError || (err as Error)?.message?.includes('fetch'))
    return 'تعذّر الاتصال بالـ API';
  if (err instanceof ApiError) return stockErrorForStatus(err.status, err.detail);
  return 'تعذّر الاتصال بالـ API';
}

export default function StockPage() {
  const [view, setView] = useState<ViewState>('boot');
  const [tab, setTab] = useState<Tab>('current');
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [onlyShortage, setOnlyShortage] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);

  const [currentData, setCurrentData] = useState<CurrentStockItem[] | null>(null);
  const [crossData, setCrossData] = useState<CrossBranchResponse | null>(null);
  const [currentMeta, setCurrentMeta] = useState<{ count: number; truncated: boolean } | null>(
    null,
  );

  const [loadingCurrent, setLoadingCurrent] = useState(false);
  const [loadingCross, setLoadingCross] = useState(false);

  const [errorCurrent, setErrorCurrent] = useState<string | null>(null);
  const [errorCross, setErrorCross] = useState<string | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const [qTooLong, setQTooLong] = useState(false);

  const currentSeq = useRef(0);
  const crossSeq = useRef(0);
  const currentAbortRef = useRef<AbortController | null>(null);
  const crossAbortRef = useRef<AbortController | null>(null);
  const bootAbortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<number | null>(null);
  const bootDoneRef = useRef(false);

  // debounce q 300ms — trimmed length matters; track raw q but debounced is what fetches
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => setDebouncedQ(q), 300);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [q]);

  useEffect(() => {
    setQTooLong(q.trim().length > 100);
  }, [q]);

  // prune expanded ids when data changes
  useEffect(() => {
    if (!currentData) return;
    const ids = new Set(currentData.map((it) => it.drug_id));
    setExpanded((prev) => {
      const next = new Set<number>();
      for (const id of prev) if (ids.has(id)) next.add(id);
      return next;
    });
  }, [currentData]);

  const handleAuthFail = useCallback(() => {
    clearToken();
    currentSeq.current++;
    crossSeq.current++;
    currentAbortRef.current?.abort();
    crossAbortRef.current?.abort();
    bootAbortRef.current?.abort();
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    setLoadingCurrent(false);
    setLoadingCross(false);
    setCurrentData(null);
    setCrossData(null);
    setCurrentMeta(null);
    setErrorCurrent(null);
    setErrorCross(null);
    setGlobalError(null);
    setView('login');
  }, []);

  function handleLogout() {
    clearToken();
    currentSeq.current++;
    crossSeq.current++;
    currentAbortRef.current?.abort();
    crossAbortRef.current?.abort();
    bootAbortRef.current?.abort();
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    setLoadingCurrent(false);
    setLoadingCross(false);
    setCurrentData(null);
    setCrossData(null);
    setCurrentMeta(null);
    setErrorCurrent(null);
    setErrorCross(null);
    setGlobalError(null);
    setView('login');
  }

  // boot: check token and load initial current — unified via currentSeq/abort
  useEffect(() => {
    const controller = new AbortController();
    bootAbortRef.current = controller;
    let cancelled = false;
    const seq = ++currentSeq.current;
    currentAbortRef.current = controller;
    (async () => {
      const token = loadToken();
      if (!token) {
        if (!cancelled) setView('login');
        return;
      }
      setLoadingCurrent(true);
      setGlobalError(null);
      setErrorCurrent(null);
      try {
        const data = await fetchCurrentStock(token, { limit: 200 }, controller.signal);
        if (cancelled || seq !== currentSeq.current) return;
        setCurrentData(Array.isArray(data.items) ? data.items : []);
        setCurrentMeta({
          count: typeof data.count === 'number' ? data.count : (data.items?.length ?? 0),
          truncated: Boolean(data.truncated),
        });
        bootDoneRef.current = true;
        setView('ready');
      } catch (err) {
        if (cancelled || seq !== currentSeq.current) return;
        if ((err as Error)?.name === 'AbortError') return;
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          setView('login');
          return;
        }
        if (err instanceof ApiError && err.status === 403) {
          const msg = stockErrorForStatus(403, (err as ApiError).detail);
          setErrorCurrent(msg);
          setGlobalError(msg);
          setCurrentData([]);
          setCurrentMeta({ count: 0, truncated: false });
          setView('ready');
          return;
        }
        if (err instanceof ApiError && err.status === 429) {
          const msg = stockErrorForStatus(429, (err as ApiError).detail);
          setErrorCurrent(msg);
          setGlobalError(msg);
          setCurrentData([]);
          setCurrentMeta({ count: 0, truncated: false });
          setView('ready');
          return;
        }
        if (err instanceof ApiError && err.status >= 500) {
          const msg = stockErrorForStatus(err.status, (err as ApiError).detail);
          setErrorCurrent(msg);
          setGlobalError(msg);
          setCurrentData([]);
          setCurrentMeta({ count: 0, truncated: false });
          setView('ready');
          return;
        }
        // JSON parse SyntaxError or other
        if (err instanceof SyntaxError) {
          const msg = 'خطأ بالخادم — حاول لاحقاً';
          setErrorCurrent(msg);
          setGlobalError(msg);
          setCurrentData([]);
          setCurrentMeta({ count: 0, truncated: false });
          setView('ready');
          return;
        }
        if (err instanceof TypeError || (err as Error)?.message?.includes('fetch')) {
          const msg = 'تعذّر الاتصال بالـ API';
          setErrorCurrent(msg);
          setGlobalError(msg);
          setCurrentData([]);
          setCurrentMeta({ count: 0, truncated: false });
          setView('ready');
          return;
        }
        if (err instanceof ApiError) {
          const msg = stockErrorForStatus(err.status, (err as ApiError).detail);
          setErrorCurrent(msg);
          setGlobalError(msg);
          setCurrentData([]);
          setCurrentMeta({ count: 0, truncated: false });
          setView('ready');
          return;
        }
        setGlobalError('تعذّر الاتصال بالـ API');
        setView('error');
      } finally {
        if (!cancelled && seq === currentSeq.current) {
          if (currentAbortRef.current === controller) currentAbortRef.current = null;
          if (bootAbortRef.current === controller) bootAbortRef.current = null;
          setLoadingCurrent(false);
        }
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
      if (currentAbortRef.current === controller) currentAbortRef.current = null;
      if (bootAbortRef.current === controller) bootAbortRef.current = null;
    };
  }, []);

  // fetch current on debouncedQ changes (when ready)
  useEffect(() => {
    if (view !== 'ready') return;
    // M2: skip duplicate boot fetch — boot already fetched limit:200 no q/no shortage
    if (bootDoneRef.current) {
      bootDoneRef.current = false;
      const t = debouncedQ.trim();
      if (t === '' && !onlyShortage) return;
    }
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    const trimmed = debouncedQ.trim();
    if (trimmed.length > 100) {
      setQTooLong(true);
      // M5: clear previous errors when showing length guard
      setErrorCurrent(null);
      setErrorCross(null);
      setGlobalError(null);
      currentSeq.current++;
      currentAbortRef.current?.abort();
      currentAbortRef.current = null;
      setLoadingCurrent(false);
      return;
    }
    setQTooLong(false);
    const seq = ++currentSeq.current;
    if (currentAbortRef.current) currentAbortRef.current.abort();
    const ac = new AbortController();
    currentAbortRef.current = ac;
    setLoadingCurrent(true);
    setErrorCurrent(null);
    setGlobalError(null);
    (async () => {
      try {
        const data = await fetchCurrentStock(
          token,
          { q: trimmed || undefined, limit: 200, only_shortage: onlyShortage || undefined },
          ac.signal,
        );
        if (seq !== currentSeq.current) return;
        setCurrentData(Array.isArray(data.items) ? data.items : []);
        setCurrentMeta({
          count: typeof data.count === 'number' ? data.count : (data.items?.length ?? 0),
          truncated: Boolean(data.truncated),
        });
        setGlobalError(null);
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        if (seq !== currentSeq.current) return;
        if (err instanceof ApiError && err.status === 401) {
          handleAuthFail();
          return;
        }
        const msg = mapStockError(err);
        setErrorCurrent(msg);
      } finally {
        if (seq === currentSeq.current) {
          if (currentAbortRef.current === ac) currentAbortRef.current = null;
          setLoadingCurrent(false);
        }
      }
    })();

    return () => {
      ac.abort();
    };
  }, [debouncedQ, view, onlyShortage, handleAuthFail]);

  // fetch cross-branch when tab is cross or filters change
  useEffect(() => {
    if (view !== 'ready') return;
    if (tab !== 'cross') return;
    if (q.trim().length > 100) {
      crossSeq.current++;
      crossAbortRef.current?.abort();
      crossAbortRef.current = null;
      setLoadingCross(false);
      return;
    }
    const trimmedEarly = debouncedQ.trim();
    if (trimmedEarly.length > 100) {
      // consistent with current tab: hide table, show qTooLong banner, abort stale
      crossSeq.current++;
      crossAbortRef.current?.abort();
      crossAbortRef.current = null;
      setLoadingCross(false);
      return;
    }
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    const seq = ++crossSeq.current;
    if (crossAbortRef.current) crossAbortRef.current.abort();
    const ac = new AbortController();
    crossAbortRef.current = ac;
    setLoadingCross(true);
    setErrorCross(null);
    const trimmed = debouncedQ.trim();
    (async () => {
      try {
        const data = await fetchCrossBranch(
          token,
          {
            q: trimmed || undefined,
            only_shortage: onlyShortage || undefined,
            include_inactive: includeInactive || undefined,
          },
          ac.signal,
        );
        if (seq !== crossSeq.current) return;
        setCrossData(data);
        setGlobalError(null);
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        if (seq !== crossSeq.current) return;
        if (err instanceof ApiError && err.status === 401) {
          handleAuthFail();
          return;
        }
        const msg = mapStockError(err);
        setErrorCross(msg);
      } finally {
        if (seq === crossSeq.current) {
          if (crossAbortRef.current === ac) crossAbortRef.current = null;
          setLoadingCross(false);
        }
      }
    })();
    return () => {
      ac.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, debouncedQ, q, onlyShortage, includeInactive, view, handleAuthFail]);

  // handle token changes from other tabs / expiry
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'pharmatag:token' && !e.newValue) {
        handleAuthFail();
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [handleAuthFail]);

  // cleanup on unmount
  useEffect(() => {
    return () => {
      currentAbortRef.current?.abort();
      crossAbortRef.current?.abort();
      bootAbortRef.current?.abort();
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, []);

  function toggleExpand(drugId: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(drugId)) next.delete(drugId);
      else next.add(drugId);
      return next;
    });
  }

  const chip =
    view === 'boot' || view === 'login' ? (
      <StatusChip kind="offline" labelAr="تسجيل الدخول" labelEn="Sign in" />
    ) : view === 'ready' ? (
      <StatusChip kind="online" labelAr="الخادم متصل" labelEn="API online" />
    ) : (
      <StatusChip kind="saved" labelAr="الخادم غير متاح" labelEn="API unavailable" />
    );

  if (view === 'boot') {
    return (
      <Shell>
        <section dir="rtl" className="flex flex-col gap-3">
          <h1 className="pt-title text-2xl">المخزون</h1>
          <p className="pt-caption" role="status" aria-live="polite">
            جارٍ التحميل…
          </p>
        </section>
      </Shell>
    );
  }

  if (view === 'login') {
    return (
      <Shell>
        <section className="flex h-full flex-col items-start gap-3" dir="rtl">
          <h1 className="pt-title text-2xl">المخزون</h1>
          <p className="pt-caption">سجّل الدخول أولاً من شاشة الأدوية لعرض المخزون.</p>
          <a href="/drugs" className="pt-caption text-[var(--accent-color)] underline">
            الذهاب للأدوية
          </a>
        </section>
      </Shell>
    );
  }

  if (view === 'error' && !currentData && !crossData) {
    return (
      <Shell>
        <section className="flex h-full flex-col items-start gap-3" dir="rtl">
          <h1 className="pt-title text-2xl">المخزون</h1>
          {chip}
          <p className="pt-caption text-red-600" role="alert">
            {globalError ?? 'تعذّر الاتصال بالـ API'}
          </p>
          <button
            type="button"
            onClick={() => {
              const t = loadToken();
              if (!t) setView('login');
              else window.location.reload();
            }}
            className="w-fit rounded border border-border px-3 py-1.5 text-sm"
          >
            إعادة المحاولة
          </button>
        </section>
      </Shell>
    );
  }

  // ready
  const CURRENT_LIMIT = 200;
  const currentTruncated =
    currentMeta?.truncated ?? (currentData !== null && currentData.length >= CURRENT_LIMIT);
  const currentCount = currentMeta?.count ?? currentData?.length ?? 0;
  // derive filtered & sorted current items
  const filteredCurrent: CurrentStockItem[] | null = (() => {
    if (currentData === null) return null;
    let list = [...currentData];
    if (onlyShortage) {
      list = list.filter((it) => !isOverstocked(it.qty, it.minimum));
    }
    // sort shortage DESC, then drugname ASC — guard against corrupt decimal
    list.sort((a, b) => {
      let sa = '0.0000';
      let sb = '0.0000';
      try {
        sa = shortageOf(a.qty, a.minimum);
      } catch {}
      try {
        sb = shortageOf(b.qty, b.minimum);
      } catch {}
      let cmp = 0;
      try {
        cmp = compareDecimal(sb, sa);
      } catch {}
      if (cmp !== 0) return cmp;
      return String(a.drugname ?? '').localeCompare(String(b.drugname ?? ''));
    });
    return list;
  })();

  const isLoading = tab === 'current' ? loadingCurrent : loadingCross;
  const errorBanner = tab === 'current' ? errorCurrent : errorCross;

  // determine empty states
  const currentIsEmpty = filteredCurrent !== null && filteredCurrent.length === 0;
  const crossIsEmpty = crossData !== null && crossData.items.length === 0;
  const hasQ = debouncedQ.trim().length > 0;

  return (
    <Shell>
      <section className="flex h-full flex-col gap-4" dir="rtl">
        <div className="flex items-center gap-3">
          <h1 className="pt-title text-2xl">المخزون</h1>
          {chip}
          <button
            type="button"
            className="ms-auto pt-caption cursor-pointer rounded-md border border-border px-3 py-1"
            onClick={handleLogout}
          >
            تسجيل الخروج
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-border pb-2">
          <button
            type="button"
            onClick={() => setTab('current')}
            className={
              'rounded px-3 py-1.5 text-sm ' +
              (tab === 'current' ? 'bg-[var(--accent-color)] text-white' : 'border border-border')
            }
            aria-pressed={tab === 'current'}
          >
            المخزون الحالي
          </button>
          <button
            type="button"
            onClick={() => setTab('cross')}
            className={
              'rounded px-3 py-1.5 text-sm ' +
              (tab === 'cross' ? 'bg-[var(--accent-color)] text-white' : 'border border-border')
            }
            aria-pressed={tab === 'cross'}
          >
            عبر الفروع
          </button>
          <a
            href="/reports"
            className="pt-caption ms-auto self-center text-[var(--accent-color)] underline"
          >
            التقارير
          </a>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-1 gap-2 min-w-[240px]">
            <input
              aria-label="ابحث بالباركود أو اسم الدواء"
              placeholder="ابحث بالباركود أو الاسم (عربي/إنجليزي)"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  const target = e.target as HTMLInputElement;
                  const val = target.value;
                  if (debounceRef.current) window.clearTimeout(debounceRef.current);
                  setQ(val);
                  setDebouncedQ(val);
                }
              }}
              className="flex-1 rounded-md border border-border px-3 py-2 text-sm"
            />
          </div>
          <label className="flex items-center gap-2 pt-caption cursor-pointer select-none">
            <input
              type="checkbox"
              checked={onlyShortage}
              onChange={(e) => setOnlyShortage(e.target.checked)}
              aria-label="النواقص فقط"
            />
            النواقص فقط
          </label>
          {tab === 'cross' && (
            <label className="flex items-center gap-2 pt-caption cursor-pointer select-none">
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(e) => setIncludeInactive(e.target.checked)}
                aria-label="يشمل غير النشط"
              />
              يشمل غير النشط
            </label>
          )}
        </div>

        {qTooLong && (
          <p className="pt-caption text-red-600" role="alert">
            نص البحث طويل جداً — الحد 100 حرف
          </p>
        )}

        {(errorBanner || globalError) && (
          <p className="pt-caption text-red-600" role="alert">
            {errorBanner ?? globalError}
          </p>
        )}

        {qTooLong ? null : isLoading ? (
          <p className="pt-caption" role="status" aria-live="polite">
            جارٍ التحميل…
          </p>
        ) : tab === 'current' ? (
          <>
            {filteredCurrent === null ? (
              <p className="pt-caption" role="status">
                جارٍ التحميل…
              </p>
            ) : currentIsEmpty ? (
              hasQ ? (
                <p className="pt-caption">لا توجد نتائج للبحث عن “{debouncedQ.trim()}”</p>
              ) : onlyShortage ? (
                <p className="pt-caption">لا توجد نواقص — ارجع للعرض الكامل</p>
              ) : (
                <p className="pt-caption">لا يوجد مخزون في هذا الفرع</p>
              )
            ) : (
              <div className="pt-card flex flex-col gap-3">
                {currentTruncated && (
                  <p
                    className="pt-caption rounded bg-amber-100 px-3 py-2 text-amber-800"
                    role="status"
                  >
                    {hasQ
                      ? `تم اقتطاع النتائج — العدد الإجمالي ${currentCount} وتم عرض ${currentData?.length ?? 0} (الحد ${CURRENT_LIMIT})`
                      : onlyShortage
                        ? `تم اقتطاع النتائج — العدد الإجمالي ${currentCount} وتم عرض ${currentData?.length ?? 0} (الحد ${CURRENT_LIMIT}) — قد تكون هناك نواقص إضافية خارج أول ${CURRENT_LIMIT}`
                        : `تم اقتطاع النتائج — تم عرض ${currentData?.length ?? 0} صنف (الحد ${CURRENT_LIMIT}) — استخدم البحث لتحديد صنف`}
                  </p>
                )}
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-start text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="pt-caption px-3 py-2 text-start">الاسم العربي</th>
                        <th className="pt-caption px-3 py-2 text-start">الاسم الإنجليزي</th>
                        <th className="pt-caption px-3 py-2 text-start">الباركود</th>
                        <th className="pt-caption px-3 py-2 text-start">السعر</th>
                        <th className="pt-caption px-3 py-2 text-start">الرصيد</th>
                        <th className="pt-caption px-3 py-2 text-start">الحد الأدنى</th>
                        <th className="pt-caption px-3 py-2 text-start">العجز</th>
                        <th className="pt-caption px-3 py-2 text-start">الدفعات</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCurrent.flatMap((item) => {
                        const shortage = shortageOf(item.qty, item.minimum);
                        const isExpanded = expanded.has(item.drug_id);
                        const batches = safeBatches(item.batches);
                        const rows: React.ReactNode[] = [
                          <tr key={item.drug_id} className="border-b border-border h-8">
                            <td className="px-3 py-2">{String(item.drugnamear ?? '') || '—'}</td>
                            <td className="pt-mono px-3 py-2 text-muted">
                              {String(item.drugname ?? '')}
                            </td>
                            <td className="pt-mono px-3 py-2">
                              {String(item.barcode ?? '') || '—'}
                            </td>
                            <td className="pt-mono px-3 py-2">{safeFormat4(item.price)}</td>
                            <td className="pt-mono px-3 py-2">{safeFormat4(item.qty)}</td>
                            <td className="pt-mono px-3 py-2">{safeFormat4(item.minimum)}</td>
                            <td className="pt-mono px-3 py-2">{shortage}</td>
                            <td className="px-3 py-1">
                              <button
                                type="button"
                                onClick={() => toggleExpand(item.drug_id)}
                                className="rounded border border-border px-2 py-1 text-xs"
                              >
                                {isExpanded ? 'إخفاء الدفعات' : 'عرض الدفعات'}
                              </button>
                            </td>
                          </tr>,
                        ];
                        if (isExpanded) {
                          rows.push(
                            <tr key={`${item.drug_id}-batches`}>
                              <td
                                colSpan={8}
                                className="bg-[var(--background-secondary)] px-3 py-2"
                              >
                                {batches.length === 0 ? (
                                  <p className="pt-caption">لا توجد دفعات</p>
                                ) : (
                                  <table className="w-full border-collapse text-start text-xs">
                                    <thead>
                                      <tr className="border-b border-border">
                                        <th className="pt-caption px-2 py-1 text-start">الكمية</th>
                                        <th className="pt-caption px-2 py-1 text-start">التكلفة</th>
                                        <th className="pt-caption px-2 py-1 text-start">
                                          تاريخ الانتهاء
                                        </th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {batches.map((b) => (
                                        <tr
                                          key={String(b.batch_id)}
                                          className="border-b border-border"
                                        >
                                          <td className="pt-mono px-2 py-1">
                                            {safeFormat4(b.qty)}
                                          </td>
                                          <td className="pt-mono px-2 py-1">
                                            {safeFormat4(b.cost)}
                                          </td>
                                          <td className="px-2 py-1">
                                            {b.expire ? String(b.expire) : '—'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                )}
                              </td>
                            </tr>,
                          );
                        }
                        return rows;
                      })}
                    </tbody>
                  </table>
                </div>
                <p className="pt-caption text-muted">
                  الرصيد والحد الأدنى والعجز بدقة 4 خانات عشرية
                </p>
                <div className="flex flex-wrap gap-2 border-t border-border pt-3">
                  <a href="/reports" className="pt-caption rounded border border-border px-3 py-1">
                    عرض تقرير النواقص
                  </a>
                  <a href="/reports" className="pt-caption rounded border border-border px-3 py-1">
                    عرض تقرير المخزون الحالي
                  </a>
                </div>
              </div>
            )}
          </>
        ) : (
          // cross-branch tab
          <>
            {crossData === null && !errorCross ? (
              <p className="pt-caption" role="status">
                جارٍ التحميل…
              </p>
            ) : crossIsEmpty ? (
              hasQ ? (
                <p className="pt-caption">لا توجد نتائج للبحث عن “{debouncedQ.trim()}”</p>
              ) : onlyShortage ? (
                <p className="pt-caption">لا توجد نواقص</p>
              ) : includeInactive ? (
                <p className="pt-caption">لا توجد نتائج — لا يوجد فرع غير نشط مطابق</p>
              ) : (
                <p className="pt-caption">لا يوجد مخزون في هذا الفرع</p>
              )
            ) : crossData ? (
              <div className="pt-card flex flex-col gap-3">
                {crossData.truncated && (
                  <p
                    className="pt-caption rounded bg-amber-100 px-3 py-2 text-amber-800"
                    role="status"
                  >
                    تم اقتطاع النتائج — العدد الإجمالي {crossData.count} وتم عرض{' '}
                    {crossData.items.length} (الحد 1000)
                  </p>
                )}
                {!crossData.truncated && (
                  <p className="pt-caption text-muted">
                    العدد الإجمالي {crossData.count} — مرتبة حسب العجز تنازلياً
                  </p>
                )}
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-start text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="pt-caption px-3 py-2 text-start">الفرع</th>
                        <th className="pt-caption px-3 py-2 text-start">الاسم العربي</th>
                        <th className="pt-caption px-3 py-2 text-start">الاسم الإنجليزي</th>
                        <th className="pt-caption px-3 py-2 text-start">الباركود</th>
                        <th className="pt-caption px-3 py-2 text-start">الرصيد</th>
                        <th className="pt-caption px-3 py-2 text-start">الحد الأدنى</th>
                        <th className="pt-caption px-3 py-2 text-start">العجز</th>
                      </tr>
                    </thead>
                    <tbody>
                      {crossData.items.map((item) => (
                        <tr
                          key={`${String(item.branch_id)}-${String(item.drug_id)}`}
                          className="border-b border-border h-8"
                        >
                          <td className="px-3 py-2">
                            {String(item.pharname ?? '') || String(item.pharmacyid ?? '')} (
                            {String(item.pharmacyid ?? '')})
                          </td>
                          <td className="px-3 py-2">{String(item.drugnamear ?? '') || '—'}</td>
                          <td className="pt-mono px-3 py-2 text-muted">
                            {String(item.drugname ?? '')}
                          </td>
                          <td className="pt-mono px-3 py-2">{String(item.barcode ?? '') || '—'}</td>
                          <td className="pt-mono px-3 py-2">{safeFormat4(item.qty)}</td>
                          <td className="pt-mono px-3 py-2">{safeFormat4(item.minimum)}</td>
                          <td className="pt-mono px-3 py-2">{safeFormat4(item.shortage)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex flex-wrap gap-2 border-t border-border pt-3">
                  <a href="/reports" className="pt-caption rounded border border-border px-3 py-1">
                    عرض تقرير المخزون عبر الفروع
                  </a>
                </div>
              </div>
            ) : null}
          </>
        )}

        <p className="pt-caption text-xs text-muted">
          القراءة فقط — اعتماد الفروقات عبر طلبات الجرد، غير مدرج في هذه الشريحة.
        </p>
      </section>
    </Shell>
  );
}
