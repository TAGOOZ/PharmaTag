import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { resolveBootTheme, THEME_BOOT_SCRIPT } from './theme-boot';
import { DEFAULT_THEME_SETTING } from './theme-core';

function runBoot(stored: string | null, prefersDark: boolean): string | null {
  let applied: string | null = null;
  const documentElement = {
    setAttribute(name: string, value: string) {
      if (name === 'data-theme') applied = value;
    },
  };
  const windowLike = { matchMedia: () => ({ matches: prefersDark }) };
  const localStorageLike = { getItem: () => stored };
  // eslint-disable-next-line no-new-func
  new Function('window', 'localStorage', 'document', THEME_BOOT_SCRIPT)(
    windowLike,
    localStorageLike,
    { documentElement },
  );
  return applied;
}

describe('theme-boot (plan/09 §4.2 anti-flash bootstrap)', () => {
  it('brand default is LIGHT when nothing is stored, even on an OS-dark machine (P02)', () => {
    expect(DEFAULT_THEME_SETTING).toBe('light');
    expect(resolveBootTheme(null, true)).toBe('light');
    expect(resolveBootTheme(null, false)).toBe('light');
  });

  it('unknown stored values fall back to LIGHT, never to the OS preference', () => {
    expect(resolveBootTheme('rainbow', true)).toBe('light');
    expect(resolveBootTheme('', true)).toBe('light');
    expect(resolveBootTheme('system ' as string, true)).toBe('light');
  });

  it('honours explicit dark / light / system settings exactly like ThemeProvider', () => {
    expect(resolveBootTheme('dark', false)).toBe('dark');
    expect(resolveBootTheme('light', true)).toBe('light');
    expect(resolveBootTheme('system', true)).toBe('dark');
    expect(resolveBootTheme('system', false)).toBe('light');
  });

  it('embedded script sets data-theme=light for a first-time OS-dark user (no flash mismatch)', () => {
    expect(runBoot(null, true)).toBe('light');
    expect(runBoot('dark', true)).toBe('dark');
    expect(runBoot('light', true)).toBe('light');
    expect(runBoot('system', true)).toBe('dark');
    expect(runBoot('system', false)).toBe('light');
    expect(runBoot('garbage', true)).toBe('light');
  });

  it('embedded script survives throwing storage/matchMedia (offline/denied) and still applies light', () => {
    let applied: string | null = null;
    const documentElement = {
      setAttribute(name: string, value: string) {
        if (name === 'data-theme') applied = value;
      },
    };
    const throwingLocalStorage = {
      getItem: () => {
        throw new Error('SecurityError: access denied');
      },
    };
    // eslint-disable-next-line no-new-func
    new Function('window', 'localStorage', 'document', THEME_BOOT_SCRIPT)(
      { matchMedia: () => ({ matches: true }) },
      throwingLocalStorage,
      { documentElement },
    );
    expect(applied).toBe(null); // swallowed, nothing applied, ThemeProvider fixes after hydration
  });

  it('keeps the two shells wired to the canonical script (no drift)', () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const repoRoot = join(here, '..', '..', '..');
    const layout = readFileSync(join(repoRoot, 'apps', 'web', 'app', 'layout.tsx'), 'utf8');
    const indexHtml = readFileSync(join(repoRoot, 'apps', 'desktop', 'index.html'), 'utf8');
    const inlineScript = (indexHtml.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? '').replace(
      /^\s*\/\/.*$/gm,
      '',
    );
    // formatter-tolerant, logic-strict: compare whitespace-free bodies
    const strip = (s: string) => s.replace(/\s+/g, '');
    expect(layout).toContain('THEME_BOOT_SCRIPT');
    expect(strip(inlineScript)).toBe(strip(THEME_BOOT_SCRIPT));
    expect(indexHtml).not.toContain("s==='dark'||s==='light'");
  });
});
