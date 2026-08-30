'use client';

import { useEffect, useState } from 'react';
import type { Drug, PriceLevel } from '@/lib/api';
import { addDecimal, isQtyValid, normalizeDecimal } from '@/lib/posMoney';

export interface CartItem {
  key: string;
  drug: Drug;
  qty: string;
  price_level: PriceLevel;
  disc_percent: string;
}

export const CART_KEY = 'pharmatag:pos:cart';

export function usePosCart() {
  const [cart, setCart] = useState<CartItem[]>([]);

  // Apple: persist cart across refresh (F5) — minimal localStorage, no IndexedDB overengineering
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(CART_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as unknown;
        if (Array.isArray(parsed) && parsed.length) {
          const valid = (parsed as CartItem[]).filter(
            (it) =>
              it &&
              typeof it.key === 'string' &&
              it.drug &&
              typeof it.drug.id === 'number' &&
              typeof it.qty === 'string' &&
              typeof it.price_level === 'string',
          );
          if (valid.length) setCart(valid);
          else window.localStorage.removeItem(CART_KEY);
        }
      }
    } catch {
      try {
        window.localStorage.removeItem(CART_KEY);
      } catch {}
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    try {
      if (cart.length) window.localStorage.setItem(CART_KEY, JSON.stringify(cart));
      else window.localStorage.removeItem(CART_KEY);
    } catch {}
  }, [cart]);

  function addToCart(drug: Drug): string | null {
    const existingInCart = cart.find((c) => c.drug.id === drug.id && c.price_level === 'public');
    if (existingInCart) {
      const norm = normalizeDecimal(existingInCart.qty);
      if (!isQtyValid(norm)) {
        return 'كمية غير صالحة — صحح الكمية قبل الإضافة';
      }
    }
    setCart((prev) => {
      const idx = prev.findIndex((c) => c.drug.id === drug.id && c.price_level === 'public');
      if (idx >= 0) {
        const next = [...prev];
        const existing = next[idx];
        if (!existing) return prev;
        const norm = normalizeDecimal(existing.qty);
        if (!isQtyValid(norm)) return prev;
        const bumped = addDecimal(norm, '1');
        next[idx] = { ...existing, qty: bumped };
        return next;
      }
      const key =
        globalThis.crypto?.randomUUID?.() ??
        `${drug.id}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      return [
        ...prev,
        {
          key,
          drug,
          qty: '1',
          price_level: 'public',
          disc_percent: '',
        },
      ];
    });
    return null;
  }

  function updateCart(key: string, patch: Partial<CartItem>) {
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
