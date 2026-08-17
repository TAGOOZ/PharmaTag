/**
 * Pre-hydration theme bootstrap — the anti-flash script (plan/09 §4.2).
 *
 * Runs before first paint and MUST mirror ThemeProvider's resolution exactly.
 * Brand default is LIGHT when nothing is stored or the stored value is unknown
 * (P02) — the old behavior of following the OS for a missing value flashed
 * dark→light for OS-dark first-time users.
 */
import {
  normalizeThemeSetting,
  type ResolvedTheme,
  resolveTheme,
  THEME_STORAGE_KEY,
} from './theme-core';

/** Pure resolution used by the embedded script (testable in isolation). */
export function resolveBootTheme(stored: string | null, systemPrefersDark: boolean): ResolvedTheme {
  return resolveTheme(normalizeThemeSetting(stored), systemPrefersDark);
}

/** Canonical inline script — embedded by BOTH shells (web layout + desktop index.html). */
export const THEME_BOOT_SCRIPT = `(()=>{var s;var t;try{s=localStorage.getItem('${THEME_STORAGE_KEY}');if(s==='dark'){t='dark'}else if(s==='light'){t='light'}else if(s==='system'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}else{t='light'}document.documentElement.setAttribute('data-theme',t);}catch(_e){}})();`;
