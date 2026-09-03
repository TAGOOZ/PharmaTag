// @vitest-environment happy-dom
import { ThemeProvider } from '@pharmatag/ui';
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MoneyPage from './page';

vi.mock('next/navigation', () => ({
  usePathname: () => '/money',
  useRouter: () => ({ push: vi.fn() }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const DRAWER_EMPTY = { movements: [] };
const DRAWER_TWO = {
  movements: [
    {
      id: 1,
      branch_id: 1,
      datee: '2026-08-20',
      direction: 'in',
      reason: 'opening',
      method: 'cash',
      amount: '0.10',
      user_id: 1,
      ref_invoice_id: null,
      created_at: '2026-08-20T08:00:00',
    },
    {
      id: 2,
      branch_id: 1,
      datee: '2026-08-20',
      direction: 'out',
      reason: 'expense',
      method: 'network',
      amount: '0.20',
      user_id: 1,
      ref_invoice_id: null,
      created_at: '2026-08-20T09:00:00',
    },
  ],
};

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string) => headers[name.toLowerCase()] ?? null,
    },
    json: async () => body,
    text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
    clone() {
      return this as unknown as Response;
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
});

afterEach(async () => {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
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
    await new Promise((r) => setTimeout(r, 0));
  });
}

function textOf(): string {
  return host.textContent ?? '';
}

function buttonByText(text: string): HTMLButtonElement {
  const btn = [...host.querySelectorAll('button')].find((b) =>
    (b.textContent ?? '').trim().includes(text),
  );
  if (!btn)
    throw new Error(
      `no button containing "${text}" found. Buttons: ${[...host.querySelectorAll('button')].map((b) => b.textContent?.trim()).join(' | ')}`,
    );
  return btn as HTMLButtonElement;
}

async function click(text: string) {
  await act(async () => {
    buttonByText(text).click();
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
    await new Promise((r) => setTimeout(r, 0));
  });
}

describe.sequential('MoneyPage — shell & drawer', () => {
  it('asks for login when no token is stored', async () => {
    await render(<MoneyPage />);
    expect(textOf()).toContain('سجّل الدخول أولاً');
  });

  it('renders the six money tabs once drawer loads', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    for (const tab of ['الدرج', 'تقفيل اليوم', 'القيود', 'كشوفات', 'ميزان', 'شهور']) {
      expect(textOf()).toContain(tab);
    }
  });

  it('shows the drawer empty state in Arabic', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    expect(textOf()).toContain('لا توجد حركات لهذا اليوم');
  });

  it('renders server movement amounts verbatim (no client float recompute)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_TWO);
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    // 0.10 and 0.20 must appear exactly as the server sent them
    expect(textOf()).toContain('0.10');
    expect(textOf()).toContain('0.20');
  });

  it('clears a stale token and asks for login on 401', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale-tok');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'expired' }, 401)),
    );
    await render(<MoneyPage />);
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('سجّل الدخول أولاً');
  });

  it('shows API-down distinctly from auth failures', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('fetch failed');
      }),
    );
    await render(<MoneyPage />);
    expect(textOf()).toContain('تعذّر الاتصال بالـ API');
    // token is kept — this is connectivity, not auth
    expect(window.localStorage.getItem('pharmatag:token')).toBe('tok-1');
  });

  it('switching tabs is client-only (no refetch of drawer)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      if (String(url).includes('/api/v1/drawer/day-close')) return jsonResponse({ day_closes: [] });
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    const before = fetchMock.mock.calls.length;
    await click('تقفيل اليوم');
    expect(textOf()).toContain('لا يوجد تقفيل لهذا اليوم');
    // exactly one new fetch (the day-close list), drawer was not refetched
    const drawerCalls = fetchMock.mock.calls.filter(([u]) =>
      String(u).includes('/api/v1/drawer/movements'),
    );
    expect(drawerCalls).toHaveLength(1);
    expect(fetchMock.mock.calls.length).toBe(before + 1);
  });
});

