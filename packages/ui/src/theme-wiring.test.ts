import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

/**
 * Cross-app CSS wiring invariants (edge-case pass, issue #4):
 * every `var(--…)` referenced by the Tailwind `@theme inline` blocks in the two
 * app CSS files MUST resolve to a token defined in tokens.css — otherwise the
 * utility class it feeds (bg-surface, border-border, text-brand, …) compiles to
 * an invalid `rgb(var(--undefined))` and the property is dropped.
 */
const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..', '..');
const tokensCss = readFileSync(join(here, 'styles', 'tokens.css'), 'utf8');

const appCss = {
  web: readFileSync(join(repoRoot, 'apps', 'web', 'app', 'globals.css'), 'utf8'),
  desktop: readFileSync(join(repoRoot, 'apps', 'desktop', 'src', 'index.css'), 'utf8'),
};

function referencedTokens(css: string): string[] {
  return [...css.matchAll(/var\((--[\w-]+)\)/g)]
    .map((m) => m[1])
    .filter((name): name is string => name !== undefined);
}

function definedInTokens(name: string): boolean {
  return new RegExp(`${name}\\s*:`).test(tokensCss);
}

describe('app CSS @theme inline wiring (no utility may reference an undefined token)', () => {
  for (const [app, css] of Object.entries(appCss)) {
    it(`${app}: every var() in the theme block resolves to a token defined in tokens.css`, () => {
      const missing = [...new Set(referencedTokens(css))].filter((name) => !definedInTokens(name));
      expect(missing, `undefined tokens referenced by ${app} CSS: ${missing.join(', ')}`).toEqual(
        [],
      );
    });
  }

  it('maps the surface/elevated/border/brand utilities to real tokens (never invented names)', () => {
    for (const css of Object.values(appCss)) {
      expect(css).toContain('--color-surface: rgb(var(--background-secondary));');
      expect(css).toContain('--color-elevated: rgb(var(--background-tertiary));');
      expect(css).toContain('--color-border: rgb(var(--border));');
      expect(css).toContain('--color-brand: rgb(var(--accent-color));');
      expect(css).not.toContain('--surface-soft');
      expect(css).not.toContain('--surface-elevated');
      expect(css).not.toContain('--border-default');
      expect(css).not.toContain('--brand-solid');
    }
  });

  it('keeps the web and desktop theme mappings identical (no drift between shells)', () => {
    expect(appCss.desktop).toBe(appCss.web);
  });
});

describe('prefers-reduced-motion (plan/09 §2.3 — motion collapses to instant)', () => {
  const block = tokensCss.match(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*{([^}]*)}/);
  const body = block?.[1] ?? '';

  it('defines a reduced-motion block overriding the motion tokens', () => {
    expect(block, 'missing @media (prefers-reduced-motion: reduce) block').toBeTruthy();
  });

  it('collapses every duration/ease token to 0ms or linear', () => {
    for (const token of [
      '--transition-fast',
      '--transition-normal',
      '--dur-fast',
      '--dur-base',
      '--dur-slow',
      '--dur-slower',
    ]) {
      expect(body).toMatch(new RegExp(`${token}\\s*:\\s*0ms;`));
    }
    expect(body).toMatch(/--ease-std\s*:\s*linear;/);
  });
});

describe('color-scheme + font loading (no native scrollbar/FOIT regressions)', () => {
  it('sets color-scheme light by default and dark under html[data-theme="dark"] in both shells', () => {
    for (const css of Object.values(appCss)) {
      expect(css).toMatch(/color-scheme:\s*light;/);
      expect(css).toMatch(/html\[data-theme='dark'\]\s*{[^}]*color-scheme:\s*dark;/);
    }
  });

  it('loads every @font-face with font-display: swap (no FOIT)', () => {
    const fontsCss = readFileSync(join(here, 'styles', 'fonts.css'), 'utf8');
    const faceCount = (fontsCss.match(/@font-face/g) ?? []).length;
    expect(faceCount).toBeGreaterThan(0);
    expect((fontsCss.match(/font-display:\s*swap;/g) ?? []).length).toBe(faceCount);
  });
});

describe('dark parity (computed — the dark theme must never introduce or drop tokens)', () => {
  function propNames(css: string): string[] {
    return [...css.matchAll(/(--[\w-]+)\s*:/g)]
      .map((m) => m[1])
      .filter((n): n is string => n !== undefined);
  }

  const darkBlock = tokensCss.match(/\[data-theme=['"]dark['"]\]\s*{([^}]*)}/)?.[1] ?? '';
  const darkNames = [...new Set(propNames(darkBlock))];

  it('every token the dark theme overrides also exists in the light (:root) theme', () => {
    expect(darkNames.length).toBeGreaterThan(0);
    for (const name of darkNames) {
      expect(definedInTokens(name), `dark defines ${name} but light (:root) does not`).toBe(true);
    }
  });

  it('every color token the app CSS feeds into rgb() is overridden in the dark theme', () => {
    const rgbInner = (css: string) =>
      [...css.matchAll(/rgb\(var\((--[\w-]+)\)\)/g)]
        .map((m) => m[1])
        .filter((n): n is string => n !== undefined);
    const colorTokens = [...new Set([...rgbInner(appCss.web), ...rgbInner(appCss.desktop)])];
    expect(colorTokens.length).toBeGreaterThan(0);
    for (const name of colorTokens) {
      expect(definedInTokens(name), `${name} missing from tokens.css`).toBe(true);
      expect(
        darkNames,
        `${name} missing from the dark theme (would render light in dark mode)`,
      ).toContain(name);
    }
  });
});
