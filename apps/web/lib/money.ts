import { API_URL, throwForStatus as apiThrowForStatus } from './api';

async function throwForStatus(res: Response): Promise<void> {
  return apiThrowForStatus(res);
}

async function readJson<T>(res: Response): Promise<T> {
  try {
    return (await res.json()) as T;
  } catch (e) {
    throw new SyntaxError(e instanceof Error ? e.message : 'invalid json');
  }
}

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

function jsonHeaders(token: string): Record<string, string> {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };
}

/** Append only non-empty params (server treats '' as missing; keeps URLs clean). */
function withParams(base: string, params: Record<string, string | undefined>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== '') qs.set(k, v);
  }
  const s = qs.toString();
  return s ? `${base}?${s}` : base;
}

// ── Drawer ─────────────────────────────────────────────────────────────────

export interface DrawerMovement {
  id: number;
  branch_id: number;
  datee: string;
  direction: string;
  reason: string;
  method: string;
  amount: string;
  user_id: number | null;
  ref_invoice_id: number | null;
  created_at: string;
}

export interface DrawerMovementsResponse {
  movements: DrawerMovement[];
}

export interface MovementCreateBody {
  datee?: string;
  direction: 'in' | 'out';
  reason:
    | 'cash_sale'
    | 'cash_return'
    | 'supplier_pay'
    | 'customer_settlement'
    | 'expense'
    | 'transfer'
    | 'opening'
    | 'correction';
  method: 'cash' | 'network';
  amount: string;
  ref_invoice_id?: number;
}

export async function fetchDrawerMovements(
  token: string,
  params: { datee?: string; limit?: number } = {},
  signal?: AbortSignal,
): Promise<DrawerMovementsResponse> {
  const url = withParams(`${API_URL}/api/v1/drawer/movements`, {
    datee: params.datee,
    limit: params.limit != null ? String(params.limit) : undefined,
  });
  const res = await fetch(url, { headers: authHeaders(token), signal });
  await throwForStatus(res);
  if (res.status === 204) return { movements: [] };
  const body = await readJson<DrawerMovementsResponse>(res);
  if (!body || !Array.isArray(body.movements)) return { movements: [] };
  return body;
}

export async function createMovement(
  token: string,
  body: MovementCreateBody,
  signal?: AbortSignal,
): Promise<DrawerMovement> {
  const res = await fetch(`${API_URL}/api/v1/drawer/movements`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(body),
    signal,
  });
  await throwForStatus(res);
  return readJson<DrawerMovement>(res);
}

export type DayClose = Record<string, string | number | null>;

export interface DayCloseListResponse {
  day_closes: DayClose[];
}

export async function fetchDayCloses(
  token: string,
  params: { datee?: string; limit?: number } = {},
  signal?: AbortSignal,
): Promise<DayCloseListResponse> {
  const url = withParams(`${API_URL}/api/v1/drawer/day-close`, {
    datee: params.datee,
    limit: params.limit != null ? String(params.limit) : undefined,
  });
  const res = await fetch(url, { headers: authHeaders(token), signal });
  await throwForStatus(res);
  if (res.status === 204) return { day_closes: [] };
  const body = await readJson<DayCloseListResponse>(res);
  if (!body || !Array.isArray(body.day_closes)) return { day_closes: [] };
  return body;
}

export async function closeDay(
  token: string,
  body: { datee?: string; counted_cash: string },
  signal?: AbortSignal,
): Promise<DayClose> {
  const res = await fetch(`${API_URL}/api/v1/drawer/day-close`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(body),
    signal,
  });
  await throwForStatus(res);
  return readJson<DayClose>(res);
}

