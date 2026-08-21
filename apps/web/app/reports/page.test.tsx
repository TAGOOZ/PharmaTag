// @vitest-environment happy-dom

import { ThemeProvider } from '@pharmatag/ui';
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ReportsPage from './page';

vi.mock('next/navigation', () => ({
  usePathname: () => '/reports',
  useRouter: () => ({ push: vi.fn() }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const CATALOG = {
  reports: [
    {
      code: 'drawer_handover',
      category: 'money',
      title_ar: 'تسليم الدرج',
      title_en: 'Drawer Handover',
      params: ['date_from', 'date_to'],
      paper: 'A4',
    },
    {
      code: 'stock_minimum',
      category: 'stock',
      title_ar: 'النواقص (أقل من الحد الأدنى)',
      title_en: 'Stock Below Minimum',
      params: [],
      paper: 'A4',
    },
  ],
};

const QUEUE = {
  jobs: [
    {
      id: 3,
      report_code: 'day_profit',
      params: {},
      paper: 'A4',
      status: 'queued',
      created_at: '2026-08-21T10:00:00Z',
      done_at: null,
    },
  ],
};

const GRID = {
  title_ar: 'النواقص (أقل من الحد الأدنى)',
  title_en: 'Stock Below Minimum',
  meta: [{ label: 'عدد الأصناف', value: '1' }],
  columns: ['الصنف', 'الرصيد'],
  rows: [['بانادول إكسترا (Panadol)', '2.00']],
  foot: null,
  note: null,
};

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  window.localStorage.clear();
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function render(node: ReactNode) {
  await act(async () => {
    root.render(<ThemeProvider>{node}</ThemeProvider>);
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

async function click(text: string) {
  await act(async () => {
    buttonByText(text).click();
  });
}

function _urlIncludesQueue(url: unknown): boolean {
  return String(url).includes('/print-queue');
}

describe('ReportsPage', () => {
  it('asks for login when no token is stored', async () => {
    await render(<ReportsPage />);
    expect(textOf()).toContain('سجّل الدخول أولاً');
    expect(textOf()).not.toContain('تسليم الدرج');
  });

  it('renders the catalog grouped by category for a stored token', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (...args: unknown[]) =>
        _urlIncludesQueue(args[0]) ? jsonResponse(QUEUE) : jsonResponse(CATALOG),
      ),
    );
    await render(<ReportsPage />);
    expect(textOf()).toContain('تسليم الدرج');
    expect(textOf()).toContain('المال');
    expect(textOf()).toContain('المخزون');
    expect(textOf()).toContain('قائمة الطباعة (1 في الانتظار)');
  });

  it('shows the param form only for the selected report and renders its grid', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes('/print-queue')) return jsonResponse(QUEUE);
      if (url.includes('format=grid')) return jsonResponse(GRID);
      return jsonResponse(CATALOG);
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<ReportsPage />);

    // before selection: no date inputs, no action buttons
    expect(host.querySelectorAll('input[type="date"]')).toHaveLength(0);

    await click('تسليم الدرج');
    // drawer_handover has date_from + date_to
    expect(host.querySelectorAll('input[type="date"]')).toHaveLength(2);

    await click('عرض');
    expect(textOf()).toContain('بانادول إكسترا (Panadol)');
    const gridCall = fetchMock.mock.calls.find(([u]) =>
      String(u).includes('format=grid'),
    ) as unknown as [string] | undefined;
    expect(gridCall?.[0]).toContain('/api/v1/reports/drawer_handover?format=grid');
  });

  it('clears a stale token and returns to the login prompt on 401', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({}, 401)),
    );
    await render(<ReportsPage />);
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('سجّل الدخول أولاً');
  });

  it('surfaces a connectivity error distinct from auth', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Promise.reject(new TypeError('fetch failed'))),
    );
    await render(<ReportsPage />);
    expect(textOf()).toContain('تعذّر الاتصال بالـ API');
  });
});
