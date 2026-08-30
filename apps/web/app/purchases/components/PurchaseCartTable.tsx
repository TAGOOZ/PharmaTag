'use client';

import type { PurchaseCartItem } from '../hooks/usePurchaseCart';

interface Props {
  cart: PurchaseCartItem[];
  onUpdate: (key: string, patch: Partial<PurchaseCartItem>) => void;
  onRemove: (key: string) => void;
}

export function PurchaseCartTable({ cart, onUpdate, onRemove }: Props) {
  if (cart.length === 0) return <p className="pt-caption">العربة فارغة — ابحث وأضف أدوية</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-start text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="pt-caption px-3 py-2 text-start">الدواء</th>
            <th className="pt-caption px-3 py-2 text-start">الكمية</th>
            <th className="pt-caption px-3 py-2 text-start">سعر الشراء</th>
            <th className="pt-caption px-3 py-2 text-start">تاريخ الانتهاء</th>
            <th className="pt-caption px-3 py-2 text-start">خصم %</th>
            <th className="pt-caption px-3 py-2 text-start">إجراء</th>
          </tr>
        </thead>
        <tbody>
          {cart.map((item) => (
            <tr key={item.key} className="border-b border-border h-7">
              <td className="px-3 py-1">
                <div className="flex flex-col">
                  <span>{item.drug.drugnamear || item.drug.drugname}</span>
                  <span className="pt-mono text-xs text-muted">{item.drug.drugname}</span>
                </div>
              </td>
              <td className="px-3 py-1">
                <input
                  aria-label={`الكمية للصنف ${item.drug.drugnamear || item.drug.drugname}`}
                  type="text"
                  inputMode="decimal"
                  value={item.qty}
                  onChange={(e) => onUpdate(item.key, { qty: e.target.value })}
                  className="w-20 rounded border border-border px-2 py-1"
                />
              </td>
              <td className="px-3 py-1">
                <input
                  aria-label={`سعر الشراء للصنف ${item.drug.drugnamear || item.drug.drugname}`}
                  type="text"
                  inputMode="decimal"
                  placeholder="0.0000"
                  value={item.unit_cost}
                  onChange={(e) => onUpdate(item.key, { unit_cost: e.target.value })}
                  className="w-24 rounded border border-border px-2 py-1"
                />
              </td>
              <td className="px-3 py-1">
                <input
                  aria-label={`تاريخ الانتهاء للصنف ${item.drug.drugname}`}
                  type="date"
                  value={item.expire}
                  onChange={(e) => onUpdate(item.key, { expire: e.target.value })}
                  className="w-32 rounded border border-border px-2 py-1"
                />
              </td>
              <td className="px-3 py-1">
                <input
                  aria-label={`خصم للصنف ${item.drug.drugname}`}
                  type="text"
                  inputMode="decimal"
                  placeholder="0"
                  value={item.disc_percent}
                  onChange={(e) => onUpdate(item.key, { disc_percent: e.target.value })}
                  className="w-16 rounded border border-border px-2 py-1"
                />
              </td>
              <td className="px-3 py-1">
                <button
                  type="button"
                  onClick={() => onRemove(item.key)}
                  className="rounded border border-border px-2 py-1 text-xs"
                >
                  حذف
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
