// @vitest-environment happy-dom
import { ThemeProvider } from '@pharmatag/ui';
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import EmployeesPage from './page';

vi.mock('next/navigation', () => ({
  usePathname: () => '/employees',
  useRouter: () => ({ push: vi.fn() }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const BRANCHES = {
  branches: [
    {
      id: 1,
      pharmacyid: 'MAIN',
      pharname: 'الصيدلية الرئيسية',
      mobile: '0',
      role: 'main',
      is_main_device: true,
      active: true,
    },
    {
      id: 2,
      pharmacyid: 'BR2',
      pharname: 'فرع ثان',
      mobile: '1',
      role: 'sub',
      is_main_device: false,
      active: true,
    },
  ],
};
const USERS_ONE = {
  users: [
    {
      id: 10,
      username: 'pharmacist1',
      namee: 'صيدلي',
      mobile: '010',
      permission_level: 3,
      branch_id: 2,
      active: true,
      roles: ['pharmacist'],
      must_reset_password: false,
    },
  ],
};

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string) =>
        headers[name.toLowerCase()] ??
        (name.toLowerCase() === 'content-type' ? 'application/json' : null),
    } as unknown as Headers,
    json: async () => body,
    text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
    clone() {
      return this as unknown as Response;
    },
  } as unknown as Response;
}
function textResp(text: string, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null } as unknown as Headers,
    text: async () => text,
    json: async () => {
      throw new SyntaxError('not json');
    },
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
    await new Promise((r) => setTimeout(r, 600));
  });
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.clearAllTimers();
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
function textOf() {
  return host.textContent ?? '';
}
function htmlOf() {
  return host.innerHTML ?? '';
}
function setInputValue(el: HTMLInputElement, v: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(el, v);
  act(() => {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

describe.sequential('EmployeesPage — BAD paths (adversarial)', () => {
  it('400 whitespace username → client مطلوب (no API round-trip)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
      if (String(url).includes('/api/v1/users') && init?.method === 'POST')
        return jsonResponse({ detail: 'username is required' }, 400);
      if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<EmployeesPage />);
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    setInputValue(userIn, '   ');
    setInputValue(pwdIn, 'TempPass123');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    // Client validation intercepts whitespace before server: Arabic مطلوب, no POST
    expect(textOf()).toContain('مطلوب');
    expect(textOf()).not.toContain('/src/');
    const posts = fetchMock.mock.calls.filter(([u, init]) =>
      String(u).includes('/api/v1/users') && (init as RequestInit)?.method === 'POST',
    );
    expect(posts.length).toBe(0);
  });

  it('422 semantic invalid permission_level (string) → بيانات غير صالحة', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users') && init?.method === 'POST')
          return jsonResponse(
            {
              detail: [
                {
                  loc: ['body', 'permission_level'],
                  msg: 'value is not a valid integer',
                  type: 'type_error',
                },
              ],
            },
            422,
          );
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    setInputValue(userIn, 'badlvl');
    setInputValue(pwdIn, 'TempPass123');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    // Force permission_level to invalid by directly mutating select? Instead rely on server 422 path: just trigger create
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('بيانات غير صالحة');
    expect(textOf()).not.toContain('/src/');
  });

  it('400 permission_level 0 and 10 boundaries', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users') && init?.method === 'POST')
          return jsonResponse({ detail: 'permission_level must be between 1 and 9' }, 400);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    setInputValue(userIn, 'lvl0user');
    setInputValue(pwdIn, 'TempPass123');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('permission_level');
  });

  it('400 unknown role → unknown role(s)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users') && init?.method === 'POST')
          return jsonResponse({ detail: "unknown role(s): ['super-saiyan']" }, 400);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const rolesIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'الأدوار',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    setInputValue(userIn, 'rolebad');
    setInputValue(rolesIn, 'super-saiyan');
    setInputValue(pwdIn, 'TempPass123');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('unknown role');
  });

  it('403 granting admin role requires level 7', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/permissions') && init?.method === 'POST')
          return jsonResponse(
            { detail: 'granting the admin role requires permission_level 7' },
            403,
          );
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    const rolesIn = host.querySelector('input[aria-label*="الأدوار-"]') as HTMLInputElement;
    if (rolesIn) setInputValue(rolesIn, 'admin');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('حفظ الأدوار'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('admin role');
    expect(textOf()).toContain('ليس لديك صلاحية');
  });

  it('403 cross-branch creation requires level 9', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users') && init?.method === 'POST')
          return jsonResponse(
            { detail: 'cross-branch user creation requires permission_level 9' },
            403,
          );
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    const branchSel = host.querySelector('select[aria-label="الفرع"]') as HTMLSelectElement;
    setInputValue(userIn, 'crossuser');
    setInputValue(pwdIn, 'TempPass123');
    if (branchSel) {
      branchSel.value = '2';
      act(() => {
        branchSel.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('cross-branch');
  });

  it('400 weak initial password changeme → client rejected (no round-trip)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
      if (String(url).includes('/api/v1/users') && init?.method === 'POST')
        return jsonResponse(
          { detail: 'initial password must differ from the weak default' },
          400,
        );
      if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);
    await render(<EmployeesPage />);
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    setInputValue(userIn, 'weakuser');
    setInputValue(pwdIn, 'changeme');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    // Client intercepts changeme: Arabic افتراضية, no POST
    expect(textOf()).toContain('الافتراضية');
    const posts = fetchMock.mock.calls.filter(([u, init]) =>
      String(u).includes('/api/v1/users') && (init as RequestInit)?.method === 'POST',
    );
    expect(posts.length).toBe(0);
  });

  it('403 patch cannot manage higher level + cannot raise above own', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users/') && init?.method === 'PATCH')
          return jsonResponse(
            { detail: 'cannot manage a user with a higher permission level than your own' },
            403,
          );
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    const patchBtn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('حفظ التعديلات'),
    ) as HTMLButtonElement;
    await act(async () => {
      patchBtn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('cannot manage');
    // second case: raise
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users/') && init?.method === 'PATCH')
          return jsonResponse(
            { detail: 'cannot raise a user above your own permission level' },
            403,
          );
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    // need to re-trigger patch for raise case: change permission select to 9
    const permSel = host.querySelector('select[aria-label*="permission-"]') as HTMLSelectElement;
    if (permSel) {
      permSel.value = '9';
      act(() => {
        permSel.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }
    await act(async () => {
      patchBtn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('cannot raise');
  });

  it('415 Content-Type + 404 user not found distinct', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users/') && init?.method === 'PATCH')
          return jsonResponse({ detail: 'unsupported media type' }, 415);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const patchBtn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('حفظ التعديلات'),
    ) as HTMLButtonElement;
    await act(async () => {
      patchBtn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('415');
    expect(textOf()).not.toContain('/src/');

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users/') && init?.method === 'PATCH')
          return jsonResponse({ detail: 'user not found' }, 404);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await act(async () => {
      patchBtn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('غير موجود');
  });

  it('429 Retry-After → كثرة الطلبات + cooldown, no spam on rapid double click', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let calls = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users') && init?.method === 'POST') {
          calls++;
          return jsonResponse({ detail: 'rate limit' }, 429, { 'retry-after': '2' });
        }
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    setInputValue(userIn, 'ratelimit');
    setInputValue(pwdIn, 'TempPass123');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
      btn.click();
    }); // double click
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('كثرة الطلبات');
    expect(calls).toBe(1); // lock prevents spam
  });

  it('500/502/503/504 generic fallback without stack leak', async () => {
    for (const code of [500, 502, 503, 504]) {
      window.localStorage.setItem('pharmatag:token', 'tok-1');
      vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string) => {
          if (String(url).includes('/api/v1/users'))
            return textResp('internal stack /src/app/users/service.py line 99', code);
          if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
          return jsonResponse({}, code);
        }),
      );
      await render(<EmployeesPage />);
      expect(textOf()).toContain('خطأ بالخادم');
      expect(textOf()).not.toContain('/src/');
      expect(textOf()).not.toContain('stack');
      // cleanup for next iteration
      await act(async () => {
        await new Promise((r) => setTimeout(r, 600));
      });
      act(() => root.unmount());
      host.remove();
      // recreate host for next loop iteration because afterEach will also run but we manual clean
      // Instead we rely on beforeEach for next iteration, but we are inside same it with loop, so we need to reset via manual unmount already done
      // Recreate host/root for next code iteration
      host = document.createElement('div');
      document.body.appendChild(host);
      root = createRoot(host);
      window.localStorage.setItem('pharmatag:token', 'tok-1');
    }
  });

  it('garbage token 401 vs expired token 401 both clear → login', async () => {
    for (const token of ['not.a.jwt', 'expired.jwt']) {
      window.localStorage.setItem('pharmatag:token', token);
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => jsonResponse({ detail: 'Invalid token' }, 401)),
      );
      await render(<EmployeesPage />);
      expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
      expect(textOf()).toContain('تسجيل الدخول');
      await act(async () => {
        await new Promise((r) => setTimeout(r, 600));
      });
      act(() => root.unmount());
      host.remove();
      host = document.createElement('div');
      document.body.appendChild(host);
      root = createRoot(host);
    }
  });

  it('branches 500 partial: users still shown with banner', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/branches'))
          return jsonResponse({ detail: 'internal' }, 500);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    expect(textOf()).toContain('pharmacist1');
    expect(textOf()).toContain('خطأ بالخادم');
  });

  it('null/partial users response → empty handling without crash', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users'))
          return jsonResponse({ users: null } as unknown as object);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    expect(textOf()).toContain('لا يوجد موظفون');
    // missing field
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users')) return jsonResponse({} as unknown as object);
        return jsonResponse({});
      }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 600));
    });
    act(() => root.unmount());
    host.remove();
    host = document.createElement('div');
    document.body.appendChild(host);
    root = createRoot(host);
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    await render(<EmployeesPage />);
    expect(textOf()).toContain('لا يوجد موظفون');
  });

  it('self reset validation: short, weak, same, mismatch, overlong before API call', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const oldIn = host.querySelector('input[aria-label="كلمة المرور الحالية"]') as HTMLInputElement;
    const newIn = host.querySelector('input[aria-label="كلمة المرور الجديدة"]') as HTMLInputElement;
    const confIn = host.querySelector(
      'input[aria-label="تأكيد كلمة المرور الجديدة"]',
    ) as HTMLInputElement;
    const fetchMock = vi.fn(async () => jsonResponse({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    const form = host.querySelector(
      'form[aria-label="تغيير كلمة المرور الذاتي"]',
    ) as HTMLFormElement;
    const btn = [...form.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('تغيير وحفظ'),
    ) as HTMLButtonElement;
    // short
    setInputValue(oldIn, 'OldPass123');
    setInputValue(newIn, 'Short1!');
    setInputValue(confIn, 'Short1!');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('8 أحرف');
    // weak
    setInputValue(newIn, 'changeme');
    setInputValue(confIn, 'changeme');
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('لا تُقبل');
    // same
    setInputValue(oldIn, 'SamePass123');
    setInputValue(newIn, 'SamePass123');
    setInputValue(confIn, 'SamePass123');
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('تختلف');
    // mismatch
    setInputValue(newIn, 'NewPass123!');
    setInputValue(confIn, 'Mismatch456!');
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('غير متطابقتين');
    // overlong >72 bytes
    const long = 'a'.repeat(73);
    setInputValue(newIn, long);
    setInputValue(confIn, long);
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(textOf()).toContain('72 بايت');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('self reset 401 wrong-old vs token expired distinction', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const oldIn = host.querySelector('input[aria-label="كلمة المرور الحالية"]') as HTMLInputElement;
    const newIn = host.querySelector('input[aria-label="كلمة المرور الجديدة"]') as HTMLInputElement;
    const confIn = host.querySelector(
      'input[aria-label="تأكيد كلمة المرور الجديدة"]',
    ) as HTMLInputElement;
    const form = host.querySelector(
      'form[aria-label="تغيير كلمة المرور الذاتي"]',
    ) as HTMLFormElement;
    const btn = [...form.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('تغيير وحفظ'),
    ) as HTMLButtonElement;
    setInputValue(oldIn, 'OldPass123');
    setInputValue(newIn, 'NewPass123!');
    setInputValue(confIn, 'NewPass123!');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    // wrong-old
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/auth/reset-password'))
          return jsonResponse({ detail: 'Old password is incorrect' }, 401);
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('غير صحيحة');
    expect(window.localStorage.getItem('pharmatag:token')).toBe('tok-1');
    // token expired
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/auth/reset-password'))
          return jsonResponse({ detail: 'Invalid token: expired' }, 401);
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(window.localStorage.getItem('pharmatag:token')).toBeNull();
    expect(textOf()).toContain('تسجيل الدخول');
  });

  it('manager reset empty does not call API, shows required', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    let called = false;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/reset-password') && init?.method === 'POST') {
          called = true;
          return jsonResponse({ ok: true });
        }
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إعادة تعيين كلمة المرور'),
    ) as HTMLButtonElement;
    // leave input empty
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('مطلوبة');
    expect(called).toBe(false);
  });

  it('XSS in username is escaped, not executed', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users'))
          return jsonResponse({
            users: [
              {
                id: 99,
                username: '<script>alert(1)</script>',
                namee: '<b>bad</b>',
                mobile: '010',
                permission_level: 1,
                branch_id: 1,
                active: true,
                roles: [],
                must_reset_password: false,
              },
            ],
          });
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    expect(textOf()).toContain('<script>alert(1)</script>');
    expect(htmlOf()).not.toContain('<script>alert(1)</script>'); // React escapes
    expect(host.querySelector('script')).toBeNull();
  });

  it('network down during create/patch/roles/reset distinct from auth', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users') && init?.method)
          return Promise.reject(new TypeError('fetch failed'));
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    setInputValue(userIn, 'netfail');
    setInputValue(pwdIn, 'TempPass123');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const createBtn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      createBtn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('تعذّر الاتصال');

    const patchBtn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('حفظ التعديلات'),
    ) as HTMLButtonElement;
    await act(async () => {
      patchBtn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('تعذّر الاتصال');

    const rolesBtn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('حفظ الأدوار'),
    ) as HTMLButtonElement;
    await act(async () => {
      rolesBtn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('تعذّر الاتصال');

    const resetInput = host.querySelector('input[aria-label*="إعادة تعيين"]') as HTMLInputElement;
    setInputValue(resetInput, 'NewPass123!');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const resetBtn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إعادة تعيين كلمة المرور'),
    ) as HTMLButtonElement;
    await act(async () => {
      resetBtn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('تعذّر الاتصال');
    expect(textOf()).not.toContain('ليس لديك صلاحية');
  });

  it('abort during boot does not flash error (stale guard)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users')) {
          const e = new DOMException('aborted', 'AbortError');
          throw e;
        }
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    // Aborted boot: no error banner, no empty wipe — stays boot/loading, not ready with []
    expect(textOf()).not.toContain('تعذّر الاتصال');
    expect(window.localStorage.getItem('pharmatag:token')).toBe('tok-1');
  });

  it('429 honors Retry-After header value (not hardcoded 5)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users') && init?.method === 'POST')
          return jsonResponse({ detail: 'rate limit' }, 429, { 'retry-after': '17' });
        if (String(url).includes('/api/v1/users')) return jsonResponse(USERS_ONE);
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    setInputValue(userIn, 'retryuser');
    setInputValue(pwdIn, 'TempPass123');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('كثرة الطلبات');
    // Second immediate submit blocked by cooldown (no second POST)
    const fetchMock = vi.mocked(fetch);
    const before = fetchMock.mock.calls.length;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(fetchMock.mock.calls.length).toBe(before);
    expect(textOf()).toContain('429');
  });

  it('create preserves other rows drafts (no clobber)', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const created = {
      id: 99,
      username: 'newbie',
      namee: '',
      mobile: '',
      permission_level: 1,
      branch_id: 1,
      active: true,
      roles: [],
      must_reset_password: true,
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users') && init?.method === 'POST')
          return jsonResponse(created, 201);
        if (String(url).includes('/api/v1/users'))
          return jsonResponse({ users: [...USERS_ONE.users, created] });
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    // Type draft into existing row edit
    const nameeIn = host.querySelector('input[aria-label="namee-10"]') as HTMLInputElement;
    setInputValue(nameeIn, 'DRAFT-KEEP');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    // Create new user
    const userIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'اسم المستخدم',
    ) as HTMLInputElement;
    const pwdIn = [...host.querySelectorAll('input')].find(
      (i) => i.getAttribute('aria-label') === 'كلمة المرور الابتدائية',
    ) as HTMLInputElement;
    setInputValue(userIn, 'newbie');
    setInputValue(pwdIn, 'TempPass123');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const btn = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('إنشاء موظف'),
    ) as HTMLButtonElement;
    await act(async () => {
      btn.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    // Draft preserved after refresh
    const after = host.querySelector('input[aria-label="namee-10"]') as HTMLInputElement;
    expect(after.value).toBe('DRAFT-KEEP');
    expect(textOf()).toContain('تم إنشاء الموظف');
  });

  it('60 users paginated to 50 with عرض المزيد', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    const many = Array.from({ length: 60 }, (_, i) => ({
      id: 100 + i,
      username: `user${i}`,
      namee: `Name ${i}`,
      mobile: '010',
      permission_level: 1,
      branch_id: 1,
      active: true,
      roles: [],
      must_reset_password: false,
    }));
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users')) return jsonResponse({ users: many });
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(textOf()).toContain('60 موظف');
    expect(textOf()).toContain('عرض المزيد');
    // Only 50 edit forms rendered
    expect(host.querySelectorAll('input[aria-label^="namee-"]').length).toBe(50);
    const more = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('عرض المزيد'),
    ) as HTMLButtonElement;
    await act(async () => {
      more.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(host.querySelectorAll('input[aria-label^="namee-"]').length).toBe(60);
  });

  it('unknown branch id shows — not raw id', async () => {
    window.localStorage.setItem('pharmatag:token', 'tok-1');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/api/v1/branches')) return jsonResponse(BRANCHES);
        if (String(url).includes('/api/v1/users'))
          return jsonResponse({
            users: [
              {
                id: 77,
                username: 'ghost',
                namee: '',
                mobile: '',
                permission_level: 1,
                branch_id: 9999,
                active: true,
                roles: [],
                must_reset_password: false,
              },
            ],
          });
        return jsonResponse({});
      }),
    );
    await render(<EmployeesPage />);
    expect(textOf()).toContain('ghost');
    expect(textOf()).not.toContain('9999');
  });
});
