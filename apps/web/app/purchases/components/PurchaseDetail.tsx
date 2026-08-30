'use client';

import type { PurchaseOut } from '@/lib/api';

interface Props {
  selectedId: number | null;
  selectedPurchase: PurchaseOut | null;
  detailLoading: boolean;
  detailError: string | null;
  returnQty: Record<number, string>;
  onReturnQtyChange: (lineId: number, value: string) => void;
  returning: boolean;
  returnError: string | null;
  returnResult: PurchaseOut | null;
  onReturn: () => void;
}

export function PurchaseDetail({
  selectedId,
  selectedPurchase,
  detailLoading,
  detailError,
  returnQty,
  onReturnQtyChange,
  returning,
  returnError,
  returnResult,
  onReturn,
}: Props) {
  if (selectedId === null)
    return (
      <div className="pt-card">
        <p className="pt-caption">اختر فاتورة أولاً لعرض تفاصيلها</p>
      </div>
    );
  return (
    <div className="pt-card flex flex-col gap-3">
      <h3 className="pt-title text-base">تفاصيل فاتورة الشراء</h3>
      {detailLoading && <p className="pt-caption">جارٍ التحميل…</p>}
      {detailError && (
        <p role="alert" className="pt-caption text-red-600">
          {detailError}
        </p>
      )}
      {selectedPurchase && (
        <>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex gap-1">
              <dt className="pt-caption">رقم الفاتورة:</dt>
              <dd className="pt-mono">{selectedPurchase.invoice_no}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">التاريخ:</dt>
              <dd>{selectedPurchase.datee}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">المورد:</dt>
              <dd>{selectedPurchase.party_id ?? '—'}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الإجمالي:</dt>
              <dd>{selectedPurchase.totalvalue}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">المدفوع:</dt>
              <dd>{selectedPurchase.payed}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الآجل:</dt>
              <dd>{selectedPurchase.agel}</dd>
            </div>
          </dl>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-start text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="pt-caption px-2 py-1 text-start">الدواء</th>
                  <th className="pt-caption px-2 py-1 text-start">الكمية</th>
                  <th className="pt-caption px-2 py-1 text-start">سعر الشراء</th>
                  <th className="pt-caption px-2 py-1 text-start">تاريخ الانتهاء</th>
                  <th className="pt-caption px-2 py-1 text-start">الإجمالي</th>
                </tr>
              </thead>
              <tbody>
                {selectedPurchase.lines.map((line) => (
                  <tr key={line.id} className="border-b border-border h-7">
                    <td className="px-2 py-1">{line.drugnamear || line.drugname}</td>
                    <td className="px-2 py-1">{line.qty}</td>
                    <td className="px-2 py-1">{line.cost}</td>
                    <td className="px-2 py-1">{line.expire ?? '—'}</td>
                    <td className="px-2 py-1">{line.line_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-1 text-xs">
            <span className="pt-caption">طرق الدفع:</span>
            <span>
              {selectedPurchase.payments.map((p) => `${p.method}:${p.amount}`).join(' · ') || '—'}
            </span>
          </div>
          {selectedPurchase.journal && (
            <p className="pt-caption text-xs">
              القيد #{selectedPurchase.journal.entry_no} —{' '}
              {selectedPurchase.journal.balanced ? 'متوازن' : 'غير متوازن'} — مدين{' '}
              {selectedPurchase.journal.debit_total} / دائن {selectedPurchase.journal.credit_total}
            </p>
          )}
          <div className="flex flex-col gap-2 border-t border-border pt-3">
            <h4 className="pt-caption font-bold">إرجاع أصناف من هذه الفاتورة</h4>
            {selectedPurchase.lines.length === 0 ? (
              <p className="pt-caption">لا توجد أسطر قابلة للإرجاع — فاتورة بلا أصناف</p>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-start text-xs">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="pt-caption px-2 py-1 text-start">الدواء</th>
                        <th className="pt-caption px-2 py-1 text-start">الكمية الأصلية</th>
                        <th className="pt-caption px-2 py-1 text-start">كمية الإرجاع</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedPurchase.lines.map((line) => (
                        <tr key={line.id} className="border-b border-border h-7">
                          <td className="px-2 py-1">{line.drugnamear || line.drugname}</td>
                          <td className="px-2 py-1">{line.qty}</td>
                          <td className="px-2 py-1">
                            <input
                              aria-label={`كمية إرجاع للسطر ${line.drugnamear || line.drugname}`}
                              type="text"
                              inputMode="decimal"
                              placeholder="0"
                              value={returnQty[line.id] ?? ''}
                              onChange={(e) => onReturnQtyChange(line.id, e.target.value)}
                              className="w-20 rounded border border-border px-2 py-1"
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {returnError && (
                  <p role="alert" className="pt-caption text-red-600">
                    {returnError}
                  </p>
                )}
                <button
                  type="button"
                  onClick={onReturn}
                  disabled={returning}
                  className="w-fit rounded bg-[var(--accent-color)] px-4 py-1.5 text-xs text-white disabled:opacity-50"
                >
                  {returning ? 'جارٍ الإرجاع…' : 'إرجاع الكمية المحددة'}
                </button>
                {returnResult && (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3 dark:bg-amber-950/30">
                    <p className="pt-caption font-bold text-amber-700">
                      تم إنشاء مرتجع شراء #{returnResult.invoice_no} — تتبع للأصل #
                      {selectedPurchase.invoice_no}
                    </p>
                    <p className="pt-caption text-xs">
                      الإجمالي المرتجع {returnResult.totalvalue} — المدفوع {returnResult.payed} —
                      الآجل {returnResult.agel}
                    </p>
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}
      {!detailLoading && !detailError && !selectedPurchase && (
        <p className="pt-caption">جارٍ تحميل تفاصيل الفاتورة…</p>
      )}
    </div>
  );
}
