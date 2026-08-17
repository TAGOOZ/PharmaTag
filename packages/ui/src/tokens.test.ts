import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, 'styles', 'tokens.css'), 'utf8');

function block(selector: string): string {
  // tolerate both attribute quote styles (' and ") in the CSS
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/['"]/g, `['"]`);
  const re = new RegExp(`${escaped}\\s*\\{([^}]*)\\}`, 's');
  const match = css.match(re);
  if (!match) throw new Error(`no block for ${selector}`);
  const value = match[1];
  if (value === undefined) throw new Error(`empty block for ${selector}`);
  return value;
}

const light = block(':root');
const dark = block("[data-theme='dark']");

function definedIn(text: string, name: string): boolean {
  return new RegExp(`${name}\\s*:`).test(text);
}

const requiredSemanticTokens = [
  '--background-primary',
  '--background-secondary',
  '--background-tertiary',
  '--background-modifier-border',
  '--background-form-field',
  '--background-well',
  '--background-scrim',
  '--text-normal',
  '--text-muted',
  '--text-faint',
  '--text-on-accent',
  '--text-secondary-strong',
  '--text-muted-strong',
  '--text-disabled',
  '--text-placeholder',
  '--text-inverse',
  '--accent-color',
  '--accent-color-hover',
  '--accent-active',
  '--accent-soft',
  '--accent-border',
  '--accent-contrast',
  '--accent-focus-ring',
  '--border',
  '--border-strong',
  '--border-faint',
  '--priority-high-text',
  '--priority-high-text-strong',
  '--priority-high-soft',
  '--priority-high-solid',
  '--priority-high-on-solid',
  '--priority-medium-text',
  '--priority-medium-soft',
  '--priority-medium-solid',
  '--priority-medium-on-solid',
  '--priority-low-text',
  '--priority-low-soft',
  '--priority-low-solid',
  '--priority-low-on-solid',
  '--control-bg',
  '--control-bg-hover',
  '--control-bg-active',
  '--control-bg-disabled',
  '--control-border',
  '--control-border-focus',
  '--focus-ring',
  '--focus-ring-offset',
  '--selection-bg',
  '--selection-text',
  '--table-bg',
  '--table-stripe',
  '--table-hover',
  '--table-selected',
  '--table-header-bg',
  '--table-header-text',
  '--table-border',
  '--table-totals-bg',
  '--table-sticky-bg',
  '--pos-line',
  '--pos-totals-bg',
  '--pos-key-bg',
  '--pos-key-accent',
  '--pos-total-accent',
  '--danger-solid-strong',
];

describe('plan/09 token sheet (packages/ui/src/styles/tokens.css)', () => {
  it('keeps brand hexes as primitives (--pr-*) in every theme', () => {
    expect(definedIn(light, '--pr-bg-0')).toBe(true);
    expect(definedIn(light, '--pr-accent')).toBe(true);
    expect(definedIn(dark, '--pr-bg-0')).toBe(true);
    expect(definedIn(dark, '--pr-accent')).toBe(true);
  });

  it('defines every required bookmarkX semantic token in the light (:root) theme', () => {
    for (const name of requiredSemanticTokens) {
      expect(definedIn(light, name), `missing ${name} in :root`).toBe(true);
    }
  });

  it('defines every required semantic token in the dark ([data-theme="dark"]) theme', () => {
    for (const name of requiredSemanticTokens) {
      expect(definedIn(dark, name), `missing ${name} in [data-theme="dark"]`).toBe(true);
    }
  });

  it('is light-primary: light values live in :root and the dark override is additive', () => {
    expect(definedIn(light, '--background-primary')).toBe(true);
    expect(definedIn(dark, '--background-primary')).toBe(true);
    const lightPrimary = light.match(/--background-primary\s*:\s*([^;]+);/)?.[1]?.trim();
    const darkPrimary = dark.match(/--background-primary\s*:\s*([^;]+);/)?.[1]?.trim();
    expect(lightPrimary).toBe('255 255 255');
    expect(darkPrimary).toBe('30 30 30');
  });

  it('exposes the plan/09 sheet aliases (--color-*) that extend the bookmarkX base', () => {
    for (const alias of [
      '--color-bg-app',
      '--color-text-primary',
      '--color-accent',
      '--color-table-stripe',
    ]) {
      expect(definedIn(light, alias), `missing alias ${alias}`).toBe(true);
    }
  });

  it('defines the shared scales used by components', () => {
    for (const scale of [
      '--space-xs',
      '--space-3xl',
      '--radius-xs',
      '--radius-full',
      '--shadow-xs',
      '--shadow-xl',
      '--z-base',
      '--z-toast',
      '--dur-fast',
      '--ease-std',
      '--density-row-sm',
      '--touch-target',
      '--pt-font-sans',
      '--pt-font-display',
      '--pt-font-body',
      '--pt-font-mono',
    ]) {
      expect(definedIn(light, scale), `missing scale ${scale}`).toBe(true);
    }
  });
});
