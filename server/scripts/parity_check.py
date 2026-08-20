#!/usr/bin/env python
"""Twin-parity CI guard (plan/01 §4.3#2).

Asserts the Postgres (Alembic) and SQLite twin describe the SAME table/column
set and that the money scale mapping holds — PG NUMERIC(n,s) <-> SQLite INTEGER
(value × 10^s). Never a REAL/FLOAT/DOUBLE on PG. Fails the build if the twins
drift again. Both sides are parsed across all migration scripts (CREATE TABLE
+ incremental ALTER TABLE ADD COLUMN), so later revisions stay parity'd too.

Usage: python scripts/parity_check.py  (run from server/; needs alembic on PATH)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent

# plugin-owned [S] tables that must NOT be in core rev 001 (A08)
PLUGIN_TABLES = {
    "einvoice_log", "einvoice_counters",
    "transfers", "transfer_lines", "needs", "purchase_orders", "dead_stock_exchange",
    "chain_buy_orders", "branch_registry", "drug_sync_outbox", "drug_interactions",
    "external_drug_catalog", "archive_imports", "archive_exports", "user_drawer_money",
}

CREATE_RE = re.compile(r"CREATE TABLE (?:IF NOT EXISTS )?(\w+)\s*\((.*?)\);", re.S | re.I)
# incremental column adds: alembic `op.add_column` renders as ALTER TABLE
# ADD COLUMN in offline SQL — captured so post-rev-001 migrations stay parity'd.
ALTER_ADD_COL_RE = re.compile(
    r"ALTER TABLE (\w+)\s+ADD COLUMN\s+(\w+)\s+(\S+)", re.I
)
# lines that open a table-body continuation (constraints), not a column
CONSTRAINT_KW = {"PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "REFERENCES"}


def _columns(body: str) -> dict[str, str]:
    cols: dict[str, str] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\w+)\s+(\S+)", line)
        if not m:
            continue
        name, typ = m.group(1), m.group(2)
        if name.upper() in CONSTRAINT_KW:
            continue
        typ = typ.rstrip(",").rstrip(";").rstrip("(")
        cols[name] = typ
    return cols


def parse_sqlite(paths: list[Path]) -> dict[str, dict[str, str]]:
    """Parse the SQLite twin across ALL migration scripts (001 base + later
    incremental ALTER TABLE ADD COLUMN scripts), merging into one table map."""
    tables: dict[str, dict[str, str]] = {}
    for path in paths:
        sql = path.read_text(encoding="utf-8")
        for m in CREATE_RE.finditer(sql):
            name = m.group(1)
            if name == "schema_migrations":
                continue
            tables[name] = _columns(m.group(2))
        for m in ALTER_ADD_COL_RE.finditer(sql):
            name, col, typ = m.group(1), m.group(2), m.group(3)
            tables.setdefault(name, {})[col] = typ.rstrip(",").rstrip(";").rstrip("(")
    return tables


def parse_postgres_offline() -> dict[str, dict[str, str]]:
    sql = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=SERVER, capture_output=True, text=True, check=True,
    ).stdout
    tables: dict[str, dict[str, str]] = {}
    for m in CREATE_RE.finditer(sql):
        name = m.group(1)
        if name == "alembic_version":
            continue
        tables[name] = _columns(m.group(2))
    for m in ALTER_ADD_COL_RE.finditer(sql):
        name, col, typ = m.group(1), m.group(2), m.group(3)
        tables.setdefault(name, {})[col] = typ.rstrip(",").rstrip(";").rstrip("(")
    return tables


def normalize(pg_type: str) -> str:
    t = pg_type.upper().replace("WITH TIME ZONE", "TZ").strip()
    return t


def main() -> int:
    sqlite = parse_sqlite(sorted((SERVER / "sqlite" / "migrations").glob("*.sql")))
    pg = parse_postgres_offline()
    # the desktop runtime twin — a single merged script the Tauri app bundles
    # (`apps/desktop/src/resources/schema_sqlite.sql`) and applies on first boot.
    desktop = parse_sqlite([SERVER.parent / "schema" / "schema_sqlite.sql"])

    errors: list[str] = []

    for t in sqlite:
        if t not in pg:
            errors.append(f"SQLite table {t!r} missing from Postgres")
    for t in pg:
        if t not in sqlite:
            errors.append(f"Postgres table {t!r} missing from SQLite twin")

    # the desktop bundle must describe the exact same schema as the migrations twin
    for t in sqlite:
        if t not in desktop:
            errors.append(f"desktop twin missing table {t!r} (schema/schema_sqlite.sql)")
    for t in desktop:
        if t not in sqlite:
            errors.append(f"desktop twin has extra table {t!r} (not in migrations twin)")
    for t in sqlite:
        if t not in desktop:
            continue
        for col, stype in sqlite[t].items():
            if col not in desktop[t]:
                errors.append(f"desktop twin missing column {t}.{col}")
            elif desktop[t][col] != stype:
                errors.append(
                    f"desktop twin type drift: {t}.{col} is {desktop[t][col]} "
                    f"(migrations twin: {stype})"
                )
        for col in desktop[t]:
            if col not in sqlite[t]:
                errors.append(f"desktop twin extra column {t}.{col}")

    for t in pg:
        if t in PLUGIN_TABLES:
            errors.append(f"plugin-owned table {t!r} leaked into core rev 001 (A08)")
        if t in ("drug_sync_outbox", "branch_registry"):
            continue
        for col, ptype in pg[t].items():
            if col in ("id",) and "GENERATED" in ptype.upper():
                continue
            if t in sqlite and col not in sqlite[t]:
                errors.append(f"Postgres column {t}.{col} missing from SQLite")
            nt = normalize(ptype)
            if any(bad in nt for bad in ("REAL", "FLOAT", "DOUBLE")):
                errors.append(f"REAL/FLOAT money leak: {t}.{col} is {ptype}")
            if nt.startswith("NUMERIC"):
                if t not in sqlite or sqlite[t].get(col, "").upper() != "INTEGER":
                    errors.append(
                        f"money type drift: PG {t}.{col} {ptype} "
                        f"-> SQLite {sqlite[t].get(col, 'MISSING')} (must be INTEGER minor units)"
                    )
        for col in sqlite.get(t, {}):
            if col not in pg[t]:
                errors.append(f"SQLite column {t}.{col} missing from Postgres")

    if errors:
        print("PARITY FAIL")
        for e in sorted(set(errors)):
            print(" -", e)
        return 1
    print(
        f"PARITY OK — {len(pg)} tables, {sum(len(c) for c in pg.values())} PG columns "
        f"mirrored in SQLite twin + desktop bundle (schema/schema_sqlite.sql); "
        f"no REAL/FLOAT money; no plugin tables in core."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())