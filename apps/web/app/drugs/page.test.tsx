// @vitest-environment happy-dom

import { ThemeProvider } from '@pharmatag/ui';
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DrugsPage from './page';

vi.mock('next/navigation', () => ({
  usePathname: () => '/drugs',
  useRouter: () => ({ push: vi.fn() }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const LIST = {
  branch: { id: 1, pharmacyid: 'MAIN', pharname: 'Main Pharmacy' },
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
      price: '12.50',
      price_now: '12.50',
      tax_type: 'exempt',
      vat: '0.00',
      active: true,
    },
  ],
};

const EMPTY_LIST = { branch: { id: 1, pharmacyid: 'MAIN', pharname: 'Main Pharmacy' }, drugs: [] };

const LOGIN_OK = {
  access_token: 'tok-1',
  refresh_token: 'r-1',
  token_type: 'bearer',
  must_reset_password: false,
  user: { id: 1, username: 'admin', namee: '', permission_level: 9, branch_id: 1 },
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

function setInputValue(el: Element, value: string) {
  const input = el as HTMLInputElement;
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(input, value);
  act(() => {
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

function setCredentials(username: string, password: string) {
  const [userField, passField] = [...host.querySelectorAll('input')];
  if (!userField || !passField) throw new Error('login form inputs missing');
  setInputValue(userField, username);
  setInputValue(passField, password);
}

function setResetPasswords(newPass: string, confirm: string, oldPass?: string) {
  const inputs = [...host.querySelectorAll('input')];
  if (inputs.length !== 3) throw new Error(`expected 3 reset-form inputs, got ${inputs.length}`);
  const [oldField, newField, confirmField] = inputs;
  if (!oldField || !newField || !confirmField) throw new Error('reset-form inputs missing');
  if (oldPass !== undefined) setInputValue(oldField, oldPass);
  setInputValue(newField, newPass);
  setInputValue(confirmField, confirm);
}

async function click(text: string) {
  await act(async () => {
    buttonByText(text).click();
  });
}

describe('DrugsPage', () => {
  it('shows the login form when no token is stored', async () => {
    await render(<DrugsPage />);
    expect(textOf()).toContain('تسجيل الدخول');
    expect(textOf()).not.toContain('بانادول إكسترا');
  });

  it('renders the drug table for a stored valid token', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(LIST)),
    );
    await render(<DrugsPage />);
    expect(textOf()).toContain('بانادول إكسترا');
    expect(textOf()).toContain('12.50');
    expect(textOf()).toContain('تسجيل الخروج');
  });

  it('shows the empty-catalog state', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(EMPTY_LIST)),
    );
    await render(<DrugsPage />);
    expect(textOf()).toContain('لا توجد أدوية مفعّلة');
  });

  it('clears a stale 401 token and returns to login', async () => {
    window.localStorage.setItem('pharmatag:token', 'stale');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({}, 401)),
    );
    await render(<DrugsPage />);
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('تسجيل الدخول');
  });

  it('logs in via the form and shows the drug table', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'changeme');
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(LOGIN_OK))
        .mockResolvedValueOnce(jsonResponse(LIST)),
    );
    await click('دخول');
    expect(textOf()).toContain('بانادول إكسترا');
  });

  it('blocks navigation and shows the forced password-reset form when the password must be reset', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'changeme');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ ...LOGIN_OK, must_reset_password: true, access_token: 'tok-x' }),
      ),
    );
    await click('دخول');
    expect(textOf()).toContain('يجب تغيير كلمة المرور الافتراضية');
    expect(textOf()).not.toContain('بانادول إكسترا');
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(host.querySelectorAll('input')).toHaveLength(3);
  });

  it('completes login after a forced reset sets a new password', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'changeme');
    const login = jsonResponse({ ...LOGIN_OK, must_reset_password: true, access_token: 'tok-x' });
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(login)
        .mockResolvedValueOnce(jsonResponse({ ok: true }))
        .mockResolvedValueOnce(jsonResponse(LIST)),
    );
    await click('دخول');
    setResetPasswords('NewPass123!', 'NewPass123!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('بانادول إكسترا');
    expect(window.localStorage.getItem('pharmatag:token')).toBe('tok-x');
  });

  it('surfaces a wrong old password as 401 on the forced-reset form', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'changeme');
    const login = jsonResponse({ ...LOGIN_OK, must_reset_password: true, access_token: 'tok-x' });
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(login)
        .mockResolvedValueOnce(jsonResponse({ detail: 'Old password is incorrect' }, 401)),
    );
    await click('دخول');
    setResetPasswords('NewPass123!', 'NewPass123!', 'wrong');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('كلمة المرور الحالية غير صحيحة');
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).not.toContain('بانادول إكسترا');
  });

  it('surfaces a rejected new password as 400 on the forced-reset form', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'changeme');
    const login = jsonResponse({ ...LOGIN_OK, must_reset_password: true, access_token: 'tok-x' });
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(login)
        .mockResolvedValueOnce(jsonResponse({ detail: 'must differ' }, 400)),
    );
    await click('دخول');
    setResetPasswords('NewPass123!', 'NewPass123!', 'OldPass123');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('كلمة المرور الجديدة مرفوضة');
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
  });

  it('surfaces a connectivity failure on the forced-reset form', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'changeme');
    const login = jsonResponse({ ...LOGIN_OK, must_reset_password: true, access_token: 'tok-x' });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(login).mockRejectedValueOnce(new TypeError('fetch failed')),
    );
    await click('دخول');
    setResetPasswords('NewPass123!', 'NewPass123!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('تعذّر الاتصال بالـ API');
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
  });

  it('does not strand the user on the reset form when the post-reset drug fetch fails', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'changeme');
    const login = jsonResponse({ ...LOGIN_OK, must_reset_password: true, access_token: 'tok-x' });
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(login)
        .mockResolvedValueOnce(jsonResponse({ ok: true }))
        .mockRejectedValueOnce(new TypeError('fetch failed')),
    );
    await click('دخول');
    setResetPasswords('NewPass123!', 'NewPass123!');
    await click('تغيير وحفظ');
    // password changed + token saved: not stuck on the reset form, and the
    // form's old password is no longer offered as a retry target.
    expect(window.localStorage.getItem('pharmatag:token')).toBe('tok-x');
    expect(host.querySelectorAll('input')).toHaveLength(0);
    expect(textOf()).toContain('تعذّر جلب قائمة الأدوية');
  });

  it('validates the new password client-side before calling the API', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'changeme');
    const fetchMock = vi.fn(async () =>
      jsonResponse({ ...LOGIN_OK, must_reset_password: true, access_token: 'tok-x' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await click('دخول');

    setResetPasswords('Short1!', 'Short1!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('8 أحرف على الأقل');

    setResetPasswords('changeme', 'changeme');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('لا تُقبل ككلمة مرور جديدة');

    setResetPasswords('NewPass123!', 'Mismatch456!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('غير متطابقتين');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
  });

  it('shows an invalid-credentials message on 401', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'wrong');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({}, 401)),
    );
    await click('دخول');
    expect(textOf()).toContain('بيانات الدخول غير صحيحة');
  });

  it('shows a connectivity message on network failure, distinct from bad credentials', async () => {
    await render(<DrugsPage />);
    setCredentials('admin', 'changeme');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Promise.reject(new TypeError('fetch failed'))),
    );
    await click('دخول');
    expect(textOf()).toContain('تعذّر الاتصال بالـ API');
  });

  it('logs out and returns to the login form', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(LIST)),
    );
    await render(<DrugsPage />);
    await click('تسجيل الخروج');
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('تسجيل الدخول');
  });
});
