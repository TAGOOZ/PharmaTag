import { describe, expect, it } from 'vitest';
import { ApiError } from '@/lib/api';
import { mapMoneyError, moneyErrorMessage } from './moneyErrors';

describe('moneyErrors', () => {
  it('maps SyntaxError to the generic server message', () => {
    expect(mapMoneyError(new SyntaxError('bad json'))).toBe('خطأ بالخادم — حاول لاحقاً');
  });

  it('maps fetch TypeErrors to API-down, distinct from auth', () => {
    expect(mapMoneyError(new TypeError('fetch failed'))).toBe('تعذّر الاتصال بالـ API');
  });

  it('surfaces short server detail verbatim for actionable codes', () => {
    expect(moneyErrorMessage(400, 'journal is not balanced')).toContain('journal is not balanced');
    expect(moneyErrorMessage(409, 'month is already closed')).toContain('month is already closed');
    expect(moneyErrorMessage(404, 'party not found')).toContain('party not found');
  });

  it('strips stack-trace leaks from 500 details', () => {
    const msg = moneyErrorMessage(500, 'File "/src/app/money/entries.py", line 1');
    expect(msg).not.toContain('/src/');
    expect(msg).toBe('خطأ بالخادم — حاول لاحقاً');
  });

  it('maps 429/401/403 through the shared status catalog', () => {
    expect(mapMoneyError(new ApiError(429, 'slow down'))).toContain('429');
    expect(mapMoneyError(new ApiError(401))).toContain('الجلسة');
    expect(mapMoneyError(new ApiError(403))).toContain('صلاحية');
  });

  it('drops HTML error bodies instead of rendering markup', () => {
    const msg = moneyErrorMessage(500, '<html><body>boom</body></html>');
    expect(msg).not.toContain('<html>');
    expect(msg).toBe('خطأ بالخادم — حاول لاحقاً');
  });

  it('falls back to API-down for unknown error shapes', () => {
    expect(mapMoneyError(new Error('weird'))).toBe('تعذّر الاتصال بالـ API');
    expect(mapMoneyError(null)).toBe('تعذّر الاتصال بالـ API');
  });
});
