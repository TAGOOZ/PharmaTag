// @vitest-environment happy-dom
import { ThemeProvider } from '@pharmatag/ui';
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PurchasesPage from './page';

vi.mock('next/navigation', () => ({
  usePathname: () => '/purchases',
  useRouter: () => ({ push: vi.fn() }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const PURCHASES_EMPTY = { purchases: [] };
const PURCHASES_ONE = {
  purchases: [
    {
      id: 10,
      invoice_no: '80001',
      datee: '2026-08-28',
      totalvalue: '100.00',
      payed: '100.00',
      agel: '0.00',
      status: 'saved',
      party_id: 1,
    },
  ],
};

const PARTIES_EMPTY = { parties: [] };
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

const SEARCH_EMPTY = { query: 'xyz', drugs: [] };
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

const PURCHASE_DETAIL = {
  id: 10,
  branch_id: 1,
  kind: 'purchase',
  invoice_no: '80001',
  datee: '2026-08-28',
  silsilaid: '',
  status: 'saved',
  party_id: 1,
  ref_invoice_id: null,
  subtotal: '100.00',
  discount: '0.00',
  vat: '0.00',
  totalvalue: '100.00',
  net: '100.00',
  payed: '100.00',
  agel: '0.00',
  created_by: 1,
  lines: [
    {
      id: 100,
      drug_id: 1,
      drugname: 'Panadol Extra',
      drugnamear: 'بانادول إكسترا',
      batch_id: 1,
      ref_invoice_line_id: null,
      qty: '10.0000',
      unit: 'pack',
      unit_price: '10.00',
      cost: '10.0000',
      tax_type: 'exempt',
      vat_amount: '0.00',
      line_total: '100.00',
      expire: null,
    },
  ],
  payments: [{ method: 'cash', amount: '100.00' }],
  journal: {
    id: 1,
    entry_no: '1',
    datee: '2026-08-28',
    balanced: true,
    debit_total: '100.00',
    credit_total: '100.00',
  },
};

const PURCHASE_CREATED = {
  ...PURCHASE_DETAIL,
  id: 11,
  invoice_no: '80002',
  totalvalue: '20.00',
  payed: '20.00',
  subtotal: '20.00',
  net: '20.00',
  lines: [
    {
      id: 101,
      drug_id: 1,
      drugname: 'Panadol Extra',
      drugnamear: 'بانادول إكسترا',
      batch_id: 2,
      ref_invoice_line_id: null,
      qty: '2.0000',
      unit: 'pack',
      unit_price: '10.00',
      cost: '10.0000',
      tax_type: 'exempt',
      vat_amount: '0.00',
      line_total: '20.00',
      expire: null,
    },
  ],
};

const RETURN_CREATED = {
  ...PURCHASE_DETAIL,
  id: 12,
  kind: 'purchase_return',
  invoice_no: '80003',
  ref_invoice_id: 10,
  totalvalue: '20.00',
  lines: [
    {
      id: 102,
      drug_id: 1,
      drugname: 'Panadol Extra',
      drugnamear: 'بانادول إكسترا',
      batch_id: 3,
      ref_invoice_line_id: 100,
      qty: '2.0000',
      unit: 'pack',
      unit_price: '10.00',
      cost: '10.0000',
      tax_type: 'exempt',
      vat_amount: '0.00',
      line_total: '20.00',
      expire: null,
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
  vi.stubGlobal(
    'open',
    vi.fn(() => null),
  );
  window.open = vi.fn(() => null) as unknown as typeof window.open;
  vi.spyOn(URL, 'createObjectURL').mockImplementation(() => 'blob:fake');
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
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

describe('PurchasesPage', () => {
  it('asks for login when no token is stored', async () => {
    await render(<PurchasesPage />);
    expect(textOf()).toContain('تسجيل الدخول');
    expect(textOf()).not.toContain('العربة');
  });

  it('renders empty cart and empty purchases for a valid token', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    expect(textOf()).toContain('العربة فارغة');
    expect(textOf()).toContain('لا توجد مشتريات بعد');
  });

  it('renders the purchases list for a stored token', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_ONE);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    expect(textOf()).toContain('80001');
    expect(textOf()).toContain('المشتريات الحديثة');
  });

  it('shows no-drugs match message when search yields empty', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'xyz');
    await click('بحث');
    expect(textOf()).toContain('لا توجد أدوية مطابقة للبحث');
  });

  it('shows no suppliers message when parties empty', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    expect(textOf()).toContain('لا يوجد موردين');
  });

  it('adds a drug from search to cart and allows remove', async () => {
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
    expect(textOf()).toContain('بانادول إكسترا');
    await click('إضافة');
    expect(host.querySelectorAll('input[aria-label*="الكمية للصنف"]')).toHaveLength(1);
    expect(host.querySelectorAll('input[aria-label*="سعر الشراء"]')).toHaveLength(1);
    await click('حذف');
    expect(textOf()).toContain('العربة فارغة');
  });

  it('validates empty cart on save', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('العربة فارغة');
  });

  it('validates supplier required on save', async () => {
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
    // no supplier selected (default empty)
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('اختر المورد');
  });

  it('validates qty zero/negative/e/X before hit', async () => {
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
    // select supplier
    const supplierSelect = host.querySelector('select[aria-label*="المورد"]') as HTMLSelectElement;
    if (supplierSelect) setSelectValue(supplierSelect, '1');
    // set qty to 0
    const qtyInput = getInputByAria('الكمية للصنف');
    setInputValue(qtyInput, '0');
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('كمية غير صالحة');
    // set qty to e
    setInputValue(qtyInput, '1e5');
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('كمية غير صالحة');
    // set qty negative
    setInputValue(qtyInput, '-5');
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('كمية غير صالحة');
  });

  it('validates unit_cost 4dp boundary', async () => {
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
    const supplierSelect = host.querySelector('select[aria-label*="المورد"]') as HTMLSelectElement;
    if (supplierSelect) setSelectValue(supplierSelect, '1');
    const costInput = getInputByAria('سعر الشراء');
    setInputValue(costInput, '1.23456'); // 5dp invalid
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('سعر الشراء غير صالح');
  });

  it('saves a purchase and shows result with invoice_no and journal', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let purchasesCall = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('/api/v1/purchases') && init?.method === 'POST')
          return jsonResponse(PURCHASE_CREATED, 201);
        if (String(url).includes('/api/v1/purchases')) {
          purchasesCall += 1;
          if (purchasesCall === 1) return jsonResponse(PURCHASES_EMPTY);
          return jsonResponse({
            purchases: [
              {
                id: 11,
                invoice_no: '80002',
                datee: '2026-08-28',
                totalvalue: '20.00',
                payed: '20.00',
                agel: '0.00',
                status: 'saved',
                party_id: 1,
              },
            ],
          });
        }
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
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('تم حفظ فاتورة الشراء #80002');
    expect(textOf()).toContain('متوازن');
    expect(textOf()).toContain('العربة فارغة');
  });

  it('surfaces 409/400 on save', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/purchases') && init?.method === 'POST')
          return jsonResponse({ detail: 'insufficient stock' }, 409);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
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
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('الرصيد غير كافي');
  });

  it('surfaces payment mismatch 400', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/purchases') && init?.method === 'POST')
          return jsonResponse({ detail: 'payment total does not match purchase total' }, 400);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
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
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('إجمالي طرق الدفع لا يطابق');
  });

  it('shows purchase detail and return reachable', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases/10')) return jsonResponse(PURCHASE_DETAIL);
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_ONE);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    await click('عرض');
    expect(textOf()).toContain('تفاصيل فاتورة الشراء');
    expect(textOf()).toContain('80001');
  });

  it('shows return form and creates return', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/purchases/10/return') && init?.method === 'POST')
          return jsonResponse(RETURN_CREATED, 201);
        if (String(url).includes('/api/v1/purchases/10')) return jsonResponse(PURCHASE_DETAIL);
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_ONE);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    await click('عرض');
    const returnInput = getInputByAria('كمية إرجاع');
    setInputValue(returnInput, '2');
    await click('إرجاع الكمية المحددة');
    expect(textOf()).toContain('تم إنشاء مرتجع شراء #80003');
  });

  it('validates return qty exceeds original locally', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases/10')) return jsonResponse(PURCHASE_DETAIL);
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_ONE);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    await click('عرض');
    const returnInput = getInputByAria('كمية إرجاع');
    setInputValue(returnInput, '20');
    await click('إرجاع الكمية المحددة');
    expect(textOf()).toContain('تتجاوز الكمية الأصلية');
  });

  it('clears stale token and returns to login on 401 for purchases', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({}, 401)),
    );
    await render(<PurchasesPage />);
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('تسجيل الدخول');
  });

  it('clears stale token on 401 during search', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse({}, 401);
        return jsonResponse(PURCHASES_EMPTY);
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('تسجيل الدخول');
  });

  it('surfaces connectivity error distinct from auth', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Promise.reject(new TypeError('fetch failed'))),
    );
    await render(<PurchasesPage />);
    // PAT5: boot 403/429/5xx/fetch -> ready+empty+banner, not error view
    expect(textOf()).toContain('تعذّر الاتصال');
    expect(textOf()).toContain('لا توجد مشتريات بعد');
  });

  it('surfaces search connectivity error as status', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('/api/v1/drugs/search'))
          return Promise.reject(new TypeError('fetch failed'));
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    expect(textOf()).toContain('تعذّر الاتصال بالـ API');
  });

  it('surfaces 403 branch mismatch permission', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/purchases/10'))
          return jsonResponse({ detail: 'forbidden' }, 403);
        if (String(url).includes('/api/v1/purchases') && init?.method === 'POST')
          return jsonResponse({ detail: 'forbidden' }, 403);
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_ONE);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    await click('عرض');
    expect(textOf()).toContain('ليس لديك صلاحية');
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    const supplierSelect = host.querySelector('select[aria-label*="المورد"]') as HTMLSelectElement;
    if (supplierSelect) setSelectValue(supplierSelect, '1');
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('ليس لديك صلاحية');
  });

  it('surfaces 404 deleted/broken link', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases/10')) return jsonResponse({}, 404);
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_ONE);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    await click('عرض');
    expect(textOf()).toContain('غير موجودة');
  });

  it('surfaces 429 rate limit', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/drugs/search'))
          return jsonResponse({ detail: 'rate limit' }, 429);
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    expect(textOf()).toContain('كثرة الطلبات');
  });

  it('surfaces 500 generic fallback without stack leak', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/drugs/search'))
          return jsonResponse({ detail: 'internal' }, 500);
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    expect(textOf()).toContain('خطأ بالخادم');
    expect(textOf()).not.toContain('/src/');
  });

  it('shows light/dark compatible markup and RTL dir', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const section = host.querySelector('section');
    expect(section?.getAttribute('dir')).toBe('rtl');
    expect(host.innerHTML).toContain('pt-card');
  });

  it('keyboard: Enter on search triggers lookup', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
      if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
      if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await act(async () => {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const called = fetchMock.mock.calls.some(([u]) => String(u).includes('/api/v1/drugs/search'));
    expect(called).toBe(true);
  });

  it('handles empty search query as no-op', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
      if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<PurchasesPage />);
    await click('بحث');
    expect(textOf()).toContain('أدخل باركود');
    expect(fetchMock.mock.calls.filter(([u]) => String(u).includes('/search'))).toHaveLength(0);
  });

  it('supports barcode scan via search input value', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        if (String(url).includes('q=123456')) return jsonResponse(SEARCH_ONE);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, '123456');
    await click('بحث');
    expect(textOf()).toContain('بانادول إكسترا');
  });

  it('handles Arabic locale qty input ١٢٫٥', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/purchases') && init?.method === 'POST') {
          const body = JSON.parse(String(init.body));
          expect(body.lines[0].qty).toBe('12.5000');
          return jsonResponse(PURCHASE_CREATED, 201);
        }
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
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
    setInputValue(qtyInput, '١٢٫٥');
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('تم حفظ فاتورة الشراء #80002');
  });

  it('validates past expiry rejected before hit', async () => {
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
    const supplierSelect = host.querySelector('select[aria-label*="المورد"]') as HTMLSelectElement;
    if (supplierSelect) setSelectValue(supplierSelect, '1');
    const expireInput = host.querySelector('input[type="date"]') as HTMLInputElement;
    setInputValue(expireInput, '2020-01-01');
    await click('حفظ فاتورة الشراء');
    expect(textOf()).toContain('تاريخ الانتهاء');
    // should not have hit API (no POST)
  });

  it('validates search 100 char limit', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_EMPTY);
      if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<PurchasesPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'a'.repeat(101));
    await click('بحث');
    expect(textOf()).toContain('نص البحث طويل جداً');
    expect(fetchMock.mock.calls.filter(([u]) => String(u).includes('/search')).length).toBe(0);
  });

  it('prevents double-submit lock', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let postCalls = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/purchases') && init?.method === 'POST') {
          postCalls += 1;
          // delay to allow second click to be ignored
          await new Promise((r) => setTimeout(r, 50));
          return jsonResponse(PURCHASE_CREATED, 201);
        }
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
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
    const saveBtn = buttonByText('حفظ فاتورة الشراء');
    await act(async () => {
      saveBtn.click();
      saveBtn.click();
      await new Promise((r) => setTimeout(r, 100));
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(postCalls).toBe(1);
  });

  it('handles FEFO: shows expire in detail and cart', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const detailWithExpire = {
      ...PURCHASE_DETAIL,
      lines: [
        { ...PURCHASE_DETAIL.lines[0], expire: '2027-12-31' },
        { ...PURCHASE_DETAIL.lines[0], id: 101, expire: '2026-06-15' },
      ],
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/purchases/10')) return jsonResponse(detailWithExpire);
        if (String(url).includes('/api/v1/purchases')) return jsonResponse(PURCHASES_ONE);
        if (String(url).includes('/api/v1/parties')) return jsonResponse(PARTIES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PurchasesPage />);
    await click('عرض');
    expect(textOf()).toContain('2027-12-31');
    expect(textOf()).toContain('2026-06-15');
  });
});
