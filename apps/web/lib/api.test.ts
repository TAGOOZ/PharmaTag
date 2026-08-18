import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  clearToken,
  fetchDrugs,
  loadToken,
  login,
  resetPassword,
  saveToken,
} from './api';

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

describe('resetPassword client', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts old+new password with the bearer token and resolves on success', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init: RequestInit) =>
      jsonResponse({ ok: true }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await resetPassword('tok-9', 'changeme', 'NewPass123!');
    const call = fetchMock.mock.calls[0];
    if (!call) throw new Error('resetPassword did not call fetch');
    const [url, init] = call;
    const headers = init.headers as Record<string, string>;
    expect(url).toContain('/api/v1/auth/reset-password');
    expect(headers.Authorization).toBe('Bearer tok-9');
    expect(JSON.parse(init.body as string)).toEqual({
      old_password: 'changeme',
      new_password: 'NewPass123!',
    });
  });

  it('surfaces 401 for a wrong old password', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'Old password is incorrect' }, 401)),
    );
    await expect(resetPassword('tok', 'wrong', 'NewPass123!')).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
    });
  });

  it('surfaces 400 for a rejected new password (weak default / same as old)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'must differ' }, 400)),
    );
    await expect(resetPassword('tok', 'changeme', 'changeme')).rejects.toMatchObject({
      name: 'ApiError',
      status: 400,
    });
  });

  it('surfaces a network failure as a plain error (no status)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Promise.reject(new TypeError('fetch failed'))),
    );
    await expect(resetPassword('tok', 'changeme', 'NewPass123!')).rejects.not.toBeInstanceOf(
      ApiError,
    );
  });
});
