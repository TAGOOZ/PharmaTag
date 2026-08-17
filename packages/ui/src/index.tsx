import type { NavItem } from './components/AppShell';
import {
  BoxIcon,
  CartIcon,
  CashIcon,
  ChartIcon,
  CoinsIcon,
  GearIcon,
  HomeIcon,
  PillIcon,
  UsersIcon,
} from './components/icons';

export { AppShell, type AppShellProps, type NavItem } from './components/AppShell';
export { Badge, type BadgeProps, type BadgeTone } from './components/Badge';
export { Button, type ButtonProps, type ButtonVariant } from './components/Button';
export { Card, type CardProps } from './components/Card';
export {
  BoxIcon,
  CartIcon,
  CashIcon,
  ChartIcon,
  CoinsIcon,
  GearIcon,
  HomeIcon,
  PillIcon,
  TagCrossMark,
  UsersIcon,
} from './components/icons';
export { LanguageToggle, type LanguageToggleProps } from './components/LanguageToggle';
export { StatusChip, type StatusChipProps, type StatusKind } from './components/StatusChip';
export {
  applyLanguage,
  formatDate,
  formatMoney,
  formatNumber,
  getDir,
  isRTL,
  type LanguageTarget,
} from './rtl';
export {
  type ThemeContextValue,
  ThemeProvider,
  type ThemeProviderProps,
  ThemeToggle,
  useTheme,
} from './theme';
export { resolveBootTheme, THEME_BOOT_SCRIPT } from './theme-boot';
export {
  applyTheme,
  createThemeStorage,
  DEFAULT_THEME_SETTING,
  isThemeSetting,
  normalizeThemeSetting,
  type ResolvedTheme,
  resolveTheme,
  THEME_STORAGE_KEY,
  type ThemeSetting,
  type ThemeStorage,
  type ThemeTarget,
} from './theme-core';

/** Module rail (plan/03 §3.1) — the app-level navigation shared by web + desktop. */
export const MODULE_NAV: NavItem[] = [
  { key: '/', labelAr: 'الرئيسية', labelEn: 'Dashboard', icon: <HomeIcon /> },
  { key: '/drugs', labelAr: 'الادوية', labelEn: 'Drugs', icon: <PillIcon /> },
  { key: '/pos', labelAr: 'المبيعات', labelEn: 'Sales / POS', icon: <CashIcon /> },
  { key: '/purchases', labelAr: 'المشتريات', labelEn: 'Purchases', icon: <CartIcon /> },
  { key: '/stock', labelAr: 'المخزون', labelEn: 'Stock', icon: <BoxIcon /> },
  { key: '/money', labelAr: 'المال', labelEn: 'Money', icon: <CoinsIcon /> },
  { key: '/reports', labelAr: 'التقارير', labelEn: 'Reports', icon: <ChartIcon /> },
  { key: '/employees', labelAr: 'الموظفين', labelEn: 'Employees', icon: <UsersIcon /> },
  { key: '/settings', labelAr: 'الاعدادات', labelEn: 'Settings', icon: <GearIcon /> },
];
