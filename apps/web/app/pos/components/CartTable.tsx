'use client';

import { formatMoney } from '@pharmatag/ui';
import type { PriceLevel } from '@/lib/api';
import type { CartItem } from '../hooks/usePosCart';

const PRICE_LEVEL_LABELS: Record<PriceLevel, string> = {
  public: 'جمهور',
  wholesale: 'جملة',
  cost: 'تكلفة',
};

interface CartTableProps {
  cart: CartItem[];
  onUpdate: (key: string, patch: Partial<CartItem>) => void;
  onRemove: (key: string) => void;
}

export function CartTable({ cart, onUpdate, onRemove }: CartTableProps) {
  if (cart.length === 0) {
    return <p className="pt-caption">العربة فارغة — ابحث وأضف أدوية</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-start text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="pt-caption px-3 py-2 text-start">الدواء</th>
            <th className="pt-caption px-3 py-2 text-start">الكمية</th>
            <th className="pt-caption px-3 py-2 text-start">التسعير</th>
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
                <select
                  aria-label={`مستوى السعر للصنف ${item.drug.drugname}`}
                  value={item.price_level}
                  onChange={(e) =>
                    onUpdate(item.key, { price_level: e.target.value as PriceLevel })
                  }
                  className="rounded border border-border bg-transparent px-2 py-1"
                >
                  <option value="public">
                    {PRICE_LEVEL_LABELS.public} — {formatMoney(Number(item.drug.price))}
                  </option>
                  <option value="wholesale">
                    {PRICE_LEVEL_LABELS.wholesale} —{' '}
                    {formatMoney(Number(item.drug.price_wholesale ?? item.drug.price))}
                  </option>
                  <option value="cost">
                    {PRICE_LEVEL_LABELS.cost} —{' '}
                    {formatMoney(Number(item.drug.price_cost ?? item.drug.price))}
                  </option>
                </select>
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
