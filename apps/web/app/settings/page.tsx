'use client';

import { type FormEvent, useEffect, useState } from 'react';
import { Shell } from '@/components/shell';
import { ApiError, loadToken, resetPassword } from '@/lib/api';
import { RESET_ERROR_TEXT, type ResetError, validateNewPassword } from '@/lib/change-password';

type AuthState = 'boot' | 'signed-out' | 'signed-in';

export default function SettingsPage() {
  const [auth, setAuth] = useState<AuthState>('boot');
  const [form, setForm] = useState({ oldPassword: '', newPassword: '', confirm: '' });
  const [error, setError] = useState<ResetError>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setAuth(loadToken() ? 'signed-in' : 'signed-out');
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const token = loadToken();
    if (!token) return;
    const clientError = validateNewPassword(form.oldPassword, form.newPassword, form.confirm);
    if (clientError) {
      setError(clientError);
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(false);
    try {
      await resetPassword(token, form.oldPassword, form.newPassword);
      setSuccess(true);
      setForm({ oldPassword: '', newPassword: '', confirm: '' });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('wrong-old');
      } else if (err instanceof ApiError && err.status === 400) {
        setError('rejected');
      } else {
        setError('network');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Shell>
      <section className="flex h-full flex-col gap-4">
        <h1 className="pt-title text-2xl">الاعدادات</h1>
        {auth === 'boot' ? (
          <p className="pt-caption">جارٍ التحميل…</p>
        ) : auth === 'signed-out' ? (
          <p className="pt-caption">سجّل الدخول أولاً لتغيير كلمة المرور.</p>
        ) : (
          <div className="pt-card w-full max-w-sm">
            <form className="flex flex-col gap-3" onSubmit={submit}>
              <p className="pt-title text-lg">تغيير كلمة المرور</p>
              <label className="pt-caption flex flex-col gap-1">
                كلمة المرور الحالية
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={form.oldPassword}
                  autoComplete="current-password"
                  onChange={(e) => setForm((f) => ({ ...f, oldPassword: e.target.value }))}
                  required
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                كلمة المرور الجديدة
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={form.newPassword}
                  autoComplete="new-password"
                  onChange={(e) => setForm((f) => ({ ...f, newPassword: e.target.value }))}
                  required
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                تأكيد كلمة المرور الجديدة
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={form.confirm}
                  autoComplete="new-password"
                  onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))}
                  required
                />
              </label>
              {error && <p className="pt-caption text-red-600">{RESET_ERROR_TEXT[error]}</p>}
              {success && <p className="pt-caption text-green-600">تم تغيير كلمة المرور بنجاح.</p>}
              <button
                type="submit"
                disabled={submitting}
                className="pt-caption cursor-pointer rounded-md bg-surface-elevated px-4 py-2 disabled:opacity-50"
              >
                {submitting ? 'جارٍ الحفظ…' : 'تغيير وحفظ'}
              </button>
            </form>
          </div>
        )}
      </section>
    </Shell>
  );
}
