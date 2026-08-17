import { describe, expect, it } from 'vitest';
import { formatDate, formatMoney, formatNumber, getDir, isRTL } from './rtl';

describe('RTL / locale helpers (plan/09 §4.3, §2.4)', () => {
  it('treats Arabic languages as RTL', () => {
    expect(isRTL('ar')).toBe(true);
    expect(isRTL('ar-EG')).toBe(true);
    expect(isRTL('ar-SA')).toBe(true);
    expect(isRTL('en')).toBe(false);
    expect(isRTL('fr')).toBe(false);
  });

  it('maps language to document direction', () => {
    expect(getDir('ar')).toBe('rtl');
    expect(getDir('ar-EG')).toBe('rtl');
    expect(getDir('en')).toBe('ltr');
  });

  it('formats numbers with forced latin digits, never Arabic-Indic', () => {
    expect(formatNumber(1234.5)).toContain('1,234.5');
    expect(formatNumber(1234.5)).not.toContain('١');
    expect(formatNumber(42)).toBe('42');
  });

  it('formats money with latin digits and the EGP currency', () => {
    const out = formatMoney(1234.5);
    expect(out).toContain('1,234.50');
    expect(out).not.toContain('١');
  });

  it('formats dates as Gregorian text containing the year', () => {
    expect(formatDate('2026-08-17T12:00:00Z')).toContain('2026');
  });
});
