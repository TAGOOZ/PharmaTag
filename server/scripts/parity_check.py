#!/usr/bin/env python
"""Twin-parity CI guard (plan/01 §4.3#2).

Asserts the Postgres (Alembic) and SQLite twin describe the SAME table/column
set and that the money scale mapping holds — PG NUMERIC(n,s) <-> SQLite INTEGER
(value × 10^s). Never a REAL/FLOAT/DOUBLE on PG. Fails the build if the twins
drift again. Both sides are parsed across all migration scripts (CREATE TABLE
+ incremental ALTER TABLE ADD COLUMN), so later revisions stay parity'd too.

Constraint-level parity (#57): every CHECK constraint present on PG must be
present (by normalized expression) in BOTH twins, and the key UNIQUE backstops
must exist in the twin DDL — a dropped constraint in one twin can no longer
print PARITY OK.

Usage: python scripts/parity_check.py  (run from server/; needs alembic on PATH)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

SERVER = Path(__file__).resolve().parent.parent

# plugin-owned [S] tables that must NOT be in core rev 001 (A08).
# einvoice_log/einvoice_counters were reconciled into CORE by S4.1 (#28,
# ADR-0002): the log+counter write is locked inside the sale transaction
# (G12/STRICT A09) with SQLite-twin parity — they are core truth now.
# needs/purchase_orders(_lines) were reconciled into CORE by S5.3 (#33):
# the needs→transfer handoff writes a transfers row and G12 atomicity is core.
# transfers/transfer_lines were reconciled into CORE by S5.2 (#32, T1 —
# ADR-0002 precedent): titaninn.itemsasstring is dead code (0 p-code refs),
# the chain-plugin migration machinery is deferred until a second plugin
# needs it, and the dispatch/receive stock writes need core G12 atomicity.
# dead_stock_exchange/chain_buy_orders were reconciled into CORE by S5.6
# (#36, T1 — ADR-0002 precedent): ChainBuyStore/ChainBuyUsers 12-col merged
# into chain_buy_orders + RawakidTablew roاكد into dead_stock_exchange;
# logistics plugin schema deferred until second plugin needs it.
PLUGIN_TABLES = {
    "branch_registry", "drug_sync_outbox", "drug_interactions",
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
            if name == "schema_migrations" or name.endswith("_new"):
                # `_new` = the SQLite rebuild idiom (rev 029): a temporary copy
                # renamed over the original inside one script, never a real table.
                continue
            tables[name] = _columns(m.group(2))
        for m in ALTER_ADD_COL_RE.finditer(sql):
            name, col, typ = m.group(1), m.group(2), m.group(3)
            tables.setdefault(name, {})[col] = typ.rstrip(",").rstrip(";").rstrip("(")
    return tables


def _paren_end(s: str, open_idx: int) -> int:
    """Index of the ')' matching the '(' at open_idx."""
    depth = 0
    for k in range(open_idx, len(s)):
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return len(s) - 1


def _checks_by_table(sql: str) -> dict[str, dict[str, Optional[str]]]:
    """CHECK constraints grouped by table: {table: {normalized_expr: name|None}}.

    Sources: inline CHECKs inside CREATE TABLE bodies AND `ALTER TABLE … ADD
    CONSTRAINT … CHECK` (offline alembic renders rev-029-style backstops this
    way). Paren-matched so nested parens (IN lists) survive. Table-scoped on
    purpose (#57 drift proof): identical expressions on different tables (two
    `qty >= 0`) must not mask each other.
    """
    tables: dict[str, dict[str, Optional[str]]] = {}
    fragments: list[tuple[str, str]] = []
    for m in CREATE_RE.finditer(sql):
        # group(2) is the lazy-captured table body between '(' and the first ');'
        if not m.group(2):
            continue
        fragments.append((m.group(1), f"({m.group(2)})"))
    for m in re.finditer(
        r"ALTER TABLE (\w+)\s+ADD CONSTRAINT \w+\s+(?:CHECK|UNIQUE)\s*\(",
        sql, re.I,
    ):
        end = _paren_end(sql, m.end() - 1)
        fragments.append((m.group(1), sql[m.start() : end + 1]))
    # incremental ALTER TABLE ADD COLUMN lines can carry their own column-level
    # CHECK (rev 005 twin pattern) — keep the whole statement as a fragment.
    for m in re.finditer(r"ALTER TABLE (\w+)\s+ADD COLUMN[^;]*;", sql, re.I):
        fragments.append((m.group(1), m.group(0)))

    for table, frag in fragments:
        if table in ("alembic_version", "schema_migrations"):
            continue
        found = tables.setdefault(table, {})
        low = frag.lower()
        i = 0
        while True:
            j = low.find("check", i)
            if j < 0:
                break
            op = frag.index("(", j)
            end = _paren_end(frag, op)
            pre = re.search(r"CONSTRAINT (\w+)\s*$", frag[:j], re.I)
            found.setdefault(
                _norm(frag[op + 1 : end]),
                pre.group(1) if pre else None,
            )
            i = end
    return tables


def _norm(s: str) -> str:
    """Whitespace-insensitive comparison form for DDL fragments."""
    return re.sub(r"\s+", "", s.lower())


# Key UNIQUE backstops (patterns.md): the PG side names them, but older twin
# DDL declares them inline UNNAMED — matched by their column signature instead.
KEY_UNIQUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "uq_transfers_source_fatid": ("uq_transfers_source_fatid",),
    "uq_transfers_branch_no": ("unique(source_branch_id,transfer_no)",),
    "uq_stock_batches": ("unique(branch_id,drug_id,randomid)",),
}

# Documented intentional equivalents: the twin expresses the same invariant
# with different DDL (see sqlite/migrations/005 header — per-column CHECKs).
EQUIVALENT_CHECK_FRAGMENTS: dict[str, tuple[str, ...]] = {
    "ck_drugs_prices_nonneg": (
        "price>=0",
        "price_wholesale>=0",
        "price_cost>=0",
    ),
}


def check_constraint_parity(
    pg_checks: dict[str, dict[str, Optional[str]]],
    twin_checks: dict[str, dict[str, dict[str, Optional[str]]]],
    errors: list[str],
) -> int:
    """Every PG CHECK must exist on the SAME table in EVERY twin (the twin's
    `_new` rebuild copy counts); key UNIQUE backstops must exist by name or
    column signature. Returns how many constraints were verified."""
    verified = 0
    for table, checks in sorted(pg_checks.items()):
        for expr, name in sorted(checks.items()):
            label = f"{table}.{name or f'CHECK({expr[:40]}…)'}"
            equivalent = EQUIVALENT_CHECK_FRAGMENTS.get(name or "", ())
            for twin_name, tables in twin_checks.items():
                twin_exprs = {
                    *tables.get(table, {}),
                    # rev-029-style rebuild: constraint lands on `<t>_new`
                    *tables.get(f"{table}_new", {}),
                }
                ok = expr in twin_exprs or (
                    bool(equivalent) and all(frag in twin_exprs for frag in equivalent)
                )
                if not ok:
                    errors.append(
                        f"constraint drift: PG {label} missing from {twin_name}"
                    )
            verified += 1
    return verified


def parse_postgres_offline(sql: str) -> dict[str, dict[str, str]]:
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


# ---------------------------------------------------------------------------
# Row-level parity for seeded tables (#53): report_catalog must be identical
# across PG and both SQLite twins. Fresh twin apply must yield all catalog
# rows matching Postgres; future drift is caught here.
# ---------------------------------------------------------------------------

_PG_CATALOG_INSERT_RE = re.compile(
    r"INSERT INTO report_catalog \(code, category, title_ar, title_en, params, paper, sort\) "
    r"VALUES \('([^']*)', '([^']*)', '([^']*)', '([^']*)',.*?\'(\[.*?\])\'.*?, '([^']*)', (\d+)\)",
    re.I | re.S,
)
_PG_CATALOG_UPDATE_RE = re.compile(
    r"UPDATE report_catalog SET params =.*?\'(\[.*?\])\'.*?WHERE code = '([^']*)'",
    re.I | re.S,
)
_SQLITE_CATALOG_INSERT_BLOCK_RE = re.compile(
    r"INSERT(?: OR IGNORE)? INTO report_catalog \(code, category, title_ar, title_en, params, paper, sort\) VALUES\s*(.+?);",
    re.I | re.S,
)
_SQLITE_CATALOG_TUPLE_RE = re.compile(
    r"\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'(\[.*?\])'\s*,\s*'([^']*)'\s*,\s*(\d+)\s*\)",
    re.S,
)
_SQLITE_CATALOG_UPDATE_RE = re.compile(
    r"UPDATE report_catalog SET params\s*=\s*'([^']*)'\s*WHERE\s+code\s*=\s*'([^']*)'",
    re.I,
)


def _normalize_params(raw: str) -> str:
    """Canonical JSON form for params comparison (whitespace-insensitive)."""
    try:
        obj = json.loads(raw)
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return raw.strip()


def _catalog_from_pg_sql(sql: str) -> dict[str, tuple]:
    """Apply PG INSERTs + UPDATEs in file order to build final catalog map."""
    events: list[tuple[int, str, re.Match]] = []
    for m in _PG_CATALOG_INSERT_RE.finditer(sql):
        events.append((m.start(), "insert", m))
    for m in _PG_CATALOG_UPDATE_RE.finditer(sql):
        events.append((m.start(), "update", m))
    events.sort(key=lambda x: x[0])
    catalog: dict[str, tuple] = {}
    for _, typ, m in events:
        if typ == "insert":
            code, category, title_ar, title_en, params_raw, paper, sort = m.groups()
            catalog[code] = (
                category,
                title_ar,
                title_en,
                _normalize_params(params_raw),
                paper,
                int(sort),
            )
        else:
            params_raw, code = m.groups()
            if code in catalog:
                cat, ta, te, _old, pap, srt = catalog[code]
                catalog[code] = (cat, ta, te, _normalize_params(params_raw), pap, srt)
    return catalog


def _catalog_from_sqlite_sql(sql: str) -> dict[str, tuple]:
    """Apply SQLite INSERT (incl. OR IGNORE) + UPDATE in order."""
    events: list[tuple[int, str, re.Match]] = []
    for m in _SQLITE_CATALOG_INSERT_BLOCK_RE.finditer(sql):
        events.append((m.start(), "insert", m))
    for m in _SQLITE_CATALOG_UPDATE_RE.finditer(sql):
        events.append((m.start(), "update", m))
    events.sort(key=lambda x: x[0])
    catalog: dict[str, tuple] = {}
    for _, typ, m in events:
        if typ == "insert":
            block = m.group(1)
            is_ignore = "OR IGNORE" in m.group(0).upper()
            for tup in _SQLITE_CATALOG_TUPLE_RE.finditer(block):
                code, category, title_ar, title_en, params_raw, paper, sort = tup.groups()
                if is_ignore and code in catalog:
                    continue
                catalog[code] = (
                    category,
                    title_ar,
                    title_en,
                    _normalize_params(params_raw),
                    paper,
                    int(sort),
                )
        else:
            params_raw, code = m.groups()
            if code in catalog:
                cat, ta, te, _old, pap, srt = catalog[code]
                catalog[code] = (cat, ta, te, _normalize_params(params_raw), pap, srt)
    return catalog


def _catalog_from_sqlite_paths(paths: list[Path]) -> dict[str, tuple]:
    """SQLite migrations twin: apply files in sorted order, OR IGNORE semantics."""
    # Concatenate in sorted order but preserve per-file OR IGNORE handling;
    # feeding the combined SQL to _catalog_from_sqlite_sql preserves order.
    combined = "\n".join(p.read_text(encoding="utf-8") for p in sorted(paths))
    return _catalog_from_sqlite_sql(combined)


def check_seeded_row_parity(
    pg_catalog: dict[str, tuple],
    twin_catalogs: dict[str, dict[str, tuple]],
    errors: list[str],
) -> int:
    """Every PG report_catalog row must exist identically in each twin."""
    verified = 0
    for code, pg_row in sorted(pg_catalog.items()):
        all_match = True
        for twin_name, catalog in twin_catalogs.items():
            if code not in catalog:
                errors.append(f"seeded row drift: PG report_catalog {code!r} missing from {twin_name}")
                all_match = False
            elif catalog[code] != pg_row:
                errors.append(
                    f"seeded row drift: PG report_catalog {code!r} mismatch in {twin_name}: "
                    f"PG={pg_row} vs twin={catalog[code]}"
                )
                all_match = False
        if all_match:
            verified += 1
    for twin_name, catalog in twin_catalogs.items():
        for code in sorted(catalog):
            if code not in pg_catalog:
                errors.append(f"seeded row drift: extra report_catalog {code!r} in {twin_name} not in PG")
    return verified


def main() -> int:
    pg_sql = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=SERVER, capture_output=True, text=True, check=True,
    ).stdout
    sqlite = parse_sqlite(sorted((SERVER / "sqlite" / "migrations").glob("*.sql")))
    pg = parse_postgres_offline(pg_sql)
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

    # constraint-level parity (#57): PG CHECK expressions + key UNIQUE backstops
    twin_sqls = {
        "migrations twin": "\n".join(
            p.read_text(encoding="utf-8")
            for p in sorted((SERVER / "sqlite" / "migrations").glob("*.sql"))
        ),
        "desktop bundle (schema/schema_sqlite.sql)": (
            SERVER.parent / "schema" / "schema_sqlite.sql"
        ).read_text(encoding="utf-8"),
    }
    constraints = check_constraint_parity(
        _checks_by_table(pg_sql),
        {name: _checks_by_table(sql) for name, sql in twin_sqls.items()},
        errors,
    )
    for unique_name, patterns in KEY_UNIQUE_PATTERNS.items():
        found = 0
        for sql in twin_sqls.values():
            nt = _norm(sql)
            if any(p in nt for p in patterns):
                found += 1
        if found == len(twin_sqls):
            constraints += 1
        else:
            errors.append(
                f"constraint drift: key UNIQUE {unique_name} missing from a twin"
            )

    # seeded row parity (#53): report_catalog must be identical across PG and both SQLite twins
    pg_catalog = _catalog_from_pg_sql(pg_sql)
    twin_catalogs = {
        "migrations twin": _catalog_from_sqlite_paths(
            sorted((SERVER / "sqlite" / "migrations").glob("*.sql"))
        ),
        "desktop bundle (schema/schema_sqlite.sql)": _catalog_from_sqlite_sql(
            (SERVER.parent / "schema" / "schema_sqlite.sql").read_text(encoding="utf-8")
        ),
    }
    seeded_verified = check_seeded_row_parity(pg_catalog, twin_catalogs, errors)

    # ensure Tauri-bundled copy is identical to canonical schema (drift undetected otherwise)
    canonical_path = SERVER.parent / "schema" / "schema_sqlite.sql"
    tauri_path = SERVER.parent / "apps" / "desktop" / "src" / "resources" / "schema_sqlite.sql"
    if tauri_path.exists():
        if canonical_path.read_text(encoding="utf-8") != tauri_path.read_text(encoding="utf-8"):
            errors.append(
                "desktop bundle drift: apps/desktop/src/resources/schema_sqlite.sql != schema/schema_sqlite.sql "
                "(run cp schema/schema_sqlite.sql apps/desktop/src/resources/schema_sqlite.sql)"
            )

    if errors:
        print("PARITY FAIL")
        for e in sorted(set(errors)):
            print(" -", e)
        return 1
    print(
        f"PARITY OK — {len(pg)} tables, {sum(len(c) for c in pg.values())} PG columns "
        f"mirrored in SQLite twin + desktop bundle (schema/schema_sqlite.sql); "
        f"{constraints} constraints (CHECKs + key UNIQUE backstops) verified on both twins; "
        f"{seeded_verified} seeded report_catalog rows verified on both twins; "
        f"no REAL/FLOAT money; no plugin tables in core."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())