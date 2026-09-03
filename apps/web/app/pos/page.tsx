'use client';

import { StatusChip } from '@pharmatag/ui';
import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { Shell } from '@/components/shell';
import {
  ApiError,
  clearToken,
  createSale,
  createSaleReturn,
  type Drug,
  fetchSale,
  fetchSales,
  type LoginResponse,
  loadToken,
  login,
  openSalePrint,
  type PriceLevel,
  resetPassword,
  type SaleOut,
  type SaleSummary,
  saveToken,
  searchDrugs,
} from '@/lib/api';
import { RESET_ERROR_TEXT, type ResetError, validateNewPassword } from '@/lib/change-password';
import {
  compareDecimal,
  errorForStatus,
  isInRange,
  isMoneyValid,
  isPositive,
  isQtyValid,
  isZero,
  normalizeDecimal,
  toFixed2,
  toFixed4,
} from '@/lib/posMoney';
import { CartTable } from './components/CartTable';
import { PaymentForm } from './components/PaymentForm';
import { SaleDetail } from './components/SaleDetail';
import { SalesList } from './components/SalesList';
import { SearchPanel } from './components/SearchPanel';
import { CART_KEY, usePosCart } from './hooks/usePosCart';

type ViewState = 'boot' | 'login' | 'ready' | 'error';
type LoginError = 'invalid' | 'network' | null;

