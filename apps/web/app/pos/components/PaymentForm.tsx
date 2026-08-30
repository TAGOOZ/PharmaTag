'use client';

import type { SaleOut } from '@/lib/api';

interface PaymentFormProps {
  invoiceDisc: string;
  onInvoiceDiscChange: (v: string) => void;
  payCash: string;
  onPayCashChange: (v: string) => void;
  payCard: string;
  onPayCardChange: (v: string) => void;
  payCredit: string;
  onPayCreditChange: (v: string) => void;
  saving: boolean;
  saveError: string | null;
  salesError: string | null;
  saveResult: SaleOut | null;
  printError: string | null;
  cartLength: number;
  onSave: () => void;
  onPrint: (id: number, kind: 'print' | 'tax-document') => void;
}

export function PaymentForm({
  invoiceDisc,
  onInvoiceDiscChange,
  payCash,
  onPayCashChange,
  payCard,
  onPayCardChange,
  payCredit,
  onPayCreditChange,
  saving,
  saveError,
  salesError,
  saveResult,
  printError,
  cartLength,
  onSave,
  onPrint,
}: PaymentFormProps) {
  return (
    <>
      <div className="flex flex-wrap items-end gap-3 border-t border-border pt-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="pt-caption">خصم الفاتورة %</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="0"
            value={invoiceDisc}
            onChange={(e) => onInvoiceDiscChange(e.target.value)}
            className="w-24 rounded border border-border px-2 py-1"
          />
        </label>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="pt-caption">نقداً (cash)</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={payCash}
            onChange={(e) => onPayCashChange(e.target.value)}
            className="rounded border border-border px-2 py-1"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="pt-caption">شبكة (card)</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={payCard}
            onChange={(e) => onPayCardChange(e.target.value)}
            className="rounded border border-border px-2 py-1"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="pt-caption">آجل (credit)</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={payCredit}
            onChange={(e) => onPayCreditChange(e.target.value)}
            className="rounded border border-border px-2 py-1"
          />
        </label>
      </div>
      <p className="pt-caption text-xs text-muted">
        المدفوع (payed = نقداً + شبكة) + الآجل (agel = credit) يجب أن يطابق الإجمالي المحسوب على
        الخادم — الأرقام هنا بالجنيه.
      </p>

      {saveError && (
        <p role="alert" className="pt-caption text-red-600">
          {saveError}
        </p>
      )}
      {salesError && (
        <p role="status" className="pt-caption text-red-600">
          {salesError}
        </p>
      )}

      <button
        type="button"
        onClick={onSave}
        disabled={saving || cartLength === 0}
        className="pt-caption cursor-pointer rounded-md bg-[var(--accent-color)] px-4 py-2 text-white disabled:opacity-50"
      >
        {saving ? 'جارٍ الحفظ…' : 'حفظ الفاتورة'}
      </button>

      {saveResult && (
        <div className="rounded-md border border-green-200 bg-green-50 p-3 dark:bg-green-950/30">
          <p className="pt-caption font-bold text-green-700">
            تم حفظ الفاتورة #{saveResult.invoice_no} — الإجمالي {saveResult.totalvalue} جنيه
          </p>
          <dl className="mt-2 grid grid-cols-2 gap-1 text-sm">
            <div className="flex gap-1">
              <dt className="pt-caption">الإجمالي الفرعي:</dt>
              <dd>{saveResult.subtotal}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الخصم:</dt>
              <dd>{saveResult.discount}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الضريبة:</dt>
              <dd>{saveResult.vat}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الصافي:</dt>
              <dd>{saveResult.net}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">المدفوع:</dt>
              <dd>{saveResult.payed}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الآجل:</dt>
              <dd>{saveResult.agel}</dd>
            </div>
            <div className="flex gap-1">
              <dt className="pt-caption">الحالة:</dt>
              <dd>{saveResult.status}</dd>
            </div>
            {saveResult.journal && (
              <div className="flex gap-1">
                <dt className="pt-caption">القيد:</dt>
                <dd>
                  {saveResult.journal.balanced ? 'متوازن' : 'غير متوازن'} #
                  {saveResult.journal.entry_no} — مدين {saveResult.journal.debit_total} / دائن{' '}
                  {saveResult.journal.credit_total}
                </dd>
              </div>
            )}
          </dl>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onPrint(saveResult.id, 'print')}
              className="rounded border border-border px-3 py-1 text-xs"
            >
              طباعة الفاتورة (80مم)
            </button>
            <button
              type="button"
              onClick={() => onPrint(saveResult.id, 'tax-document')}
              className="rounded border border-border px-3 py-1 text-xs"
            >
              المستند الضريبي
            </button>
          </div>
        </div>
      )}

      {printError && <p className="pt-caption text-red-600">{printError}</p>}
    </>
  );
}
