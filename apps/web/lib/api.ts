export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const TOKEN_KEY = 'pharmatag:token';

export type Health = { status: string };

/** A non-2xx API response. `status === 401` means the credential/session is bad. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`API returned ${status}`);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function throwForStatus(res: Response): Promise<void> {
  if (!res.ok) throw new ApiError(res.status);
}

export function loadToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function saveToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const res = await fetch(`${API_URL}/healthz`, { signal });
  await throwForStatus(res);
  return (await res.json()) as Health;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  must_reset_password: boolean;
  user: {
    id: number;
    username: string;
    namee: string;
    permission_level: number;
    branch_id: number;
  };
}

export async function login(
  username: string,
  password: string,
  signal?: AbortSignal,
): Promise<LoginResponse> {
  const res = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as LoginResponse;
}

/** Self-service password change (ticket #37): proves the current password,
 * sets a new one. 401 = wrong old password, 400 = rejected new password. */
export async function resetPassword(
  token: string,
  oldPassword: string,
  newPassword: string,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/auth/reset-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    signal,
  });
  await throwForStatus(res);
}

export interface Drug {
  id: number;
  drugname: string;
  drugnamear: string;
  generic: string;
  classy: string;
  co: string;
  units: number;
  unitsmall: number;
  price: string;
  price_now: string;
  tax_type: string;
  vat: string;
  active: boolean;
}

export interface DrugListResponse {
  branch: { id: number; pharmacyid: string; pharname: string };
  drugs: Drug[];
}

/** Branch drug master for the authenticated user (ticket #6 / S0.3). */
export async function fetchDrugs(token: string, signal?: AbortSignal): Promise<DrugListResponse> {
  const res = await fetch(`${API_URL}/api/v1/drugs`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as DrugListResponse;
}
