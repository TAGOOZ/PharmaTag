import { ApiError } from '@/lib/api';
import { errorForStatus } from '@/lib/posMoney';

/** Server detail is surfaced verbatim (when short) for actionable codes. */
export function moneyErrorMessage(status: number, detail?: string): string {
  if (
    detail &&
    (detail.includes('/src/') ||
      detail.toLowerCase().includes('stack') ||
      detail.trimStart().startsWith('<'))
  ) {
    // Stack traces and HTML error pages never render verbatim.
    return errorForStatus(status);
  }
  const base = errorForStatus(status, detail);
  if (
    detail &&
    detail.length < 200 &&
    (status === 400 || status === 403 || status === 404 || status === 409 || status === 422)
  ) {
    if (!base.includes(detail)) return `${base} — ${detail}`;
  }
  return base;
}

export function mapMoneyError(err: unknown): string {
  if (err instanceof SyntaxError) return 'خطأ بالخادم — حاول لاحقاً';
  if (err instanceof TypeError || (err as Error)?.message?.includes('fetch'))
    return 'تعذّر الاتصال بالـ API';
  if (err instanceof ApiError) return moneyErrorMessage(err.status, err.detail);
  return 'تعذّر الاتصال بالـ API';
}
