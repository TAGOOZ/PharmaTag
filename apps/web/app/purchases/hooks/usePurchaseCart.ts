'use client';

import { useEffect, useRef, useState } from 'react';
import type { Drug } from '@/lib/api';
import { addDecimal, isQtyValid, normalizeDecimal } from '@/lib/posMoney';

export interface PurchaseCartItem {
  key: string;
  drug: Drug;
  qty: string;
  unit_cost: string;
  expire: string;
  disc_percent: string;
}

export const PURCHASE_CART_KEY = 'pharmatag:purchases:cart';

export function usePurchaseCart() {
  const [cart, setCartState] = useState<PurchaseCartItem[]>([]);
  const cartRef = useRef<PurchaseCartItem[]>([]);
  // keep ref synced on render
  cartRef.current = cart;

  function setCart(
    update: PurchaseCartItem[] | ((prev: PurchaseCartItem[]) => PurchaseCartItem[]),
  ) {
    if (typeof update === 'function') {
      const fn = update as (prev: PurchaseCartItem[]) => PurchaseCartItem[];
      const next = fn(cartRef.current);
      cartRef.current = next;
      setCartState(next);
    } else {
      cartRef.current = update;
      setCartState(update);
    }
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: setCart stable wrapper
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PURCHASE_CART_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as unknown;
        if (Array.isArray(parsed) && parsed.length) {
          const valid = (parsed as PurchaseCartItem[]).filter(
            (it) =>
              it &&
              typeof it.key === 'string' &&
              it.drug &&
              typeof it.drug.id === 'number' &&
              typeof it.qty === 'string' &&
              typeof it.unit_cost === 'string',
          );
          if (valid.length) setCart(valid);
          else window.localStorage.removeItem(PURCHASE_CART_KEY);
        }
      }
    } catch {
      try {
        window.localStorage.removeItem(PURCHASE_CART_KEY);
      } catch {}
    }
  }, []);

  useEffect(() => {
    try {
      if (cart.length) window.localStorage.setItem(PURCHASE_CART_KEY, JSON.stringify(cart));
      else window.localStorage.removeItem(PURCHASE_CART_KEY);
    } catch {}
  }, [cart]);

  // sync across tabs — avoid clobber when same cart edited in another tab
  // biome-ignore lint/correctness/useExhaustiveDependencies: setCart stable wrapper
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key !== PURCHASE_CART_KEY) return;
      try {
        const raw = e.newValue;
        if (!raw) {
          setCart([]);
          return;
        }
        const parsed = JSON.parse(raw) as unknown;
        if (Array.isArray(parsed)) {
          const valid = (parsed as PurchaseCartItem[]).filter(
            (it) =>
              it &&
              typeof it.key === 'string' &&
              it.drug &&
              typeof it.drug.id === 'number' &&
              typeof it.qty === 'string' &&
              typeof it.unit_cost === 'string',
          );
          setCart(valid);
        } else if (!parsed) setCart([]);
      } catch {}
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  function addToCart(drug: Drug): string | null {
    // Use ref for latest cart to avoid stale closure when updateCart just fired in same tick
    const current = cartRef.current;
    const existing = current.find((c) => c.drug.id === drug.id && c.expire === '');
    if (existing) {
      const norm = normalizeDecimal(existing.qty);
      if (!isQtyValid(norm)) return 'كمية غير صالحة — صحح الكمية قبل الإضافة';
    }
    // functional update still handles concurrent prev correctly, but validation already done via ref
    setCart((prev) => {
      const idx = prev.findIndex((c) => c.drug.id === drug.id && c.expire === '');
      if (idx >= 0) {
        const ent = prev[idx];
        if (!ent) return prev;
        const norm = normalizeDecimal(ent.qty);
        if (!isQtyValid(norm)) return prev;
        const bumped = addDecimal(norm, '1');
        const next = [...prev];
        next[idx] = { ...ent, qty: bumped };
        return next;
      }
      const key =
        globalThis.crypto?.randomUUID?.() ??
        `${drug.id}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      return [
        ...prev,
        { key, drug, qty: '1', unit_cost: drug.price ?? '0.00', expire: '', disc_percent: '' },
      ];
    });
    return null;
  }

  function updateCart(key: string, patch: Partial<PurchaseCartItem>) {
    setCart((prev) => prev.map((c) => (c.key === key ? { ...c, ...patch } : c)));
  }

  function removeFromCart(key: string) {
    setCart((prev) => prev.filter((c) => c.key !== key));
  }

  function clearCart() {
    setCart([]);
  }

  return { cart, setCart, addToCart, updateCart, removeFromCart, clearCart };
}
