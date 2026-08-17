/**
 * RTL / locale helpers (plan/09 §4.3, §2.4).
 * Arabic-first: `dir="rtl" lang="ar"` is the structural default; numerals stay
 * Western (latn) for data entry and money, dates render Gregorian via Intl.
 */

export function isRTL(lang: string): boolean {
  return lang.toLowerCase().startsWith('ar');
}

export function getDir(lang: string): 'rtl' | 'ltr' {
  return isRTL(lang) ? 'rtl' : 'ltr';
}

export interface LanguageTarget {
  lang: string;
  dir: string;
}

export function applyLanguage(target: LanguageTarget, lang: string): void {
  target.lang = lang;
  target.dir = getDir(lang);
}

const latinNumerals = { numberingSystem: 'latn' } as const;

export function formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat('ar-EG', { ...latinNumerals, ...options }).format(value);
}

export function formatMoney(value: number, currency = 'EGP'): string {
  return new Intl.NumberFormat('ar-EG', {
    ...latinNumerals,
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatDate(
  value: string | number | Date,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat('ar-EG', {
    ...latinNumerals,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...options,
  }).format(date);
}
