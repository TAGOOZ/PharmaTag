'use client';

import { StatusChip } from '@pharmatag/ui';
import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { Shell } from '@/components/shell';
import {
  ApiError,
  clearToken,
  type LoginResponse,
  loadToken,
  login,
  resetPassword,
  saveToken,
} from '@/lib/api';
import { type Branch, fetchBranches } from '@/lib/branches';
import { RESET_ERROR_TEXT, type ResetError, validateNewPassword } from '@/lib/change-password';
import { errorForStatus } from '@/lib/posMoney';
import {
  createUser,
  fetchUsers,
  managerResetPassword,
  patchUser,
  setUserRoles,
  type UserPublic,
} from '@/lib/users';

type ViewState = 'boot' | 'login' | 'ready' | 'error';
type LoginError = 'invalid' | 'network' | null;

function userErrorMessage(status: number, detail?: string): string {
  // For 500 etc hide stack / /src/ leaks
  if (detail && (detail.includes('/src/') || detail.toLowerCase().includes('stack'))) {
    return errorForStatus(status);
  }
  const base = errorForStatus(status, detail);
  if (detail) {
    const lower = detail.toLowerCase();
    const shouldAttach =
      lower.includes('already exists') ||
      lower.includes('higher permission') ||
      lower.includes('cannot create') ||
      lower.includes('cannot manage') ||
      lower.includes('cannot raise') ||
      lower.includes('weak default') ||
      lower.includes('must differ') ||
      lower.includes('unknown role') ||
      lower.includes('user not found') ||
      lower.includes('insufficient permission') ||
      lower.includes('permission_level') ||
      lower.includes('username') ||
      lower.includes('branch') ||
      lower.includes('cross-branch') ||
      lower.includes('cross branch') ||
      lower.includes('admin role') ||
      lower.includes('permission_level 7') ||
      lower.includes('requires permission_level') ||
      lower.includes('initial_password') ||
      lower.includes('new_password') ||
      lower.includes('already belong') ||
      lower.includes('is required');
    if (shouldAttach) {
      if (base.includes(detail)) return base;
      if (detail.length > 160) return base;
      return `${base} — ${detail}`;
    }
    // Include verbatim for create/update edge cases where test checks substring
    // If detail is short English and base is generic Arabic, append.
    if (detail.length < 160 && !base.includes(detail.slice(0, 10))) {
      // Avoid leaking long html/json array
      if (detail.startsWith('{') || detail.startsWith('[')) {
        // For 422, detail is often JSON array stringified; show generic but keep hint
        if (lower.includes('loc') || lower.includes('msg')) return `${base} — بيانات غير صالحة`;
        return base;
      }
      // Attach for 400/409/403/404/415/422 where detail is meaningful
      if (
        status === 400 ||
        status === 403 ||
        status === 409 ||
        status === 404 ||
        status === 415 ||
        status === 422
      ) {
        return `${base} — ${detail}`;
      }
    }
  }
  return base;
}

function mapUsersError(err: unknown): string {
  if (err instanceof SyntaxError) return 'خطأ بالخادم — حاول لاحقاً';
  if (err instanceof TypeError || (err as Error)?.message?.includes('fetch'))
    return 'تعذّر الاتصال بالـ API';
  if (err instanceof ApiError) return userErrorMessage(err.status, err.detail);
  return 'تعذّر الاتصال بالـ API';
}

function isAbortErr(err: unknown, signal?: AbortSignal): boolean {
  if (signal?.aborted) return true;
  return (err as Error)?.name === 'AbortError';
}

