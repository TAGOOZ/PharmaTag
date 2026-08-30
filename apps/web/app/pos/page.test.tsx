// @vitest-environment happy-dom

import { ThemeProvider } from '@pharmatag/ui';
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PosPage from './page';

vi.mock('next/navigation', () => ({
  usePathname: () => '/pos',
  useRouter: () => ({ push: vi.fn() }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const SALES_EMPTY = { sales: [] };
const SALES_ONE: {
  sales: {
    id: number;
    invoice_no: string;
    datee: string;
    totalvalue: string;
    payed: string;
    agel: string;
    status: string;
  }[];
} = {
  sales: [
    {
      id: 10,
      invoice_no: '70001',
      datee: '2026-08-28',
      totalvalue: '100.00',
      payed: '100.00',
      agel: '0.00',
      status: 'saved',
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

const SALE_DETAIL = {
  id: 10,
  branch_id: 1,
  kind: 'sale',
  invoice_no: '70001',
  datee: '2026-08-28',
  silsilaid: '',
  status: 'saved',
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
      cost: '5.00',
      tax_type: 'exempt',
      vat_amount: '0.00',
      line_total: '100.00',
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

const SALE_CREATED = {
  ...SALE_DETAIL,
  id: 11,
  invoice_no: '70002',
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
      batch_id: 1,
      ref_invoice_line_id: null,
      qty: '2.0000',
      unit: 'pack',
      unit_price: '10.00',
      cost: '5.00',
      tax_type: 'exempt',
      vat_amount: '0.00',
      line_total: '20.00',
    },
  ],
};

const RETURN_CREATED = {
  ...SALE_DETAIL,
  id: 12,
  kind: 'sale_return',
  invoice_no: '70003',
  ref_invoice_id: 10,
  totalvalue: '20.00',
  totalvalue2: '20.00',
  lines: [
    {
      id: 102,
      drug_id: 1,
      drugname: 'Panadol Extra',
      drugnamear: 'بانادول إكسترا',
      batch_id: 2,
      ref_invoice_line_id: 100,
      qty: '2.0000',
      unit: 'pack',
      unit_price: '10.00',
      cost: '5.00',
      tax_type: 'exempt',
      vat_amount: '0.00',
      line_total: '20.00',
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

function textHtmlResponse(html: string, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => html,
    json: async () => {
      throw new SyntaxError('not json');
    },
  } as unknown as Response;
}

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  window.localStorage.clear();
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  // stub window.open and URL.createObjectURL for print tests
  vi.stubGlobal(
    'open',
    vi.fn(() => null),
  );
  window.open = vi.fn(() => null) as unknown as typeof window.open;
  // URL.createObjectURL stub
  vi.spyOn(URL, 'createObjectURL').mockImplementation(() => 'blob:fake');
  // revoke
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
  // flush pending effects (sales fetch)
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
}

function textOf(): string {
  return host.textContent ?? '';
}

function buttonByText(text: string): HTMLButtonElement {
  const button = [...host.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  if (!button) throw new Error(`no button with text "${text}"`);
  return button as HTMLButtonElement;
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

describe('PosPage', () => {
  it('asks for login when no token is stored', async () => {
    await render(<PosPage />);
    expect(textOf()).toContain('تسجيل الدخول');
    expect(textOf()).not.toContain('العربة');
  });

  it('renders empty cart and empty sales for a valid token', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    expect(textOf()).toContain('العربة فارغة');
    expect(textOf()).toContain('لا توجد مبيعات بعد');
  });

  it('renders the sales list grouped for a stored token', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    expect(textOf()).toContain('70001');
    expect(textOf()).toContain('المبيعات الحديثة');
  });

  it('shows no-drugs match message when search yields empty', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'xyz');
    await click('بحث');
    expect(textOf()).toContain('لا توجد أدوية مطابقة للبحث');
  });

  it('adds a drug from search to cart and allows remove', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    expect(textOf()).toContain('بانادول إكسترا');
    await click('إضافة');
    expect(textOf()).toContain('العربة');
    expect(host.querySelectorAll('input[aria-label*="الكمية للصنف"]')).toHaveLength(1);
    // remove
    await click('حذف');
    expect(textOf()).toContain('العربة فارغة');
  });

  it('validates empty cart on save', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    await click('حفظ الفاتورة');
    expect(textOf()).toContain('العربة فارغة');
  });

  it('saves a sale and shows result with invoice_no and journal', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let salesCall = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        if (String(url).includes('/api/v1/sales') && init?.method === 'POST')
          return jsonResponse(SALE_CREATED, 201);
        if (String(url).includes('/api/v1/sales')) {
          salesCall += 1;
          // first call boot, second after save refresh
          if (salesCall === 1) return jsonResponse(SALES_EMPTY);
          return jsonResponse({
            sales: [
              {
                id: 11,
                invoice_no: '70002',
                datee: '2026-08-28',
                totalvalue: '20.00',
                payed: '20.00',
                agel: '0.00',
                status: 'saved',
              },
            ],
          });
        }
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    // add drug
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    await click('حفظ الفاتورة');
    expect(textOf()).toContain('تم حفظ الفاتورة #70002');
    expect(textOf()).toContain('متوازن');
    expect(textOf()).toContain('طباعة الفاتورة');
    // cart cleared
    expect(textOf()).toContain('العربة فارغة');
  });

  it('surfaces insufficient stock 409', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/sales') && init?.method === 'POST')
          return jsonResponse({ detail: 'insufficient stock' }, 409);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    await click('حفظ الفاتورة');
    expect(textOf()).toContain('الرصيد غير كافي');
  });

  it('surfaces credit limit 400', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/sales') && init?.method === 'POST')
          return jsonResponse(
            { detail: 'credit limit exceeded: current debt 90.00 + 20.00 exceeds limit 100.00' },
            400,
          );
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    // set credit payment to trigger credit limit path - third payment input is credit
    const allInputs = [...host.querySelectorAll('input')].filter(
      (i) => (i as HTMLInputElement).placeholder === '0.00',
    );
    if (allInputs[2]) setInputValue(allInputs[2] as HTMLInputElement, '20.00');
    await click('حفظ الفاتورة');
    expect(textOf()).toContain('تجاوز حد الائتمان');
  });

  it('surfaces payment mismatch 400', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/sales') && init?.method === 'POST')
          return jsonResponse({ detail: 'payment total does not match sale total' }, 400);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    await click('حفظ الفاتورة');
    expect(textOf()).toContain('إجمالي طرق الدفع لا يطابق');
  });

  it('shows sale detail and reachable print buttons', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (
          String(url).includes('/api/v1/sales/10/print') ||
          String(url).includes('/tax-document/print')
        )
          return textHtmlResponse('<html>print</html>');
        if (String(url).includes('/api/v1/sales/10')) return jsonResponse(SALE_DETAIL);
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    await click('عرض');
    expect(textOf()).toContain('تفاصيل الفاتورة');
    expect(textOf()).toContain('70001');
    expect(textOf()).toContain('طباعة الفاتورة');
    // print - should call window.open via blob
    // stub already
    await click('طباعة الفاتورة (80مم)');
    expect(window.open).toHaveBeenCalled();
  });

  it('shows return form reachable from detail and creates return', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/sales/10/return') && init?.method === 'POST')
          return jsonResponse(RETURN_CREATED, 201);
        if (String(url).includes('/api/v1/sales/10')) return jsonResponse(SALE_DETAIL);
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    await click('عرض');
    // set return qty
    const returnInput = getInputByAria('كمية إرجاع');
    setInputValue(returnInput, '2');
    await click('إرجاع الكمية المحددة');
    expect(textOf()).toContain('تم إنشاء فاتورة مرتجع #70003');
  });

  it('validates return qty exceeds original locally', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales/10')) return jsonResponse(SALE_DETAIL);
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    await click('عرض');
    const returnInput = getInputByAria('كمية إرجاع');
    setInputValue(returnInput, '20');
    await click('إرجاع الكمية المحددة');
    expect(textOf()).toContain('تتجاوز الكمية الأصلية');
  });

  it('shows sale-return without original clear message', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    expect(textOf()).toContain('اختر فاتورة أولاً لإرجاعها');
  });

  it('clears a stale token and returns to login on 401 for sales', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({}, 401)),
    );
    await render(<PosPage />);
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('تسجيل الدخول');
  });

  it('clears stale token on 401 during search', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse({}, 401);
        return jsonResponse(SALES_EMPTY);
      }),
    );
    await render(<PosPage />);
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
    await render(<PosPage />);
    // boot fetch failure should go to error view with connectivity message
    expect(textOf()).toContain('تعذّر جلب');
  });

  it('surfaces search connectivity error as status', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        if (String(url).includes('/api/v1/drugs/search'))
          return Promise.reject(new TypeError('fetch failed'));
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
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
        if (String(url).includes('/api/v1/sales/10'))
          return jsonResponse({ detail: 'forbidden' }, 403);
        if (String(url).includes('/api/v1/sales') && init?.method === 'POST')
          return jsonResponse({ detail: 'forbidden' }, 403);
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_ONE);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    // try detail 403
    await click('عرض');
    expect(textOf()).toContain('ليس لديك صلاحية');
    // try save 403
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    await click('إضافة');
    await click('حفظ الفاتورة');
    expect(textOf()).toContain('ليس لديك صلاحية');
  });

  it('surfaces 404 deleted/broken link', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales/10')) return jsonResponse({}, 404);
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_ONE);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
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
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
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
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await click('بحث');
    expect(textOf()).toContain('خطأ بالخادم');
    expect(textOf()).not.toContain('/src/');
    expect(textOf()).not.toContain('stack');
  });

  it('shows light/dark compatible markup and RTL dir', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    const section = host.querySelector('section');
    expect(section?.getAttribute('dir')).toBe('rtl');
    expect(host.innerHTML).toContain('pt-card');
  });

  it('keyboard: Enter on search triggers lookup', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
      if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_ONE);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<PosPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, 'pan');
    await act(async () => {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    // after Enter, search should have been called
    const called = fetchMock.mock.calls.some(([u]) => String(u).includes('/api/v1/drugs/search'));
    expect(called).toBe(true);
  });

  it('handles empty search query as no-op', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<PosPage />);
    await click('بحث');
    expect(textOf()).toContain('أدخل باركود');
    // no search fetch
    expect(fetchMock.mock.calls.filter(([u]) => String(u).includes('/search'))).toHaveLength(0);
  });

  it('supports barcode scan via search input value', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/sales')) return jsonResponse(SALES_EMPTY);
        if (String(url).includes('q=123456')) return jsonResponse(SEARCH_ONE);
        if (String(url).includes('/api/v1/drugs/search')) return jsonResponse(SEARCH_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<PosPage />);
    const input = host.querySelector('input[placeholder*="ابحث بالباركود"]') as HTMLInputElement;
    setInputValue(input, '123456');
    await click('بحث');
    expect(textOf()).toContain('بانادول إكسترا');
  });
});
