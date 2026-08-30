'use client';

import type { SaleSummary } from '@/lib/api';

interface SalesListProps {
  sales: SaleSummary[] | null;
  salesError: string | null;
  salesSearch: string;
  onSalesSearchChange: (v: string) => void;
  selectedId: number | null;
  onOpenDetail: (id: number) => void;
  onRefresh: () => void;
}

export function SalesList({
  sales,
  salesError,
  salesSearch,
  onSalesSearchChange,
  selectedId,
  onOpenDetail,
  onRefresh,
}: SalesListProps) {
  const filteredSales =
    sales && salesSearch.trim()
      ? sales.filter((s) => s.invoice_no.includes(salesSearch.trim()))
      : sales;

  return (
    <div className="pt-card flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="pt-title text-lg">المبيعات الحديثة</h2>
        <button
          type="button"
          onClick={onRefresh}
          className="ms-auto rounded border border-border px-3 py-1 text-xs"
        >
          تحديث
        </button>
      </div>
      <input
        placeholder="بحث برقم الفاتورة"
        value={salesSearch}
        onChange={(e) => onSalesSearchChange(e.target.value)}
        className="rounded border border-border px-2 py-1 text-sm"
        aria-label="بحث برقم الفاتورة"
      />
      {sales === null && !salesError && <p className="pt-caption">جارٍ التحميل…</p>}
      {sales !== null && sales.length === 0 && <p className="pt-caption">لا توجد مبيعات بعد</p>}
      {salesError && <p className="pt-caption text-red-600">{salesError}</p>}
      {filteredSales &&
        filteredSales.length === 0 &&
        sales &&
        sales.length > 0 &&
        salesSearch.trim() && <p className="pt-caption">لا توجد نتائج للبحث برقم الفاتورة</p>}
      {filteredSales !== null && filteredSales.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-start text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="pt-caption px-3 py-2 text-start">رقم الفاتورة</th>
                  <th className="pt-caption px-3 py-2 text-start">التاريخ</th>
                  <th className="pt-caption px-3 py-2 text-start">الإجمالي</th>
                  <th className="pt-caption px-3 py-2 text-start">الحالة</th>
                  <th className="pt-caption px-3 py-2 text-start">عرض</th>
                </tr>
              </thead>
              <tbody>
                {filteredSales.map((s) => (
                  <tr
                    key={s.id}
                    className={`border-b border-border h-7 ${selectedId === s.id ? 'bg-[var(--background-secondary)]' : ''}`}
                  >
                    <td className="pt-mono px-3 py-1">{s.invoice_no}</td>
                    <td className="px-3 py-1 text-xs">{s.datee}</td>
                    <td className="pt-mono px-3 py-1">{s.totalvalue}</td>
                    <td className="px-3 py-1 text-xs">{s.status}</td>
                    <td className="px-3 py-1">
                      <button
                        type="button"
                        onClick={() => onOpenDetail(s.id)}
                        className="rounded bg-surface-elevated px-3 py-1 text-xs"
                      >
                        عرض
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {sales && sales.length >= 100 && (
            <p className="pt-caption text-xs">عرض أحدث 100 فاتورة — الأقدم يتطلب البحث</p>
          )}
        </>
      )}
    </div>
  );
}