function setInputValue(el: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(el, value);
  act(() => {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

function setSelectValue(el: HTMLSelectElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set;
  setter?.call(el, value);
  act(() => {
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

function inputByAria(label: string): HTMLInputElement {
  const el = [...host.querySelectorAll('input')].find((i) =>
    (i.getAttribute('aria-label') ?? '').includes(label),
  );
  if (!el) throw new Error(`no input aria-label containing "${label}"`);
  return el as HTMLInputElement;
}

function selectByAria(label: string): HTMLSelectElement {
  const el = [...host.querySelectorAll('select')].find((s) =>
    (s.getAttribute('aria-label') ?? '').includes(label),
  );
  if (!el) throw new Error(`no select aria-label containing "${label}"`);
  return el as HTMLSelectElement;
}

async function submitForm() {
  await act(async () => {
    const form = host.querySelector('form');
    if (!form) throw new Error('no form found');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
    await new Promise((r) => setTimeout(r, 0));
  });
}

const DAY_CLOSE_ONE = {
  day_closes: [
    {
      id: 11,
      branch_id: 1,
      datee: '2026-08-20',
      drawer_start: '500.00',
      expected_cash: '1200.50',
      counted_cash: '1199.00',
      difference: '-1.50',
      net_cash: '700.50',
      net_network: '300.00',
      manual_cash: '0.00',
      manual_card: '0.00',
      supplier_payments: '0.00',
      purchases: '0.00',
      expenses: '0.00',
      cost_of_sales: '0.00',
      net_profit: '0.00',
      discounts: '0.00',
      vat_sales: '0.00',
      vat_purchases: '0.00',
      vat_expenses: '0.00',
      status: 'closed',
      closed_by: 1,
      closed_at: '2026-08-20T23:59:00',
    },
  ],
};

const JOURNAL_LIST = {
  entries: [
    {
      id: 5,
      journal_id: 50,
      entry_no: 'J-2026-08-0001',
      branch_id: 1,
      datee: '2026-08-01',
      description: 'قيد افتتاحي',
      source: 'manual',
      total: '0.30',
      reverses_entry_id: null,
      lines: [
        {
          account_id: 1,
          account_code: '1000',
          account_name: 'الصندوق',
          debit: '0.10',
          credit: '0.00',
          note: '',
        },
        {
          account_id: 2,
          account_code: '1010',
          account_name: 'البنك',
          debit: '0.20',
          credit: '0.00',
          note: '',
        },
        {
          account_id: 3,
          account_code: '4000',
          account_name: 'المبيعات',
          debit: '0.00',
          credit: '0.30',
          note: '',
        },
      ],
    },
  ],
};

describe.sequential('MoneyPage — journals', () => {
  function stubBase(extra?: (url: string, init?: RequestInit) => Promise<Response | null> | null) {
    return vi.fn(async (url: string, init?: RequestInit) => {
      const override = extra ? await extra(url, init) : null;
      if (override) return override;
      if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      if (String(url).includes('/api/v1/drawer/day-close')) return jsonResponse({ day_closes: [] });
      return jsonResponse({});
    });
  }

  it('shows the journals empty state in Arabic', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubBase(async (url) => {
        if (String(url).includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('القيود');
    expect(textOf()).toContain('لا توجد قيود يدوية');
  });

  it('lists entries and shows detail lines verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubBase(async (url) => {
        if (/\/api\/v1\/journals\/manual\/\d+/.test(String(url)))
          return jsonResponse(JOURNAL_LIST.entries[0]);
        if (String(url).includes('/api/v1/journals/manual')) return jsonResponse(JOURNAL_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('القيود');
    expect(textOf()).toContain('قيد افتتاحي');
    expect(textOf()).toContain('J-2026-08-0001');
    await click('عرض');
    // server totals rendered verbatim — 0.10+0.20=0.30 would drift under float
    expect(textOf()).toContain('0.10');
    expect(textOf()).toContain('0.20');
    expect(textOf()).toContain('0.30');
  });

  it('creates a balanced journal with raw line amounts', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubBase(async (url, init) => {
      if (String(url).includes('/api/v1/journals/manual') && init?.method === 'POST') {
        const body = JSON.parse(init.body as string) as Record<string, unknown>;
        const lines = body.lines as { account_code: string; debit?: string; credit?: string }[];
        return jsonResponse(
          {
            id: 6,
            journal_id: 51,
            entry_no: 'J-2026-08-0002',
            branch_id: 1,
            datee: body.datee,
            description: body.description,
            source: 'manual',
            total: '100.00',
            reverses_entry_id: null,
            lines: lines.map((l) => ({
              account_code: l.account_code,
              debit: l.debit ?? '0.00',
              credit: l.credit ?? '0.00',
            })),
          },
          201,
        );
      }
      if (String(url).includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('القيود');
    setInputValue(inputByAria('البيان'), 'قيد تجريبي');
    setInputValue(inputByAria('الحساب 1'), '1000');
    setInputValue(inputByAria('مدين 1'), '100.00');
    setInputValue(inputByAria('الحساب 2'), '4000');
    setInputValue(inputByAria('دائن 2'), '100.00');
    await submitForm();
    expect(textOf()).toContain('تم إنشاء القيد');
    expect(textOf()).toContain('J-2026-08-0002');
  });

  it('defaults an empty journal date to the Cairo business day (never UTC)', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-01-15T22:30:00Z'));
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubBase(async (url, init) => {
      if (String(url).includes('/api/v1/journals/manual') && init?.method === 'POST') {
        const body = JSON.parse(init.body as string) as Record<string, unknown>;
        return jsonResponse(
          {
            id: 6,
            journal_id: 51,
            entry_no: 'J-2',
            datee: '2026-08-20',
            description: body.description,
            total: '100.00',
            lines: [],
          },
          201,
        );
      }
      if (String(url).includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('القيود');
    setInputValue(inputByAria('البيان'), 'قيد بلا تاريخ');
    setInputValue(inputByAria('الحساب 1'), '1000');
    setInputValue(inputByAria('مدين 1'), '100.00');
    setInputValue(inputByAria('الحساب 2'), '4000');
    setInputValue(inputByAria('دائن 2'), '100.00');
    await submitForm();
    const calls = fetchMock.mock.calls as unknown as [string, (RequestInit | undefined)?][];
    const post = calls.find(([, init]) => init?.method === 'POST');
    expect(post).toBeDefined();
    // 22:30Z January = 00:30+ next day in Cairo (UTC+2).
    expect((JSON.parse(post?.[1]?.body as string) as Record<string, unknown>).datee).toBe(
      '2026-01-16',
    );
  });

  it('surfaces the server balanced-check 400 verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubBase(async (url, init) => {
        if (String(url).includes('/api/v1/journals/manual') && init?.method === 'POST')
          return jsonResponse(
            { detail: 'journal is not balanced: SUM(debit) != SUM(credit)' },
            400,
          );
        if (String(url).includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('القيود');
    setInputValue(inputByAria('البيان'), 'قيد غير متزن');
    setInputValue(inputByAria('الحساب 1'), '1000');
    setInputValue(inputByAria('مدين 1'), '100.00');
    setInputValue(inputByAria('الحساب 2'), '4000');
    setInputValue(inputByAria('دائن 2'), '99.99');
    await submitForm();
    expect(textOf()).toContain('journal is not balanced');
  });

  it('reverses an entry and surfaces double-reverse 409', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let reversed = false;
    vi.stubGlobal(
      'fetch',
      stubBase(async (url, init) => {
        if (String(url).includes('/reverse') && init?.method === 'POST') {
          if (reversed) return jsonResponse({ detail: 'a reversal entry cannot be reversed' }, 409);
          reversed = true;
          return jsonResponse({ ...JOURNAL_LIST.entries[0], id: 7, reverses_entry_id: 5 }, 201);
        }
        if (/\/api\/v1\/journals\/manual\/\d+/.test(String(url)))
          return jsonResponse(JOURNAL_LIST.entries[0]);
        if (String(url).includes('/api/v1/journals/manual')) return jsonResponse(JOURNAL_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('القيود');
    await click('عرض');
    await click('عكس القيد');
    expect(textOf()).toContain('تم عكس القيد');
    await click('عكس القيد');
    expect(textOf()).toContain('a reversal entry cannot be reversed');
  });

  it('hides the journal form on 403 with the gate message', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubBase(async (url, init) => {
        if (String(url).includes('/api/v1/journals/manual') && init?.method === 'POST')
          return jsonResponse({ detail: 'missing permission: journals.manage' }, 403);
        if (String(url).includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('القيود');
    setInputValue(inputByAria('البيان'), 'قيد ممنوع');
    setInputValue(inputByAria('الحساب 1'), '1000');
    setInputValue(inputByAria('مدين 1'), '10.00');
    setInputValue(inputByAria('الحساب 2'), '4000');
    setInputValue(inputByAria('دائن 2'), '10.00');
    await submitForm();
    expect(textOf()).toContain('ليس لديك صلاحية');
    expect(host.querySelector('form')).toBeNull();
  });
});

const PARTIES_LIST = {
  parties: [
    {
      id: 7,
      branch_id: 1,
      kind: 'supplier',
      typee: '',
      namee: 'Supplier A',
      name_ar: 'مورد أ',
      mobile: '',
      adress: '',
      governorate: '',
      district: '',
      credit_limit: '0.00',
      active: true,
    },
    {
      id: 8,
      branch_id: 1,
      kind: 'customer',
      typee: '',
      namee: 'Customer B',
      name_ar: 'عميل ب',
      mobile: '',
      adress: '',
      governorate: '',
      district: '',
      credit_limit: '500.00',
      active: true,
    },
  ],
};

const STATEMENT_ONE = {
  party: { id: 7, namee: 'Supplier A', name_ar: 'مورد أ', kind: 'supplier' },
  side: 'ap',
  account_code: '2000',
  account_name: 'الموردون',
  period: { month: 8, year: 2026, date_from: null, date_to: null },
  opening_balance: '100.00',
  closing_balance: '150.00',
  debit_total: '10.00',
  credit_total: '60.00',
  movements: [
    {
      datee: '2026-08-05',
      description: 'فاتورة شراء',
      account_code: '1200',
      account_name: 'المخزون',
      debit: '0.00',
      credit: '60.00',
      running_balance: '160.00',
    },
    {
      datee: '2026-08-10',
      description: 'سداد',
      account_code: '1000',
      account_name: 'الصندوق',
      debit: '10.00',
      credit: '0.00',
      running_balance: '150.00',
    },
  ],
};

const PAYABLES_ONE = {
  branch_id: 1,
  total: '150.00',
  payables: [
    { party_id: 7, namee: 'Supplier A', name_ar: 'مورد أ', kind: 'supplier', balance: '150.00' },
  ],
};

const RECEIVABLES_ONE = {
  branch_id: 1,
  total: '200.50',
  receivables: [
    {
      party_id: 8,
      namee: 'Customer B',
      name_ar: 'عميل ب',
      kind: 'customer',
      credit_limit: '500.00',
      balance: '200.50',
    },
  ],
};

const VOUCHERS_ONE = {
  vouchers: [
    {
      id: 3,
      voucher_no: 'V-1',
      voucher_type: 'receipt',
      party: { id: 8, namee: 'Customer B', name_ar: 'عميل ب', kind: 'customer' },
      datee: '2026-08-10',
      method: 'cash',
      amount: '0.30',
      description: 'سند قبض',
      journal_id: 60,
      entry_no: 'J-x',
      reverses_voucher_id: null,
      created_by: 1,
    },
  ],
};

describe.sequential('MoneyPage — statements & settlements', () => {
  function stubMoney(extra: (url: string, init?: RequestInit) => Promise<Response | null> | null) {
    return vi.fn(async (url: string, init?: RequestInit) => {
      const override = await extra(url, init);
      if (override) return override;
      const u = String(url);
      if (u.includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      if (u.includes('/api/v1/drawer/day-close')) return jsonResponse({ day_closes: [] });
      if (/\/api\/v1\/journals\/manual\/\d+/.test(u)) return jsonResponse(JOURNAL_LIST.entries[0]);
      if (u.includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
      return jsonResponse({});
    });
  }

  it('shows Arabic empty states for payables, receivables and vouchers', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    expect(textOf()).toContain('لا توجد مستحقات للموردين');
    expect(textOf()).toContain('لا توجد ذمم مدينة');
    expect(textOf()).toContain('لا توجد سندات');
  });

  it('renders a party statement grid verbatim (opening → movements → closing)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/statement')) return jsonResponse(STATEMENT_ONE);
        if (u.includes('/api/v1/parties/payables')) return jsonResponse(PAYABLES_ONE);
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('الطرف'), '7');
    await click('عرض الكشف');
    expect(textOf()).toContain('100.00');
    expect(textOf()).toContain('160.00');
    expect(textOf()).toContain('150.00');
    expect(textOf()).toContain('فاتورة شراء');
  });

  it('surfaces an inverted-range 400 with the server detail verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/statement'))
          return jsonResponse({ detail: 'date_from must not be after date_to' }, 400);
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('الطرف'), '7');
    await click('عرض الكشف');
    expect(textOf()).toContain('date_from must not be after date_to');
  });

  it('creates a receipt voucher with the raw amount', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/api/v1/receivables/vouchers') && init?.method === 'POST') {
          const body = JSON.parse(init.body as string) as Record<string, unknown>;
          return jsonResponse(
            {
              id: 4,
              voucher_no: 'V-2',
              voucher_type: body.voucher_type,
              party: { id: 8, namee: 'Customer B', name_ar: 'عميل ب', kind: 'customer' },
              datee: body.datee,
              method: body.method,
              amount: body.amount,
              description: '',
              journal_id: 61,
              entry_no: 'J-y',
              reverses_voucher_id: null,
              created_by: 1,
            },
            201,
          );
        }
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
        if (u.includes('/api/v1/receivables')) return jsonResponse(RECEIVABLES_ONE);
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    expect(textOf()).toContain('200.50');
    setSelectValue(selectByAria('نوع السند'), 'receipt');
    setSelectValue(selectByAria('طرف السند'), '8');
    setInputValue(inputByAria('مبلغ السند'), '75.25');
    await submitForm();
    expect(textOf()).toContain('تم إنشاء السند');
    expect(textOf()).toContain('75.25');
  });

  it('defaults an empty voucher date to the Cairo business day (never UTC)', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-08-20T22:30:00Z'));
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url, init) => {
      const u = String(url);
      if (u.includes('/api/v1/receivables/vouchers') && init?.method === 'POST') {
        const body = JSON.parse(init.body as string) as Record<string, unknown>;
        return jsonResponse(
          {
            id: 4,
            voucher_no: 'V-2',
            voucher_type: body.voucher_type,
            party: { id: 8, namee: 'Customer B', name_ar: 'عميل ب', kind: 'customer' },
            datee: '2026-08-20',
            method: 'cash',
            amount: body.amount,
            description: '',
            journal_id: 61,
            entry_no: 'J-y',
            reverses_voucher_id: null,
            created_by: 1,
          },
          201,
        );
      }
      if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
      if (u.includes('/api/v1/receivables'))
        return jsonResponse({ total: '0.00', receivables: [] });
      if (u.includes('/api/v1/parties/payables'))
        return jsonResponse({ total: '0.00', payables: [] });
      if (u.includes('/api/v1/parties') || u.includes('/api/v1/parties'))
        return jsonResponse(PARTIES_LIST);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('نوع السند'), 'receipt');
    setSelectValue(selectByAria('طرف السند'), '8');
    setInputValue(inputByAria('مبلغ السند'), '75.25');
    await submitForm();
    const calls = fetchMock.mock.calls as unknown as [string, (RequestInit | undefined)?][];
    const post = calls.find(([, init]) => init?.method === 'POST');
    expect(post).toBeDefined();
    const body = JSON.parse(post?.[1]?.body as string) as Record<string, unknown>;
    // 22:30Z = 01:30 next day in Cairo; a UTC default would post 2026-08-20.
    expect(body.datee).toBe('2026-08-21');
  });

  it('reverses a voucher and surfaces double-reverse 409', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let reversed = false;
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/reverse') && init?.method === 'POST') {
          if (reversed)
            return jsonResponse({ detail: 'a reversal voucher cannot be reversed' }, 409);
          reversed = true;
          return jsonResponse({ ...VOUCHERS_ONE.vouchers[0], id: 5, reverses_voucher_id: 3 }, 201);
        }
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse(VOUCHERS_ONE);
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    expect(textOf()).toContain('0.30');
    await click('عكس السند');
    expect(textOf()).toContain('تم عكس السند');
    await click('عكس السند');
    expect(textOf()).toContain('a reversal voucher cannot be reversed');
  });

  it('hides the voucher form on 403 with the gate message', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/api/v1/receivables/vouchers') && init?.method === 'POST')
          return jsonResponse({ detail: 'missing permission: receivables.manage' }, 403);
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('نوع السند'), 'receipt');
    setSelectValue(selectByAria('طرف السند'), '8');
    setInputValue(inputByAria('مبلغ السند'), '10.00');
    await submitForm();
    expect(textOf()).toContain('ليس لديك صلاحية');
    expect(host.querySelectorAll('form')).toHaveLength(0);
  });
});

const TRIAL_BALANCE = {
  branch_id: 1,
  period: { month: 8, year: 2026 },
  accounts: [
    {
      code: '1000',
      name_ar: 'الصندوق',
      name_en: 'Cash',
      type: 'asset',
      opening_debit: '500.00',
      opening_credit: '0.00',
      opening_balance: '500.00',
      debit: '0.10',
      credit: '0.00',
      closing_debit: '500.10',
      closing_credit: '0.00',
      closing_balance: '500.10',
    },
    {
      code: '4000',
      name_ar: 'المبيعات',
      name_en: 'Sales',
      type: 'income',
      opening_debit: '0.00',
      opening_credit: '0.00',
      opening_balance: '0.00',
      debit: '0.00',
      credit: '0.10',
      closing_debit: '0.00',
      closing_credit: '0.10',
      closing_balance: '-0.10',
    },
  ],
  totals: {
    opening_debit: '500.00',
    opening_credit: '500.00',
    debit: '0.10',
    credit: '0.10',
    closing_debit: '500.10',
    closing_credit: '500.10',
  },
  balanced: true,
};

const BALANCE_SHEET = {
  branch_id: 1,
  period: { month: 8, year: 2026 },
  assets: {
    total: '1000.00',
    accounts: [
      {
        code: '1000',
        name_ar: 'الصندوق',
        type: 'asset',
        side: 'debit',
        amount: '1000.00',
        balance: '1000.00',
      },
    ],
  },
  liabilities: {
    total: '600.00',
    accounts: [
      {
        code: '2000',
        name_ar: 'الموردون',
        type: 'liability',
        side: 'credit',
        amount: '600.00',
        balance: '-600.00',
      },
    ],
  },
  equity: {
    total: '400.00',
    accounts: [
      {
        code: '3000',
        name_ar: 'رأس المال',
        type: 'equity',
        side: 'credit',
        amount: '400.00',
        balance: '-400.00',
      },
    ],
  },
  opening_retained_earnings: '0.00',
  net_income: '0.00',
  total_assets: '1000.00',
  total_liabilities_equity: '1000.00',
  balanced: true,
};

describe.sequential('MoneyPage — mizan', () => {
  function stubMoney(extra: (url: string, init?: RequestInit) => Promise<Response | null> | null) {
    return vi.fn(async (url: string, init?: RequestInit) => {
      const override = await extra(url, init);
      if (override) return override;
      const u = String(url);
      if (u.includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      if (u.includes('/api/v1/drawer/day-close')) return jsonResponse({ day_closes: [] });
      if (/\/api\/v1\/journals\/manual\/\d+/.test(u)) return jsonResponse(JOURNAL_LIST.entries[0]);
      if (u.includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
      return jsonResponse({});
    });
  }

  it('shows the trial-balance empty state in Arabic', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/api/v1/accounts/trial-balance'))
          return jsonResponse({ accounts: [], totals: {}, balanced: true });
        if (u.includes('/api/v1/accounts/balance-sheet'))
          return jsonResponse({
            assets: { total: '0.00', accounts: [] },
            liabilities: { total: '0.00', accounts: [] },
            equity: { total: '0.00', accounts: [] },
            total_assets: '0.00',
            total_liabilities_equity: '0.00',
            balanced: true,
          });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('ميزان');
    expect(textOf()).toContain('لا توجد حسابات لهذه الفترة');
  });

  it('renders trial-balance rows and the server balanced flag verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('format=html')) return jsonResponse('<html></html>');
        if (u.includes('/api/v1/accounts/trial-balance')) return jsonResponse(TRIAL_BALANCE);
        if (u.includes('/api/v1/accounts/balance-sheet')) return jsonResponse(BALANCE_SHEET);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('ميزان');
    expect(textOf()).toContain('الصندوق');
    expect(textOf()).toContain('500.10');
    expect(textOf()).toContain('الميزان متوازن');
    // balance-sheet identity rendered verbatim from the server
    expect(textOf()).toContain('1000.00');
    expect(textOf()).toContain('الميزانية متوازنة');
  });

  it('sends period params on عرض and opens the printable HTML', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('format=html')) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => null },
          text: async () => '<html>ميزانية عمومية</html>',
        } as unknown as Response;
      }
      if (u.includes('/api/v1/accounts/trial-balance')) return jsonResponse(TRIAL_BALANCE);
      if (u.includes('/api/v1/accounts/balance-sheet')) return jsonResponse(BALANCE_SHEET);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    const openMock = vi.spyOn(window, 'open').mockReturnValue({} as Window);
    const createUrlMock = vi.fn(() => 'blob:fake');
    vi.stubGlobal('URL', {
      createObjectURL: createUrlMock,
      revokeObjectURL: vi.fn(),
    } as unknown as typeof URL);
    await render(<MoneyPage />);
    await click('ميزان');
    setInputValue(inputByAria('السنة'), '2026');
    setInputValue(inputByAria('الشهر'), '8');
    await click('عرض');
    const tbCalls = (fetchMock.mock.calls as unknown as [string][]).map(([u]) => String(u));
    expect(
      tbCalls.some(
        (u) =>
          u.includes('/api/v1/accounts/trial-balance') &&
          u.includes('year=2026') &&
          u.includes('month=8'),
      ),
    ).toBe(true);
    await click('نسخة للطباعة');
    expect(openMock).toHaveBeenCalled();
  });

  it('clears the token and asks for login on 401', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale-tok');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/api/v1/accounts/')) return jsonResponse({ detail: 'expired' }, 401);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('ميزان');
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('سجّل الدخول أولاً');
  });

  it('loads trial-balance and balance-sheet exactly once each on mount', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('/api/v1/accounts/trial-balance')) return jsonResponse(TRIAL_BALANCE);
      if (u.includes('/api/v1/accounts/balance-sheet')) return jsonResponse(BALANCE_SHEET);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('ميزان');
    const calls = fetchMock.mock.calls as unknown as [string][];
    const tb = calls.filter(([u]) => String(u).includes('/api/v1/accounts/trial-balance'));
    const bs = calls.filter(
      ([u]) =>
        String(u).includes('/api/v1/accounts/balance-sheet') && !String(u).includes('format=html'),
    );
    expect(tb).toHaveLength(1);
    expect(bs).toHaveLength(1);
  });

  it('shows a popup-blocked message instead of failing silently', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('format=html')) {
          return {
            ok: true,
            status: 200,
            headers: { get: () => null },
            text: async () => '<html>ميزانية عمومية</html>',
          } as unknown as Response;
        }
        if (u.includes('/api/v1/accounts/trial-balance')) return jsonResponse(TRIAL_BALANCE);
        if (u.includes('/api/v1/accounts/balance-sheet')) return jsonResponse(BALANCE_SHEET);
        return null;
      }),
    );
    vi.spyOn(window, 'open').mockReturnValue(null);
    const revokeMock = vi.fn();
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:fake'),
      revokeObjectURL: revokeMock,
    } as unknown as typeof URL);
    await render(<MoneyPage />);
    await click('ميزان');
    await click('نسخة للطباعة');
    expect(textOf()).toContain('النافذة المنبثقة محجوبة');
    expect(revokeMock).toHaveBeenCalledWith('blob:fake');
  });

  it('keeps the successful half when one mizan fetch is forbidden', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/api/v1/accounts/trial-balance')) return jsonResponse(TRIAL_BALANCE);
        if (u.includes('/api/v1/accounts/balance-sheet'))
          return jsonResponse({ detail: 'forbidden' }, 403);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('ميزان');
    expect(textOf()).toContain('الصندوق');
    expect(textOf()).toContain('500.10');
    expect(textOf()).toContain('ليس لديك صلاحية');
  });
});

