import { describe, expect, it } from 'vitest';
import {
  createThemeStorage,
  DEFAULT_THEME_SETTING,
  normalizeThemeSetting,
  resolveTheme,
} from './theme-core';

describe('theme resolution (plan/09 §4.2: light default, system|light|dark)', () => {
  it('resolves explicit light to light regardless of system preference', () => {
    expect(resolveTheme('light', true)).toBe('light');
    expect(resolveTheme('light', false)).toBe('light');
  });

  it('resolves explicit dark to dark regardless of system preference', () => {
    expect(resolveTheme('dark', true)).toBe('dark');
    expect(resolveTheme('dark', false)).toBe('dark');
  });

  it('follows the system preference when the setting is system', () => {
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
  });

  it('defaults to light when no explicit setting is stored (P02 brand default)', () => {
    expect(DEFAULT_THEME_SETTING).toBe('light');
  });

  it('normalizes unknown stored values back to the light default', () => {
    expect(normalizeThemeSetting('seafoam')).toBe('light');
    expect(normalizeThemeSetting(null)).toBe('light');
    expect(normalizeThemeSetting(undefined)).toBe('light');
    expect(normalizeThemeSetting('dark')).toBe('dark');
    expect(normalizeThemeSetting('system')).toBe('system');
  });
});

describe('theme storage (persisted under pharmatag:theme)', () => {
  function memoryStore() {
    const values = new Map<string, string>();
    return {
      store: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => {
          values.set(key, value);
        },
      },
      values,
    };
  }

  it('returns null when nothing has been persisted yet', () => {
    const { store } = memoryStore();
    expect(createThemeStorage(store).read()).toBeNull();
  });

  it('persists the chosen setting', () => {
    const { store, values } = memoryStore();
    const storage = createThemeStorage(store);
    storage.write('dark');
    expect(values.get('pharmatag:theme')).toBe('dark');
    expect(storage.read()).toBe('dark');
  });

  it('normalizes a corrupted persisted value to the light default', () => {
    const { store } = memoryStore();
    store.setItem('pharmatag:theme', 'rainbow');
    expect(createThemeStorage(store).read()).toBe('light');
  });

  it('is a safe no-op when no storage is available (SSR / privacy mode)', () => {
    const storage = createThemeStorage(undefined);
    expect(storage.read()).toBeNull();
    expect(() => storage.write('dark')).not.toThrow();
  });
});
