'use client';

import dynamic from 'next/dynamic';
import { Shell } from '@/components/shell';

const TodaySummary = dynamic(
  () => import('@/components/today-summary').then((m) => m.TodaySummary),
  {
    ssr: false,
    loading: () => <div className="pt-caption">جارٍ تحميل الملخص…</div>,
  },
);

export default function DashboardPage() {
  return (
    <Shell>
      <section className="flex h-full flex-col gap-6">
        <h1 className="pt-title text-2xl">الرئيسية</h1>
        <div className="max-w-sm">
          <TodaySummary />
        </div>
      </section>
    </Shell>
  );
}
