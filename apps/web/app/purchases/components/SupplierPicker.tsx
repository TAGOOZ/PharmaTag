'use client';

import type { Party } from '@/lib/api';

interface Props {
  parties: Party[] | null;
  partiesError: string | null;
  value: string;
  onChange: (v: string) => void;
}

export function SupplierPicker({ parties, partiesError, value, onChange }: Props) {
  return (
    <div className="flex flex-col gap-1">
      <p className="pt-caption">المورد</p>
      {parties === null ? (
        <p className="pt-caption">جارٍ تحميل الموردين…</p>
      ) : parties.length === 0 ? (
        <p className="pt-caption">لا يوجد موردين — أضف مورداً من إدارة الأطراف أولاً</p>
      ) : (
        <select
          aria-label="المورد"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="rounded-md border border-border bg-transparent px-3 py-2 text-sm"
        >
          <option value="">اختر المورد</option>
          {parties.map((p) => (
            <option key={p.id} value={String(p.id)}>
              {p.name_ar || p.namee} — {p.namee}
            </option>
          ))}
        </select>
      )}
      {partiesError && <p className="pt-caption text-red-600">{partiesError}</p>}
    </div>
  );
}
