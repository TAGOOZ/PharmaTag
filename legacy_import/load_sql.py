"""Load decoded .phy JSONL into the target schema (PostgreSQL or SQLite).

Target tables follow schema_complete.sql + SCHEMA_EVALUATION.md:
  Daily.phy         -> drawer_movements / daily_close
  daily-manual.phy  -> manual_journal_entries
  usersmony.phy     -> user_drawer_money
  delivery.phy      -> transfers (status)

Mode:
  --dry-run   print row counts and a sample (default, no DB needed)
  --psql DSN  use psycopg (postgres)  [not bundled; requires psycopg2]
  --sqlite FILE  write into SQLite DB (stdlib)
"""
import argparse
import json
import os
import sqlite3
import sys

MAPPINGS = {
    "Daily.phy": {
        "table": "drawer_movements",
        "row": lambda d: {
            "record_no": d["_recno"],
            "amount": d.get("money0"),
            "amount_secondary": d.get("money1"),
            "amount_tertiary": d.get("money2"),
            "txn_count": d.get("txn_count"),
        },
    },
    "daily-manual.phy": {
        "table": "manual_journal_entries",
        "row": lambda d: {"record_no": d["_recno"], "amount": d.get("money0")},
    },
    "daily-manual-2.phy": {
        "table": "manual_journal_entries",
        "row": lambda d: {"record_no": d["_recno"], "amount": d.get("money0")},
    },
    "usersmony.phy": {
        "table": "user_drawer_money",
        "row": lambda d: {
            "record_no": d["_recno"],
            "user_idx": d.get("user_idx"),
            "amount": d.get("money"),
        },
    },
    "delivery.phy": {
        "table": "transfers",
        "row": lambda d: {"record_no": d["_recno"], "status": 0},  # placeholder
    },
    "tar.phy": {
        "table": "drugs",
        "row": lambda d: {
            "record_no": d["_recno"],
            "name_en": d.get("name_en"),
            "name_ar": d.get("name_ar"),
        },
    },
}


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def dry_run(jsonl_path):
    base = os.path.basename(jsonl_path).replace(".jsonl", "")
    spec = MAPPINGS.get(base)
    if spec is None:
        return {"file": jsonl_path, "status": "NO_MAPPING", "rows": 0}
    rows = 0
    sample = []
    for d in load_jsonl(jsonl_path):
        rows += 1
        if len(sample) < 2:
            sample.append(spec["row"](d))
    return {"file": jsonl_path, "table": spec["table"], "status": "OK", "rows": rows, "sample": sample}


def to_sqlite(jsonl_path, db_path):
    base = os.path.basename(jsonl_path).replace(".jsonl", "")
    spec = MAPPINGS.get(base)
    if spec is None:
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rows = [spec["row"](d) for d in load_jsonl(jsonl_path)]
    cols = list(rows[0].keys()) if rows else ["record_no"]
    placeholders = ",".join("?" * len(cols))
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS {spec['table']} ({', '.join(cols)})"
    )
    cur.executemany(
        f"INSERT OR REPLACE INTO {spec['table']} ({','.join(cols)}) VALUES ({placeholders})",
        [tuple(r[c] for c in cols) for r in rows],
    )
    conn.commit()
    cur.execute(f"SELECT COUNT(*) FROM {spec['table']}")
    n = cur.fetchone()[0]
    conn.close()
    return {"table": spec["table"], "rows_in_table": n, "inserted": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", nargs="+", help="one or more .jsonl from migrate_phy.py")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--sqlite", default=None, help="write into this SQLite file")
    args = ap.parse_args()

    for p in args.jsonl:
        if args.sqlite:
            r = to_sqlite(p, args.sqlite)
            print(f"[{r['table'] if r else 'NO_MAP':20s}] {os.path.basename(p)} -> {r}")
        else:
            r = dry_run(p)
            print(f"[{r['status']:20s}] {os.path.basename(p)} rows={r['rows']} table={r.get('table')}")
            if r.get("sample"):
                print("   sample:", json.dumps(r["sample"], ensure_ascii=False))


if __name__ == "__main__":
    main()