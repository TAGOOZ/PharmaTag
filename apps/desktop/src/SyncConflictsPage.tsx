import { StatusChip } from '@pharmatag/ui';
import type Database from '@tauri-apps/plugin-sql';
import { useEffect, useState } from 'react';
import type { SqlRunner } from './db';

type SyncConflictRow = {
  id: number;
  branch_id: number;
  entity: string;
  entity_id: number | null;
  payload: string | null; // TEXT JSON
  status: string;
  created_at: string | null;
  synced_at: string | null;
};

type Conflict = {
  id: number;
  branch_id: number;
  entity: string;
  loser: Record<string, unknown>;
  winner: Record<string, unknown> | null;
  skipped_reason: string;
  updated_at: string | null;
  resolved: boolean;
};

type PageState = 'loading' | 'ready' | 'error';

function parsePayload(text: string | null): Record<string, unknown> {
  if (!text) return {};
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return {};
  }
}

/** Convert exact 4dp string like "10.0000" to minor units integer (×10000). */
function toMinorUnits(v: unknown): number | null {
  if (v == null) return null;
  const s = String(v).trim();
  if (s === '') return null;
  // exact 4dp via string split to avoid binary float error
  const neg = s.startsWith('-');
  const abs = neg ? s.slice(1) : s;
  const [intPart, fracPart = ''] = abs.split('.');
  const frac = `${fracPart}0000`.slice(0, 4);
  const minor = Number(intPart) * 10000 + Number(frac);
  return neg ? -minor : minor;
}

/**
 * Desktop offline sync conflict panel (G10, #60) — reads the local SQLite
 * `sync_log` replica directly (no network). RTL, empty state, light/dark.
 */