const MONTHS_LIST = {
  months: [
    {
      branch_id: 1,
      year: 2026,
      month: 7,
      status: 'closed',
      closed_by: 1,
      closed_at: '2026-08-01T00:00:00',
    },
  ],
};

const MONTH_CLOSED = {
  branch_id: 1,
  year: 2026,
  month: 8,
  status: 'closed',
  closed_by: 1,
  closed_at: '2026-09-01T00:00:00',
  next_open_balances: { year: 2026, month: 9, rows: [], total_debit: '0.00', total_credit: '0.00' },
};

const OPEN_BALANCES = {
  branch_id: 1,
  year: 2026,
  month: 9,
  rows: [
    {
      account_id: 1,
      code: '1000',
      name_ar: 'الصندوق',
      name_en: 'Cash',
      debit: '500.10',
      credit: '0.00',
    },
  ],
  total_debit: '500.10',
  total_credit: '0.00',
};

const OPENING_ONE = {
  branch_id: 1,
  year: 2026,
  month: 8,
  opening_date: '2026-07-31',
  journal_id: 70,
  entry_no: 'J-open-1',
  description: 'أرصدة افتتاحية',
  total_debit: '500.10',
  total_credit: '500.10',
  rows: [
    {
      account_id: 1,
      account_code: '1000',
      account_name: 'الصندوق',
      type: 'asset',
      debit: '500.10',
      credit: '0.00',
      balance: '500.10',
    },
  ],
  balanced: true,
};

