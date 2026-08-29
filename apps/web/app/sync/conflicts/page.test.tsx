// @vitest-environment happy-dom

import { ThemeProvider } from '@pharmatag/ui';
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SyncConflictsPage from './page';

vi.mock('next/navigation', () => ({
  usePathname: () => '/sync/conflicts',
  useRouter: () => ({ push: vi.fn() }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const CONFLICTS_EMPTY = { conflicts: [], items: [], count: 0, branch_id: 1 };

const CONFLICTS_ONE = {
  conflicts: [
    {
      id: 101,
      branch_id: 1,
      entity: 'branch_stock',
      entity_id: 5,
      created_at: '2026-08-27T10:00:00Z',
      synced_at: '2026-08-27T10:01:00Z',
      updated_at: '2026-08-27T10:01:00Z',
      skipped_reason: 'stale snapshot (updated_at=2026-08-27T09:00:00+00:00) — local row is newer',
      loser: { branch_id: 1, drug_id: 5, qty: '10.0000', minimum: '5.0000' },
      winner: {
        branch_id: 1,
        drug_id: 5,
        qty: '15.0000',
        minimum: '5.0000',
        lastedit: '2026-08-27T10:01:00Z',
      },
      payload: { branch_id: 1, drug_id: 5, qty: '10.0000', minimum: '5.0000' },
      resolved: false,
    },
  ],
  items: [
    {
      id: 101,
      branch_id: 1,
      entity: 'branch_stock',
      entity_id: 5,
      created_at: '2026-08-27T10:00:00Z',
      synced_at: '2026-08-27T10:01:00Z',
      updated_at: '2026-08-27T10:01:00Z',
      skipped_reason: 'stale snapshot',
      loser: { branch_id: 1, drug_id: 5, qty: '10.0000' },
      winner: { branch_id: 1, drug_id: 5, qty: '15.0000' },
      payload: { branch_id: 1, drug_id: 5, qty: '10.0000' },
      resolved: false,
    },
  ],
  count: 1,
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
  const btn = [...host.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  if (!btn) throw new Error(`no button with text "${text}"`);
  return btn as HTMLButtonElement;
}

async function click(text: string) {
  await act(async () => {
    buttonByText(text).click();
  });
}

describe('SyncConflictsPage', () => {
  it('asks for login when no token is stored', async () => {
    await render(<SyncConflictsPage />);
    expect(textOf()).toContain('سجّل الدخول أولاً');
    expect(textOf()).not.toContain('10.0000');
  });

  it('renders empty state when no conflicts exist', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(CONFLICTS_EMPTY)),
    );
    await render(<SyncConflictsPage />);
    expect(textOf()).toContain('لا توجد تعارضات للمراجعة');
    expect(textOf()).toContain('LWW');
  });

  it('renders the conflicts table with loser, winner and updated_at', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(CONFLICTS_ONE)),
    );
    await render(<SyncConflictsPage />);
    expect(textOf()).toContain('رصيد الفرع');
    expect(textOf()).toContain('10.0000');
    expect(textOf()).toContain('15.0000');
    expect(textOf()).toContain('2026-08-27');
    expect(textOf()).toContain('استعادة');
  });

  it('shows light/dark compatible markup and RTL dir', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(CONFLICTS_EMPTY)),
    );
    await render(<SyncConflictsPage />);
    const section = host.querySelector('section');
    expect(section?.getAttribute('dir')).toBe('rtl');
    // empty state uses background-secondary which supports light/dark via CSS vars
    expect(host.innerHTML).toContain('bg-[var(--background-secondary)]');
  });

  it('restores a conflict via POST and shows success', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let conflictCalls = 0;
    const fetchMock = vi.fn(async (url: string, opts?: RequestInit) => {
      if (String(url).includes('/restore') && opts?.method === 'POST') {
        return jsonResponse({ id: 101, restored: true });
      }
      if (String(url).includes('/conflicts')) {
        conflictCalls += 1;
        // first call returns one conflict, second after restore returns empty (resolved)
        if (conflictCalls === 1) {
          return jsonResponse(CONFLICTS_ONE);
        }
        return jsonResponse(CONFLICTS_EMPTY);
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<SyncConflictsPage />);
    expect(textOf()).toContain('استعادة');
    await click('استعادة');
    // after restore, success message appears
    // need to wait for reload (restore does POST then GET)
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('تمت استعادة التعارض بنجاح');
  });

  it('surfaces 403 on restore when not a manager', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, _opts?: RequestInit) => {
        if (String(url).includes('/restore')) {
          return jsonResponse({ detail: 'forbidden' }, 403);
        }
        return jsonResponse(CONFLICTS_ONE);
      }),
    );
    await render(<SyncConflictsPage />);
    await click('استعادة');
    expect(textOf()).toContain('ليس لديك صلاحية الاستعادة');
  });

  it('clears a stale token and returns to login prompt on 401', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({}, 401)),
    );
    await render(<SyncConflictsPage />);
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('سجّل الدخول أولاً');
  });

  it('filters by entity query param', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('entity=transfer')) {
        return jsonResponse({ conflicts: [], items: [], count: 0 });
      }
      return jsonResponse(CONFLICTS_ONE);
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<SyncConflictsPage />);
    // change select to transfer
    const select = host.querySelector('select') as HTMLSelectElement;
    expect(select).toBeTruthy();
    await act(async () => {
      select.value = 'transfer';
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    // after filter change, fetch should have been called with entity=transfer
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const calledWithTransfer = fetchMock.mock.calls.some(([u]) =>
      String(u).includes('entity=transfer'),
    );
    expect(calledWithTransfer).toBe(true);
  });
});
