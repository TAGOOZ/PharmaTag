'use client';

import type { PurchaseOut } from '@/lib/api';

interface Props {
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
  purchasesError: string | null;
  saveResult: PurchaseOut | null;
  onSave: () => void;
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
  purchasesError,
  saveResult,
  onSave,
}: Props) {
  return (
    <div className="flex flex-col gap-3">
      <label className="pt-caption flex flex-col gap-1">
        خصم الفاتورة %
        <input
          aria-label="خصم الفاتورة"
          type="text"
          inputMode="decimal"
          placeholder="0"
          value={invoiceDisc}
          onChange={(e) => onInvoiceDiscChange(e.target.value)}
          className="w-full rounded-md border border-border px-3 py-2 text-sm"
        />
      </label>
      <div className="grid grid-cols-3 gap-2">
        <label className="pt-caption flex flex-col gap-1">
          نقدي
          <input
            aria-label="المبلغ النقدي"
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={payCash}
            onChange={(e) => onPayCashChange(e.target.value)}
            className="rounded-md border border-border px-3 py-2"
          />
        </label>
        <label className="pt-caption flex flex-col gap-1">
          شبكة
          <input
            aria-label="مبلغ الشبكة"
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={payCard}
            onChange={(e) => onPayCardChange(e.target.value)}
            className="rounded-md border border-border px-3 py-2"
          />
        </label>
        <label className="pt-caption flex flex-col gap-1">
          آجل
          <input
            aria-label="مبلغ الآجل"
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={payCredit}
            onChange={(e) => onPayCreditChange(e.target.value)}
            className="rounded-md border border-border px-3 py-2"
          />
        </label>
      </div>
      {saveError && (
        <p role="alert" className="pt-caption text-red-600">
          {saveError}
        </p>
      )}
      {purchasesError && <p className="pt-caption text-red-600">{purchasesError}</p>}
      {saveResult && (
        <div className="rounded-md border border-green-200 bg-green-50 p-3 dark:bg-green-950/30">
          <p className="pt-caption font-bold text-green-700">
            تم حفظ فاتورة الشراء #{saveResult.invoice_no}
          </p>
          <p className="pt-caption text-xs">
            الإجمالي {saveResult.totalvalue} — المدفوع {saveResult.payed} — الآجل {saveResult.agel}
          </p>
          {saveResult.journal && (
            <p className="pt-caption text-xs">
              {saveResult.journal.balanced ? 'متوازن' : 'غير متوازن'} — مدين{' '}
              {saveResult.journal.debit_total} / دائن {saveResult.journal.credit_total}
            </p>
          )}
        </div>
      )}
      <button
        type="button"
        onClick={onSave}
        disabled={saving}
        className="pt-caption w-fit cursor-pointer rounded-md bg-[var(--accent-color)] px-4 py-2 text-white disabled:opacity-50"
      >
        {saving ? 'جارٍ الحفظ…' : 'حفظ فاتورة الشراء'}
      </button>
    </div>
  );
}