describe.sequential('MoneyPage — months', () => {
  function stubMoney(extra: (url: string, init?: RequestInit) => Promise<Response | null> | null) {
    return vi.fn(async (url: string, init?: RequestInit) => {
      const override = await extra(url, init);
      if (override) return override;
      const u = String(url);
      if (u.includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      if (u.includes('/api/v1/drawer/day-close')) return jsonResponse({ day_closes: [] });
      if (/\/api\/v1\/journals\/manual\/\d+/.test(u)) return jsonResponse(JOURNAL_LIST.entries[0]);
      if (u.includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
      return jsonResponse({});
    });
  }

  it('shows the months empty state in Arabic', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        if (String(url).includes('/api/v1/months')) return jsonResponse({ months: [] });
        if (String(url).includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('شهور');
    expect(textOf()).toContain('لا توجد شهور مقفلة');
  });

  it('closes a month and renders the returned status', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/api/v1/months/2026/8/close') && init?.method === 'POST')
          return jsonResponse(MONTH_CLOSED);
        if (u.includes('/api/v1/months')) return jsonResponse({ months: [] });
        if (u.includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('شهور');
    setInputValue(inputByAria('السنة'), '2026');
    setInputValue(inputByAria('الشهر'), '8');
    await click('تقفيل الشهر');
    expect(textOf()).toContain('تم تقفيل الشهر');
    expect(textOf()).toContain('closed');
  });

  it('surfaces double-close 409 with the server detail verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/close') && init?.method === 'POST')
          return jsonResponse({ detail: 'month is already closed' }, 409);
        if (u.includes('/api/v1/months')) return jsonResponse(MONTHS_LIST);
        if (u.includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('شهور');
    setInputValue(inputByAria('السنة'), '2026');
    setInputValue(inputByAria('الشهر'), '7');
    await click('تقفيل الشهر');
    expect(textOf()).toContain('month is already closed');
  });

  it('reopens a closed month via the manager endpoint', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url, init) => {
      const u = String(url);
      if (u.includes('/api/v1/months/2026/7/reopen') && init?.method === 'POST')
        return jsonResponse({ ...MONTH_CLOSED, year: 2026, month: 7, status: 'reopened' });
      if (u.includes('/api/v1/months')) return jsonResponse(MONTHS_LIST);
      if (u.includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('شهور');
    expect(textOf()).toContain('closed');
    await click('إعادة فتح الشهر');
    expect(textOf()).toContain('reopened');
    expect(
      (fetchMock.mock.calls as unknown as [string][]).some(([u]) =>
        String(u).includes('/months/2026/7/reopen'),
      ),
    ).toBe(true);
  });

  it('reads month open-balances and opening balances verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/open-balances')) return jsonResponse(OPEN_BALANCES);
        if (u.includes('/api/v1/opening-balances/2026/8')) return jsonResponse(OPENING_ONE);
        if (u.includes('/api/v1/months')) return jsonResponse(MONTHS_LIST);
        if (u.includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('شهور');
    await click('عرض الأرصدة');
    expect(textOf()).toContain('500.10');
    expect(textOf()).toContain('الصندوق');
    setInputValue(inputByAria('السنة'), '2026');
    setInputValue(inputByAria('الشهر'), '8');
    await click('عرض أرصدة الافتتاح');
    expect(textOf()).toContain('J-open-1');
  });

  it('hides the close form on 403 with the gate message', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/close') && init?.method === 'POST')
          return jsonResponse({ detail: 'missing permission: months.close' }, 403);
        if (u.includes('/api/v1/months')) return jsonResponse({ months: [] });
        if (u.includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('شهور');
    setInputValue(inputByAria('السنة'), '2026');
    setInputValue(inputByAria('الشهر'), '8');
    await click('تقفيل الشهر');
    expect(textOf()).toContain('ليس لديك صلاحية');
  });
});

