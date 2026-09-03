import { API_URL, throwForStatus as apiThrowForStatus } from './api';

export interface CurrentStockBatch {
  batch_id: number;
  randomid: string;
  qty: string;
  cost: string;
  expire: string | null;
}

export interface CurrentStockItem {
  branch_id: number;
  drug_id: number;
  drugname: string;
  drugnamear: string;
  barcode: string;
  qty: string;
  minimum: string;
  price: string;
  batches: CurrentStockBatch[];
}

export interface CurrentStockResponse {
  items: CurrentStockItem[];
  count?: number;
  truncated?: boolean;
}

export interface CrossBranchItem {
  branch_id: number;
  pharmacyid: string;
  pharname: string;
  drug_id: number;
  drugname: string;
  drugnamear: string;
  barcode: string;
  qty: string;
  minimum: string;
  shortage: string;
  silsilaid: string;
  classy: string;
  lastedit: string | null;
}

export interface CrossBranchResponse {
  count: number;
  truncated: boolean;
  drug_id?: number;
  items: CrossBranchItem[];
}

async function throwForStatus(res: Response): Promise<void> {
  // Reuse api's throwForStatus logic via shared helper to avoid drift (M4)
  // Clone handling is in apiThrowForStatus; we delegate to avoid duplication
  // but keep local wrapper for type safety if api changes
  return apiThrowForStatus(res);
}

export async function fetchCurrentStock(
  token: string,
  params: { q?: string; limit?: number; only_shortage?: boolean } = {},
  signal?: AbortSignal,
): Promise<CurrentStockResponse> {
  const qs = new URLSearchParams();
  if (params.q?.trim()) qs.set('q', params.q.trim());
  if (params.limit != null) qs.set('limit', String(params.limit));
  if (params.only_shortage) qs.set('only_shortage', 'true');
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const res = await fetch(`${API_URL}/api/v1/stock/current${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  // 204 has no body
  if (res.status === 204) return { items: [] };
  let body: unknown;
  try {
    body = await res.json();
  } catch (e) {
    // malformed JSON — surface as SyntaxError so page shows generic server error, not network
    throw new SyntaxError(e instanceof Error ? e.message : 'invalid json');
  }
  const typed = body as CurrentStockResponse;
  if (!typed || !Array.isArray(typed.items)) return { items: [] };
  return typed;
}

export async function fetchCrossBranch(
  token: string,
  params: {
    drug_id?: number;
    q?: string;
    only_shortage?: boolean;
    include_inactive?: boolean;
  } = {},
  signal?: AbortSignal,
): Promise<CrossBranchResponse> {
  const qs = new URLSearchParams();
  if (params.drug_id) qs.set('drug_id', String(params.drug_id));
  if (params.q?.trim()) qs.set('q', params.q.trim());
  if (params.only_shortage) qs.set('only_shortage', 'true');
  if (params.include_inactive) qs.set('include_inactive', 'true');
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const res = await fetch(`${API_URL}/api/v1/stock/cross-branch${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  if (res.status === 204) return { count: 0, truncated: false, items: [] };
  let body: unknown;
  try {
    body = (await res.json()) as unknown;
  } catch (e) {
    throw new SyntaxError(e instanceof Error ? e.message : 'invalid json');
  }
  const typed = body as CrossBranchResponse;
  // normalize missing fields
  return {
    count: typeof typed.count === 'number' ? typed.count : (typed.items?.length ?? 0),
    truncated: Boolean(typed.truncated),
    drug_id: typed.drug_id,
    items: Array.isArray(typed.items) ? typed.items : [],
  };
}
