import { API_URL, throwForStatus } from './api';

export interface Branch {
  id: number;
  pharmacyid: string;
  pharname: string;
  phar?: string;
  mobile?: string;
  adress?: string;
  governorate?: string;
  district?: string;
  role?: string;
  is_main_device?: boolean;
  active?: boolean;
}

export interface BranchesResponse {
  branches: Branch[];
}

export async function fetchBranches(
  token: string,
  signal?: AbortSignal,
): Promise<BranchesResponse> {
  const res = await fetch(`${API_URL}/api/v1/branches`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  if (res.status === 204) return { branches: [] };
  let body: unknown;
  try {
    body = await res.json();
  } catch (e) {
    throw new SyntaxError(e instanceof Error ? e.message : 'invalid json');
  }
  const typed = body as BranchesResponse;
  if (!typed || !Array.isArray(typed.branches)) return { branches: [] };
  return typed;
}