async function clickNth(text: string, n: number) {
  await act(async () => {
    const btns = [...host.querySelectorAll('button')].filter((b) =>
      (b.textContent ?? '').trim().includes(text),
    );
    const btn = btns[n];
    if (!btn) throw new Error(`no button #${n} containing "${text}" found`);
    (btn as HTMLButtonElement).click();
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
    await new Promise((r) => setTimeout(r, 0));
  });
}

function noContentResponse(): Response {
  return {
    ok: true,
    status: 204,
    headers: { get: () => null },
    json: async () => {
      throw new SyntaxError('Unexpected end of JSON input');
    },
    text: async () => '',
    clone() {
      return this as unknown as Response;
    },
  } as unknown as Response;
}

describe.sequential('MoneyPage — edge cases', () => {
  function stubMoney(extra: (url: string, init?: RequestInit) => Promise<Response | null> | null) {
    return vi.fn(async (url: string, init?: RequestInit) => {
      const override = await extra(url, init);
      if (override) return override;
      const u = String(url);
      if (u.includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      if (u.includes('/api/v1/drawer/day-close')) return jsonResponse({ day_closes: [] });
      if (/\/api\/v1\/journals\/manual\/\d+/.test(u)) return jsonResponse(JOURNAL_LIST.entries[0]);
      if (u.includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
      return jsonResponse({});
    });
  }

  it('treats 204 no-content as empty without calling .json()', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/drawer/movements')) return noContentResponse();
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    expect(textOf()).toContain('لا توجد حركات لهذا اليوم');
  });

  it('surfaces a deleted-party 404 with the server detail verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/statement')) return jsonResponse({ detail: 'party not found' }, 404);
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('الطرف'), '7');
    await click('عرض الكشف');
    expect(textOf()).toContain('party not found');
  });

  it('shows a 429 rate-limit message without dropping the token', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/api/v1/drawer/day-close') && init?.method === 'POST')
          return jsonResponse({ detail: 'slow down' }, 429, { 'retry-after': '5' });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('تقفيل اليوم');
    setInputValue(inputByAria('المبلغ المعدود'), '5.00');
    await submitForm();
    expect(textOf()).toContain('429');
    expect(window.localStorage.getItem('pharmatag:token')).toBe('tok-1');
  });

  it('never leaks server stack traces (/src/) to the screen', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        if (String(url).includes('/api/v1/drawer/movements'))
          return jsonResponse({ detail: 'File "/src/app/money/entries.py", line 42, boom' }, 500);
        return null;
      }),
    );
    await render(<MoneyPage />);
    expect(textOf()).toContain('خطأ بالخادم — حاول لاحقاً');
    expect(textOf()).not.toContain('/src/');
  });

  it('maps 422 semantic errors to an Arabic invalid-data message', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/api/v1/receivables/vouchers') && init?.method === 'POST')
          return jsonResponse({ detail: 'amount must be positive' }, 422);
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('نوع السند'), 'receipt');
    setSelectValue(selectByAria('طرف السند'), '8');
    setInputValue(inputByAria('مبلغ السند'), '10.00');
    await submitForm();
    expect(textOf()).toContain('بيانات غير صالحة');
  });

  it('rejects a zero journal line client-side with no round-trip', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async () => null);
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('القيود');
    setInputValue(inputByAria('البيان'), 'قيد صفري');
    setInputValue(inputByAria('الحساب 1'), '1000');
    setInputValue(inputByAria('مدين 1'), '0.00');
    setInputValue(inputByAria('الحساب 2'), '4000');
    setInputValue(inputByAria('دائن 2'), '0.00');
    await submitForm();
    expect(textOf()).toContain('أكبر من الصفر');
    const calls = fetchMock.mock.calls as unknown as [string, (RequestInit | undefined)?][];
    expect(calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
  });

  it('rejects a zero voucher amount client-side with no round-trip', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
      if (u.includes('/api/v1/receivables'))
        return jsonResponse({ total: '0.00', receivables: [] });
      if (u.includes('/api/v1/parties/payables'))
        return jsonResponse({ total: '0.00', payables: [] });
      if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('نوع السند'), 'receipt');
    setSelectValue(selectByAria('طرف السند'), '8');
    setInputValue(inputByAria('مبلغ السند'), '0');
    await submitForm();
    expect(textOf()).toContain('أكبر من الصفر');
    const calls = fetchMock.mock.calls as unknown as [string, (RequestInit | undefined)?][];
    expect(calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
  });

  it('rejects journal client errors (blank description, double-sided line) with no round-trip', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      if (String(url).includes('/api/v1/journals/manual')) return jsonResponse({ entries: [] });
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('القيود');
    // blank description (required attribute aside, handler validates)
    setInputValue(inputByAria('الحساب 1'), '1000');
    setInputValue(inputByAria('مدين 1'), '10.00');
    setInputValue(inputByAria('الحساب 2'), '4000');
    setInputValue(inputByAria('دائن 2'), '10.00');
    await submitForm();
    expect(textOf()).toContain('البيان مطلوب');
    // double-sided line
    setInputValue(inputByAria('البيان'), 'قيد مزدوج');
    setInputValue(inputByAria('دائن 1'), '5.00');
    await submitForm();
    expect(textOf()).toContain('مدين أو دائن — وليس الاثنين');
    const calls = fetchMock.mock.calls as unknown as [string, (RequestInit | undefined)?][];
    expect(calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
  });

  it('blocks a month/year + date-range combo client-side with no round-trip', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('/api/v1/parties/payables'))
        return jsonResponse({ total: '0.00', payables: [] });
      if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
      if (u.includes('/api/v1/receivables'))
        return jsonResponse({ total: '0.00', receivables: [] });
      if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('الطرف'), '7');
    setInputValue(inputByAria('الشهر'), '8');
    const from = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'من تاريخ',
    ) as HTMLInputElement;
    setInputValue(from, '2026-08-01');
    await click('عرض الكشف');
    expect(textOf()).toContain('الشهر والسنة أو المدى');
    const calls = fetchMock.mock.calls as unknown as [string, (RequestInit | undefined)?][];
    expect(calls.filter(([u]) => String(u).includes('/statement'))).toHaveLength(0);
  });

  it('surfaces the ambiguous-period 400 verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/statement'))
          return jsonResponse({ detail: 'pass month/year OR a date range, not both' }, 400);
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('الطرف'), '7');
    await click('عرض الكشف');
    expect(textOf()).toContain('pass month/year OR a date range, not both');
  });

  it('hides gated drawer content on list-level 403', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/drawer/movements'))
          return jsonResponse({ detail: 'missing permission' }, 403);
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    expect(textOf()).toContain('ليس لديك صلاحية');
    expect(host.querySelector('form')).toBeNull();
  });

  it('is RTL with keyboard-focusable tabs and selected-state tracking', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
        if (String(url).includes('/api/v1/drawer/day-close'))
          return jsonResponse({ day_closes: [] });
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    const section = host.querySelector('section[dir="rtl"]');
    expect(section).not.toBeNull();
    const tabs = [...host.querySelectorAll('[role="tab"]')];
    expect(tabs).toHaveLength(6);
    for (const t of tabs) expect((t as HTMLElement).tagName).toBe('BUTTON');
    expect(tabs[0]?.getAttribute('aria-selected')).toBe('true');
    await click('تقفيل اليوم');
    const tabsAfter = [...host.querySelectorAll('[role="tab"]')];
    expect(tabsAfter[0]?.getAttribute('aria-selected')).toBe('false');
    expect(tabsAfter[1]?.getAttribute('aria-selected')).toBe('true');
  });

  it('ignores a stale journal detail that resolves after a newer one', async () => {
    const entryA = { ...JOURNAL_LIST.entries[0], id: 5, entry_no: 'J-A', description: 'قيد أ' };
    const entryB = {
      ...JOURNAL_LIST.entries[0],
      id: 6,
      entry_no: 'J-B',
      description: 'قيد ب',
      lines: [
        { account_code: '1000', account_name: 'الصندوق', debit: '7.77', credit: '0.00' },
        { account_code: '4000', account_name: 'المبيعات', debit: '0.00', credit: '7.77' },
      ],
    };
    const deferreds: { id: number; resolve: (r: Response) => void }[] = [];
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        const m = u.match(/\/api\/v1\/journals\/manual\/(\d+)/);
        if (m) {
          const id = Number(m[1]);
          return new Promise<Response>((resolve) => {
            deferreds.push({ id, resolve });
          });
        }
        if (u.endsWith('/api/v1/journals/manual'))
          return jsonResponse({ entries: [entryA, entryB] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('القيود');
    await clickNth('عرض', 0);
    // Row A is now expanded (its button reads إخفاء) — row B's عرض is index 0.
    await clickNth('عرض', 0);
    expect(deferreds.map((d) => d.id)).toEqual([5, 6]);
    // B resolves first, then stale A resolves last — B must stay visible.
    deferreds.find((d) => d.id === 6)?.resolve(jsonResponse(entryB));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    deferreds.find((d) => d.id === 5)?.resolve(jsonResponse(entryA));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
      await new Promise((r) => setTimeout(r, 0));
    });
    // The expanded detail must show B's lines even though A's fetch resolved last.
    expect(textOf()).toContain('7.77');
  });

  it('ignores stale month balances that resolve after a newer request', async () => {
    const months = {
      months: [
        { branch_id: 1, year: 2026, month: 7, status: 'closed', closed_by: 1, closed_at: 'x' },
        { branch_id: 1, year: 2026, month: 8, status: 'closed', closed_by: 1, closed_at: 'x' },
      ],
    };
    const deferreds: { key: string; resolve: (r: Response) => void }[] = [];
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/open-balances')) {
          const m = u.match(/\/months\/(\d+)\/(\d+)\/open-balances/);
          const key = m ? `${m[1]}/${m[2]}` : u;
          return new Promise<Response>((resolve) => {
            deferreds.push({ key, resolve });
          });
        }
        if (/\/api\/v1\/months\/\d+\/\d+$/.test(u)) return jsonResponse({ detail: 'x' }, 404);
        if (u.includes('/api/v1/months')) return jsonResponse(months);
        if (u.includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('شهور');
    await clickNth('عرض الأرصدة', 0);
    await clickNth('عرض الأرصدة', 1);
    // Second request (2026/8) resolves first, stale first (2026/7) last.
    deferreds
      .find((d) => d.key === '2026/8')
      ?.resolve(jsonResponse({ rows: [], total_debit: '8.00', total_credit: '8.00' }));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    deferreds
      .find((d) => d.key === '2026/7')
      ?.resolve(jsonResponse({ rows: [], total_debit: '7.00', total_credit: '7.00' }));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('أرصدة 2026/8');
    expect(textOf()).not.toContain('أرصدة 2026/7');
  });

  it('disables reverse actions after a journal reverse 403', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/reverse') && init?.method === 'POST')
          return jsonResponse({ detail: 'missing permission' }, 403);
        if (/\/api\/v1\/journals\/manual\/\d+/.test(u))
          return jsonResponse(JOURNAL_LIST.entries[0]);
        if (u.includes('/api/v1/journals/manual')) return jsonResponse(JOURNAL_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('القيود');
    await click('عرض');
    await click('عكس القيد');
    expect(textOf()).toContain('ليس لديك صلاحية');
    const reverseBtns = [...host.querySelectorAll('button')].filter((b) =>
      (b.textContent ?? '').includes('عكس القيد'),
    );
    expect(reverseBtns.length).toBeGreaterThan(0);
    for (const b of reverseBtns) expect((b as HTMLButtonElement).disabled).toBe(true);
  });

  it('disables reverse actions after a voucher reverse 403', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/reverse') && init?.method === 'POST')
          return jsonResponse({ detail: 'missing permission' }, 403);
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse(VOUCHERS_ONE);
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    await click('عكس السند');
    expect(textOf()).toContain('ليس لديك صلاحية');
    const reverseBtns = [...host.querySelectorAll('button')].filter((b) =>
      (b.textContent ?? '').includes('عكس السند'),
    );
    expect(reverseBtns.length).toBeGreaterThan(0);
    for (const b of reverseBtns) expect((b as HTMLButtonElement).disabled).toBe(true);
  });

  it('disables reopen actions after a day-close reopen 403', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/reopen') && init?.method === 'POST')
          return jsonResponse({ detail: 'missing permission' }, 403);
        if (u.includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
        if (u.includes('/api/v1/drawer/day-close')) return jsonResponse(DAY_CLOSE_ONE);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('تقفيل اليوم');
    await click('إعادة فتح');
    expect(textOf()).toContain('ليس لديك صلاحية');
    const reopenBtns = [...host.querySelectorAll('button')].filter((b) =>
      (b.textContent ?? '').includes('إعادة فتح'),
    );
    expect(reopenBtns.length).toBeGreaterThan(0);
    for (const b of reopenBtns) expect((b as HTMLButtonElement).disabled).toBe(true);
  });

  it('disables reopen actions after a month reopen 403', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/reopen') && init?.method === 'POST')
          return jsonResponse({ detail: 'missing permission' }, 403);
        if (u.includes('/api/v1/months')) return jsonResponse(MONTHS_LIST);
        if (u.includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('شهور');
    await click('إعادة فتح الشهر');
    expect(textOf()).toContain('ليس لديك صلاحية');
    const reopenBtns = [...host.querySelectorAll('button')].filter((b) =>
      (b.textContent ?? '').includes('إعادة فتح الشهر'),
    );
    expect(reopenBtns.length).toBeGreaterThan(0);
    for (const b of reopenBtns) expect((b as HTMLButtonElement).disabled).toBe(true);
  });

  it('fetches the party picker with a single unfiltered call', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('/api/v1/parties/payables'))
        return jsonResponse({ total: '0.00', payables: [] });
      if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
      if (u.includes('/api/v1/receivables'))
        return jsonResponse({ total: '0.00', receivables: [] });
      if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('كشوفات');
    const calls = fetchMock.mock.calls as unknown as [string][];
    const pickerCalls = calls
      .map(([u]) => String(u))
      .filter((u) => u.includes('/api/v1/parties') && !u.includes('/payables'));
    // one unfiltered list call (no kind= supplier/customer/both triple-fetch)
    expect(pickerCalls).toHaveLength(1);
    expect(pickerCalls[0]).not.toContain('kind=');
    expect(textOf()).toContain('مورد أ');
  });

  it('requests the party picker with the server-max limit', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('/api/v1/parties/payables'))
        return jsonResponse({ total: '0.00', payables: [] });
      if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
      if (u.includes('/api/v1/receivables'))
        return jsonResponse({ total: '0.00', receivables: [] });
      if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('كشوفات');
    const calls = fetchMock.mock.calls as unknown as [string][];
    const picker = calls
      .map(([u]) => String(u))
      .find((u) => u.includes('/api/v1/parties') && !u.includes('/payables'));
    expect(picker).toContain('limit=200');
  });

  it('falls back to the English name when name_ar is empty', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({
            total: '5.00',
            payables: [
              { party_id: 9, namee: 'NoArabic', name_ar: '', kind: 'supplier', balance: '5.00' },
            ],
          });
        if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    expect(textOf()).toContain('NoArabic');
  });

  it('surfaces month-detail errors instead of falling back silently', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('/open-balances')) return jsonResponse(OPEN_BALANCES);
      if (/\/api\/v1\/months\/\d+\/\d+$/.test(u)) return jsonResponse({ detail: 'denied' }, 403);
      if (u.includes('/api/v1/months')) return jsonResponse(MONTHS_LIST);
      if (u.includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('شهور');
    await click('عرض الأرصدة');
    expect(textOf()).toContain('denied');
    const calls = fetchMock.mock.calls as unknown as [string][];
    expect(calls.filter(([u]) => String(u).includes('/open-balances'))).toHaveLength(0);
  });

  it('disables reopen while a close is pending (shared lock)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let resolveClose!: (r: Response) => void;
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url, init) => {
        const u = String(url);
        if (u.includes('/close') && init?.method === 'POST')
          return new Promise<Response>((resolve) => {
            resolveClose = resolve;
          });
        if (u.includes('/api/v1/months')) return jsonResponse(MONTHS_LIST);
        if (u.includes('/api/v1/opening-balances')) return jsonResponse({ periods: [] });
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('شهور');
    setInputValue(inputByAria('السنة'), '2026');
    setInputValue(inputByAria('الشهر'), '8');
    await act(async () => {
      const btn = buttonByText('تقفيل الشهر');
      btn.click();
    });
    const reopenBtns = [...host.querySelectorAll('button')].filter((b) =>
      (b.textContent ?? '').includes('إعادة فتح الشهر'),
    );
    expect(reopenBtns.length).toBeGreaterThan(0);
    for (const b of reopenBtns) expect((b as HTMLButtonElement).disabled).toBe(true);
    resolveClose(jsonResponse(MONTH_CLOSED));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('تم تقفيل الشهر');
  });

  it('logs out when the trial-balance half 401s even if the sheet succeeds', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale-tok');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/api/v1/accounts/trial-balance'))
          return jsonResponse({ detail: 'expired' }, 401);
        if (u.includes('/api/v1/accounts/balance-sheet')) return jsonResponse(BALANCE_SHEET);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('ميزان');
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('سجّل الدخول أولاً');
  });

  it('rejects a non-numeric mizan month client-side and shows the period', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('/api/v1/accounts/trial-balance')) return jsonResponse(TRIAL_BALANCE);
      if (u.includes('/api/v1/accounts/balance-sheet')) return jsonResponse(BALANCE_SHEET);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('ميزان');
    expect(textOf()).toContain('الفترة');
    setInputValue(inputByAria('الشهر'), 'أغسطس');
    await click('عرض');
    expect(textOf()).toContain('شهراً وسنة صحيحين');
    const calls = fetchMock.mock.calls as unknown as [string][];
    // mount (2) only — the عرض click must not refetch
    expect(calls.filter(([u]) => String(u).includes('/api/v1/accounts/'))).toHaveLength(2);
  });

  it('rejects an inverted statement range client-side with no round-trip', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('/api/v1/parties/payables'))
        return jsonResponse({ total: '0.00', payables: [] });
      if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
      if (u.includes('/api/v1/receivables'))
        return jsonResponse({ total: '0.00', receivables: [] });
      if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('الطرف'), '7');
    const inputs = [...host.querySelectorAll('input')];
    const from = inputs.find(
      (i) => i.getAttribute('aria-label') === 'من تاريخ',
    ) as HTMLInputElement;
    const to = inputs.find((i) => i.getAttribute('aria-label') === 'إلى تاريخ') as HTMLInputElement;
    setInputValue(from, '2026-08-10');
    setInputValue(to, '2026-08-01');
    await click('عرض الكشف');
    expect(textOf()).toContain('من تاريخ بعد إلى تاريخ');
    const calls = fetchMock.mock.calls as unknown as [string][];
    expect(calls.filter(([u]) => String(u).includes('/statement'))).toHaveLength(0);
  });

  it('forwards the AR/AP side for dual parties', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = stubMoney(async (url) => {
      const u = String(url);
      if (u.includes('/statement')) return jsonResponse(STATEMENT_ONE);
      if (u.includes('/api/v1/parties/payables'))
        return jsonResponse({ total: '0.00', payables: [] });
      if (u.includes('/api/v1/receivables/vouchers')) return jsonResponse({ vouchers: [] });
      if (u.includes('/api/v1/receivables'))
        return jsonResponse({ total: '0.00', receivables: [] });
      if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
      return null;
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('كشوفات');
    setSelectValue(selectByAria('الطرف'), '7');
    setSelectValue(selectByAria('الجهة'), 'ap');
    await click('عرض الكشف');
    const calls = fetchMock.mock.calls as unknown as [string][];
    expect(
      calls.some(([u]) => String(u).includes('/statement') && String(u).includes('side=ap')),
    ).toBe(true);
  });

  it('labels card vouchers distinctly and renders rows missing party_id', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/api/v1/receivables/vouchers'))
          return jsonResponse({
            vouchers: [
              {
                id: 3,
                voucher_no: 'V-1',
                voucher_type: 'receipt',
                party: { id: 8, namee: 'C', name_ar: 'عميل', kind: 'customer' },
                datee: '2026-08-10',
                method: 'card',
                amount: '1.00',
                description: '',
                journal_id: 1,
                entry_no: 'J',
                reverses_voucher_id: null,
                created_by: 1,
              },
              {
                id: 4,
                voucher_no: 'V-2',
                voucher_type: 'payment',
                party: { id: 7, namee: 'S', name_ar: 'مورد', kind: 'supplier' },
                datee: '2026-08-10',
                method: 'cash',
                amount: '2.00',
                description: '',
                journal_id: 2,
                entry_no: 'J',
                reverses_voucher_id: null,
                created_by: 1,
              },
            ],
          });
        if (u.includes('/api/v1/receivables'))
          return jsonResponse({ total: '0.00', receivables: [] });
        if (u.includes('/api/v1/parties/payables'))
          return jsonResponse({ total: '0.00', payables: [] });
        if (u.includes('/api/v1/parties')) return jsonResponse(PARTIES_LIST);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('كشوفات');
    const cells = [...host.querySelectorAll('td')].map((td) => (td.textContent ?? '').trim());
    expect(cells).toContain('بطاقة');
    expect(cells).toContain('سند صرف');
  });

  it('moves tab selection with arrow keys', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
        if (String(url).includes('/api/v1/drawer/day-close'))
          return jsonResponse({ day_closes: [] });
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    const tabs = [...host.querySelectorAll('[role="tab"]')] as HTMLElement[];
    expect(tabs[0]?.getAttribute('aria-selected')).toBe('true');
    await act(async () => {
      tabs[0]?.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const after = [...host.querySelectorAll('[role="tab"]')];
    // RTL: ArrowLeft moves forward to day-close
    expect(after[1]?.getAttribute('aria-selected')).toBe('true');
  });

  it('renders mizan totals foot verbatim from the server', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      stubMoney(async (url) => {
        const u = String(url);
        if (u.includes('/api/v1/accounts/trial-balance')) return jsonResponse(TRIAL_BALANCE);
        if (u.includes('/api/v1/accounts/balance-sheet')) return jsonResponse(BALANCE_SHEET);
        return null;
      }),
    );
    await render(<MoneyPage />);
    await click('ميزان');
    expect(textOf()).toContain('الإجمالي');
    expect(textOf()).toContain('500.10');
  });
});

