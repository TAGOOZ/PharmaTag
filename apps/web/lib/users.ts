import { API_URL, throwForStatus } from './api';

export interface UserPublic {
  id: number;
  username: string;
  namee: string;
  mobile: string;
  permission_level: number;
  branch_id: number | null;
  active: boolean;
  roles: string[];
  must_reset_password: boolean;
}

export interface UsersResponse {
  users: UserPublic[];
}

export async function fetchUsers(token: string, signal?: AbortSignal): Promise<UsersResponse> {
  const res = await fetch(`${API_URL}/api/v1/users`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  if (res.status === 204) return { users: [] };
  let body: unknown;
  try {
    body = await res.json();
  } catch (e) {
    throw new SyntaxError(e instanceof Error ? e.message : 'invalid json');
  }
  const typed = body as UsersResponse;
  if (!typed || !Array.isArray(typed.users)) return { users: [] };
  return typed;
}

export async function fetchUser(
  token: string,
  id: number,
  signal?: AbortSignal,
): Promise<UserPublic> {
  const res = await fetch(`${API_URL}/api/v1/users/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as UserPublic;
}

export interface CreateUserPayload {
  username: string;
  namee?: string;
  mobile?: string | null;
  permission_level: number;
  branch_id?: number | null;
  initial_password: string;
  roles?: string[];
}

export async function createUser(
  token: string,
  payload: CreateUserPayload,
  signal?: AbortSignal,
): Promise<UserPublic> {
  const res = await fetch(`${API_URL}/api/v1/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as UserPublic;
}

export interface PatchUserPayload {
  namee?: string | null;
  mobile?: string | null;
  active?: boolean | null;
  permission_level?: number | null;
}

export async function patchUser(
  token: string,
  id: number,
  payload: PatchUserPayload,
  signal?: AbortSignal,
): Promise<UserPublic> {
  const res = await fetch(`${API_URL}/api/v1/users/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as UserPublic;
}

export async function setUserRoles(
  token: string,
  id: number,
  roles: string[],
  signal?: AbortSignal,
): Promise<UserPublic> {
  const res = await fetch(`${API_URL}/api/v1/users/${id}/permissions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ roles }),
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as UserPublic;
}

export async function managerResetPassword(
  token: string,
  id: number,
  newPassword: string,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/users/${id}/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ new_password: newPassword }),
    signal,
  });
  await throwForStatus(res);
}