export default function PosPage() {
  const [view, setView] = useState<ViewState>('boot');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState<LoginError>(null);
  const [pendingAuth, setPendingAuth] = useState<LoginResponse | null>(null);
  const [resetForm, setResetForm] = useState({ oldPassword: '', newPassword: '', confirm: '' });
  const [resetError, setResetError] = useState<ResetError>(null);
  const [submitting, setSubmitting] = useState(false);

  // POS state
  const [sales, setSales] = useState<SaleSummary[] | null>(null);
  const [salesError, setSalesError] = useState<string | null>(null);
  const [salesSearch, setSalesSearch] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedSale, setSelectedSale] = useState<SaleOut | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Drug[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const { cart, addToCart: hookAddToCart, updateCart, removeFromCart, clearCart } = usePosCart();
  const [invoiceDisc, setInvoiceDisc] = useState('');
  const [payCash, setPayCash] = useState('');
  const [payCard, setPayCard] = useState('');
  const [payCredit, setPayCredit] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveResult, setSaveResult] = useState<SaleOut | null>(null);
  const [printError, setPrintError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      searchAbortRef.current?.abort();
      detailAbortRef.current?.abort();
    };
  }, []);

  // return
  const [returnQty, setReturnQty] = useState<Record<number, string>>({});
  const [returning, setReturning] = useState(false);
  const [returnError, setReturnError] = useState<string | null>(null);
  const [returnResult, setReturnResult] = useState<SaleOut | null>(null);

  const savingLock = useRef(false);
  const returningLock = useRef(false);
  const detailSeq = useRef(0);
  const searchSeq = useRef(0);
  const searchAbortRef = useRef<AbortController | null>(null);
  const detailAbortRef = useRef<AbortController | null>(null);

  function handleAuthFail() {
    clearToken();
    detailSeq.current++;
    searchSeq.current++;
    searchAbortRef.current?.abort();
    detailAbortRef.current?.abort();
    try {
      window.localStorage.removeItem(CART_KEY);
    } catch {}
    clearCart();
    setInvoiceDisc('');
    setPayCash('');
    setPayCard('');
    setPayCredit('');
    setSearchResults(null);
    setSearchError(null);
    setSaveError(null);
    setSalesError(null);
    setPrintError(null);
    setReturnQty({});
    setReturnError(null);
    setReturnResult(null);
    setDetailError(null);
    setSelectedSale(null);
    setSelectedId(null);
    setSales(null);
    setPendingAuth(null);
    setResetError(null);
    setView('login');
  }

  function logout() {
    clearToken();
    detailSeq.current++;
    searchSeq.current++;
    searchAbortRef.current?.abort();
    detailAbortRef.current?.abort();
    try {
      window.localStorage.removeItem(CART_KEY);
    } catch {}
    clearCart();
    setSales(null);
    setSelectedSale(null);
    setSelectedId(null);
    setSaveResult(null);
    setSearchResults(null);
    setSearchError(null);
    setSaveError(null);
    setSalesError(null);
    setPrintError(null);
    setReturnQty({});
    setReturnError(null);
    setReturnResult(null);
    setDetailError(null);
    setInvoiceDisc('');
    setPayCash('');
    setPayCard('');
    setPayCredit('');
    setPendingAuth(null);
    setResetError(null);
    setView('login');
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: handleAuthFail stable for POS
  const loadSales = useCallback(async (token: string, signal?: AbortSignal) => {
    setSalesError(null);
    try {
      const res = await fetchSales(token, signal);
      setSales(res.sales.slice(0, 100));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      }
      if (err instanceof TypeError || (err as Error)?.message?.includes('fetch')) {
        setSalesError('تعذّر الاتصال بالـ API');
      } else if (err instanceof ApiError) {
        setSalesError(errorForStatus(err.status, (err as ApiError).detail));
      } else {
        setSalesError('تعذّر جلب المبيعات');
      }
    }
  }, []);

  // biome-ignore lint/correctness/useExhaustiveDependencies: handleAuthFail stable for POS
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    (async () => {
      const token = loadToken();
      if (!token) {
        if (!cancelled) setView('login');
        return;
      }
      try {
        const res = await fetchSales(token, controller.signal);
        if (cancelled) return;
        setSalesError(null);
        setSales(res.sales.slice(0, 100));
        setView('ready');
      } catch (err) {
        if (cancelled) return;
        if ((err as Error)?.name === 'AbortError') return;
        if (err instanceof ApiError && err.status === 401) {
          handleAuthFail();
        } else if (
          err instanceof ApiError &&
          (err.status === 403 || err.status === 429 || err.status >= 500)
        ) {
          setSales([]);
          setSalesError(errorForStatus(err.status, (err as ApiError).detail));
          setView('ready');
        } else if (err instanceof SyntaxError) {
          setSales([]);
          setSalesError('خطأ بالخادم — حاول لاحقاً');
          setView('ready');
        } else if (err instanceof TypeError || (err as Error)?.message?.includes('fetch')) {
          setSales([]);
          setSalesError('تعذّر الاتصال بالـ API');
          setView('ready');
        } else {
          setView('error');
        }
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  async function submitLogin(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setLoginError(null);
    try {
      const auth = await login(username, password);
      if (auth.must_reset_password) {
        setPendingAuth(auth);
        setResetForm({ oldPassword: password, newPassword: '', confirm: '' });
        setResetError(null);
        setSubmitting(false);
        return;
      }
      saveToken(auth.access_token);
      try {
        const res = await fetchSales(auth.access_token);
        setSales(res.sales.slice(0, 100));
      } catch {
        // sales fetch failure is non-fatal after login; show ready with error banner
        setSalesError('تعذّر جلب المبيعات — حاول تحديث القائمة');
      }
      setView('ready');
      setUsername('');
      setPassword('');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setLoginError('invalid');
      } else {
        setLoginError('network');
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function submitReset(e: FormEvent) {
    e.preventDefault();
    const auth = pendingAuth;
    if (!auth) return;
    const clientError = validateNewPassword(
      resetForm.oldPassword,
      resetForm.newPassword,
      resetForm.confirm,
    );
    if (clientError) {
      setResetError(clientError);
      return;
    }
    setSubmitting(true);
    setResetError(null);
    try {
      await resetPassword(auth.access_token, resetForm.oldPassword, resetForm.newPassword);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        const d = (err.detail ?? '').toLowerCase();
        if (d.includes('token') || d.includes('expired') || d.includes('session')) {
          clearToken();
          setPendingAuth(null);
          setView('login');
          setResetError(null);
        } else {
          setResetError('wrong-old');
        }
      } else if (err instanceof ApiError && err.status === 400) {
        setResetError('rejected');
      } else {
        setResetError('network');
      }
      setSubmitting(false);
      return;
    }
    setPendingAuth(null);
    setResetForm({ oldPassword: '', newPassword: '', confirm: '' });
    // Apple: don't reuse pre-reset token (server may rotate) — force re-login with new password
    try {
      window.localStorage.removeItem('pharmatag:token');
    } catch {}
    setView('login');
    setSubmitting(false);
    return;
  }

  async function doSearch() {
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults(null);
      setSearchError(null);
      return;
    }
    if (q.length > 100) {
      setSearchError('نص البحث طويل جداً — الحد 100 حرف');
      setSearchResults([]);
      return;
    }
    if (searchAbortRef.current) searchAbortRef.current.abort();
    const ac = new AbortController();
    searchAbortRef.current = ac;
    const mySeq = ++searchSeq.current;
    setSearching(true);
    setSearchError(null);
    try {
      const res = await searchDrugs(token, q, ac.signal);
      if (mySeq !== searchSeq.current) return;
      const active = res.drugs.filter((d) => d.active);
      if (res.drugs.length > 0 && active.length === 0) {
        setSearchError('الدواء غير نشط — غير متاح للبيع');
      }
      setSearchResults(active);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return;
      if (mySeq !== searchSeq.current) return;
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      }
      if (err instanceof ApiError) {
        setSearchError(errorForStatus(err.status, (err as ApiError).detail));
      } else {
        setSearchError('تعذّر الاتصال بالـ API');
      }
      setSearchResults([]);
    } finally {
      if (searchAbortRef.current === ac) searchAbortRef.current = null;
      if (mySeq === searchSeq.current) setSearching(false);
    }
  }

  function addToCart(drug: Drug) {
    const err = hookAddToCart(drug);
    if (err) {
      setSaveError(err);
      return;
    }
    setSaveError(null);
  }

  async function saveSale() {
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    if (cart.length === 0) {
      setSaveError('العربة فارغة — أضف صنفاً واحداً على الأقل');
      return;
    }
    // validate qtys — Apple: normalize locale (٫,،, Arabic digits) then strict regex, no binary float drift (string-based)
    for (const item of cart) {
      const rawQty = normalizeDecimal(item.qty);
      if (!rawQty || !isQtyValid(rawQty) || !isPositive(rawQty)) {
        setSaveError(`كمية غير صالحة للصنف ${item.drug.drugnamear || item.drug.drugname}`);
        return;
      }
      const rawDisc = normalizeDecimal(item.disc_percent);
      if (rawDisc) {
        if (!isMoneyValid(rawDisc) || !isInRange(rawDisc, '0', '100')) {
          setSaveError(`خصم غير صالح للصنف ${item.drug.drugnamear}`);
          return;
        }
      }
    }
    const rawInvDisc = normalizeDecimal(invoiceDisc);
    if (rawInvDisc) {
      if (!isMoneyValid(rawInvDisc) || !isInRange(rawInvDisc, '0', '100')) {
        setSaveError('خصم الفاتورة يجب أن يكون بين 0 و 100');
        return;
      }
    }

    const payments: { method: 'cash' | 'card' | 'credit'; amount?: string }[] = [];
    const pushPayment = (raw: string, method: 'cash' | 'card' | 'credit', label: string) => {
      const t = normalizeDecimal(raw);
      if (!t) return true;
      if (!isMoneyValid(t) || compareDecimal(t, '0') < 0) {
        setSaveError(label);
        return false;
      }
      if (isZero(t)) return true; // "0" means no amount — not an error (Apple: explicit 0 ≠ payment)
      payments.push({ method, amount: toFixed2(t) });
      return true;
    };
    if (!pushPayment(payCash, 'cash', 'مبلغ النقدي غير صالح')) return;
    if (!pushPayment(payCard, 'card', 'مبلغ الشبكة غير صالح')) return;
    if (!pushPayment(payCredit, 'credit', 'مبلغ الآجل غير صالح')) return;

    if (savingLock.current) return;
    savingLock.current = true;
    setSaving(true);
    setSaveError(null);
    setSaveResult(null);
    setPrintError(null);
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 15_000);
    try {
      const body = {
        lines: cart.map((c) => {
          const line: {
            drug_id: number;
            qty: string;
            price_level?: PriceLevel;
            disc_percent?: string;
          } = {
            drug_id: c.drug.id,
            qty: toFixed4(normalizeDecimal(c.qty)),
          };
          if (c.price_level !== 'public') line.price_level = c.price_level;
          const discNorm = normalizeDecimal(c.disc_percent);
          if (discNorm) line.disc_percent = toFixed2(discNorm);
          return line;
        }),
        disc_percent: rawInvDisc ? toFixed2(rawInvDisc) : undefined,
        payments: payments.length ? payments : undefined,
      };
      const out = await createSale(token, body, ac.signal);
      clearTimeout(timer);
      setSaveResult(out);
      // refresh sales list — separate controller so createSale time doesn't eat fetch timeout (Apple: isolate)
      const ac2 = new AbortController();
      const timer2 = setTimeout(() => ac2.abort(), 8000);
      try {
        const res = await fetchSales(token, ac2.signal);
        setSales(res.sales.slice(0, 100));
      } catch (e) {
        if (e instanceof ApiError) setSalesError(errorForStatus(e.status, e.detail));
        else if ((e as Error)?.name === 'AbortError') setSalesError('انتهت مهلة جلب المبيعات');
        else setSalesError('تعذّر تحديث قائمة المبيعات بعد الحفظ');
      } finally {
        clearTimeout(timer2);
      }
      // keep cart for editing? clear after successful save per POS flow
      clearCart();
      setPayCash('');
      setPayCard('');
      setPayCredit('');
      setInvoiceDisc('');
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        setSaveError('انتهت مهلة الاتصال — حاول مجدداً');
      } else if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      } else if (err instanceof ApiError) {
        setSaveError(
          errorForStatus(err.status, (err as ApiError).detail ?? (err as Error).message),
        );
      } else {
        setSaveError('تعذّر الاتصال بالـ API');
      }
    } finally {
      clearTimeout(timer);
      savingLock.current = false;
      setSaving(false);
    }
  }

  async function openDetail(id: number) {
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    if (detailAbortRef.current) detailAbortRef.current.abort();
    const ac = new AbortController();
    detailAbortRef.current = ac;
    const mySeq = ++detailSeq.current;
    setSelectedId(id);
    setSelectedSale(null);
    setDetailError(null);
    setReturnError(null);
    setReturnResult(null);
    setReturnQty({});
    setDetailLoading(true);
    try {
      const sale = await fetchSale(token, id, ac.signal);
      if (mySeq !== detailSeq.current) return;
      setSelectedSale(sale);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return;
      if (mySeq !== detailSeq.current) return;
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      }
      if (err instanceof ApiError) {
        setDetailError(errorForStatus(err.status, (err as ApiError).detail));
      } else {
        setDetailError('تعذّر الاتصال بالـ API');
      }
    } finally {
      if (detailAbortRef.current === ac) detailAbortRef.current = null;
      if (mySeq === detailSeq.current) setDetailLoading(false);
    }
  }

  async function doReturn() {
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    if (!selectedSale) {
      setReturnError('اختر فاتورة أولاً لإرجاعها');
      return;
    }
    const lines: { ref_invoice_line_id: number; qty: string }[] = [];
    for (const line of selectedSale.lines) {
      const qtyStr = normalizeDecimal(returnQty[line.id] ?? '');
      if (!qtyStr) continue;
      if (!isQtyValid(qtyStr) || !isPositive(qtyStr)) {
        setReturnError(`كمية الإرجاع غير صالحة للسطر ${line.drugnamear || line.drugname}`);
        return;
      }
      if (compareDecimal(qtyStr, line.qty) > 0) {
        setReturnError(
          `كمية الإرجاع تتجاوز الكمية الأصلية (${line.qty}) للصنف ${line.drugnamear || line.drugname}`,
        );
        return;
      }
      lines.push({ ref_invoice_line_id: line.id, qty: toFixed4(qtyStr) });
    }
    if (lines.length === 0) {
      setReturnError('حدد كمية لسطر واحد على الأقل للإرجاع');
      return;
    }
    if (returningLock.current) return;
    returningLock.current = true;
    setReturning(true);
    setReturnError(null);
    setReturnResult(null);
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 15_000);
    try {
      const out = await createSaleReturn(token, selectedSale.id, { lines }, ac.signal);
      clearTimeout(timer);
      setReturnResult(out);
      setReturnQty({});
      const ac2 = new AbortController();
      const timer2 = setTimeout(() => ac2.abort(), 8000);
      try {
        const res = await fetchSales(token, ac2.signal);
        setSales(res.sales.slice(0, 100));
      } catch (e) {
        if (e instanceof ApiError) setSalesError(errorForStatus(e.status, e.detail));
        else if ((e as Error)?.name === 'AbortError') setSalesError('انتهت مهلة جلب المبيعات');
        else setSalesError('تعذّر تحديث قائمة المبيعات بعد الإرجاع');
      } finally {
        clearTimeout(timer2);
      }
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        setReturnError('انتهت مهلة الاتصال — حاول مجدداً');
      } else if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      } else if (err instanceof ApiError) {
        setReturnError(
          errorForStatus(err.status, (err as ApiError).detail ?? (err as Error).message),
        );
      } else {
        setReturnError('تعذّر الاتصال بالـ API');
      }
    } finally {
      clearTimeout(timer);
      returningLock.current = false;
      setReturning(false);
    }
  }

  async function handlePrint(id: number, kind: 'print' | 'tax-document') {
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    setPrintError(null);
    try {
      await openSalePrint(token, id, kind);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      }
      if (err instanceof ApiError) {
        setPrintError(errorForStatus(err.status, (err as ApiError).detail));
      } else {
        setPrintError('تعذّر الاتصال بالـ API');
      }
    }
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
        <p className="pt-caption">جارٍ التحميل…</p>
      </Shell>
    );
  }

  if (pendingAuth) {
    return (
      <Shell>
        <section className="flex h-full flex-col gap-4">
          <div className="flex items-center gap-3">
            <h1 className="pt-title text-2xl">نقطة البيع</h1>
            {chip}
          </div>
          <div className="pt-card w-full max-w-sm">
            <form className="flex flex-col gap-3" onSubmit={submitReset}>
              <p className="pt-title text-lg">تغيير كلمة المرور</p>
              <p className="pt-caption">
                يجب تغيير كلمة المرور الافتراضية قبل الدخول. أدخل كلمة مرور جديدة قوية.
              </p>
              <label className="pt-caption flex flex-col gap-1">
                كلمة المرور الحالية
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={resetForm.oldPassword}
                  autoComplete="current-password"
                  onChange={(e) => setResetForm((f) => ({ ...f, oldPassword: e.target.value }))}
                  required
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                كلمة المرور الجديدة
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={resetForm.newPassword}
                  autoComplete="new-password"
                  onChange={(e) => setResetForm((f) => ({ ...f, newPassword: e.target.value }))}
                  required
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                تأكيد كلمة المرور الجديدة
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={resetForm.confirm}
                  autoComplete="new-password"
                  onChange={(e) => setResetForm((f) => ({ ...f, confirm: e.target.value }))}
                  required
                />
              </label>
              {resetError && (
                <p className="pt-caption text-red-600">{RESET_ERROR_TEXT[resetError]}</p>
              )}
              <button
                type="submit"
                disabled={submitting}
                className="pt-caption cursor-pointer rounded-md bg-surface-elevated px-4 py-2 disabled:opacity-50"
              >
                {submitting ? 'جارٍ الحفظ…' : 'تغيير وحفظ'}
              </button>
            </form>
          </div>
        </section>
      </Shell>
    );
  }

  if (view === 'login') {
    return (
      <Shell>
        <section className="flex h-full flex-col gap-4">
          <div className="flex items-center gap-3">
            <h1 className="pt-title text-2xl">نقطة البيع</h1>
            {chip}
          </div>
          <div className="pt-card w-full max-w-sm">
            <form className="flex flex-col gap-3" onSubmit={submitLogin}>
              <p className="pt-title text-lg">تسجيل الدخول</p>
              <label className="pt-caption flex flex-col gap-1">
                اسم المستخدم
                <input
                  className="rounded-md border border-border px-3 py-2"
                  value={username}
                  autoComplete="username"
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                كلمة المرور
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={password}
                  autoComplete="current-password"
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </label>
              {loginError === 'invalid' && (
                <p className="pt-caption text-red-600">بيانات الدخول غير صحيحة — أعد المحاولة.</p>
              )}
              {loginError === 'network' && (
                <p className="pt-caption text-red-600">
                  تعذّر الاتصال بالـ API — تأكد من تشغيله على http://localhost:8000.
                </p>
              )}
              <button
                type="submit"
                disabled={submitting}
                className="pt-caption cursor-pointer rounded-md bg-surface-elevated px-4 py-2 disabled:opacity-50"
              >
                {submitting ? 'جارٍ الدخول…' : 'دخول'}
              </button>
            </form>
          </div>
        </section>
      </Shell>
    );
  }

  if (view === 'error') {
    return (
      <Shell>
        <section className="flex h-full flex-col gap-4">
          <div className="flex items-center gap-3">
            <h1 className="pt-title text-2xl">نقطة البيع</h1>
            {chip}
          </div>
          <p className="pt-caption">
            تعذّر جلب بيانات نقطة البيع من الخادم — تأكد من تشغيل الـ API على http://localhost:8000.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={async () => {
                const token = loadToken();
                if (!token) {
                  setView('login');
                  return;
                }
                setView('boot');
                try {
                  const res = await fetchSales(token);
                  setSales(res.sales);
                  setView('ready');
                } catch (err) {
                  if (err instanceof ApiError && err.status === 401) {
                    clearToken();
                    setView('login');
                  } else {
                    setView('error');
                  }
                }
              }}
              className="w-fit rounded border border-border px-3 py-1.5 text-sm"
            >
              إعادة المحاولة
            </button>
            <button
              type="button"
              onClick={logout}
              className="w-fit rounded border border-border px-3 py-1.5 text-sm"
            >
              تسجيل الخروج
            </button>
          </div>
        </section>
      </Shell>
    );
  }

  // ready
  return (
    <Shell>
      <section className="flex h-full flex-col gap-4" dir="rtl">
        <div className="flex items-center gap-3">
          <h1 className="pt-title text-2xl">نقطة البيع</h1>
          {chip}
          <button
            type="button"
            className="ms-auto pt-caption cursor-pointer rounded-md border border-border px-3 py-1"
            onClick={logout}
          >
            تسجيل الخروج
          </button>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Search + Cart */}
          <div className="flex flex-col gap-4">
            <SearchPanel
              searchQuery={searchQuery}
              onSearchQueryChange={setSearchQuery}
              searching={searching}
              searchError={searchError}
              searchResults={searchResults}
              onSearch={doSearch}
              onAdd={addToCart}
            />

            <div className="pt-card flex flex-col gap-3">
              <h2 className="pt-title text-lg">العربة</h2>
              <CartTable cart={cart} onUpdate={updateCart} onRemove={removeFromCart} />
              <PaymentForm
                invoiceDisc={invoiceDisc}
                onInvoiceDiscChange={setInvoiceDisc}
                payCash={payCash}
                onPayCashChange={setPayCash}
                payCard={payCard}
                onPayCardChange={setPayCard}
                payCredit={payCredit}
                onPayCreditChange={setPayCredit}
                saving={saving}
                saveError={saveError}
                salesError={salesError}
                saveResult={saveResult}
                printError={printError}
                cartLength={cart.length}
                onSave={saveSale}
                onPrint={handlePrint}
              />
            </div>
          </div>

          {/* Sales list + detail */}
          <div className="flex flex-col gap-4">
            <SalesList
              sales={sales}
              salesError={salesError}
              salesSearch={salesSearch}
              onSalesSearchChange={setSalesSearch}
              selectedId={selectedId}
              onOpenDetail={openDetail}
              onRefresh={() => {
                const token = loadToken();
                if (token) void loadSales(token);
              }}
            />

            <SaleDetail
              selectedId={selectedId}
              selectedSale={selectedSale}
              detailLoading={detailLoading}
              detailError={detailError}
              printError={printError}
              returnQty={returnQty}
              onReturnQtyChange={(lineId, value) =>
                setReturnQty((prev) => ({ ...prev, [lineId]: value }))
              }
              returning={returning}
              returnError={returnError}
              returnResult={returnResult}
              onPrint={handlePrint}
              onReturn={doReturn}
            />
          </div>
        </div>

        <p className="pt-caption text-xs text-muted">
          المجاميع محسوبة على الخادم فقط — العميل يرسل الكميات والأسعار المرجعية، لا الإجماليات.
        </p>
      </section>
    </Shell>
  );
}
