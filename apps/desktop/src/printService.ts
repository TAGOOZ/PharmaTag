/**
 * PrintService — printer-per-purpose abstraction (plan/03 §5.5, P09).
 * Desktop: ESC/POS thermal + drawer + labels via Rust `printing` commands.
 * Web: fallback to PDF/80mm via `window.print()` + `@page:80mm`.
 *
 * Printer-per-purpose selection (receipt/barcode/A4/label) + `app_config`
 * persistence, Windows + Linux (Linux `lp`/`usb` via Rust, Windows via winspool).
 * Offline / no printer / paper-out / permission denied are surfaced as Err, never panic.
 */

import type { SqlRunner } from './db';

// Re-export for tests
export type PrinterPurpose = 'receipt' | 'barcode' | 'a4' | 'label';

export type PrinterConfig = {
  receiptPrinter?: string;
  barcodePrinter?: string;
  a4Printer?: string;
  labelPrinter?: string;
  autoPrint?: boolean;
  openDrawerOnPrint?: boolean;
};

// app_config keys — printer-per-purpose
const KEYS: Record<keyof PrinterConfig, string> = {
  receiptPrinter: 'printer_receipt',
  barcodePrinter: 'printer_barcode',
  a4Printer: 'printer_a4',
  labelPrinter: 'printer_label',
  autoPrint: 'printer_auto_print',
  openDrawerOnPrint: 'printer_open_drawer',
};

// Detect Tauri runtime — if not present, we're in web fallback or Vitest
function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window;
}

// Lazy invoke — avoids hard dep on @tauri-apps/api in Vitest (which mocks window)
async function tauriInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  // Dynamic import so web bundle doesn't pull Tauri
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<T>(cmd, args);
}

/**
 * Read printer config from local SQLite `app_config` (or fallback to empty).
 * Mirrors server `Branch.printer_config` JSONB but per-device via `app_config`.
 */
export async function getPrinterConfig(db: SqlRunner): Promise<PrinterConfig> {
  try {
    const rows = await db.select<{ key: string; value: string }>(
      `SELECT key, value FROM app_config WHERE key IN ('${Object.values(KEYS).join("','")}')`,
    );
    const map = new Map(rows.map((r) => [r.key, r.value]));
    const cfg: PrinterConfig = {};
    for (const [field, key] of Object.entries(KEYS) as [keyof PrinterConfig, string][]) {
      const v = map.get(key);
      if (v == null || v === '') continue;
      if (field === 'autoPrint' || field === 'openDrawerOnPrint') {
        (cfg as Record<string, unknown>)[field] = v === 'true';
      } else {
        (cfg as Record<string, unknown>)[field] = v;
      }
    }
    return cfg;
  } catch {
    return {};
  }
}

export async function setPrinterConfig(
  db: SqlRunner,
  patch: Partial<PrinterConfig>,
): Promise<void> {
  for (const [field, value] of Object.entries(patch) as [keyof PrinterConfig, unknown][]) {
    const key = KEYS[field];
    if (!key) continue;
    const str = typeof value === 'boolean' ? String(value) : String(value ?? '');
    // UPSERT app_config
    await db.execute(
      `INSERT INTO app_config (key, value, updated_at) VALUES (?, ?, datetime('now')) ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now')`,
      [key, str, str],
    );
  }
}

export function printerForPurpose(cfg: PrinterConfig, purpose: PrinterPurpose): string | undefined {
  switch (purpose) {
    case 'receipt':
      return cfg.receiptPrinter;
    case 'barcode':
      return cfg.barcodePrinter;
    case 'a4':
      return cfg.a4Printer;
    case 'label':
      return cfg.labelPrinter;
  }
}

/** List OS printers via Rust `list_printers` — empty array if offline/no printers. */
export async function listPrinters(): Promise<string[]> {
  if (!isTauri()) return [];
  try {
    const printers = await tauriInvoke<string[]>('list_printers');
    return Array.isArray(printers) ? printers : [];
  } catch (e) {
    // permission denied / offline / no printer — surface as empty, caller can check
    if (String(e).toLowerCase().includes('permission')) throw e;
    return [];
  }
}

/** Raw ESC/POS bytes to printer — desktop via Rust, web falls back to `window.print()` preview. */
export async function printRaw(printerName: string, data: Uint8Array): Promise<void> {
  if (!data || data.length === 0) throw new Error('no data to print');
  if (data.length > 1024 * 1024) throw new Error('payload too large');

  if (!isTauri()) {
    // Web fallback: use window.print() with 80mm @page — caller should have rendered HTML
    // For raw bytes we cannot print thermally on web, so we open a print preview with hex dump
    if (typeof window !== 'undefined' && typeof window.print === 'function') {
      // Minimal fallback — real web wiring is #38 POS auto-print
      window.print();
      return;
    }
    throw new Error('printing not available on web (no Tauri)');
  }

  // Tauri path — bytes as number array for serde
  await tauriInvoke('print_raw', {
    printerName: printerName ?? '',
    data: Array.from(data),
  });
}

/** Cash drawer pulse `ESC p` — desktop only, web is no-op (browser cannot pulse). */
export async function openDrawer(printerName?: string): Promise<void> {
  if (!isTauri()) {
    // Web: no drawer hardware — no-op but not an error (spec: hardware only on desktop)
    return;
  }
  await tauriInvoke('open_drawer', { printerName: printerName ?? '' });
}

/** ZPL/EPL label to label printer. */
export async function printLabel(printerName: string, zpl: string): Promise<void> {
  if (!zpl || zpl.trim() === '') throw new Error('no ZPL data');
  if (!isTauri()) {
    if (typeof window !== 'undefined' && typeof window.print === 'function') {
      window.print();
      return;
    }
    throw new Error('label printing not available on web');
  }
  await tauriInvoke('print_label', { printerName: printerName ?? '', zpl });
}

/** Convenience: print receipt text lines via ESC/POS. Builds bytes in Rust `build_receipt_bytes` helper. */
export async function printReceipt(
  printerName: string,
  lines: string[],
  opts?: { cut?: boolean },
): Promise<void> {
  const text = lines.join('\n');
  const data = new TextEncoder().encode(text);
  // Add cut if requested — real ESC/POS cut handled in Rust build_receipt_bytes, but we just append here
  const payload = opts?.cut ? new Uint8Array([...data, 0x1d, 0x56, 0x00]) : data;
  await printRaw(printerName, payload);
}

/** Edge-case helper — check if printing is available (Tauri + at least one printer). */
export async function isPrintingAvailable(): Promise<boolean> {
  if (!isTauri()) return false;
  try {
    const printers = await listPrinters();
    return printers.length > 0;
  } catch {
    return false;
  }
}