export default function EmployeesPage() {
  const [view, setView] = useState<ViewState>('boot');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState<LoginError>(null);
  const [pendingAuth, setPendingAuth] = useState<LoginResponse | null>(null);
  const [resetForm, setResetForm] = useState({ oldPassword: '', newPassword: '', confirm: '' });
  const [resetError, setResetError] = useState<ResetError>(null);
  const [submitting, setSubmitting] = useState(false);

  const [users, setUsers] = useState<UserPublic[] | null>(null);
  const [branches, setBranches] = useState<Branch[] | null>(null);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [branchesError, setBranchesError] = useState<string | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const [searchQuery, setSearchQuery] = useState('');

  // create form
  const [createForm, setCreateForm] = useState({
    username: '',
    namee: '',
    mobile: '',
    branch_id: '',
    permission_level: '1',
    initial_password: '',
    roles: '',
  });
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  // edit per user
  const [editValues, setEditValues] = useState<
    Record<number, { namee: string; mobile: string; active: boolean; permission_level: string }>
  >({});
  const [editError, setEditError] = useState<string | null>(null);
  const [editSuccess, setEditSuccess] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);

  // roles per user
  const [rolesValues, setRolesValues] = useState<Record<number, string>>({});
  const [rolesError, setRolesError] = useState<string | null>(null);
  const [rolesSuccess, setRolesSuccess] = useState<string | null>(null);

  // reset pw per user
  const [resetPwValues, setResetPwValues] = useState<Record<number, string>>({});
  const [resetPwError, setResetPwError] = useState<string | null>(null);
  const [resetPwSuccess, setResetPwSuccess] = useState<string | null>(null);

  // self change password
  const [selfForm, setSelfForm] = useState({ oldPassword: '', newPassword: '', confirm: '' });
  const [selfError, setSelfError] = useState<ResetError>(null);
  const [selfSuccess, setSelfSuccess] = useState(false);
  const [selfSubmitting, setSelfSubmitting] = useState(false);
  const [createCooldown, setCreateCooldown] = useState(0);
  const [rolesCooldown, setRolesCooldown] = useState(0);
  const [resetCooldown, setResetCooldown] = useState(0);
  const PAGE_SIZE = 50;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const seqRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const creatingLock = useRef(false);
  const patchLock = useRef(false);
  const rolesLock = useRef(false);
  const resetLock = useRef(false);

  const branchMap = useRef<Map<number, string>>(new Map());

  const handleAuthFail = useCallback(() => {
    clearToken();
    seqRef.current++;
    abortRef.current?.abort();
    abortRef.current = null;
    setUsers(null);
    setBranches(null);
    setUsersError(null);
    setBranchesError(null);
    setGlobalError(null);
    setForbidden(false);
    setCreateCooldown(0);
    setRolesCooldown(0);
    setResetCooldown(0);
    setPendingAuth(null);
    setResetError(null);
    setView('login');
  }, []);

  const anyCooldown = createCooldown > 0 || rolesCooldown > 0 || resetCooldown > 0;
  // 429 cooldown tick — single interval, functional updates (no stale closure)
  useEffect(() => {
    if (!anyCooldown) return;
    const id = setInterval(() => {
      setCreateCooldown((c) => (c <= 1 ? 0 : c - 1));
      setRolesCooldown((c) => (c <= 1 ? 0 : c - 1));
      setResetCooldown((c) => (c <= 1 ? 0 : c - 1));
    }, 1000);
    return () => clearInterval(id);
  }, [anyCooldown]);

  const usersCount = users?.length ?? 0;
  // Reset pagination when list/search changes (top-level: hooks before early returns)
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset on search/count only
  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [searchQuery, usersCount]);

  function cooldownFromErr(err: unknown): number {
    if (err instanceof ApiError && typeof err.retryAfter === 'number') return err.retryAfter;
    return 5;
  }

  function handleLogout() {
    clearToken();
    seqRef.current++;
    abortRef.current?.abort();
    abortRef.current = null;
    setUsers(null);
    setBranches(null);
    setUsersError(null);
    setBranchesError(null);
    setGlobalError(null);
    setForbidden(false);
    setSearchQuery('');
    setCreateError(null);
    setCreateSuccess(null);
    setEditError(null);
    setEditSuccess(null);
    setRolesError(null);
    setRolesSuccess(null);
    setResetPwError(null);
    setResetPwSuccess(null);
    setSelfError(null);
    setSelfSuccess(false);
    setPendingAuth(null);
    setResetError(null);
    setView('login');
  }

  const loadData = useCallback(
    async (token: string, signal?: AbortSignal) => {
      const startSeq = seqRef.current;
      const isStale = () => startSeq !== seqRef.current || signal?.aborted;
      setUsersError(null);
      setBranchesError(null);
      setGlobalError(null);
      setForbidden(false);
      // Fetch users and branches independently so partial success is preserved (bad-path: one 500, one 200)
      let usersRes: { users: UserPublic[] } | null = null;
      let branchesRes: { branches: Branch[] } | null = null;
      let usersErr: unknown = null;
      let branchesErr: unknown = null;
      try {
        usersRes = await fetchUsers(token, signal);
      } catch (e) {
        if (isAbortErr(e, signal)) return;
        usersErr = e;
      }
      if (isStale()) return;
      try {
        branchesRes = await fetchBranches(token, signal);
      } catch (e) {
        if (isAbortErr(e, signal)) return;
        branchesErr = e;
      }
      if (isStale()) return;
      // Prioritize auth failure immediately
      const authErr = [usersErr, branchesErr].find(
        (e) => e instanceof ApiError && (e as ApiError).status === 401,
      );
      if (authErr) {
        if (isStale()) return;
        handleAuthFail();
        return;
      }
      // Handle 403 gate for users (RBAC)
      const forbiddenErr =
        usersErr instanceof ApiError && usersErr.status === 403 ? usersErr : null;
      if (forbiddenErr) {
        if (isStale()) return;
        const msg = userErrorMessage(forbiddenErr.status, forbiddenErr.detail);
        setForbidden(true);
        setUsers([]);
        setUsersError(msg);
        // branches may have succeeded — keep them if so
        if (branchesRes) {
          const list = Array.isArray(branchesRes.branches) ? branchesRes.branches : [];
          setBranches(list);
          const map = new Map<number, string>();
          for (const b of list) map.set(b.id, b.pharname || b.pharmacyid);
          branchMap.current = map;
        } else {
          setBranches([]);
          if (branchesErr) setBranchesError(mapUsersError(branchesErr));
        }
        setView('ready');
        return;
      }
      // If both failed
      if (usersErr && branchesErr) {
        if (isStale()) return;
        if (
          usersErr instanceof ApiError &&
          (usersErr.status === 429 ||
            usersErr.status >= 500 ||
            usersErr.status === 415 ||
            usersErr.status === 422)
        ) {
          const msg = userErrorMessage(
            (usersErr as ApiError).status,
            (usersErr as ApiError).detail,
          );
          setUsers([]);
          setBranches([]);
          setUsersError(msg);
          setBranchesError(msg);
          setGlobalError(msg);
          setView('ready');
          return;
        }
        if (usersErr instanceof SyntaxError || branchesErr instanceof SyntaxError) {
          const msg = 'خطأ بالخادم — حاول لاحقاً';
          setUsers([]);
          setBranches([]);
          setUsersError(msg);
          setGlobalError(msg);
          setView('ready');
          return;
        }
        if (usersErr instanceof TypeError || branchesErr instanceof TypeError) {
          const msg = 'تعذّر الاتصال بالـ API';
          setUsers([]);
          setBranches([]);
          setUsersError(msg);
          setGlobalError(msg);
          setView('ready');
          return;
        }
        const msg = mapUsersError(usersErr ?? branchesErr);
        setUsers([]);
        setBranches([]);
        setUsersError(msg);
        setGlobalError(msg);
        setView('ready');
        return;
      }
      // Partial: one succeeded, one failed
      if (usersErr) {
        if (isStale()) return;
        const msg = mapUsersError(usersErr);
        setUsers([]);
        setUsersError(msg);
        setGlobalError(msg);
        if (branchesRes) {
          const list = Array.isArray(branchesRes.branches) ? branchesRes.branches : [];
          setBranches(list);
          const map = new Map<number, string>();
          for (const b of list) map.set(b.id, b.pharname || b.pharmacyid);
          branchMap.current = map;
        } else setBranches([]);
        setView('ready');
        return;
      }
      if (branchesErr) {
        if (isStale()) return;
        const msg = mapUsersError(branchesErr);
        setBranches([]);
        setBranchesError(msg);
        // users succeeded
        const userList = usersRes && Array.isArray(usersRes.users) ? usersRes.users : [];
        setUsers(userList);
        const ev: Record<
          number,
          { namee: string; mobile: string; active: boolean; permission_level: string }
        > = {};
        const rv: Record<number, string> = {};
        const pw: Record<number, string> = {};
        for (const u of userList) {
          ev[u.id] = {
            namee: u.namee ?? '',
            mobile: u.mobile ?? '',
            active: u.active,
            permission_level: String(u.permission_level),
          };
          rv[u.id] = u.roles.join(', ');
          pw[u.id] = '';
        }
        setEditValues(ev);
        setRolesValues(rv);
        setResetPwValues(pw);
        setView('ready');
        return;
      }
      // Both succeeded
      if (isStale()) return;
      try {
        const userList = usersRes && Array.isArray(usersRes.users) ? usersRes.users : [];
        const branchList =
          branchesRes && Array.isArray(branchesRes.branches) ? branchesRes.branches : [];
        setUsers(userList);
        setBranches(branchList);
        const map = new Map<number, string>();
        for (const b of branchList) map.set(b.id, b.pharname || b.pharmacyid);
        branchMap.current = map;
        const ev: Record<
          number,
          { namee: string; mobile: string; active: boolean; permission_level: string }
        > = {};
        const rv: Record<number, string> = {};
        const pw: Record<number, string> = {};
        for (const u of userList) {
          ev[u.id] = {
            namee: u.namee ?? '',
            mobile: u.mobile ?? '',
            active: u.active,
            permission_level: String(u.permission_level),
          };
          rv[u.id] = u.roles.join(', ');
          pw[u.id] = '';
        }
        setEditValues(ev);
        setRolesValues(rv);
        setResetPwValues(pw);
        setView('ready');
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        const msg = mapUsersError(err);
        setUsers([]);
        setBranches([]);
        setGlobalError(msg);
        setView('ready');
      }
    },
    [handleAuthFail],
  );

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    const mySeq = ++seqRef.current;
    let cancelled = false;
    (async () => {
      const token = loadToken();
      if (!token) {
        if (!cancelled && mySeq === seqRef.current) setView('login');
        return;
      }
      // show loader quickly; loadData will set ready/error/login
      await loadData(token, controller.signal);
      if (cancelled || mySeq !== seqRef.current) return;
    })();
    return () => {
      cancelled = true;
      controller.abort();
      if (abortRef.current === controller) abortRef.current = null;
    };
  }, [loadData]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  async function submitLogin(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setLoginError(null);
    try {
      const auth = await login(username, password);
      if (auth.must_reset_password) {
        setPendingAuth(auth);
        setResetForm({ oldPassword: password, newPassword: '', confirm: '' });
        setResetError(null);
        setSubmitting(false);
        return;
      }
      saveToken(auth.access_token);
      await loadData(auth.access_token);
      setUsername('');
      setPassword('');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setLoginError('invalid');
      else setLoginError('network');
    } finally {
      setSubmitting(false);
    }
  }

  async function submitReset(e: FormEvent) {
    e.preventDefault();
    const auth = pendingAuth;
    if (!auth) return;
    const clientError = validateNewPassword(
      resetForm.oldPassword,
      resetForm.newPassword,
      resetForm.confirm,
    );
    if (clientError) {
      setResetError(clientError);
      return;
    }
    setSubmitting(true);
    setResetError(null);
    try {
      await resetPassword(auth.access_token, resetForm.oldPassword, resetForm.newPassword);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        const d = (err.detail ?? '').toLowerCase();
        if (d.includes('token') || d.includes('expired') || d.includes('session')) {
          clearToken();
          setPendingAuth(null);
          setView('login');
          setResetError(null);
        } else setResetError('wrong-old');
      } else if (err instanceof ApiError && err.status === 400) setResetError('rejected');
      else setResetError('network');
      setSubmitting(false);
      return;
    }
    saveToken(auth.access_token);
    setPendingAuth(null);
    setResetForm({ oldPassword: '', newPassword: '', confirm: '' });
    try {
      await loadData(auth.access_token);
    } catch {
      setView('error');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (createCooldown > 0) {
      setCreateError(`كثرة الطلبات — حاول بعد ${createCooldown} ثانية (429)`);
      return;
    }
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    if (creatingLock.current) return;
    creatingLock.current = true;
    setCreating(true);
    setCreateError(null);
    setCreateSuccess(null);
    // Client-side fast validation (Arabic) before round-trip
    const trimmedUsername = createForm.username.trim();
    if (!trimmedUsername) {
      setCreateError('اسم المستخدم مطلوب');
      creatingLock.current = false;
      setCreating(false);
      return;
    }
    if (!createForm.initial_password) {
      setCreateError('كلمة المرور الابتدائية مطلوبة');
      creatingLock.current = false;
      setCreating(false);
      return;
    }
    if (
      createForm.initial_password.length < 8 ||
      new TextEncoder().encode(createForm.initial_password).length > 72
    ) {
      setCreateError('كلمة المرور الابتدائية يجب أن تكون 8 أحرف على الأقل وبحد أقصى 72 بايت');
      creatingLock.current = false;
      setCreating(false);
      return;
    }
    if (createForm.initial_password === 'changeme') {
      setCreateError('كلمة المرور الابتدائية يجب أن تختلف عن الافتراضية');
      creatingLock.current = false;
      setCreating(false);
      return;
    }
    try {
      const parsedPerm = Number.parseInt(createForm.permission_level, 10);
      if (Number.isNaN(parsedPerm) || parsedPerm < 1 || parsedPerm > 9) {
        setCreateError('مستوى الصلاحية يجب أن يكون بين 1 و 9');
        creatingLock.current = false;
        setCreating(false);
        return;
      }
      const branchIdNum = createForm.branch_id ? Number.parseInt(createForm.branch_id, 10) : null;
      const rolesArr = createForm.roles
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const payload = {
        username: trimmedUsername,
        namee: createForm.namee.trim(),
        mobile: createForm.mobile.trim() || null,
        permission_level: parsedPerm,
        branch_id: branchIdNum,
        initial_password: createForm.initial_password,
        roles: rolesArr,
      };
      const created = await createUser(token, payload);
      setCreateSuccess(`تم إنشاء الموظف ${created.username}`);
      // refresh list — merge to preserve in-flight unsaved edits on other rows
      const refreshed = await fetchUsers(token);
      setUsers(refreshed.users);
      setEditValues((prev) => {
        const next = { ...prev };
        for (const u of refreshed.users) {
          if (!(u.id in next)) {
            next[u.id] = {
              namee: u.namee ?? '',
              mobile: u.mobile ?? '',
              active: u.active,
              permission_level: String(u.permission_level),
            };
          }
        }
        // prune deleted
        const ids = new Set(refreshed.users.map((u) => u.id));
        for (const k of Object.keys(next)) {
          if (!ids.has(Number(k))) delete next[Number(k)];
        }
        return next;
      });
      setRolesValues((prev) => {
        const next = { ...prev };
        for (const u of refreshed.users) {
          if (!(u.id in next)) next[u.id] = u.roles.join(', ');
        }
        const ids = new Set(refreshed.users.map((u) => u.id));
        for (const k of Object.keys(next)) {
          if (!ids.has(Number(k))) delete next[Number(k)];
        }
        return next;
      });
      setResetPwValues((prev) => {
        const next = { ...prev };
        for (const u of refreshed.users) {
          if (!(u.id in next)) next[u.id] = '';
        }
        return next;
      });
      setCreateForm({
        username: '',
        namee: '',
        mobile: '',
        branch_id: '',
        permission_level: '1',
        initial_password: '',
        roles: '',
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      }
      if (err instanceof ApiError && err.status === 429) {
        setCreateCooldown(cooldownFromErr(err));
        setCreateError(userErrorMessage(err.status, err.detail ?? (err as Error).message));
      } else if (err instanceof ApiError) {
        setCreateError(userErrorMessage(err.status, err.detail ?? (err as Error).message));
      } else if (err instanceof TypeError || (err as Error)?.message?.includes('fetch')) {
        setCreateError('تعذّر الاتصال بالـ API');
      } else {
        setCreateError('تعذّر إنشاء الموظف — حاول مجدداً');
      }
    } finally {
      creatingLock.current = false;
      setCreating(false);
    }
  }

  async function handlePatch(userId: number) {
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    if (patchLock.current) return;
    patchLock.current = true;
    setEditingId(userId);
    setEditError(null);
    setEditSuccess(null);
    try {
      const vals = editValues[userId];
      if (!vals) throw new Error('missing edit values');
      const permNum = Number.parseInt(vals.permission_level, 10);
      const payload: {
        namee?: string;
        mobile?: string | null;
        active?: boolean;
        permission_level?: number;
      } = {};
      // Trim to avoid whitespace-only 400s; validate level range client-side
      if (Number.isNaN(permNum) || permNum < 1 || permNum > 9) {
        setEditError('مستوى الصلاحية يجب أن يكون بين 1 و 9');
        patchLock.current = false;
        setEditingId(null);
        return;
      }
      payload.namee = vals.namee.trim();
      payload.mobile = vals.mobile.trim() || null;
      payload.active = vals.active;
      payload.permission_level = permNum;
      const updated = await patchUser(token, userId, payload);
      setUsers((prev) => (prev ? prev.map((u) => (u.id === userId ? updated : u)) : prev));
      setEditValues((prev) => ({
        ...prev,
        [userId]: {
          namee: updated.namee ?? '',
          mobile: updated.mobile ?? '',
          active: updated.active,
          permission_level: String(updated.permission_level),
        },
      }));
      setEditSuccess(`تم تحديث ${updated.username}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      }
      if (err instanceof ApiError) {
        setEditError(userErrorMessage(err.status, err.detail ?? (err as Error).message));
      } else {
        setEditError('تعذّر الاتصال بالـ API');
      }
    } finally {
      patchLock.current = false;
      setEditingId(null);
    }
  }

  async function handleRoles(userId: number) {
    if (rolesCooldown > 0) {
      setRolesError(`كثرة الطلبات — حاول بعد ${rolesCooldown} ثانية (429)`);
      return;
    }
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    if (rolesLock.current) return;
    rolesLock.current = true;
    setRolesError(null);
    setRolesSuccess(null);
    try {
      const raw = rolesValues[userId] ?? '';
      const arr = raw
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const updated = await setUserRoles(token, userId, arr);
      setUsers((prev) => (prev ? prev.map((u) => (u.id === userId ? updated : u)) : prev));
      setRolesSuccess(`تم تحديث أدوار ${updated.username}: ${updated.roles.join(', ') || '—'}`);
      setRolesValues((prev) => ({ ...prev, [userId]: updated.roles.join(', ') }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      }
      if (err instanceof ApiError && err.status === 429) {
        setRolesCooldown(cooldownFromErr(err));
        setRolesError(userErrorMessage(err.status, err.detail ?? (err as Error).message));
      } else if (err instanceof ApiError) {
        setRolesError(userErrorMessage(err.status, err.detail ?? (err as Error).message));
      } else {
        setRolesError('تعذّر الاتصال بالـ API');
      }
    } finally {
      rolesLock.current = false;
    }
  }

  async function handleManagerReset(userId: number) {
    if (resetCooldown > 0) {
      setResetPwError(`كثرة الطلبات — حاول بعد ${resetCooldown} ثانية (429)`);
      return;
    }
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    if (resetLock.current) return;
    resetLock.current = true;
    setResetPwError(null);
    setResetPwSuccess(null);
    try {
      const newPw = resetPwValues[userId] ?? '';
      if (!newPw) {
        setResetPwError('كلمة المرور الجديدة مطلوبة');
        resetLock.current = false;
        return;
      }
      // Client mirror of server rules (length/bytes/weak) to avoid round-trip
      if (newPw.length < 8) {
        setResetPwError('كلمة المرور الجديدة قصيرة جداً — 8 أحرف على الأقل.');
        resetLock.current = false;
        return;
      }
      if (new TextEncoder().encode(newPw).length > 72) {
        setResetPwError('كلمة المرور الجديدة طويلة جداً — 72 بايت كحد أقصى.');
        resetLock.current = false;
        return;
      }
      if (newPw === 'changeme') {
        setResetPwError(userErrorMessage(400, 'new password must differ from the weak default'));
        resetLock.current = false;
        return;
      }
      await managerResetPassword(token, userId, newPw);
      setResetPwSuccess('تمت إعادة التعيين — سيُطلب من الموظف تغييرها عند الدخول');
      setResetPwValues((prev) => ({ ...prev, [userId]: '' }));
      // refresh to update must_reset flag — merge, preserve other rows' drafts
      const refreshed = await fetchUsers(token);
      setUsers((prev) => {
        if (!prev) return refreshed.users;
        const ids = new Set(refreshed.users.map((u) => u.id));
        const kept = prev.filter((u) => ids.has(u.id));
        const prevIds = new Set(kept.map((u) => u.id));
        const added = refreshed.users.filter((u) => !prevIds.has(u.id));
        const byId = new Map(refreshed.users.map((u) => [u.id, u]));
        return [...kept.map((u) => byId.get(u.id) ?? u), ...added];
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFail();
        return;
      }
      if (err instanceof ApiError && err.status === 429) {
        setResetCooldown(cooldownFromErr(err));
        setResetPwError(userErrorMessage(err.status, err.detail ?? (err as Error).message));
      } else if (err instanceof ApiError) {
        setResetPwError(userErrorMessage(err.status, err.detail ?? (err as Error).message));
      } else {
        setResetPwError('تعذّر الاتصال بالـ API');
      }
    } finally {
      resetLock.current = false;
    }
  }

  async function handleSelfReset(e: FormEvent) {
    e.preventDefault();
    const token = loadToken();
    if (!token) {
      setView('login');
      return;
    }
    const clientError = validateNewPassword(
      selfForm.oldPassword,
      selfForm.newPassword,
      selfForm.confirm,
    );
    if (clientError) {
      setSelfError(clientError);
      return;
    }
    setSelfSubmitting(true);
    setSelfError(null);
    setSelfSuccess(false);
    try {
      await resetPassword(token, selfForm.oldPassword, selfForm.newPassword);
      setSelfSuccess(true);
      setSelfForm({ oldPassword: '', newPassword: '', confirm: '' });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // Server contract (app/auth/router.py:81 + dependencies.py:23):
        // "Old password is incorrect" = wrong old; anything else = token bad.
        const d = (err.detail ?? '').toLowerCase();
        if (d.includes('old password')) {
          setSelfError('wrong-old');
        } else {
          handleAuthFail();
          return;
        }
      } else if (err instanceof ApiError && err.status === 400) setSelfError('rejected');
      else if (err instanceof ApiError && err.status === 429) {
        setSelfError('network');
        setResetCooldown(cooldownFromErr(err));
      } else setSelfError('network');
    } finally {
      setSelfSubmitting(false);
    }
  }

  const chip =
    view === 'boot' || view === 'login' ? (
      <StatusChip kind="offline" labelAr="تسجيل الدخول" labelEn="Sign in" />
    ) : view === 'ready' ? (
      <StatusChip kind="online" labelAr="الخادم متصل" labelEn="API online" />
    ) : (
      <StatusChip kind="saved" labelAr="الخادم غير متاح" labelEn="API unavailable" />
    );

  if (view === 'boot') {
    return (
      <Shell>
        <section dir="rtl" className="flex flex-col gap-3">
          <h1 className="pt-title text-2xl">الموظفين</h1>
          <p className="pt-caption" role="status" aria-live="polite">
            جارٍ التحميل…
          </p>
        </section>
      </Shell>
    );
  }

  if (pendingAuth) {
    return (
      <Shell>
        <section className="flex h-full flex-col gap-4" dir="rtl">
          <div className="flex items-center gap-3">
            <h1 className="pt-title text-2xl">الموظفين</h1>
            {chip}
          </div>
          <div className="pt-card w-full max-w-sm">
            <form className="flex flex-col gap-3" onSubmit={submitReset}>
              <p className="pt-title text-lg">تغيير كلمة المرور</p>
              <p className="pt-caption">
                يجب تغيير كلمة المرور الافتراضية قبل الدخول. أدخل كلمة مرور جديدة قوية.
              </p>
              <label className="pt-caption flex flex-col gap-1">
                كلمة المرور الحالية
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={resetForm.oldPassword}
                  autoComplete="current-password"
                  onChange={(e) => setResetForm((f) => ({ ...f, oldPassword: e.target.value }))}
                  required
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                كلمة المرور الجديدة
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={resetForm.newPassword}
                  autoComplete="new-password"
                  onChange={(e) => setResetForm((f) => ({ ...f, newPassword: e.target.value }))}
                  required
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                تأكيد كلمة المرور الجديدة
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={resetForm.confirm}
                  autoComplete="new-password"
                  onChange={(e) => setResetForm((f) => ({ ...f, confirm: e.target.value }))}
                  required
                />
              </label>
              {resetError && (
                <p className="pt-caption text-red-600">{RESET_ERROR_TEXT[resetError]}</p>
              )}
              <button
                type="submit"
                disabled={submitting}
                className="pt-caption cursor-pointer rounded-md bg-surface-elevated px-4 py-2 disabled:opacity-50"
              >
                {submitting ? 'جارٍ الحفظ…' : 'تغيير وحفظ'}
              </button>
            </form>
          </div>
        </section>
      </Shell>
    );
  }

  if (view === 'login') {
    return (
      <Shell>
        <section className="flex h-full flex-col gap-4" dir="rtl">
          <div className="flex items-center gap-3">
            <h1 className="pt-title text-2xl">الموظفين</h1>
            {chip}
          </div>
          <div className="pt-card w-full max-w-sm">
            <form className="flex flex-col gap-3" onSubmit={submitLogin}>
              <p className="pt-title text-lg">تسجيل الدخول</p>
              <label className="pt-caption flex flex-col gap-1">
                اسم المستخدم
                <input
                  className="rounded-md border border-border px-3 py-2"
                  value={username}
                  autoComplete="username"
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </label>
              <label className="pt-caption flex flex-col gap-1">
                كلمة المرور
                <input
                  className="rounded-md border border-border px-3 py-2"
                  type="password"
                  value={password}
                  autoComplete="current-password"
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </label>
              {loginError === 'invalid' && (
                <p className="pt-caption text-red-600">بيانات الدخول غير صحيحة — أعد المحاولة.</p>
              )}
              {loginError === 'network' && (
                <p className="pt-caption text-red-600">
                  تعذّر الاتصال بالـ API — تأكد من تشغيله على http://localhost:8000.
                </p>
              )}
              <button
                type="submit"
                disabled={submitting}
                className="pt-caption cursor-pointer rounded-md bg-surface-elevated px-4 py-2 disabled:opacity-50"
              >
                {submitting ? 'جارٍ الدخول…' : 'دخول'}
              </button>
            </form>
          </div>
        </section>
      </Shell>
    );
  }

  if (view === 'error') {
    return (
      <Shell>
        <section className="flex h-full flex-col gap-4" dir="rtl">
          <div className="flex items-center gap-3">
            <h1 className="pt-title text-2xl">الموظفين</h1>
            {chip}
          </div>
          <p className="pt-caption text-red-600" role="alert">
            {globalError ?? 'تعذّر الاتصال بالـ API'}
          </p>
          <button
            type="button"
            onClick={async () => {
              const token = loadToken();
              if (!token) setView('login');
              else {
                setView('boot');
                await loadData(token);
              }
            }}
            className="w-fit rounded border border-border px-3 py-1.5 text-sm"
          >
            إعادة المحاولة
          </button>
        </section>
      </Shell>
    );
  }

  // ready
  // Branch lookup via Map (O(1), no per-row .find). Unknown id → '—' (no raw id leak).
  const branchLookup = (() => {
    const m = new Map<number, string>(branchMap.current);
    if (branches) {
      for (const b of branches) m.set(b.id, b.pharname || b.pharmacyid);
    }
    return m;
  })();
  const branchNameOf = (branchId: number | null) => {
    if (branchId == null) return '—';
    return branchLookup.get(branchId) ?? '—';
  };

  const filteredUsers = (() => {
    if (!users) return null;
    const q = searchQuery.trim();
    if (!q) return users;
    const low = q.toLowerCase();
    return users.filter(
      (u) =>
        u.username.toLowerCase().includes(low) ||
        (u.namee?.includes(q) ?? false) ||
        (u.mobile?.includes(q) ?? false) ||
        u.roles.join(',').toLowerCase().includes(low) ||
        String(u.permission_level).includes(q) ||
        branchNameOf(u.branch_id).includes(q),
    );
  })();

  const hasQuery = searchQuery.trim().length > 0;
  const isEmpty = users !== null && users.length === 0;
  const filteredEmpty = filteredUsers !== null && filteredUsers.length === 0 && !isEmpty;
  const visibleUsers = filteredUsers ? filteredUsers.slice(0, visibleCount) : null;

  return (
    <Shell>
      <section className="flex h-full flex-col gap-4" dir="rtl">
        <div className="flex items-center gap-3">
          <h1 className="pt-title text-2xl">الموظفين</h1>
          {chip}
          <button
            type="button"
            className="ms-auto pt-caption cursor-pointer rounded-md border border-border px-3 py-1"
            onClick={handleLogout}
          >
            تسجيل الخروج
          </button>
        </div>

        {(usersError || branchesError || globalError) && (
          <p className="pt-caption text-red-600" role="alert">
            {usersError ?? branchesError ?? globalError}
          </p>
        )}

        {/* Search */}
        <div className="flex flex-wrap items-center gap-3">
          <input
            aria-label="ابحث عن موظف"
            placeholder="ابحث بالاسم أو اسم المستخدم"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') e.preventDefault();
            }}
            className="flex-1 min-w-[240px] rounded-md border border-border px-3 py-2 text-sm"
          />
          <span className="pt-caption text-muted">
            {filteredUsers ? `${filteredUsers.length} موظف` : ''}
          </span>
        </div>

        {/* Forbidden banner: form hidden */}
        {forbidden ? (
          <div className="pt-card">
            <p className="pt-caption text-red-600" role="alert">
              ليس لديك صلاحية — تحقق من دورك
            </p>
            <p className="pt-caption">لا تملك صلاحية users.manage (مستوى 6 أو دور admin).</p>
          </div>
        ) : null}

        {/* Users list */}
        <div className="pt-card flex flex-col gap-3">
          <h2 className="pt-title text-lg">قائمة الموظفين</h2>
          {isEmpty ? (
            <p className="pt-caption">لا يوجد موظفون في هذا الفرع</p>
          ) : filteredEmpty && hasQuery ? (
            <p className="pt-caption">لا توجد نتائج للبحث عن “{searchQuery.trim()}”</p>
          ) : filteredUsers && filteredUsers.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-start text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="pt-caption px-3 py-2 text-start">اسم المستخدم</th>
                    <th className="pt-caption px-3 py-2 text-start">الاسم</th>
                    <th className="pt-caption px-3 py-2 text-start">الجوال</th>
                    <th className="pt-caption px-3 py-2 text-start">الفرع</th>
                    <th className="pt-caption px-3 py-2 text-start">مستوى الصلاحية</th>
                    <th className="pt-caption px-3 py-2 text-start">نشط</th>
                    <th className="pt-caption px-3 py-2 text-start">الأدوار</th>
                    <th className="pt-caption px-3 py-2 text-start">الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {(visibleUsers ?? []).map((u) => {
                    const branchName = branchNameOf(u.branch_id);
                    const isInactive = !u.active;
                    return (
                      <tr
                        key={u.id}
                        data-user-id={u.id}
                        data-active={String(u.active)}
                        className={
                          'border-b border-border h-9 ' +
                          (isInactive ? 'opacity-50 bg-muted/20' : '')
                        }
                        aria-label={isInactive ? 'غير نشط' : 'نشط'}
                      >
                        <td className="px-3 py-2 font-mono">{u.username}</td>
                        <td className="px-3 py-2">{u.namee || '—'}</td>
                        <td className="px-3 py-2 font-mono">{u.mobile || '—'}</td>
                        <td className="px-3 py-2">{branchName}</td>
                        <td className="px-3 py-2">{u.permission_level}</td>
                        <td className="px-3 py-2">{u.active ? 'نشط' : 'غير نشط'}</td>
                        <td className="px-3 py-2">{u.roles.join(', ') || '—'}</td>
                        <td className="px-3 py-2">
                          <span className="pt-caption text-muted">
                            {u.must_reset_password ? 'يجب التغيير' : ''}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="pt-caption" role="status">
              جارٍ التحميل…
            </p>
          )}

          {/* Per-user edit / roles / reset sections — paginated via visibleUsers */}
          {visibleUsers && visibleUsers.length > 0 && (
            <div className="flex flex-col gap-4 border-t border-border pt-3">
              {visibleUsers.map((u) => (
                <div
                  key={`edit-${u.id}`}
                  className="rounded border border-border p-3 flex flex-col gap-2"
                >
                  <p className="pt-caption font-bold">تعديل: {u.username}</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label className="pt-caption flex flex-col gap-1">
                      الاسم
                      <input
                        aria-label={`namee-${u.id}`}
                        className="rounded border border-border px-2 py-1"
                        value={editValues[u.id]?.namee ?? ''}
                        onChange={(e) =>
                          setEditValues((prev) => ({
                            ...prev,
                            [u.id]: {
                              ...(prev[u.id] as NonNullable<(typeof prev)[number]>),
                              namee: e.target.value,
                            },
                          }))
                        }
                      />
                    </label>
                    <label className="pt-caption flex flex-col gap-1">
                      الجوال
                      <input
                        aria-label={`mobile-${u.id}`}
                        className="rounded border border-border px-2 py-1"
                        value={editValues[u.id]?.mobile ?? ''}
                        onChange={(e) =>
                          setEditValues((prev) => ({
                            ...prev,
                            [u.id]: {
                              ...(prev[u.id] as NonNullable<(typeof prev)[number]>),
                              mobile: e.target.value,
                            },
                          }))
                        }
                      />
                    </label>
                    <label className="pt-caption flex items-center gap-2">
                      <input
                        type="checkbox"
                        aria-label={`active-${u.id}`}
                        checked={editValues[u.id]?.active ?? true}
                        onChange={(e) =>
                          setEditValues((prev) => ({
                            ...prev,
                            [u.id]: {
                              ...(prev[u.id] as NonNullable<(typeof prev)[number]>),
                              active: e.target.checked,
                            },
                          }))
                        }
                      />
                      نشط
                    </label>
                    <label className="pt-caption flex flex-col gap-1">
                      مستوى الصلاحية
                      <select
                        aria-label={`permission-${u.id}`}
                        className="rounded border border-border px-2 py-1"
                        value={editValues[u.id]?.permission_level ?? String(u.permission_level)}
                        onChange={(e) =>
                          setEditValues((prev) => ({
                            ...prev,
                            [u.id]: {
                              ...(prev[u.id] as NonNullable<(typeof prev)[number]>),
                              permission_level: e.target.value,
                            },
                          }))
                        }
                      >
                        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                          <option key={n} value={String(n)}>
                            {n}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <button
                    type="button"
                    onClick={() => handlePatch(u.id)}
                    disabled={editingId === u.id}
                    className="w-fit rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
                  >
                    {editingId === u.id ? 'جارٍ الحفظ…' : 'حفظ التعديلات'}
                  </button>

                  {/* Roles assign */}
                  <div className="flex flex-col gap-2 border-t border-border pt-2">
                    <label className="pt-caption flex flex-col gap-1">
                      الأدوار (الصلاحيات)
                      <input
                        aria-label={`الأدوار-${u.id}`}
                        placeholder="admin, manager, pharmacist"
                        className="rounded border border-border px-2 py-1"
                        value={rolesValues[u.id] ?? ''}
                        onChange={(e) =>
                          setRolesValues((prev) => ({ ...prev, [u.id]: e.target.value }))
                        }
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => handleRoles(u.id)}
                      className="w-fit rounded border border-border px-3 py-1 text-sm"
                    >
                      حفظ الأدوار
                    </button>
                  </div>

                  {/* Manager reset password */}
                  <div className="flex flex-col gap-2 border-t border-border pt-2">
                    <label className="pt-caption flex flex-col gap-1">
                      كلمة مرور جديدة للإعادة تعيين
                      <input
                        type="password"
                        aria-label={`إعادة تعيين-${u.id}`}
                        placeholder="كلمة المرور الجديدة"
                        className="rounded border border-border px-2 py-1"
                        value={resetPwValues[u.id] ?? ''}
                        onChange={(e) =>
                          setResetPwValues((prev) => ({ ...prev, [u.id]: e.target.value }))
                        }
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => handleManagerReset(u.id)}
                      className="w-fit rounded border border-border px-3 py-1 text-sm"
                    >
                      إعادة تعيين كلمة المرور
                    </button>
                  </div>
                </div>
              ))}
              {editError && (
                <p className="pt-caption text-red-600" role="alert">
                  {editError}
                </p>
              )}
              {editSuccess && <p className="pt-caption text-green-600">{editSuccess}</p>}
              {rolesError && (
                <p className="pt-caption text-red-600" role="alert">
                  {rolesError}
                </p>
              )}
              {rolesSuccess && <p className="pt-caption text-green-600">{rolesSuccess}</p>}
              {resetPwError && (
                <p className="pt-caption text-red-600" role="alert">
                  {resetPwError}
                </p>
              )}
              {resetPwSuccess && <p className="pt-caption text-green-600">{resetPwSuccess}</p>}
              {filteredUsers && filteredUsers.length > visibleCount && (
                <button
                  type="button"
                  onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
                  className="w-fit rounded border border-border px-3 py-1 text-sm"
                >
                  عرض المزيد ({filteredUsers.length - visibleCount} متبقي)
                </button>
              )}
            </div>
          )}
        </div>

        {/* Create form — hidden when forbidden */}
        {!forbidden && (
          <div className="pt-card flex flex-col gap-3">
            <h2 className="pt-title text-lg">إنشاء موظف</h2>
            <form className="flex flex-col gap-3" noValidate onSubmit={handleCreate}>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="pt-caption flex flex-col gap-1">
                  اسم المستخدم *
                  <input
                    aria-label="اسم المستخدم"
                    placeholder="اسم المستخدم"
                    className="rounded border border-border px-3 py-2"
                    value={createForm.username}
                    onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))}
                  />
                </label>
                <label className="pt-caption flex flex-col gap-1">
                  الاسم
                  <input
                    aria-label="الاسم"
                    placeholder="الاسم (عربي)"
                    className="rounded border border-border px-3 py-2"
                    value={createForm.namee}
                    onChange={(e) => setCreateForm((f) => ({ ...f, namee: e.target.value }))}
                  />
                </label>
                <label className="pt-caption flex flex-col gap-1">
                  الجوال
                  <input
                    aria-label="الجوال"
                    placeholder="الجوال"
                    className="rounded border border-border px-3 py-2"
                    value={createForm.mobile}
                    onChange={(e) => setCreateForm((f) => ({ ...f, mobile: e.target.value }))}
                  />
                </label>
                <label className="pt-caption flex flex-col gap-1">
                  الفرع
                  <select
                    aria-label="الفرع"
                    className="rounded border border-border px-3 py-2"
                    value={createForm.branch_id}
                    onChange={(e) => setCreateForm((f) => ({ ...f, branch_id: e.target.value }))}
                  >
                    <option value="">اختر الفرع (افتراضي: فرعك)</option>
                    {branches?.map((b) => (
                      <option key={b.id} value={String(b.id)}>
                        {b.pharname} ({b.pharmacyid})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="pt-caption flex flex-col gap-1">
                  مستوى الصلاحية 1–9
                  <select
                    aria-label="مستوى الصلاحية"
                    className="rounded border border-border px-3 py-2"
                    value={createForm.permission_level}
                    onChange={(e) =>
                      setCreateForm((f) => ({ ...f, permission_level: e.target.value }))
                    }
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                      <option key={n} value={String(n)}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="pt-caption flex flex-col gap-1">
                  كلمة المرور الابتدائية *
                  <input
                    type="password"
                    aria-label="كلمة المرور الابتدائية"
                    placeholder="كلمة المرور الابتدائية"
                    className="rounded border border-border px-3 py-2"
                    value={createForm.initial_password}
                    onChange={(e) =>
                      setCreateForm((f) => ({ ...f, initial_password: e.target.value }))
                    }
                  />
                </label>
                <label className="pt-caption flex flex-col gap-1 sm:col-span-2">
                  الأدوار (مفصولة بفاصلة)
                  <input
                    aria-label="الأدوار"
                    placeholder="مثال: pharmacist, cashier"
                    className="rounded border border-border px-3 py-2"
                    value={createForm.roles}
                    onChange={(e) => setCreateForm((f) => ({ ...f, roles: e.target.value }))}
                  />
                </label>
              </div>
              {createError && (
                <p className="pt-caption text-red-600" role="alert">
                  {createError}
                </p>
              )}
              {createSuccess && <p className="pt-caption text-green-600">{createSuccess}</p>}
              <button
                type="submit"
                disabled={creating}
                className="w-fit rounded bg-surface-elevated px-4 py-2 text-sm disabled:opacity-50"
              >
                {creating ? 'جارٍ الإنشاء…' : 'إنشاء موظف'}
              </button>
            </form>
          </div>
        )}

        {/* Self change-password */}
        <div className="pt-card w-full max-w-sm">
          <form
            className="flex flex-col gap-3"
            noValidate
            onSubmit={handleSelfReset}
            aria-label="تغيير كلمة المرور الذاتي"
          >
            <p className="pt-title text-lg">تغيير كلمة المرور</p>
            <p className="pt-caption">غيّر كلمة مرورك الحالية — تُطبّق فوراً.</p>
            <label className="pt-caption flex flex-col gap-1">
              كلمة المرور الحالية
              <input
                aria-label="كلمة المرور الحالية"
                className="rounded-md border border-border px-3 py-2"
                type="password"
                value={selfForm.oldPassword}
                autoComplete="current-password"
                onChange={(e) => setSelfForm((f) => ({ ...f, oldPassword: e.target.value }))}
              />
            </label>
            <label className="pt-caption flex flex-col gap-1">
              كلمة المرور الجديدة
              <input
                aria-label="كلمة المرور الجديدة"
                className="rounded-md border border-border px-3 py-2"
                type="password"
                value={selfForm.newPassword}
                autoComplete="new-password"
                onChange={(e) => setSelfForm((f) => ({ ...f, newPassword: e.target.value }))}
              />
            </label>
            <label className="pt-caption flex flex-col gap-1">
              تأكيد كلمة المرور الجديدة
              <input
                aria-label="تأكيد كلمة المرور الجديدة"
                className="rounded-md border border-border px-3 py-2"
                type="password"
                value={selfForm.confirm}
                autoComplete="new-password"
                onChange={(e) => setSelfForm((f) => ({ ...f, confirm: e.target.value }))}
              />
            </label>
            {selfError && (
              <p className="pt-caption text-red-600">
                {RESET_ERROR_TEXT[selfError as Exclude<ResetError, null>]}
              </p>
            )}
            {selfSuccess && (
              <p className="pt-caption text-green-600">تم تغيير كلمة المرور بنجاح.</p>
            )}
            <button
              type="submit"
              disabled={selfSubmitting}
              className="pt-caption cursor-pointer rounded-md bg-surface-elevated px-4 py-2 disabled:opacity-50"
            >
              {selfSubmitting ? 'جارٍ الحفظ…' : 'تغيير وحفظ'}
            </button>
          </form>
        </div>

        <p className="pt-caption text-xs text-muted">
          الصلاحيات: مستوى 6 لإدارة الموظفين، 7 لمنح دور admin ورفع الصلاحيات، 9 للنقل بين الفروع.
        </p>
      </section>
    </Shell>
  );
}
