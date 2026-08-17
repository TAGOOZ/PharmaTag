import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, clearToken, fetchDrugs, loadToken, login, saveToken } from './api';

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe('api client auth discrimination', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('login throws ApiError(401) for bad credentials, not a network error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'Invalid' }, 401)),
    );
    await expect(login('admin', 'wrong')).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
    });
  });

  it('login surfaces a network failure as a plain error (no status)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Promise.reject(new TypeError('fetch failed'))),
    );
    await expect(login('admin', 'changeme')).rejects.not.toBeInstanceOf(ApiError);
  });

  it('fetchDrugs throws ApiError(401) for a stale token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({}, 401)),
    );
    await expect(fetchDrugs('stale-token')).rejects.toMatchObject({ status: 401 });
  });

  it('token helpers persist across save/load/clear', () => {
    expect(loadToken()).toBeNull();
    saveToken('abc.def');
    expect(loadToken()).toBe('abc.def');
    clearToken();
    expect(loadToken()).toBeNull();
  });
});
