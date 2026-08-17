export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type Health = { status: string };

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const res = await fetch(`${API_URL}/healthz`, { signal });
  if (!res.ok) throw new Error(`healthz returned ${res.status}`);
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

/** Login with a username/password (seed user for the S0.3 demo: admin/changeme). */
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
  if (!res.ok) throw new Error(`login returned ${res.status}`);
  return (await res.json()) as LoginResponse;
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
  if (!res.ok) throw new Error(`drugs returned ${res.status}`);
  return (await res.json()) as DrugListResponse;
}
