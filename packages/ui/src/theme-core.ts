/**
 * Theme core — pure, testable logic for the plan/09 theme switch.
 *
 * Brand default is LIGHT on both platforms (P02); `system | light | dark`
 * setting is persisted under `pharmatag:theme` and applied as a pure CSS
 * swap via `data-theme` on <html> (no re-render, plan/09 D5).
 */
export type ThemeSetting = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'pharmatag:theme';
export const DEFAULT_THEME_SETTING: ThemeSetting = 'light';

export function isThemeSetting(value: unknown): value is ThemeSetting {
  return value === 'system' || value === 'light' || value === 'dark';
}

export function normalizeThemeSetting(value: unknown): ThemeSetting {
  return isThemeSetting(value) ? value : DEFAULT_THEME_SETTING;
}

export function resolveTheme(setting: ThemeSetting, systemPrefersDark: boolean): ResolvedTheme {
  if (setting === 'dark') return 'dark';
  if (setting === 'light') return 'light';
  return systemPrefersDark ? 'dark' : 'light';
}

export interface ThemeTarget {
  documentElement: { dataset: Record<string, string | undefined> };
}

export function applyTheme(target: ThemeTarget, theme: ResolvedTheme): void {
  target.documentElement.dataset.theme = theme;
}

export interface ThemeStorage {
  read(): ThemeSetting | null;
  write(setting: ThemeSetting): void;
}

type KeyValueStore = Pick<Storage, 'getItem' | 'setItem'>;

export function createThemeStorage(store?: KeyValueStore): ThemeStorage {
  return {
    read() {
      if (!store) return null;
      try {
        const raw = store.getItem(THEME_STORAGE_KEY);
        return raw === null ? null : normalizeThemeSetting(raw);
      } catch {
        return null;
      }
    },
    write(setting: ThemeSetting) {
      if (!store) return;
      try {
        store.setItem(THEME_STORAGE_KEY, setting);
      } catch {
        // privacy mode / quota — the theme still applies for this session
      }
    },
  };
}
