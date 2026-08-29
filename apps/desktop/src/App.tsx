import {
  AppShell,
  formatDate,
  MODULE_NAV,
  StatusChip,
  TagCrossMark,
  ThemeToggle,
} from '@pharmatag/ui';
import type Database from '@tauri-apps/plugin-sql';
import { useCallback, useEffect, useState } from 'react';
import { DrugsPage } from './DrugsPage';
import { initDb } from './db';
import { SyncConflictsPage } from './SyncConflictsPage';

type DbState = 'booting' | 'ready' | 'error';

function currentRoute(): string {
  const hash = window.location.hash.slice(1);
  return hash.startsWith('/') ? hash : '/';
}

function PageStub({ title }: { title: string }) {
  return (
    <section className="flex h-full flex-col items-start gap-3">
      <h1 className="pt-title text-2xl">{title}</h1>
      <p className="pt-caption">هذه الشاشة تُبنى ضمن الشريحة المقابلة لها (Phase 1).</p>
    </section>
  );
}

const HOME_STUB = { title: 'الرئيسية' };

const STUBS: Record<string, { title: string }> = {
  '/': HOME_STUB,
  '/drugs': { title: 'الادوية' },
  '/pos': { title: 'نقطة البيع' },
  '/purchases': { title: 'المشتريات' },
  '/stock': { title: 'المخزون' },
  '/money': { title: 'المال' },
  '/reports': { title: 'التقارير' },
  '/employees': { title: 'الموظفين' },
  '/settings': { title: 'الاعدادات' },
  '/sync/conflicts': { title: 'تعارضات المزامنة' },
};

export function App() {
  const [route, setRoute] = useState<string>(currentRoute);
  const [dbState, setDbState] = useState<DbState>('booting');
  const [db, setDb] = useState<Database | null>(null);

  useEffect(() => {
    const onHashChange = () => setRoute(currentRoute());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    initDb()
      .then((database) => {
        setDb(database);
        setDbState('ready');
      })
      .catch(() => setDbState('error'));
  }, []);

  const navigate = useCallback((key: string) => {
    window.location.hash = key;
  }, []);

  const stub = STUBS[route] ?? HOME_STUB;

  return (
    <AppShell
      active={route}
      items={MODULE_NAV}
      onNavigate={navigate}
      header={
        <>
          <div className="flex items-center gap-2">
            <TagCrossMark size={28} />
            <div className="flex flex-col leading-tight">
              <span className="pt-title">فارما تاج</span>
              <span className="pt-caption">PharmaTag</span>
            </div>
          </div>
          <div className="ms-auto flex items-center gap-3">
            <span className="pt-mono text-sm">{formatDate(new Date().toISOString())}</span>
            {dbState === 'booting' ? (
              <StatusChip kind="offline" labelAr="قيد التهيئة" labelEn="Initializing" />
            ) : dbState === 'ready' ? (
              <StatusChip kind="online" labelAr="محلي" labelEn="Local DB ready" />
            ) : (
              <StatusChip kind="unsaved" labelAr="خطأ قاعدة البيانات" labelEn="DB error" />
            )}
            <ThemeToggle />
          </div>
        </>
      }
    >
      {route === '/drugs' ? (
        <DrugsPage db={db} />
      ) : route === '/sync/conflicts' ? (
        <SyncConflictsPage db={db} />
      ) : (
        <PageStub title={stub.title} />
      )}
    </AppShell>
  );
}
