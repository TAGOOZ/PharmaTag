'use client';

import { AppShell, MODULE_NAV, TagCrossMark, ThemeToggle } from '@pharmatag/ui';
import { usePathname, useRouter } from 'next/navigation';
import type { ReactNode } from 'react';

function activeFromPath(pathname: string): string {
  if (pathname === '/') return '/';
  return `/${pathname.split('/')[1]}`;
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <AppShell
      active={activeFromPath(pathname)}
      items={MODULE_NAV}
      onNavigate={(key) => router.push(key)}
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
            <ThemeToggle />
          </div>
        </>
      }
    >
      {children}
    </AppShell>
  );
}

export function PageStub({ title }: { title: string }) {
  return (
    <section className="flex h-full flex-col items-start gap-3">
      <h1 className="pt-title text-2xl">{title}</h1>
      <p className="pt-caption">هذه الشاشة تُبنى ضمن الشريحة المقابلة لها (Phase 1).</p>
    </section>
  );
}
