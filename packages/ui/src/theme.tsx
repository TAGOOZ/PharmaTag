'use client';

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  applyTheme,
  createThemeStorage,
  DEFAULT_THEME_SETTING,
  type ResolvedTheme,
  resolveTheme,
  type ThemeSetting,
  type ThemeStorage,
} from './theme-core';

export {
  applyTheme,
  createThemeStorage,
  DEFAULT_THEME_SETTING,
  resolveTheme,
  THEME_STORAGE_KEY,
} from './theme-core';
export type { ResolvedTheme, ThemeProviderProps, ThemeSetting };

export interface ThemeContextValue {
  /** The user's chosen setting: system | light | dark. */
  setting: ThemeSetting;
  /** The resolved theme actually applied via data-theme (light or dark). */
  theme: ResolvedTheme;
  setSetting: (setting: ThemeSetting) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ThemeProviderProps {
  children: ReactNode;
  /** Injectable storage (localStorage on web; Tauri config adapter on desktop). */
  storage?: Pick<Storage, 'getItem' | 'setItem'>;
  initialSetting?: ThemeSetting;
}

/**
 * ThemeProvider — plan/09 §4.2. Light is the brand default (P02); the setting
 * is persisted under `pharmatag:theme`, resolved against the OS preference for
 * `system`, and applied as a pure CSS swap via `data-theme` on <html>.
 */
export function ThemeProvider({ children, storage, initialSetting }: ThemeProviderProps) {
  const store: ThemeStorage = useMemo(() => {
    const backing = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined);
    return createThemeStorage(backing);
  }, [storage]);
  const [setting, setSettingState] = useState<ThemeSetting>(
    () => store.read() ?? initialSetting ?? DEFAULT_THEME_SETTING,
  );
  const [systemPrefersDark, setSystemPrefersDark] = useState<boolean>(
    () =>
      typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches,
  );

  const theme = resolveTheme(setting, systemPrefersDark);

  useEffect(() => {
    applyTheme(document, theme);
  }, [theme]);

  useEffect(() => {
    if (setting !== 'system' || typeof window === 'undefined' || !window.matchMedia) return;
    const query = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (event: MediaQueryListEvent) => setSystemPrefersDark(event.matches);
    setSystemPrefersDark(query.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, [setting]);

  const setSetting = useCallback(
    (next: ThemeSetting) => {
      setSettingState(next);
      store.write(next);
    },
    [store],
  );

  const value = useMemo(() => ({ setting, theme, setSetting }), [setting, theme, setSetting]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a <ThemeProvider>');
  return ctx;
}

const THEME_OPTIONS: ReadonlyArray<{ value: ThemeSetting; labelAr: string; labelEn: string }> = [
  { value: 'system', labelAr: 'النظام', labelEn: 'System' },
  { value: 'light', labelAr: 'فاتح', labelEn: 'Light' },
  { value: 'dark', labelAr: 'داكن', labelEn: 'Dark' },
];

export interface ThemeToggleProps {
  /** Rendered alongside the toggle for accessibility (default: none). */
  'aria-label'?: string;
}

/** Three-state theme switch (plan/09 §4.2: system | light | dark). */
export function ThemeToggle({ 'aria-label': ariaLabel = 'مظهر الواجهة' }: ThemeToggleProps) {
  const { setting, setSetting } = useTheme();
  return (
    <fieldset className="pt-toggle">
      <legend className="pt-visually-hidden">{ariaLabel}</legend>
      {THEME_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`pt-toggle-button${setting === option.value ? ' pt-toggle-button--active' : ''}`}
          aria-pressed={setting === option.value}
          title={option.labelEn}
          onClick={() => setSetting(option.value)}
        >
          {option.labelAr}
        </button>
      ))}
    </fieldset>
  );
}
