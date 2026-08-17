'use client';

import { formatMoney, StatusChip } from '@pharmatag/ui';
import { useEffect, useState } from 'react';
import { Shell } from '@/components/shell';
import { type DrugListResponse, fetchDrugs, login } from '@/lib/api';

type PageState = 'loading' | 'ready' | 'error';

const SEED_USERNAME = 'admin';
const SEED_PASSWORD = 'changeme';

export default function DrugsPage() {
  const [state, setState] = useState<PageState>('loading');
  const [data, setData] = useState<DrugListResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    (async () => {
      try {
        const auth = await login(SEED_USERNAME, SEED_PASSWORD, controller.signal);
        const list = await fetchDrugs(auth.access_token, controller.signal);
        if (cancelled) return;
        setData(list);
        setState('ready');
      } catch {
        if (!cancelled) setState('error');
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  const chip =
    state === 'loading' ? (
      <StatusChip kind="offline" labelAr="جارٍ التحميل" labelEn="Loading" />
    ) : state === 'ready' ? (
      <StatusChip kind="online" labelAr="الخادم متصل" labelEn="API online" />
    ) : (
      <StatusChip kind="saved" labelAr="الخادم غير متاح" labelEn="API unavailable" />
    );

  return (
    <Shell>
      <section className="flex h-full flex-col gap-4">
        <div className="flex items-center gap-3">
          <h1 className="pt-title text-2xl">الأدوية</h1>
          {chip}
        </div>
        {state === 'error' ? (
          <p className="pt-caption">
            تعذّر جلب قائمة الأدوية من الخادم — تأكد من تشغيل الـ API على http://localhost:8000.
          </p>
        ) : data ? (
          <div className="pt-card">
            <p className="pt-caption mb-3">فرع: {data.branch.pharname} — قائمة الأدوية المفعلة</p>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-start">
                <thead>
                  <tr className="border-b border-border">
                    <th className="pt-caption px-3 py-2 text-start">الاسم العربي</th>
                    <th className="pt-caption px-3 py-2 text-start">الاسم الإنجليزي</th>
                    <th className="pt-caption px-3 py-2 text-start">السعر (EGP)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.drugs.map((drug) => (
                    <tr key={drug.id} className="border-b border-border">
                      <td className="px-3 py-2">{drug.drugnamear}</td>
                      <td className="pt-mono px-3 py-2 text-muted">{drug.drugname}</td>
                      <td className="pt-mono px-3 py-2">{formatMoney(Number(drug.price))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>
    </Shell>
  );
}
