import type { ReactNode } from 'react';

/** Module rail navigation model (plan/03 §3.1). */
export interface NavItem {
  key: string;
  labelAr: string;
  labelEn: string;
  icon: ReactNode;
}

export interface AppShellProps {
  active: string;
  items: NavItem[];
  onNavigate: (key: string) => void;
  /** App-bar slot: wordmark, status chips, theme toggle, user menu. */
  header?: ReactNode;
  children: ReactNode;
}

/**
 * AppShell — app bar + module rail + workspace (plan/03 §3.1).
 * Presentational: receives nav as props and reports navigation via onNavigate.
 */
export function AppShell({ active, items, onNavigate, header, children }: AppShellProps) {
  return (
    <div className="pt-app-shell">
      {header ? <header className="pt-app-bar">{header}</header> : null}
      <div className="pt-app-body">
        <nav className="pt-rail" aria-label="الوحدات">
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`pt-rail-item${active === item.key ? ' pt-rail-item--active' : ''}`}
              aria-current={active === item.key ? 'page' : undefined}
              title={item.labelEn}
              onClick={() => onNavigate(item.key)}
            >
              {item.icon}
              <span>{item.labelAr}</span>
            </button>
          ))}
        </nav>
        <main className="pt-workspace">{children}</main>
      </div>
    </div>
  );
}