export function SyncConflictsPage({ db }: { db: Database | SqlRunner | null }) {
  const [state, setState] = useState<PageState>(db ? 'loading' : 'error');
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [filter, setFilter] = useState<string>('');
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    if (!db) return;
    let cancelled = false;
    (async () => {
      try {
        const rows = await (db as SqlRunner).select<SyncConflictRow>(
          "SELECT id, branch_id, entity, entity_id, payload, status, created_at, synced_at FROM sync_log WHERE status IN ('applied','skipped') ORDER BY id DESC",
        );
        if (cancelled) return;
        const list: Conflict[] = [];
        for (const r of rows) {
          const payload = parsePayload(r.payload);
          const reason = payload.skipped_reason as string | undefined;
          if (!reason) continue;
          const loser: Record<string, unknown> = {};
          for (const [k, v] of Object.entries(payload)) {
            if (
              !['skipped_reason', 'failure', 'resolved', 'resolved_at', 'restored_at'].includes(k)
            ) {
              loser[k] = v;
            }
          }
          // winner: try to fetch local winner for branch_stock / transfer / branch
          let winner: Record<string, unknown> | null = null;
          let updatedAt: string | null =
            (r.synced_at as string) ?? (r.created_at as string) ?? null;
          try {
            if (r.entity === 'branch_stock') {
              const drugId = (loser as { drug_id?: number }).drug_id;
              if (drugId != null) {
                const w = await (db as SqlRunner).select<{
                  qty: number;
                  minimum: number;
                  silsilaid: string;
                  classy: string;
                  lastedit: string | null;
                }>(
                  'SELECT qty, minimum, silsilaid, classy, lastedit FROM branch_stock WHERE branch_id = ? AND drug_id = ?',
                  [Number(r.branch_id), Number(drugId)],
                );
                if (w.length > 0) {
                  const row = w[0] as {
                    qty: number;
                    minimum: number;
                    silsilaid: string;
                    classy: string;
                    lastedit: string | null;
                  };
                  winner = {
                    branch_id: r.branch_id,
                    drug_id: drugId,
                    qty: String(row.qty),
                    minimum: String(row.minimum),
                    silsilaid: row.silsilaid ?? '',
                    classy: row.classy ?? '',
                    lastedit: row.lastedit,
                  };
                  updatedAt = row.lastedit ?? updatedAt;
                }
              }
            } else if (r.entity === 'branch') {
              const bid = (loser as { id?: number }).id;
              if (bid != null) {
                const w = await (db as SqlRunner).select<{
                  pharmacyid: string;
                  pharname: string;
                  updated_at: string | null;
                }>('SELECT pharmacyid, pharname, updated_at FROM branches WHERE id = ?', [
                  Number(bid),
                ]);
                if (w.length > 0) {
                  const row = w[0] as {
                    pharmacyid: string;
                    pharname: string;
                    updated_at: string | null;
                  };
                  winner = row as unknown as Record<string, unknown>;
                  updatedAt = row.updated_at ?? updatedAt;
                }
              }
            } else if (r.entity === 'transfer') {
              const tno = (loser as { transfer_no?: string }).transfer_no;
              const sid = (loser as { source_branch_id?: number }).source_branch_id;
              if (tno && sid != null) {
                const w = await (db as SqlRunner).select<{
                  status: string;
                  rev: number;
                  created_at: string | null;
                }>(
                  'SELECT status, rev, created_at FROM transfers WHERE source_branch_id = ? AND transfer_no = ?',
                  [Number(sid), String(tno)],
                );
                if (w.length > 0) {
                  const row = w[0] as { status: string; rev: number; created_at: string | null };
                  winner = row as unknown as Record<string, unknown>;
                  updatedAt = row.created_at ?? updatedAt;
                }
              }
            }
          } catch {
            // winner fetch is best-effort
          }
          list.push({
            id: r.id,
            branch_id: r.branch_id,
            entity: r.entity,
            loser,
            winner,
            skipped_reason: reason,
            updated_at: updatedAt,
            resolved: Boolean((payload as Record<string, unknown>).resolved),
          });
        }
        if (cancelled) return;
        setConflicts(list);
        setState('ready');
      } catch {
        if (!cancelled) setState('error');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [db]);

  async function restore(id: number) {
    if (!db) return;
    setBusyId(id);
    try {
      // Find conflict
      const c = conflicts.find((x) => x.id === id);
      if (!c) return;
      // Reapply loser as new state (non-destructive: new rev / updated_at now)
      const now = new Date().toISOString();
      const runner = db as SqlRunner;
      // helper to run in a single SQLite transaction (G12 atomic)
      const inTx = async (fn: () => Promise<void>) => {
        await runner.execute('BEGIN IMMEDIATE');
        try {
          await fn();
          await runner.execute('COMMIT');
        } catch (e) {
          try {
            await runner.execute('ROLLBACK');
          } catch {}
          throw e;
        }
      };

      if (c.entity === 'branch_stock') {
        const loser = c.loser as {
          drug_id?: number;
          qty?: string;
          minimum?: string;
          silsilaid?: string;
          classy?: string;
        };
        if (loser.drug_id == null) throw new Error('malformed loser');
        const qtyMinor = toMinorUnits(loser.qty);
        const minMinor = toMinorUnits(loser.minimum);
        const silsilaid = loser.silsilaid ?? '';
        const classy = loser.classy ?? '';

        await inTx(async () => {
          // For null qty/minimum we must keep existing value; fetch current first
          let finalQty: number | null = qtyMinor;
          let finalMin: number | null = minMinor;
          let existingQty: number | null = null;
          let existingMin: number | null = null;
          if (qtyMinor == null || minMinor == null) {
            const cur = await runner.select<{ qty: number; minimum: number }>(
              'SELECT qty, minimum FROM branch_stock WHERE branch_id = ? AND drug_id = ?',
              [Number(c.branch_id), Number(loser.drug_id)],
            );
            if (cur.length > 0) {
              const row = cur[0] as { qty: number; minimum: number };
              existingQty = row.qty;
              existingMin = row.minimum;
              if (finalQty == null) finalQty = existingQty;
              if (finalMin == null) finalMin = existingMin;
            } else {
              if (finalQty == null) finalQty = 0;
              if (finalMin == null) finalMin = 0;
            }
          }
          // UPSERT branch_stock with loser values (exact minor units)
          await runner.execute(
            'INSERT INTO branch_stock (branch_id, drug_id, qty, minimum, silsilaid, classy, lastedit) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(branch_id, drug_id) DO UPDATE SET qty = ?, minimum = ?, silsilaid = ?, classy = ?, lastedit = ?',
            [
              Number(c.branch_id),
              Number(loser.drug_id),
              finalQty ?? 0,
              finalMin ?? 0,
              String(silsilaid),
              String(classy),
              now,
              finalQty ?? 0,
              finalMin ?? 0,
              String(silsilaid),
              String(classy),
              now,
            ],
          );
          // enqueue new sync outbox row (applied immediately in local twin context)
          const payloadObj = {
            branch_id: c.branch_id,
            drug_id: loser.drug_id,
            qty: loser.qty,
            minimum: loser.minimum,
            silsilaid: silsilaid,
            classy: classy,
          };
          await runner.execute(
            'INSERT INTO sync_log (branch_id, entity, entity_id, action, payload, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
              Number(c.branch_id),
              'branch_stock',
              Number(loser.drug_id),
              'update',
              JSON.stringify(payloadObj),
              'applied',
              now,
            ],
          );
          // mark original as resolved (payload JSON update)
          const rows = await runner.select<{ payload: string }>(
            'SELECT payload FROM sync_log WHERE id = ?',
            [Number(id)],
          );
          if (rows.length > 0) {
            const orig = parsePayload((rows[0] as { payload: string }).payload);
            const updated = { ...orig, resolved: true, resolved_at: now };
            await runner.execute('UPDATE sync_log SET payload = ? WHERE id = ?', [
              JSON.stringify(updated),
              Number(id),
            ]);
          }
          // audit
          await runner.execute(
            'INSERT INTO audit_log (branch_id, entity, entity_id, field, old_value, new_value, action, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [
              Number(c.branch_id),
              'branch_stock',
              Number(loser.drug_id),
              'restore',
              'winner kept',
              JSON.stringify(loser),
              'update',
              now,
            ],
          );
        });
        // refresh list: mark as resolved locally
        setConflicts((prev) => prev.map((x) => (x.id === id ? { ...x, resolved: true } : x)));
      } else {
        // generic: just mark resolved and audit — also atomic
        await inTx(async () => {
          const rows = await runner.select<{ payload: string }>(
            'SELECT payload FROM sync_log WHERE id = ?',
            [Number(id)],
          );
          if (rows.length > 0) {
            const orig = parsePayload((rows[0] as { payload: string }).payload);
            const updated = { ...orig, resolved: true, resolved_at: now };
            await runner.execute('UPDATE sync_log SET payload = ? WHERE id = ?', [
              JSON.stringify(updated),
              Number(id),
            ]);
          }
          await runner.execute(
            'INSERT INTO audit_log (branch_id, entity, field, old_value, new_value, action, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
              Number(c.branch_id),
              String(c.entity),
              'restore',
              String(c.skipped_reason),
              JSON.stringify(c.loser),
              'update',
              now,
            ],
          );
        });
        setConflicts((prev) => prev.map((x) => (x.id === id ? { ...x, resolved: true } : x)));
      }
    } catch {
      // restore failed — leave as unresolved
    } finally {
      setBusyId(null);
    }
  }

  const chip =
    state === 'loading' ? (
      <StatusChip kind="offline" labelAr="جارٍ التحميل" labelEn="Loading" />
    ) : state === 'ready' ? (
      <StatusChip kind="online" labelAr="محلي" labelEn="Offline SQLite" />
    ) : (
      <StatusChip kind="saved" labelAr="خطأ القراءة" labelEn="Read error" />
    );

  const filtered = filter ? conflicts.filter((c) => c.entity === filter) : conflicts;

  return (
    <section className="flex h-full flex-col gap-4" dir="rtl">
      <div className="flex items-center gap-3">
        <h1 className="pt-title text-2xl">تعارضات المزامنة</h1>
        {chip}
        <span className="pt-caption rounded-full bg-[var(--background-secondary)] px-3 py-1 text-sm">
          LWW — المراجعة غير المدمرة
        </span>
      </div>
      <p className="pt-caption text-sm text-[var(--text-muted)]">
        يعمل هذا الجدول بدون اتصال — يقرأ مباشرة من نسخة `sync_log` المحلية. الخاسر هو الحمولة التي
        تم تخطيها، والرابح هو الحالة الحالية في قاعدة البيانات المحلية.
      </p>

      <div className="flex flex-wrap items-end gap-3 border-b border-[var(--border-primary)] pb-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="pt-caption">تصفية حسب الكيان</span>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded border border-[var(--border-primary)] bg-transparent px-2 py-1"
          >
            <option value="">الكل</option>
            <option value="branch_stock">رصيد الفرع</option>
            <option value="transfer">تحويل</option>
            <option value="branch">فرع</option>
            <option value="branch_identity">هوية فرع</option>
            <option value="need">حاجة</option>
            <option value="purchase_order">طلب شراء</option>
            <option value="chain_buy_order">طلب شراء جماعي</option>
            <option value="invoice">فاتورة</option>
          </select>
        </label>
        <span className="pt-caption text-sm">العدد: {filtered.length}</span>
      </div>

      {state === 'error' ? (
        <p className="pt-caption">تعذّرت قراءة تعارضات `sync_log` من قاعدة البيانات المحلية.</p>
      ) : state === 'loading' ? (
        <p className="pt-caption">جارٍ التحميل…</p>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border-primary)] bg-[var(--background-secondary)] p-8 text-center">
          <p className="pt-title text-lg">لا توجد تعارضات للمراجعة</p>
          <p className="pt-caption text-sm">
            عندما يقوم فرعان بتعديل نفس السجل أثناء عدم الاتصال، سيظهر الخاسر هنا للمراجعة.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-[var(--border-primary)] bg-[var(--background-secondary)]">
                <th className="px-3 py-2 text-start font-bold">المعرف</th>
                <th className="px-3 py-2 text-start font-bold">الكيان</th>
                <th className="px-3 py-2 text-start font-bold">الخاسر</th>
                <th className="px-3 py-2 text-start font-bold">الرابح</th>
                <th className="px-3 py-2 text-start font-bold">تاريخ التحديث</th>
                <th className="px-3 py-2 text-start font-bold">السبب</th>
                <th className="px-3 py-2 text-start font-bold">إجراء</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr
                  key={c.id}
                  className="border-b border-[var(--border-primary)] hover:bg-[var(--background-secondary)]"
                >
                  <td className="px-3 py-2 font-mono text-xs">{c.id}</td>
                  <td className="px-3 py-2">{c.entity}</td>
                  <td className="px-3 py-2">
                    <pre className="max-h-32 max-w-[280px] overflow-auto whitespace-pre-wrap break-words rounded bg-[var(--background-primary)] p-2 text-xs">
                      {JSON.stringify(c.loser, null, 2)}
                    </pre>
                  </td>
                  <td className="px-3 py-2">
                    <pre className="max-h-32 max-w-[280px] overflow-auto whitespace-pre-wrap break-words rounded bg-[var(--background-primary)] p-2 text-xs">
                      {c.winner ? JSON.stringify(c.winner, null, 2) : '—'}
                    </pre>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{c.updated_at ?? '—'}</td>
                  <td className="px-3 py-2 text-xs">{c.skipped_reason}</td>
                  <td className="px-3 py-2">
                    {c.resolved ? (
                      <span className="pt-caption text-xs text-[var(--text-muted)]">
                        تمت الاستعادة
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => restore(c.id)}
                        disabled={busyId === c.id}
                        className="rounded bg-[var(--accent-color)] px-3 py-1 text-xs text-white disabled:opacity-50"
                      >
                        {busyId === c.id ? 'جارٍ…' : 'استعادة'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
