// @vitest-environment happy-dom
import { ThemeProvider } from '@pharmatag/ui';
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { isQtyValid } from '@/lib/posMoney';
import { PURCHASE_CART_KEY, usePurchaseCart } from './hooks/usePurchaseCart';
import PurchasesPage from './page';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  usePathname: () => '/purchases',
  useRouter: () => ({ push: vi.fn() }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const PURCHASES_EMPTY = { purchases: [] };
const PARTIES_ONE = {
  parties: [
    {
      id: 1,
      branch_id: 1,
      kind: 'supplier',
      typee: 'supplier',
      namee: 'Supplier One',
      name_ar: 'مورد واحد',
      mobile: '01000000000',
      adress: '',
      governorate: '',
      district: '',
      credit_limit: '0',
      active: true,
    },
  ],
};
const SEARCH_ONE = {
  query: 'pan',
  drugs: [
    {
      id: 1,
      drugname: 'Panadol Extra',
      drugnamear: 'بانادول إكسترا',
      generic: '',
      classy: '',
      co: '',
      units: 0,
      unitsmall: 0,
      price: '10.00',
      price_wholesale: '8.00',
      price_cost: '5.00',
      price_now: '10.00',
      tax_type: 'exempt',
      vat: '0.00',
      barcodes: [],
      active: true,
    },
  ],
};

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
  } as unknown as Response;
}

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  window.localStorage.clear();
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  vi.spyOn(URL, 'createObjectURL').mockImplementation(() => 'blob:fake');
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

