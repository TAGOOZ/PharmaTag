import { formatMoney, StatusChip } from '@pharmatag/ui';
import type Database from '@tauri-apps/plugin-sql';
import { useEffect, useState } from 'react';
import { type DrugRow, listDrugs } from './drugs';

type PageState = 'loading' | 'ready' | 'error';

/**
 * Drugs screen (ticket #6 / S0.3) — reads the drug master OFFLINE from the
 * local SQLite twin (never the API). Same seed catalog as the API returns.
 */
export function DrugsPage({ db }: { db: Database | null }) {
  const [state, setState] = useState<PageState>('loading');
  const [drugs, setDrugs] = useState<DrugRow[]>([]);

  useEffect(() => {
    if (!db) return;
    let cancelled = false;
    listDrugs(db)
      .then((rows) => {
        if (cancelled) return;
        setDrugs(rows);
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [db]);

  const chip =
    state === 'loading' ? (
      <StatusChip kind="offline" labelAr="جارٍ التحميل" labelEn="Loading" />
    ) : state === 'ready' ? (
      <StatusChip kind="online" labelAr="محلي" labelEn="Offline SQLite" />
    ) : (
      <StatusChip kind="saved" labelAr="خطأ القراءة" labelEn="Read error" />
    );

  return (
    <section className="flex h-full flex-col gap-4">
      <div className="flex items-center gap-3">
        <h1 className="pt-title text-2xl">الأدوية</h1>
        {chip}
      </div>
      {state === 'error' ? (
        <p className="pt-caption">تعذّرت قراءة قائمة الأدوية من قاعدة البيانات المحلية.</p>
      ) : (
        <div className="pt-card">
          <p className="pt-caption mb-3">قائمة الأدوية المفعلة (من SQLite المحلي — بدون اتصال)</p>
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
                {drugs.map((drug) => (
                  <tr key={drug.id} className="border-b border-border">
                    <td className="px-3 py-2">{drug.drugnamear}</td>
                    <td className="pt-mono px-3 py-2 text-muted">{drug.drugname}</td>
                    <td className="pt-mono px-3 py-2">{formatMoney(drug.price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
