'use client';

import { formatMoney, StatusChip } from '@pharmatag/ui';
import { type FormEvent, useEffect, useState } from 'react';
import { Shell } from '@/components/shell';
import {
  ApiError,
  clearToken,
  type DrugListResponse,
  fetchDrugs,
  type LoginResponse,
  loadToken,
  login,
  resetPassword,
  saveToken,
} from '@/lib/api';
import { RESET_ERROR_TEXT, type ResetError, validateNewPassword } from '@/lib/change-password';
import { errorForStatus } from '@/lib/posMoney';

type ViewState = 'boot' | 'login' | 'ready' | 'error';
type LoginError = 'invalid' | 'network' | null;

export default function DrugsPage() {
  const [view, setView] = useState<ViewState>('boot');
  const [data, setData] = useState<DrugListResponse | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState<LoginError>(null);
  const [pendingAuth, setPendingAuth] = useState<LoginResponse | null>(null);
  const [resetForm, setResetForm] = useState({ oldPassword: '', newPassword: '', confirm: '' });
  const [resetError, setResetError] = useState<ResetError>(null);
  const [submitting, setSubmitting] = useState(false);

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
        const list = await fetchDrugs(token, controller.signal);
        if (cancelled) return;
        setBootError(null);
        setData(list);
        setView('ready');
      } catch (err) {
        if (cancelled) return;
        if ((err as Error)?.name === 'AbortError') return;
        if (err instanceof ApiError && err.status === 401) {
          // stale/revoked token — force a fresh login
          clearToken();
          setView('login');
        } else if (
          err instanceof ApiError &&
          (err.status === 403 || err.status === 429 || err.status >= 500)
        ) {
          const msg = errorForStatus(err.status, (err as ApiError).detail);
          setBootError(msg);
          setData({ branch: { id: 0, pharmacyid: '', pharname: '' }, drugs: [] });
          setView('ready');
        } else if (err instanceof SyntaxError) {
          const msg = 'خطأ بالخادم — حاول لاحقاً';
          setBootError(msg);
          setData({ branch: { id: 0, pharmacyid: '', pharname: '' }, drugs: [] });
          setView('ready');
        } else if (err instanceof TypeError || (err as Error)?.message?.includes('fetch')) {
          const msg = 'تعذّر الاتصال بالـ API';
          setBootError(msg);
          setData({ branch: { id: 0, pharmacyid: '', pharname: '' }, drugs: [] });
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

  async function submit(e: FormEvent) {
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
      setData(await fetchDrugs(auth.access_token));
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
        setResetError('wrong-old');
      } else if (err instanceof ApiError && err.status === 400) {
        setResetError('rejected');
      } else {
        setResetError('network');
      }
      setSubmitting(false);
      return;
    }
    // Password changed: the login token becomes the session token. Never
    // return to the reset form afterwards — the old password is already dead.
    saveToken(auth.access_token);
    setPendingAuth(null);
    setResetForm({ oldPassword: '', newPassword: '', confirm: '' });
    try {
      setData(await fetchDrugs(auth.access_token));
      setView('ready');
    } catch {
      setView('error');
    } finally {
      setSubmitting(false);
    }
  }

  function logout() {
    clearToken();
    setData(null);
    setView('login');
  }

  const chip =
    view === 'boot' || view === 'login' ? (
      <StatusChip kind="offline" labelAr="تسجيل الدخول" labelEn="Sign in" />
    ) : view === 'ready' ? (
      <StatusChip kind="online" labelAr="الخادم متصل" labelEn="API online" />
    ) : (
      <StatusChip kind="saved" labelAr="الخادم غير متاح" labelEn="API unavailable" />
    );

  return (
    <Shell>
      <section className="flex h-full flex-col gap-4">
        <div className="flex items-center gap-3">
          <h1 className="pt-title text-2xl">الأدوية</h1>
          {chip}
          {view === 'ready' && (
            <button
              type="button"
              className="ms-auto pt-caption cursor-pointer rounded-md border border-border px-3 py-1"
              onClick={logout}
            >
              تسجيل الخروج
            </button>
          )}
        </div>

        {view === 'boot' ? (
          <p className="pt-caption">جارٍ التحميل…</p>
        ) : pendingAuth ? (
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
        ) : view === 'login' ? (
          <div className="pt-card w-full max-w-sm">
            <form className="flex flex-col gap-3" onSubmit={submit}>
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
        ) : view === 'error' ? (
          <p className="pt-caption">
            تعذّر جلب قائمة الأدوية من الخادم — تأكد من تشغيل الـ API على http://localhost:8000.
          </p>
        ) : data && data.drugs.length === 0 ? (
          <>
            {bootError && (
              <p className="pt-caption text-red-600" role="alert">
                {bootError}
              </p>
            )}
            <p className="pt-caption">لا توجد أدوية مفعّلة في هذا الفرع.</p>
          </>
        ) : data ? (
          <div className="pt-card">
            {bootError && (
              <p className="pt-caption mb-3 text-red-600" role="alert">
                {bootError}
              </p>
            )}
            <p className="pt-caption mb-3">فرع: {data.branch.pharname} — قائمة الأدوية المفعلة</p>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-start">
                <thead>
                  <tr className="border-b border-border">
                    <th className="pt-caption px-3 py-2 text-start">الاسم العربي</th>
                    <th className="pt-caption px-3 py-2 text-start">الاسم الإنجليزي</th>
                    <th className="pt-caption px-3 py-2 text-start">السعر (EGP)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.drugs.map((drug) => (
                    <tr key={drug.id} className="border-b border-border">
                      <td className="px-3 py-2">{drug.drugnamear}</td>
                      <td className="pt-mono px-3 py-2 text-muted">{drug.drugname}</td>
                      <td className="pt-mono px-3 py-2">{formatMoney(drug.price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>
    </Shell>
  );
}
