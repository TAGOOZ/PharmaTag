'use client';

import type { SaleOut } from '@/lib/api';

interface SaleDetailProps {
  selectedId: number | null;
  selectedSale: SaleOut | null;
  detailLoading: boolean;
  detailError: string | null;
  printError: string | null;
  returnQty: Record<number, string>;
  onReturnQtyChange: (lineId: number, value: string) => void;
  returning: boolean;
  returnError: string | null;
  returnResult: SaleOut | null;
  onPrint: (id: number, kind: 'print' | 'tax-document') => void;
  onReturn: () => void;
}

export function SaleDetail({
  selectedId,
  selectedSale,
  detailLoading,
  detailError,
  printError,
  returnQty,
  onReturnQtyChange,
  returning,
  returnError,
  returnResult,
  onPrint,
  onReturn,
}: SaleDetailProps) {
  if (selectedId === null) {
    return (
      <div className="pt-card">
        <p className="pt-caption">اختر فاتورة أولاً لإرجاعها — اعرض فاتورة ثم حدد الكميات للإرجاع</p>
      </div>
    );
  }

  return (
    <div className="pt-card flex flex-col gap-3">
      <h3 className="pt-title text-base">تفاصيل الفاتورة</h3>
      {detailLoading && <p className="pt-caption">جارٍ التحميل…</p>}
      {detailError && (
        <p role="alert" className="pt-caption text-red-600">
          {detailError}
        </p>
      )}
      {selectedSale && (
        <>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex gap-1">
              <dt className="pt-caption">رقم الفاتورة:</dt>
              <dd className="pt-mono">{selectedSale.invoice_no}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">التاريخ:</dt>
              <dd>{selectedSale.datee}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الإجمالي:</dt>
              <dd>{selectedSale.totalvalue}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">المدفوع:</dt>
              <dd>{selectedSale.payed}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الآجل:</dt>
              <dd>{selectedSale.agel}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الضريبة:</dt>
              <dd>{selectedSale.vat}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الصافي:</dt>
              <dd>{selectedSale.net}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الحالة:</dt>
              <dd>{selectedSale.status}</dd>
            </div>
          </dl>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-start text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="pt-caption px-2 py-1 text-start">الدواء</th>
                  <th className="pt-caption px-2 py-1 text-start">الكمية</th>
                  <th className="pt-caption px-2 py-1 text-start">سعر الوحدة</th>
                  <th className="pt-caption px-2 py-1 text-start">الضريبة</th>
                  <th className="pt-caption px-2 py-1 text-start">الإجمالي</th>
                </tr>
              </thead>
              <tbody>
                {selectedSale.lines.map((line) => (
                  <tr key={line.id} className="border-b border-border h-7">
                    <td className="px-2 py-1">{line.drugnamear || line.drugname}</td>
                    <td className="px-2 py-1">{line.qty}</td>
                    <td className="px-2 py-1">{line.unit_price}</td>
                    <td className="px-2 py-1">{line.tax_type}</td>
                    <td className="px-2 py-1">{line.line_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-1 text-xs">
            <span className="pt-caption">طرق الدفع:</span>
            <span>
              {selectedSale.payments.map((p) => `${p.method}:${p.amount}`).join(' · ') || '—'}
            </span>
          </div>
          {selectedSale.journal && (
            <p className="pt-caption text-xs">
              القيد #{selectedSale.journal.entry_no} —{' '}
              {selectedSale.journal.balanced ? 'متوازن' : 'غير متوازن'} — مدين{' '}
              {selectedSale.journal.debit_total} / دائن {selectedSale.journal.credit_total}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onPrint(selectedSale.id, 'print')}
              className="rounded border border-border px-3 py-1 text-xs"
            >
              طباعة الفاتورة (80مم)
            </button>
            <button
              type="button"
              onClick={() => onPrint(selectedSale.id, 'tax-document')}
              className="rounded border border-border px-3 py-1 text-xs"
            >
              المستند الضريبي
            </button>
          </div>
          {printError && <p className="pt-caption text-red-600">{printError}</p>}

          {/* Return path */}
          <div className="flex flex-col gap-2 border-t border-border pt-3">
            <h4 className="pt-caption font-bold">إرجاع أصناف من هذه الفاتورة</h4>
            {selectedSale.lines.length === 0 ? (
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
                      {selectedSale.lines.map((line) => (
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
                      تم إنشاء فاتورة مرتجع #{returnResult.invoice_no} — تتبع للأصل #
                      {selectedSale.invoice_no}
                    </p>
                    <p className="pt-caption text-xs">
                      الإجمالي المرتجع {returnResult.totalvalue} — المدفوع {returnResult.payed} —
                      الآجل {returnResult.agel}
                    </p>
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        onClick={() => onPrint(returnResult.id, 'print')}
                        className="rounded border border-border px-3 py-1 text-xs"
                      >
                        طباعة المرتجع
                      </button>
                      <button
                        type="button"
                        onClick={() => onPrint(returnResult.id, 'tax-document')}
                        className="rounded border border-border px-3 py-1 text-xs"
                      >
                        مستند المرتجع الضريبي
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}
      {!detailLoading && !detailError && !selectedSale && (
        <p className="pt-caption">اختر فاتورة لعرض تفاصيلها</p>
      )}
    </div>
  );
}