async function render(node: ReactNode) {
  await act(async () => {
    root.render(<ThemeProvider>{node}</ThemeProvider>);
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
}

function textOf(): string {
  return host.textContent ?? '';
}
function buttonByText(text: string): HTMLButtonElement {
  const btn = [...host.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  if (!btn) throw new Error(`no button with text "${text}"`);
  return btn as HTMLButtonElement;
}
function getInputByAria(labelPart: string): HTMLInputElement {
  const el = [...host.querySelectorAll('input')].find((i) =>
    i.getAttribute('aria-label')?.includes(labelPart),
  );
  if (!el) throw new Error(`no input with aria-label containing "${labelPart}"`);
  return el as HTMLInputElement;
}
async function click(text: string) {
  await act(async () => {
    buttonByText(text).click();
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
}
function setInputValue(el: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(el, value);
  act(() => {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
}
function setSelectValue(el: HTMLSelectElement, value: string) {
  el.value = value;
  act(() => {
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

// ─────────────────────────────────────────────────────────────────
describe('MEDIUM remaining — huge paste max_digits 18', () => {
  it('rejects 15-int + 4-dec huge qty that exceeds 18 total digits', async () => {
    // 999999999999999.9999 = 15+4=19 >18 should be invalid (DB would 422)
    expect(isQtyValid('999999999999999.9999')).toBe(false);
    expect(isQtyValid('99999999999999.9999')).toBe(true); // 14+4=18 ok
    expect(isQtyValid('999999999999999')).toBe(true); // 15 int alone =15 <=18 ok
  });
  it('rejects qty huge paste at UI save boundary', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        if (String(url).includes('/api/v1/purchases') && init?.method === 'POST') {
          throw new Error('should not hit API for huge qty');
        }
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    const supplierSelect = host.querySelector('select[aria-label*="المورد"]') as HTMLSelectElement;
    if (supplierSelect) setSelectValue(supplierSelect, '1');
    const qtyInput = getInputByAria('الكمية للصنف');
    setInputValue(qtyInput, '999999999999999.9999');
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('كمية غير صالحة');
  });
});

describe('MEDIUM remaining — unit_cost zero allowed', () => {
  it('allows unit_cost zero (free sample) — no validation error', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let postHit = false;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        if (String(url).includes('/api/v1/purchases') && init?.method === 'POST') {
          postHit = true;
          const body = JSON.parse(String(init.body));
          expect(body.lines[0].unit_cost).toBe('0.0000');
          return jsonResponse(
            {
              id: 11,
              branch_id: 1,
              kind: 'purchase',
              invoice_no: '80002',
              datee: '2026-08-28',
              silsilaid: '',
              status: 'saved',
              party_id: 1,
              ref_invoice_id: null,
              subtotal: '0.00',
              discount: '0.00',
              vat: '0.00',
              totalvalue: '0.00',
              net: '0.00',
              payed: '0.00',
              agel: '0.00',
              created_by: 1,
              lines: [
                {
                  id: 101,
                  drug_id: 1,
                  drugname: 'Panadol Extra',
                  drugnamear: 'بانادول إكسترا',
                  batch_id: 1,
                  ref_invoice_line_id: null,
                  qty: '1.0000',
                  unit: 'pack',
                  unit_price: '0.00',
                  cost: '0.0000',
                  tax_type: 'exempt',
                  vat_amount: '0.00',
                  line_total: '0.00',
                  expire: null,
                },
              ],
              payments: [],
              journal: null,
            },
            201,
          );
        }
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    const supplierSelect = host.querySelector('select[aria-label*="المورد"]') as HTMLSelectElement;
    if (supplierSelect) setSelectValue(supplierSelect, '1');
    const costInput = getInputByAria('سعر الشراء');
    setInputValue(costInput, '0');
    await click('حفظ فاتورة الشراء');
    // should not show validation error, should hit API and succeed
    expect(textOf()).not.toContain('سعر الشراء غير صالح');
    expect(postHit).toBe(true);
    expect(textOf()).toContain('تم حفظ فاتورة الشراء #80002');
  });
});

describe('MEDIUM remaining — payments sum client hint', () => {
  it('shows client hint for entered payments sum before server 400', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    // fill payments to trigger hint
    const cashInput = host.querySelector('input[aria-label="المبلغ النقدي"]') as HTMLInputElement;
    setInputValue(cashInput, '50');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    // after fix, should show hint like "المدفوع المدخل" or "سيتم التحقق"
    expect(textOf()).toMatch(/المدفوع المدخل|سيتم التحقق|مطابق/i);
  });
});

describe('MEDIUM remaining — addToCart stale closure silent no-bump', () => {
  it('surfaces error when qty invalid then Add again (stale closure)', async () => {
    // Hook-level stale closure test: update qty to invalid then immediately add same drug without interim render
    let hook: ReturnType<typeof usePurchaseCart> | null = null;
    function Capture() {
      const h = usePurchaseCart();
      hook = h;
      return <div>{h.cart.map((c) => `${c.drug.id}:${c.qty}`).join(',') || 'empty'}</div>;
    }
    await render(<Capture />);
    const drug = SEARCH_ONE.drugs[0] as unknown as import('@/lib/api').Drug;
    await act(async () => {
      const err1 = hook!.addToCart(drug);
      expect(err1).toBeNull();
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('1:1');
    const key = hook!.cart[0]!.key;
    // Now simulate stale closure: update qty to invalid and immediately try to bump same drug
    // Do both state updates in same tick without waiting for hook ref to refresh (stale outer cart)
    let err2: string | null = null;
    await act(async () => {
      hook!.updateCart(key, { qty: '1e5' });
      // Immediately call addToCart without waiting for re-render — hook's outer `cart` is still stale (old qty 1)
      // Before fix, outer check sees stale valid qty and returns null, inner silently no-bump
      // After fix, inner functional updater detects invalid prev and returns error
      err2 = hook!.addToCart(drug);
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(err2).toContain('كمية غير صالحة');
    // cart should remain with invalid qty, not bumped
    expect(hook!.cart[0]!.qty).toBe('1e5');
    expect(textOf()).toContain('1e5');

    // Also verify page-level surface: editing via UI then Add shows error
    window.localStorage.clear();
    await act(async () => {
      root.unmount();
    });
    host.remove();
    host = document.createElement('div');
    document.body.appendChild(host);
    root = createRoot(host);
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    const qtyInput = getInputByAria('الكمية للصنف');
    // Set invalid and immediately Add without waiting for flush to expose stale closure at page level as well
    setInputValue(qtyInput, '1e5');
    await click('إضافة');
    expect(textOf()).toContain('كمية غير صالحة');
  });
});

describe('MEDIUM remaining — concurrent tab cart clobber storage listener', () => {
  it('syncs cart across tabs via storage event', async () => {
    function Probe() {
      const { cart } = usePurchaseCart();
      return <div>{cart.length === 0 ? 'empty' : cart.map((c) => c.drug.drugname).join(',')}</div>;
    }
    await render(<Probe />);
    expect(textOf()).toContain('empty');
    // simulate other tab writing cart
    const otherCart = [
      {
        key: 'k1',
        drug: SEARCH_ONE.drugs[0],
        qty: '2',
        unit_cost: '10.00',
        expire: '',
        disc_percent: '',
      },
    ];
    await act(async () => {
      // storage event is how browsers notify other tabs
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: PURCHASE_CART_KEY,
          newValue: JSON.stringify(otherCart),
          oldValue: null,
          storageArea: window.localStorage,
        }),
      );
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('Panadol');
    // clearing from other tab should empty
    await act(async () => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: PURCHASE_CART_KEY,
          newValue: null,
          oldValue: JSON.stringify(otherCart),
          storageArea: window.localStorage,
        }),
      );
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('empty');
  });
});

describe('MEDIUM remaining — empty supplier when parties===null loading', () => {
  it('disables save when parties still loading (null)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    // parties fetch never resolves -> parties stays null while ready? We mock purchases to resolve but parties to hang
    // To get to ready, we need to mock initial Promise.all to hang parties; instead we simulate via delayed parties and check loading hint
    // Simpler: mock fetch to return purchases quickly, but parties to delay 5s; page will stay in boot until both resolve.
    // We test SupplierPicker isolated: when parties===null, save should be disabled hint.
    // Instead we test page after login where parties fetch fails but view still ready — we can cause parties 500 then still ready via login path.
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        // login path not used here; initial boot effect
        if (String(url).includes('/api/v1/purchases') && !init?.method) {
          return jsonResponse(PURCHASES_EMPTY);
        }
        if (String(url).includes('/api/v1/parties')) {
          // fail -> parties stays null, but boot effect would go to error view. So we use login flow by clearing token and rendering login then logging in?
          return jsonResponse({ detail: 'error' }, 500);
        }
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        return jsonResponse({});
      }),
    );
    // initial render will go to error because purchases/parties 500; but we can instead test direct SupplierPicker + PaymentForm disabled
    // For this MEDIUM, we assert that when parties is null, the save button is disabled or hint shown
    // We render PurchasesPage with a fetch that resolves purchases but parties hangs — we intercept the initial effect by not awaiting parties
    // Simpler: render with token, mock purchases success but parties 500 then after boot error, check error view has no save button
    // Alternative: test isolated component behavior: if parties null, save hint appears
    // We'll do integration via manual parties null simulation: render page, then force parties null by not providing parties data and checking UI
    await render(<PurchasesPage />);
    // Since both fetches 500, view becomes error — not ready, so SupplierPicker not shown. Instead we test that error view is shown, but we need ready view with parties null.
    // To achieve ready with parties null, we login successfully then have parties fetch fail but purchases succeed — login handler sets view ready even if parties fails partially (sets error banner)
    // Let's simulate login flow: no token initially, then login
    window.localStorage.clear();
    // re-render for login flow
    await act(async () => {
      root.unmount();
    });
    host.remove();
    host = document.createElement('div');
    document.body.appendChild(host);
    root = createRoot(host);
    // Mock login success + purchases/parties fetch after login: purchases ok, parties fail
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/auth/login')) {
          return jsonResponse({
            access_token: 'tok-1',
            refresh_token: 'r',
            token_type: 'bearer',
            must_reset_password: false,
            user: { id: 1, username: 'admin', namee: 'Admin', permission_level: 9, branch_id: 1 },
          });
        }
        if (String(url).includes('/api/v1/purchases') && !init?.method)
          return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse({ detail: 'fail' }, 500);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    // fill login form
    const userInput = host.querySelector('input[autocomplete="username"]') as HTMLInputElement;
    const passInput = host.querySelector(
      'input[autocomplete="current-password"]',
    ) as HTMLInputElement;
    if (userInput && passInput) {
      setInputValue(userInput, 'admin');
      setInputValue(passInput, 'password');
      await click('دخول');
      // after login, view ready even though parties failed, SupplierPicker should show loading or error, and save should be disabled/hint
      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });
      const _html = host.innerHTML;
      // expect either loading text or disabled save hint
      expect(textOf()).toMatch(/جارٍ تحميل الموردين|لا يوجد موردين|تعذّر جلب الموردين/);
      const _saveBtn = host.querySelector('button') as HTMLButtonElement | null;
      // The save button should be disabled when parties not ready, or hint text should explain
      const saveButton = [...host.querySelectorAll('button')].find((b) =>
        b.textContent?.includes('حفظ فاتورة الشراء'),
      ) as HTMLButtonElement | undefined;
      if (saveButton) {
        // After fix, it should be disabled when parties === null
        expect(saveButton.disabled).toBe(true);
      } else {
        // if save button not found, at least hint text should mention loading
        expect(textOf()).toMatch(/جارٍ|انتظر/);
      }
    }
  });
});

describe('MEDIUM remaining — 429 backoff', () => {
  it('shows retry countdown/throttle after 429 on search', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.useFakeTimers({ shouldAdvanceTime: true } as any);
    let call = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('/api/v1/drugs/search')) {
          call += 1;
          if (call === 1) return jsonResponse({ detail: 'rate limit' }, 429);
          return jsonResponse(SEARCH_ONE);
        }
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    function findSearchBtn(): HTMLButtonElement {
      const btn = [...host.querySelectorAll('button')].find(
        (b) => b.textContent?.includes('بحث') || b.textContent?.includes('حاول'),
      );
      if (!btn) throw new Error('search button not found');
      return btn as HTMLButtonElement;
    }
    await act(async () => {
      findSearchBtn().click();
      await new Promise((r) => setTimeout(r, 0));
    });
    // should show rate limit error
    expect(textOf()).toContain('كثرة الطلبات');
    // after fix, search button should be throttled/disabled with countdown like "5ث" or "حاول"
    const searchBtn = findSearchBtn();
    // it should be disabled during cooldown
    expect(searchBtn.disabled).toBe(true);
    expect(searchBtn.textContent).toMatch(/حاول/);
    // advance timers to let cooldown expire
    await act(async () => {
      vi.advanceTimersByTime(6000);
      await new Promise((r) => setTimeout(r, 0));
    });
    // after cooldown, button should be enabled again and show "بحث"
    expect(findSearchBtn().disabled).toBe(false);
    expect(findSearchBtn().textContent).toContain('بحث');
    vi.useRealTimers();
  });
});

describe('MEDIUM remaining — api limit and 403 generic', () => {
  it('fetchPurchases uses ?limit=100', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(PURCHASES_EMPTY));
    vi.stubGlobal('fetch', fetchMock);
    const { fetchPurchases } = await import('@/lib/api');
    await fetchPurchases('tok-1');
    const firstCall = fetchMock.mock.calls[0] as unknown[] | undefined;
    const url = String(firstCall?.[0] ?? '');
    expect(url).toContain('limit=100');
  });
  it('403 error is generic not sale-specific', async () => {
    const { errorForStatus } = await import('@/lib/posMoney');
    expect(errorForStatus(403)).toBe('ليس لديك صلاحية — تحقق من دورك');
    expect(errorForStatus(403, 'forbidden sale.create')).toBe('ليس لديك صلاحية — تحقق من دورك');
  });
});
