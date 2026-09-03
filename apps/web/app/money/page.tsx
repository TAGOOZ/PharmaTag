'use client';

import { StatusChip } from '@pharmatag/ui';
import { useCallback, useEffect, useState } from 'react';
import { Shell } from '@/components/shell';
import { clearToken, loadToken } from '@/lib/api';
import DayCloseTab from './components/DayCloseTab';
import DrawerTab from './components/DrawerTab';
import JournalsTab from './components/JournalsTab';
import MizanTab from './components/MizanTab';
import MonthsTab from './components/MonthsTab';
import StatementsTab from './components/StatementsTab';

type ViewState = 'boot' | 'login' | 'ready';
type Tab = 'drawer' | 'dayclose' | 'journals' | 'statements' | 'mizan' | 'months';

const TABS: { key: Tab; label: string }[] = [
  { key: 'drawer', label: 'الدرج' },
  { key: 'dayclose', label: 'تقفيل اليوم' },
  { key: 'journals', label: 'القيود' },
  { key: 'statements', label: 'كشوفات' },
  { key: 'mizan', label: 'ميزان' },
  { key: 'months', label: 'شهور' },
];

export default function MoneyPage() {
  const [view, setView] = useState<ViewState>('boot');
  const [tab, setTab] = useState<Tab>('drawer');
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const t = loadToken();
    if (!t) {
      setView('login');
      return;
    }
    setToken(t);
    setView('ready');
  }, []);

  const handleAuthFail = useCallback(() => {
    clearToken();
    setToken(null);
    setView('login');
  }, []);

  function handleLogout() {
    clearToken();
    setToken(null);
    setView('login');
  }

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'pharmatag:token' && !e.newValue) handleAuthFail();
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [handleAuthFail]);

  if (view === 'boot') {
    return (
      <Shell>
        <section dir="rtl" className="flex flex-col gap-3">
          <h1 className="pt-title text-2xl">المال</h1>
          <p className="pt-caption" role="status" aria-live="polite">
            جارٍ التحميل…
          </p>
        </section>
      </Shell>
    );
  }

  if (view === 'login') {
    return (
      <Shell>
        <section className="flex h-full flex-col items-start gap-3" dir="rtl">
          <h1 className="pt-title text-2xl">المال</h1>
          <p className="pt-caption">سجّل الدخول أولاً من شاشة الأدوية لعرض المال.</p>
          <a href="/drugs" className="pt-caption text-[var(--accent-color)] underline">
            الذهاب للأدوية
          </a>
        </section>
      </Shell>
    );
  }

  return (
    <Shell>
      <section className="flex h-full flex-col gap-4" dir="rtl">
        <div className="flex items-center gap-3">
          <h1 className="pt-title text-2xl">المال</h1>
          <StatusChip kind="online" labelAr="الخادم متصل" labelEn="API online" />
          <button
            type="button"
            className="ms-auto pt-caption cursor-pointer rounded-md border border-border px-3 py-1"
            onClick={handleLogout}
          >
            تسجيل الخروج
          </button>
        </div>

        <div
          className="flex flex-wrap gap-2 border-b border-border pb-2"
          role="tablist"
          aria-label="أقسام المال"
          onKeyDown={(e) => {
            // RTL bar: ArrowLeft advances, ArrowRight goes back.
            if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
            e.preventDefault();
            const idx = TABS.findIndex((t) => t.key === tab);
            const delta = e.key === 'ArrowLeft' ? 1 : -1;
            const next = TABS[(idx + delta + TABS.length) % TABS.length];
            if (next) setTab(next.key);
          }}
        >
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              id={`money-tab-${t.key}`}
              aria-selected={tab === t.key}
              aria-controls="money-panel"
              tabIndex={tab === t.key ? 0 : -1}
              onClick={() => setTab(t.key)}
              className={
                'rounded px-3 py-1.5 text-sm ' +
                (tab === t.key ? 'bg-[var(--accent-color)] text-white' : 'border border-border')
              }
            >
              {t.label}
            </button>
          ))}
        </div>

        {token && (
          <div id="money-panel" role="tabpanel" aria-label="قسم المال الحالي">
            {tab === 'drawer' ? (
              <DrawerTab token={token} onAuthFail={handleAuthFail} />
            ) : tab === 'dayclose' ? (
              <DayCloseTab token={token} onAuthFail={handleAuthFail} />
            ) : tab === 'journals' ? (
              <JournalsTab token={token} onAuthFail={handleAuthFail} />
            ) : tab === 'statements' ? (
              <StatementsTab token={token} onAuthFail={handleAuthFail} />
            ) : tab === 'mizan' ? (
              <MizanTab token={token} onAuthFail={handleAuthFail} />
            ) : (
              <MonthsTab token={token} onAuthFail={handleAuthFail} />
            )}
          </div>
        )}
      </section>
    </Shell>
  );
}
