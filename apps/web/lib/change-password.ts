/** Shared change-password validation (ticket #37): client-side checks run
 * before hitting POST /api/v1/auth/reset-password, mirroring the server's
 * rules (weak default `changeme` rejected, new must differ from old). */
export type ResetError =
  | 'short'
  | 'overlong'
  | 'weak'
  | 'same'
  | 'mismatch'
  | 'wrong-old'
  | 'rejected'
  | 'network'
  | null;

export const WEAK_DEFAULT_PASSWORD = 'changeme';

export const MIN_PASSWORD_LENGTH = 8;

// bcrypt ignores bytes past 72; the API refuses these (ticket #37), so the
// client mirrors the rule to reject without a round-trip.
export const MAX_PASSWORD_BYTES = 72;

export const RESET_ERROR_TEXT: Record<Exclude<ResetError, null>, string> = {
  short: 'كلمة المرور الجديدة قصيرة جداً — 8 أحرف على الأقل.',
  overlong: 'كلمة المرور الجديدة طويلة جداً — 72 بايت كحد أقصى.',
  weak: 'كلمة المرور الافتراضية لا تُقبل ككلمة مرور جديدة.',
  same: 'كلمة المرور الجديدة يجب أن تختلف عن الحالية.',
  mismatch: 'كلمتا المرور الجديدتان غير متطابقتين.',
  'wrong-old': 'كلمة المرور الحالية غير صحيحة.',
  rejected: 'كلمة المرور الجديدة مرفوضة — اختر كلمة مختلفة.',
  network: 'تعذّر الاتصال بالـ API — تأكد من تشغيله على http://localhost:8000.',
};

/** Empty/weak input validation, client-side, before the API call. */
export function validateNewPassword(
  oldPassword: string,
  newPassword: string,
  confirm: string,
): ResetError {
  if (!oldPassword || !newPassword || !confirm) return 'short';
  if (newPassword.length < MIN_PASSWORD_LENGTH) return 'short';
  if (new TextEncoder().encode(newPassword).length > MAX_PASSWORD_BYTES) return 'overlong';
  if (newPassword === WEAK_DEFAULT_PASSWORD) return 'weak';
  if (newPassword === oldPassword) return 'same';
  if (newPassword !== confirm) return 'mismatch';
  return null;
}
