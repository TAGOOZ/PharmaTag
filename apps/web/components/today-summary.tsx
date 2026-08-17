'use client';

import { StatusChip } from '@pharmatag/ui';
import { useEffect, useState } from 'react';
import { fetchHealth } from '@/lib/api';

type ApiState = 'checking' | 'ok' | 'down';

export function TodaySummary() {
  const [state, setState] = useState<ApiState>('checking');

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then(() => setState('ok'))
      .catch(() => setState('down'));
    return () => controller.abort();
  }, []);

  return (
    <section className="pt-card flex flex-col gap-2">
      <h2 className="pt-title">ملخص اليوم</h2>
      <p className="pt-caption">بيانات اليوم تُحسب محلياً وتُصادق مع الخادم عند الاتصال.</p>
      {state === 'checking' ? (
        <StatusChip kind="offline" labelAr="جارٍ الفحص" labelEn="Checking API" />
      ) : state === 'ok' ? (
        <StatusChip kind="online" labelAr="الخادم متصل" labelEn="API online" />
      ) : (
        <StatusChip
          kind="saved"
          labelAr="الخادم غير متاح — العمل محلي"
          labelEn="API offline — working locally"
        />
      )}
    </section>
  );
}
