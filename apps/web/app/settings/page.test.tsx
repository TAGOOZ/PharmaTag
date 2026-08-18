// @vitest-environment happy-dom

import { ThemeProvider } from '@pharmatag/ui';
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsPage from './page';

vi.mock('next/navigation', () => ({
  usePathname: () => '/settings',
  useRouter: () => ({ push: vi.fn() }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

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

function setPasswords(oldPass: string, newPass: string, confirm: string) {
  const inputs = [...host.querySelectorAll('input')];
  if (inputs.length !== 3) throw new Error(`expected 3 password inputs, got ${inputs.length}`);
  const [oldField, newField, confirmField] = inputs;
  if (!oldField || !newField || !confirmField) throw new Error('password inputs missing');
  setInputValue(oldField, oldPass);
  setInputValue(newField, newPass);
  setInputValue(confirmField, confirm);
}

async function click(text: string) {
  await act(async () => {
    buttonByText(text).click();
  });
}

describe('SettingsPage', () => {
  it('asks for a sign-in when no token is stored', async () => {
    await render(<SettingsPage />);
    expect(textOf()).toContain('سجّل الدخول أولاً');
    expect(host.querySelectorAll('input')).toHaveLength(0);
  });

  it('shows the change-password form for a logged-in admin', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    await render(<SettingsPage />);
    expect(textOf()).toContain('تغيير كلمة المرور');
    expect(host.querySelectorAll('input')).toHaveLength(3);
  });

  it('changes the password and confirms success', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ ok: true })),
    );
    await render(<SettingsPage />);
    setPasswords('OldPass123', 'NewPass123!', 'NewPass123!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('تم تغيير كلمة المرور بنجاح');
  });

  it('surfaces a wrong current password as 401', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'Old password is incorrect' }, 401)),
    );
    await render(<SettingsPage />);
    setPasswords('wrong', 'NewPass123!', 'NewPass123!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('كلمة المرور الحالية غير صحيحة');
    expect(textOf()).not.toContain('تم تغيير كلمة المرور بنجاح');
  });

  it('surfaces a rejected new password as 400', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'must differ' }, 400)),
    );
    await render(<SettingsPage />);
    setPasswords('OldPass123', 'NewPass123!', 'NewPass123!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('كلمة المرور الجديدة مرفوضة');
    expect(textOf()).not.toContain('تم تغيير كلمة المرور بنجاح');
  });

  it('surfaces a connectivity failure distinctly', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Promise.reject(new TypeError('fetch failed'))),
    );
    await render(<SettingsPage />);
    setPasswords('OldPass123', 'NewPass123!', 'NewPass123!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('تعذّر الاتصال بالـ API');
    expect(textOf()).not.toContain('تم تغيير كلمة المرور بنجاح');
  });

  it('validates the new password client-side before calling the API', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    await render(<SettingsPage />);

    setPasswords('OldPass123', 'Short1!', 'Short1!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('8 أحرف على الأقل');

    setPasswords('OldPass123', 'OldPass123', 'OldPass123');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('تختلف عن الحالية');

    setPasswords('OldPass123', 'NewPass123!', 'Mismatch456!');
    await click('تغيير وحفظ');
    expect(textOf()).toContain('غير متطابقتين');

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
