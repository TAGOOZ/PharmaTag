import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './api';
import { enqueuePrintJob, fetchReportGrid, fetchReportsCatalog, paramLabel } from './reports';

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe('reports api client', () => {
  it('labels the known report params in Arabic', () => {
    expect(paramLabel('datee')).toBe('التاريخ');
    expect(paramLabel('date_from')).toBe('من تاريخ');
    expect(paramLabel('date_to')).toBe('إلى تاريخ');
    expect(paramLabel('unknown_param')).toBe('unknown_param');
  });

  it('fetches the catalog with the bearer token', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ reports: [{ code: 'day_profit', params: ['datee'] }] }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const reports = await fetchReportsCatalog('tok-1');
    expect(reports).toHaveLength(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/reports');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-1');
  });

  it('builds the grid URL with format=grid and non-empty params only', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ title_ar: 'x' }));
    vi.stubGlobal('fetch', fetchMock);
    await fetchReportGrid('tok-1', 'period_totals', { date_from: '2026-01-01', date_to: '' });
    const [url] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/reports/period_totals?format=grid');
    expect(url).toContain('date_from=2026-01-01');
    expect(url).not.toContain('date_to');
  });

  it('enqueues a print job with params snapshot and paper', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: 7, status: 'queued' }));
    vi.stubGlobal('fetch', fetchMock);
    const job = await enqueuePrintJob('tok-1', 'day_profit', { datee: '2026-08-21' }, 'A5');
    expect(job.id).toBe(7);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/reports/day_profit/print-queue');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({
      params: { datee: '2026-08-21' },
      paper: 'A5',
    });
  });

  it('raises ApiError with the status for non-2xx', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({}, 403)),
    );
    await expect(fetchReportsCatalog('tok')).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
    });
    expect(new ApiError(404).status).toBe(404);
  });
});
