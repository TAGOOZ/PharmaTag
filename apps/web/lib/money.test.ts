import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  closeDay,
  closeMonth,
  createManualJournal,
  createMovement,
  createVoucher,
  fetchBalanceSheet,
  fetchBalanceSheetHtml,
  fetchDayCloses,
  fetchDrawerMovements,
  fetchManualJournal,
  fetchManualJournals,
  fetchMonths,
  fetchOpenBalances,
  fetchOpeningBalances,
  fetchPayables,
  fetchReceivables,
  fetchStatement,
  fetchTrialBalance,
  fetchVouchers,
  reopenDay,
  reopenMonth,
  reverseManualJournal,
  reverseVoucher,
} from './money';

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    json: async () => body,
    text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
    clone() {
      return this as unknown as Response;
    },
  } as unknown as Response;
}

afterEach(() => vi.unstubAllGlobals());

type FetchCalls = { mock: { calls: unknown[][] } };

function urlOf(fetchMock: FetchCalls, n: number): string {
  const call = fetchMock.mock.calls[n];
  if (!call) throw new Error(`expected fetch call ${n}`);
  return String(call[0]);
}

describe('money api client', () => {
  it('fetches drawer movements with the bearer token', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ movements: [{ id: 1, amount: '100.00' }] }));
    vi.stubGlobal('fetch', fetchMock);
    const res = await fetchDrawerMovements('tok-1');
    expect(res.movements).toHaveLength(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/drawer/movements');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-1');
  });

  it('posts a manual movement with raw amount strings (no client math)', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: 2, amount: '0.30' }));
    vi.stubGlobal('fetch', fetchMock);
    await createMovement('tok', {
      direction: 'in',
      reason: 'opening',
      method: 'cash',
      amount: '0.10',
    });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/drawer/movements');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string).amount).toBe('0.10');
  });

  it('closes and reopens a day via the day-close endpoints', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: 1, status: 'closed' }));
    vi.stubGlobal('fetch', fetchMock);
    await closeDay('tok', { counted_cash: '1000.00' });
    const [closeUrl, closeInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(closeUrl).toContain('/api/v1/drawer/day-close');
    expect(closeInit.method).toBe('POST');
    await reopenDay('tok', 9);
    const [reopenUrl, reopenInit] = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    expect(reopenUrl).toContain('/api/v1/drawer/day-close/9/reopen');
    expect(reopenInit.method).toBe('POST');
    await fetchDayCloses('tok');
    expect(urlOf(fetchMock, 2)).toContain('/api/v1/drawer/day-close');
  });

  it('lists, reads, creates and reverses manual journals', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ entries: [] }));
    vi.stubGlobal('fetch', fetchMock);
    await fetchManualJournals('tok');
    expect(urlOf(fetchMock, 0)).toContain('/api/v1/journals/manual');
    await fetchManualJournal('tok', 3);
    expect(urlOf(fetchMock, 1)).toContain('/api/v1/journals/manual/3');
    await createManualJournal('tok', {
      datee: '2026-08-01',
      description: 'قيد افتتاحي',
      lines: [
        { account_code: '1000', debit: '100.00' },
        { account_code: '4000', credit: '100.00' },
      ],
    });
    const [postUrl, postInit] = fetchMock.mock.calls[2] as unknown as [string, RequestInit];
    expect(postUrl).toContain('/api/v1/journals/manual');
    expect(postInit.method).toBe('POST');
    await reverseManualJournal('tok', 3);
    const [revUrl] = fetchMock.mock.calls[3] as unknown as [string, RequestInit];
    expect(revUrl).toContain('/api/v1/journals/manual/3/reverse');
  });

  it('builds the statement URL with non-empty params only', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ opening_balance: '0.00', movements: [] }));
    vi.stubGlobal('fetch', fetchMock);
    await fetchStatement('tok', 5, { month: '8', year: '', date_from: '', date_to: '' });
    const [url] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/parties/5/statement');
    expect(url).toContain('month=8');
    expect(url).not.toContain('year=');
    await fetchPayables('tok');
    expect(urlOf(fetchMock, 1)).toContain('/api/v1/parties/payables');
  });

  it('posts and reverses settlement vouchers with raw amounts', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ vouchers: [] }));
    vi.stubGlobal('fetch', fetchMock);
    await fetchVouchers('tok');
    expect(urlOf(fetchMock, 0)).toContain('/api/v1/receivables/vouchers');
    await createVoucher('tok', {
      voucher_type: 'receipt',
      party_id: 7,
      datee: '2026-08-01',
      method: 'cash',
      amount: '250.75',
    });
    const [, postInit] = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    expect(postInit.method).toBe('POST');
    expect(JSON.parse(postInit.body as string).amount).toBe('250.75');
    await reverseVoucher('tok', 4);
    expect(urlOf(fetchMock, 2)).toContain('/api/v1/receivables/vouchers/4/reverse');
    await fetchReceivables('tok');
    expect(urlOf(fetchMock, 3)).toContain('/api/v1/receivables');
  });

  it('fetches trial-balance and balance-sheet with period params', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ lines: [] }));
    vi.stubGlobal('fetch', fetchMock);
    await fetchTrialBalance('tok', { year: '2026', month: '8' });
    const [tbUrl] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(tbUrl).toContain('/api/v1/accounts/trial-balance');
    expect(tbUrl).toContain('year=2026');
    expect(tbUrl).toContain('month=8');
    await fetchBalanceSheet('tok', {});
    expect(urlOf(fetchMock, 1)).toContain('/api/v1/accounts/balance-sheet');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: { get: () => null },
        text: async () => '<html>ميزانية</html>',
      })) as unknown as typeof fetch,
    );
    const html = await fetchBalanceSheetHtml('tok', { year: '2026', month: '8' });
    expect(html).toContain('ميزانية');
  });

  it('lists, closes and reopens months plus opening balances', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ months: [] }));
    vi.stubGlobal('fetch', fetchMock);
    await fetchMonths('tok');
    expect(urlOf(fetchMock, 0)).toContain('/api/v1/months');
    await closeMonth('tok', 2026, 8);
    const [closeUrl, closeInit] = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    expect(closeUrl).toContain('/api/v1/months/2026/8/close');
    expect(closeInit.method).toBe('POST');
    await reopenMonth('tok', 2026, 8);
    expect(urlOf(fetchMock, 2)).toContain('/api/v1/months/2026/8/reopen');
    await fetchOpenBalances('tok', 2026, 8);
    expect(urlOf(fetchMock, 3)).toContain('/api/v1/months/2026/8/open-balances');
    await fetchOpeningBalances('tok', 2026, 8);
    expect(urlOf(fetchMock, 4)).toContain('/api/v1/opening-balances/2026/8');
  });

  it('raises ApiError with the server status for non-2xx (verbatim detail)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'closed month' }, 409)),
    );
    await expect(fetchManualJournals('tok')).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
    });
  });
});
