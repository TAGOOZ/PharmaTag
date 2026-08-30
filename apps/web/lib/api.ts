export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const TOKEN_KEY = 'pharmatag:token';

export type Health = { status: string };

/** A non-2xx API response. `status === 401` means the credential/session is bad. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail?: string;

  constructor(status: number, detail?: string) {
    super(detail ? `API ${status}: ${detail.slice(0, 2000)}` : `API returned ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function throwForStatus(res: Response): Promise<void> {
  if (!res.ok) {
    let detail: string | undefined;
    try {
      const hasClone = typeof (res as unknown as { clone?: () => Response }).clone === 'function';
      const raw = hasClone
        ? await (res as unknown as { clone: () => Response }).clone().text()
        : await res.text();
      if (raw) {
        const trimmed = raw.slice(0, 2000);
        try {
          const j = JSON.parse(trimmed) as { detail?: unknown; message?: unknown };
          if (j && typeof j.detail === 'string' && j.detail) detail = j.detail.slice(0, 2000);
          else if (j && typeof j.message === 'string' && j.message)
            detail = j.message.slice(0, 2000);
          else if (trimmed.startsWith('{') || trimmed.startsWith('[')) detail = trimmed;
          else detail = trimmed;
        } catch {
          detail = trimmed;
        }
      }
    } catch {
      detail = undefined;
    }
    throw new ApiError(res.status, detail);
  }
}

export function loadToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function saveToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {}
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {}
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
  price_wholesale?: string;
  price_cost?: string;
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

export interface DrugSearchResponse {
  query: string;
  drugs: Drug[];
}

/** Search-as-you-type: name AR/EN or barcode prefix (ticket #8). */
export async function searchDrugs(
  token: string,
  q: string,
  signal?: AbortSignal,
): Promise<DrugSearchResponse> {
  const res = await fetch(`${API_URL}/api/v1/drugs/search?q=${encodeURIComponent(q)}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as DrugSearchResponse;
}

// ──────────────────────────────────────────────────────────────────────────────
// Sales (POS) — S1.3 / S1.5 (#9 / #11)
// ──────────────────────────────────────────────────────────────────────────────

export interface SaleSummary {
  id: number;
  invoice_no: string;
  datee: string;
  totalvalue: string;
  payed: string;
  agel: string;
  status: string;
}

export interface SalesListResponse {
  sales: SaleSummary[];
}

export type PriceLevel = 'public' | 'wholesale' | 'cost';
export type PaymentMethod = 'cash' | 'card' | 'credit';

export interface SaleLineIn {
  drug_id: number;
  qty: string;
  price_level?: PriceLevel;
  disc_percent?: string;
}

export interface PaymentSplitIn {
  method: PaymentMethod;
  amount?: string;
}

export interface SaleCreateBody {
  lines: SaleLineIn[];
  disc_percent?: string;
  payments?: PaymentSplitIn[];
  party_id?: number;
}

export interface SaleLineOut {
  id: number;
  drug_id: number;
  drugname: string;
  drugnamear: string;
  batch_id: number | null;
  ref_invoice_line_id: number | null;
  qty: string;
  unit: string;
  unit_price: string;
  cost: string;
  tax_type: string;
  vat_amount: string;
  line_total: string;
}

export interface PaymentSplitOut {
  method: string;
  amount: string;
}

export interface SaleOut {
  id: number;
  branch_id: number;
  kind: string;
  invoice_no: string;
  datee: string;
  silsilaid: string;
  status: string;
  ref_invoice_id: number | null;
  subtotal: string;
  discount: string;
  vat: string;
  totalvalue: string;
  net: string;
  payed: string;
  agel: string;
  created_by: number | null;
  lines: SaleLineOut[];
  payments: PaymentSplitOut[];
  journal: {
    id: number;
    entry_no: string;
    datee: string;
    balanced: boolean;
    debit_total: string;
    credit_total: string;
  } | null;
}

export async function fetchSales(token: string, signal?: AbortSignal): Promise<SalesListResponse> {
  const res = await fetch(`${API_URL}/api/v1/sales`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as SalesListResponse;
}

export async function fetchSale(token: string, id: number, signal?: AbortSignal): Promise<SaleOut> {
  const res = await fetch(`${API_URL}/api/v1/sales/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as SaleOut;
}

export async function createSale(
  token: string,
  body: SaleCreateBody,
  signal?: AbortSignal,
): Promise<SaleOut> {
  const res = await fetch(`${API_URL}/api/v1/sales`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as SaleOut;
}

export interface ReturnLineIn {
  ref_invoice_line_id: number;
  qty: string;
}

export interface ReturnCreateBody {
  lines: ReturnLineIn[];
  payments?: PaymentSplitIn[];
}

export async function createSaleReturn(
  token: string,
  saleId: number,
  body: ReturnCreateBody,
  signal?: AbortSignal,
): Promise<SaleOut> {
  const res = await fetch(`${API_URL}/api/v1/sales/${saleId}/return`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    signal,
  });
  await throwForStatus(res);
  return (await res.json()) as SaleOut;
}

export async function fetchSalePrintHtml(
  token: string,
  id: number,
  kind: 'print' | 'tax-document' = 'print',
): Promise<string> {
  const suffix = kind === 'tax-document' ? 'tax-document/print' : 'print';
  const res = await fetch(`${API_URL}/api/v1/sales/${id}/${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await throwForStatus(res);
  return await res.text();
}

export async function openSalePrint(
  token: string,
  id: number,
  kind: 'print' | 'tax-document' = 'print',
): Promise<void> {
  // Apple: immediate feedback keeps gesture, write directly to avoid blob revoke timing
  const win = window.open('about:blank', '_blank', 'noopener');
  if (!win) throw new ApiError(0, 'popup blocked — allow popups for printing');
  try {
    win.document.write(
      '<html><head><title>جارٍ التحميل…</title></head><body style="font-family:sans-serif;padding:20px">جارٍ التحميل…</body></html>',
    );
    const html = await fetchSalePrintHtml(token, id, kind);
    win.document.open();
    win.document.write(html);
    win.document.close();
    // keep win alive for print; revoke not needed when writing directly
  } catch (err) {
    try {
      win.close();
    } catch {}
    throw err;
  }
}