describe.sequential('MoneyPage — drawer form & day-close actions', () => {
  it('posts a manual movement with the raw amount and prepends the row', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes('/api/v1/drawer/movements') && init?.method === 'POST') {
        const body = JSON.parse(init.body as string) as Record<string, string>;
        return jsonResponse(
          {
            id: 9,
            branch_id: 1,
            datee: '2026-08-20',
            direction: body.direction,
            reason: body.reason,
            method: body.method,
            amount: body.amount,
            user_id: 1,
            ref_invoice_id: null,
            created_at: 'x',
          },
          201,
        );
      }
      if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    setInputValue(inputByAria('المبلغ'), '250.75');
    setSelectValue(selectByAria('الاتجاه'), 'in');
    await submitForm();
    expect(textOf()).toContain('تم تسجيل الحركة');
    expect(textOf()).toContain('250.75');
    const calls = fetchMock.mock.calls as unknown as [string, (RequestInit | undefined)?][];
    const postCall = calls.find(([, init]) => init?.method === 'POST');
    expect(postCall).toBeDefined();
    if (!postCall?.[1]?.body) throw new Error('expected POST body');
    expect(JSON.parse(postCall[1].body as string).amount).toBe('250.75');
  });

  it('rejects a zero amount client-side without a round-trip', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    setInputValue(inputByAria('المبلغ'), '0.00');
    await submitForm();
    expect(textOf()).toContain('أكبر من الصفر');
    const calls = fetchMock.mock.calls as unknown as [string, (RequestInit | undefined)?][];
    expect(calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
  });

  it('rejects an invalid amount client-side without a round-trip', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    setInputValue(inputByAria('المبلغ'), '12.345');
    await submitForm();
    expect(textOf()).toContain('المبلغ غير صالح');
    const calls = fetchMock.mock.calls as unknown as [string, (RequestInit | undefined)?][];
    expect(calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
  });

  it('hides the movement form and shows the gate message on 403', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/drawer/movements') && init?.method === 'POST')
          return jsonResponse({ detail: 'missing permission: drawer.manage' }, 403);
        if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    setInputValue(inputByAria('المبلغ'), '10.00');
    await submitForm();
    expect(textOf()).toContain('ليس لديك صلاحية');
    expect(host.querySelector('form')).toBeNull();
  });

  it('closes the day and renders server totals verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
        if (String(url).includes('/api/v1/drawer/day-close') && init?.method === 'POST')
          return jsonResponse(DAY_CLOSE_ONE.day_closes[0]);
        if (String(url).includes('/api/v1/drawer/day-close'))
          return jsonResponse({ day_closes: [] });
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    await click('تقفيل اليوم');
    expect(textOf()).toContain('لا يوجد تقفيل لهذا اليوم');
    setInputValue(inputByAria('المبلغ المعدود'), '1199.00');
    await submitForm();
    // server-computed equation rendered verbatim — never recomputed client-side
    expect(textOf()).toContain('1200.50');
    expect(textOf()).toContain('1199.00');
    expect(textOf()).toContain('-1.50');
  });

  it('surfaces an already-closed day 409 with the server detail verbatim', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
        if (String(url).includes('/api/v1/drawer/day-close') && init?.method === 'POST')
          return jsonResponse({ detail: 'day is already closed' }, 409);
        if (String(url).includes('/api/v1/drawer/day-close'))
          return jsonResponse({ day_closes: [] });
        return jsonResponse({});
      }),
    );
    await render(<MoneyPage />);
    await click('تقفيل اليوم');
    setInputValue(inputByAria('المبلغ المعدود'), '5.00');
    await submitForm();
    expect(textOf()).toContain('day is already closed');
  });

  it('reopens a closed day via the manager endpoint', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes('/api/v1/drawer/movements')) return jsonResponse(DRAWER_EMPTY);
      if (String(url).includes('/reopen') && init?.method === 'POST')
        return jsonResponse({ ...DAY_CLOSE_ONE.day_closes[0], status: 'reopened' });
      if (String(url).includes('/api/v1/drawer/day-close')) return jsonResponse(DAY_CLOSE_ONE);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<MoneyPage />);
    await click('تقفيل اليوم');
    expect(textOf()).toContain('1200.50');
    await click('إعادة فتح');
    expect(textOf()).toContain('reopened');
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/day-close/11/reopen'))).toBe(
      true,
    );
  });
});
