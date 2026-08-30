'use client';

import type { PurchaseSummary } from '@/lib/api';

interface Props {
  purchases: PurchaseSummary[] | null;
  purchasesError: string | null;
  purchasesSearch: string;
  onPurchasesSearchChange: (v: string) => void;
  selectedId: number | null;
  onOpenDetail: (id: number) => void;
  onRefresh: () => void;
}

export function PurchasesList({
  purchases,
  purchasesError,
  purchasesSearch,
  onPurchasesSearchChange,
  onOpenDetail,
  onRefresh,
}: Props) {
  const filtered =
    purchases && purchasesSearch.trim()
      ? purchases.filter((p) => p.invoice_no.includes(purchasesSearch.trim()))
      : purchases;
  return (
    <div className="pt-card flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="pt-title text-lg">المشتريات الحديثة</h2>
        <button
          type="button"
          onClick={onRefresh}
          className="ms-auto rounded border border-border px-3 py-1 text-xs"
        >
          تحديث
        </button>
      </div>
      <input
        aria-label="بحث فاتورة"
        placeholder="بحث برقم الفاتورة"
        value={purchasesSearch}
        onChange={(e) => onPurchasesSearchChange(e.target.value)}
        className="w-full rounded-md border border-border px-3 py-2 text-sm"
      />
      {purchasesError && <p className="pt-caption text-red-600">{purchasesError}</p>}
      {purchases === null ? (
        <p className="pt-caption">جارٍ التحميل…</p>
      ) : purchases.length === 0 ? (
        <p className="pt-caption">لا توجد مشتريات بعد</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-start text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="pt-caption px-3 py-2 text-start">رقم الفاتورة</th>
                  <th className="pt-caption px-3 py-2 text-start">التاريخ</th>
                  <th className="pt-caption px-3 py-2 text-start">الإجمالي</th>
                  <th className="pt-caption px-3 py-2 text-start">إجراء</th>
                </tr>
              </thead>
              <tbody>
                {(filtered ?? []).map((p) => (
                  <tr key={p.id} className="border-b border-border h-7">
                    <td className="pt-mono px-3 py-1">{p.invoice_no}</td>
                    <td className="px-3 py-1">{p.datee}</td>
                    <td className="px-3 py-1">{p.totalvalue}</td>
                    <td className="px-3 py-1">
                      <button
                        type="button"
                        onClick={() => onOpenDetail(p.id)}
                        className="rounded border border-border px-2 py-1 text-xs"
                      >
                        عرض
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered && filtered.length !== purchases.length && (
            <p className="pt-caption text-xs text-muted">
              عرض {filtered.length} من {purchases.length}
            </p>
          )}
          {purchases.length >= 100 && <p className="pt-caption text-xs text-muted">عرض أحدث 100</p>}
        </>
      )}
    </div>
  );
}