export async function reopenDay(
  token: string,
  closeId: number,
  signal?: AbortSignal,
): Promise<DayClose> {
  const res = await fetch(`${API_URL}/api/v1/drawer/day-close/${closeId}/reopen`, {
    method: 'POST',
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return readJson<DayClose>(res);
}

// ── Manual journals ────────────────────────────────────────────────────────

export interface ManualJournalLineIn {
  account_code: string;
  debit?: string;
  credit?: string;
  note?: string;
}

export interface ManualJournalCreateBody {
  datee: string;
  description: string;
  lines: ManualJournalLineIn[];
}

export type ManualJournalEntry = Record<string, unknown>;

export interface ManualJournalListResponse {
  entries: ManualJournalEntry[];
}

export async function fetchManualJournals(
  token: string,
  params: { limit?: number } = {},
  signal?: AbortSignal,
): Promise<ManualJournalListResponse> {
  const url = withParams(`${API_URL}/api/v1/journals/manual`, {
    limit: params.limit != null ? String(params.limit) : undefined,
  });
  const res = await fetch(url, { headers: authHeaders(token), signal });
  await throwForStatus(res);
  if (res.status === 204) return { entries: [] };
  const body = await readJson<ManualJournalListResponse>(res);
  if (!body || !Array.isArray(body.entries)) return { entries: [] };
  return body;
}

export async function fetchManualJournal(
  token: string,
  entryId: number,
  signal?: AbortSignal,
): Promise<ManualJournalEntry> {
  const res = await fetch(`${API_URL}/api/v1/journals/manual/${entryId}`, {
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return readJson<ManualJournalEntry>(res);
}

export async function createManualJournal(
  token: string,
  body: ManualJournalCreateBody,
  signal?: AbortSignal,
): Promise<ManualJournalEntry> {
  const res = await fetch(`${API_URL}/api/v1/journals/manual`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(body),
    signal,
  });
  await throwForStatus(res);
  return readJson<ManualJournalEntry>(res);
}

export async function reverseManualJournal(
  token: string,
  entryId: number,
  signal?: AbortSignal,
): Promise<ManualJournalEntry> {
  const res = await fetch(`${API_URL}/api/v1/journals/manual/${entryId}/reverse`, {
    method: 'POST',
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return readJson<ManualJournalEntry>(res);
}

// ── Statements / payables ──────────────────────────────────────────────────

export interface StatementParams {
  month?: string;
  year?: string;
  date_from?: string;
  date_to?: string;
  side?: string;
}

export type PartyStatement = Record<string, unknown>;

export async function fetchStatement(
  token: string,
  partyId: number,
  params: StatementParams = {},
  signal?: AbortSignal,
): Promise<PartyStatement> {
  const url = withParams(`${API_URL}/api/v1/parties/${partyId}/statement`, {
    month: params.month,
    year: params.year,
    date_from: params.date_from,
    date_to: params.date_to,
    side: params.side,
  });
  const res = await fetch(url, { headers: authHeaders(token), signal });
  await throwForStatus(res);
  return readJson<PartyStatement>(res);
}

export type PayablesPayload = Record<string, unknown>;

export async function fetchPayables(token: string, signal?: AbortSignal): Promise<PayablesPayload> {
  const res = await fetch(`${API_URL}/api/v1/parties/payables`, {
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  if (res.status === 204) return { payables: [] };
  return readJson<PayablesPayload>(res);
}

// ── Receivables / settlement vouchers ──────────────────────────────────────

export interface VoucherCreateBody {
  voucher_type: 'receipt' | 'payment';
  party_id: number;
  datee: string;
  method: 'cash' | 'network' | 'card';
  amount: string;
  description?: string;
}

export type SettlementVoucher = Record<string, unknown>;

export interface VoucherListResponse {
  vouchers: SettlementVoucher[];
}

export async function fetchVouchers(
  token: string,
  params: { limit?: number } = {},
  signal?: AbortSignal,
): Promise<VoucherListResponse> {
  const url = withParams(`${API_URL}/api/v1/receivables/vouchers`, {
    limit: params.limit != null ? String(params.limit) : undefined,
  });
  const res = await fetch(url, { headers: authHeaders(token), signal });
  await throwForStatus(res);
  if (res.status === 204) return { vouchers: [] };
  const body = await readJson<VoucherListResponse>(res);
  if (!body || !Array.isArray(body.vouchers)) return { vouchers: [] };
  return body;
}

export async function createVoucher(
  token: string,
  body: VoucherCreateBody,
  signal?: AbortSignal,
): Promise<SettlementVoucher> {
  const res = await fetch(`${API_URL}/api/v1/receivables/vouchers`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(body),
    signal,
  });
  await throwForStatus(res);
  return readJson<SettlementVoucher>(res);
}

export async function reverseVoucher(
  token: string,
  voucherId: number,
  signal?: AbortSignal,
): Promise<SettlementVoucher> {
  const res = await fetch(`${API_URL}/api/v1/receivables/vouchers/${voucherId}/reverse`, {
    method: 'POST',
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return readJson<SettlementVoucher>(res);
}

export type ReceivablesPayload = Record<string, unknown>;

export async function fetchReceivables(
  token: string,
  signal?: AbortSignal,
): Promise<ReceivablesPayload> {
  const res = await fetch(`${API_URL}/api/v1/receivables`, {
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  if (res.status === 204) return { receivables: [] };
  return readJson<ReceivablesPayload>(res);
}

// ── Trial balance / balance sheet ──────────────────────────────────────────

export interface MizanParams {
  month?: string;
  year?: string;
  date_from?: string;
  date_to?: string;
}

export type MizanPayload = Record<string, unknown>;

function mizanQuery(params: MizanParams): Record<string, string | undefined> {
  return {
    month: params.month,
    year: params.year,
    date_from: params.date_from,
    date_to: params.date_to,
  };
}

export async function fetchTrialBalance(
  token: string,
  params: MizanParams = {},
  signal?: AbortSignal,
): Promise<MizanPayload> {
  const url = withParams(`${API_URL}/api/v1/accounts/trial-balance`, mizanQuery(params));
  const res = await fetch(url, { headers: authHeaders(token), signal });
  await throwForStatus(res);
  return readJson<MizanPayload>(res);
}

export async function fetchBalanceSheet(
  token: string,
  params: MizanParams = {},
  signal?: AbortSignal,
): Promise<MizanPayload> {
  const url = withParams(`${API_URL}/api/v1/accounts/balance-sheet`, mizanQuery(params));
  const res = await fetch(url, { headers: authHeaders(token), signal });
  await throwForStatus(res);
  return readJson<MizanPayload>(res);
}

export async function fetchBalanceSheetHtml(
  token: string,
  params: MizanParams = {},
  signal?: AbortSignal,
): Promise<string> {
  const url = withParams(`${API_URL}/api/v1/accounts/balance-sheet`, mizanQuery(params));
  const sep = url.includes('?') ? '&' : '?';
  const res = await fetch(`${url}${sep}format=html`, {
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return await res.text();
}

// ── Months / opening balances ──────────────────────────────────────────────

export type MonthClose = Record<string, unknown>;

export interface MonthListResponse {
  months: MonthClose[];
}

export async function fetchMonths(token: string, signal?: AbortSignal): Promise<MonthListResponse> {
  const res = await fetch(`${API_URL}/api/v1/months`, {
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  if (res.status === 204) return { months: [] };
  const body = await readJson<MonthListResponse>(res);
  if (!body || !Array.isArray(body.months)) return { months: [] };
  return body;
}

export async function fetchMonth(
  token: string,
  year: number,
  month: number,
  signal?: AbortSignal,
): Promise<MonthClose> {
  const res = await fetch(`${API_URL}/api/v1/months/${year}/${month}`, {
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return readJson<MonthClose>(res);
}

export async function fetchOpenBalances(
  token: string,
  year: number,
  month: number,
  signal?: AbortSignal,
): Promise<MonthClose> {
  const res = await fetch(`${API_URL}/api/v1/months/${year}/${month}/open-balances`, {
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return readJson<MonthClose>(res);
}

export async function closeMonth(
  token: string,
  year: number,
  month: number,
  signal?: AbortSignal,
): Promise<MonthClose> {
  const res = await fetch(`${API_URL}/api/v1/months/${year}/${month}/close`, {
    method: 'POST',
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return readJson<MonthClose>(res);
}

export async function reopenMonth(
  token: string,
  year: number,
  month: number,
  signal?: AbortSignal,
): Promise<MonthClose> {
  const res = await fetch(`${API_URL}/api/v1/months/${year}/${month}/reopen`, {
    method: 'POST',
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return readJson<MonthClose>(res);
}

export type OpeningPayload = Record<string, unknown>;

export async function fetchOpeningBalances(
  token: string,
  year: number,
  month: number,
  signal?: AbortSignal,
): Promise<OpeningPayload> {
  const res = await fetch(`${API_URL}/api/v1/opening-balances/${year}/${month}`, {
    headers: authHeaders(token),
    signal,
  });
  await throwForStatus(res);
  return readJson<OpeningPayload>(res);
}
