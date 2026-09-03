import { describe, expect, it } from 'vitest';
import { businessToday } from './businessDate';

describe('businessToday', () => {
  it('uses the Cairo business day, not UTC (summer, UTC+3)', () => {
    // 22:30 UTC = 01:30 next day in Cairo — a UTC default would post yesterday.
    expect(businessToday(new Date('2026-08-20T22:30:00Z'))).toBe('2026-08-21');
    expect(businessToday(new Date('2026-08-20T20:59:00Z'))).toBe('2026-08-20');
  });

  it('uses the Cairo business day in winter (UTC+2)', () => {
    expect(businessToday(new Date('2026-01-15T22:30:00Z'))).toBe('2026-01-16');
    expect(businessToday(new Date('2026-01-15T12:00:00Z'))).toBe('2026-01-15');
  });

  it('emits a YYYY-MM-DD date string', () => {
    expect(businessToday(new Date('2026-08-01T00:00:00Z'))).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
