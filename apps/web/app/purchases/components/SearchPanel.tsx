'use client';

import { formatMoney } from '@pharmatag/ui';
import type { Drug } from '@/lib/api';

interface Props {
  searchQuery: string;
  onSearchQueryChange: (v: string) => void;
  searching: boolean;
  searchCooldown?: number;
  searchError: string | null;
  searchResults: Drug[] | null;
  onSearch: () => void;
  onAdd: (drug: Drug) => void;
}

export function SearchPanel({
  searchQuery,
  onSearchQueryChange,
  searching,
  searchCooldown = 0,
  searchError,
  searchResults,
  onSearch,
  onAdd,
}: Props) {
  return (
    <div className="pt-card flex flex-col gap-3">
      <h2 className="pt-title text-lg">بحث الأصناف (باركود / اسم عربي-إنجليزي)</h2>
      <div className="flex gap-2">
        <input
          aria-label="ابحث بالباركود أو اسم الدواء"
          placeholder="ابحث بالباركود أو اسم الدواء (عربي/إنجليزي)"
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              onSearch();
            }
          }}
          className="flex-1 rounded-md border border-border px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={onSearch}
          disabled={searching || searchCooldown > 0}
          className="pt-caption cursor-pointer rounded-md bg-surface-elevated px-4 py-2 disabled:opacity-50"
        >
          {searching ? 'جارٍ…' : searchCooldown > 0 ? `حاول بعد ${searchCooldown}ث` : 'بحث'}
        </button>
      </div>
      {searchError && <p className="pt-caption text-red-600">{searchError}</p>}
      {searching && <p className="pt-caption">جارٍ البحث…</p>}
      {searchResults !== null && !searching && !searchError && searchResults.length === 0 && (
        <p className="pt-caption">لا توجد أدوية مطابقة للبحث</p>
      )}
      {searchResults !== null && searchResults.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-start text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="pt-caption px-3 py-2 text-start">الاسم العربي</th>
                <th className="pt-caption px-3 py-2 text-start">الاسم الإنجليزي</th>
                <th className="pt-caption px-3 py-2 text-start">السعر</th>
                <th className="pt-caption px-3 py-2 text-start">إجراء</th>
              </tr>
            </thead>
            <tbody>
              {searchResults.map((drug) => (
                <tr key={drug.id} className="border-b border-border h-7">
                  <td className="px-3 py-1">{drug.drugnamear || '—'}</td>
                  <td className="pt-mono px-3 py-1 text-muted">{drug.drugname}</td>
                  <td className="pt-mono px-3 py-1">{formatMoney(Number(drug.price))}</td>
                  <td className="px-3 py-1">
                    <button
                      type="button"
                      onClick={() => onAdd(drug)}
                      className="rounded bg-[var(--accent-color)] px-3 py-1 text-xs text-white"
                    >
                      إضافة
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {searchResults === null && !searchError && !searching && (
        <p className="pt-caption text-muted">أدخل باركود أو اسماً ثم اضغط بحث أو Enter</p>
      )}
    </div>
  );
}
