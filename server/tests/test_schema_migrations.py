"""Schema migration lifecycle (ticket #1 edge pass, on a THROWAWAY database).

Runs the full Alembic lifecycle against a scratch database that is created for
the test and dropped afterwards (never touches `pharmatag_test`):

  create -> upgrade head (001..005) -> downgrade base -> upgrade head again

and asserts, beyond what CI's fresh-upgrade covers:

* `downgrade base` leaves NO leftover tables and NO leftover enum types;
* re-upgrade is idempotent — seeds land exactly once (no dupes), and the
  identity-sequence realignment (rev 004) holds after the re-upgrade so the
  next ordinary insert gets `max(id)+1` instead of colliding with a seed;
* `downgrade 002_seeds` removes only rev 003's drug rows;
* a DELETE that violates a foreign key is rejected, not silently ignored.

CI runs a fresh upgrade only; the downgrade/re-upgrade path is this pass.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg.errors import ForeignKeyViolation

SERVER = Path(__file__).resolve().parent.parent

# defaults mirror app/core/config.py / README §1
# psycopg libpq conninfo (the SQLAlchemy URL below is only for alembic subprocess)
BASE_URL = "postgresql://pharmatag_test:pharmatag_test@localhost:5432/pharmatag_test"
ALEMBIC_URL = "postgresql+psycopg://pharmatag_test:pharmatag_test@localhost:5432/pharmatag_test"

# the 15 enum types created by rev 001 (dropped on downgrade)
_CORE_ENUMS = [
    "tax_type", "sync_status", "correction_status", "shortage_method",
    "close_status", "drawer_reason", "drawer_method", "drawer_direction",
    "batch_type", "payment_method", "invoice_status", "invoice_kind",
    "journal_source", "account_type", "party_kind",
]

EXPECTED_TABLES = {  # == the SQLite twin's CREATE TABLE set (49 core + host)
    "accounts", "app_config", "app_plugins", "audit_log", "balances",
    "branch_identities", "branch_stock", "branches", "daily_close",
    "chain_buy_orders", "dead_stock_exchange",
    "drawer_movements", "drug_barcodes", "drug_costs", "drugs",
    "einvoice_counters", "einvoice_log",
    "integration_config", "invoice_lines", "invoice_versions", "invoices",
    "journal_lines", "journals", "manual_journal_entries", "month_open_balances",
    "monthly_close", "parties",
    "payment_splits", "permissions", "plugin_branch_grants",
    "plugin_dependencies", "plugin_settings", "price_change_log",
    "print_jobs", "report_catalog", "role_permissions", "roles",
    "needs", "purchase_order_lines", "purchase_orders",
    "settlement_vouchers", "shifts", "shortage_flags", "stock_batches",
    "stock_correction_requests", "sync_log", "transfer_lines", "transfers",
    "unit_conversions", "user_roles",
    "users", "work_periods",
}

# exactly-once seed counts after `upgrade head` (branches/users/admin/roles/
# COA/plugins/drugs); any dupes would push these up.
EXPECTED_COUNTS = {
    "branches": 1,
    "users": 1,
    "roles": 5,
    "permissions": 27,           # 16 seeded + drugs.manage (rev 005) +
                                 # accounts.manage (rev 009) + journals.manage (rev 011) +
                                 # receivables.manage (rev 012) + months.close (rev 013) +
                                 # opening_balances.manage (rev 014) +
                                 # branches.manage (rev 026) +
                                 # transfers.manage (rev 027) +
                                 # needs.manage (rev 031) +
                                 # stock.manage (rev 034) +
                                 # chain_buy.manage (rev 035)
    "role_permissions": 55,      # admin->all 16 + manager 6 + accountant 2 +
                                 # pharmacist 1 + cashier 1 + 005 admin grant +
                                 # 009 admin + accountant accounts.manage grants +
                                 # 011 journals.manage grants to roles 1, 4, 5 +
                                 # 012 receivables.manage grants to roles 1, 4, 5 +
                                 # 013 months.close grants to roles 1, 4, 5 +
                                 # 014 opening_balances.manage grants to roles 1, 4, 5 +
                                 # 026 branches.manage grants to roles 1, 5 +
                                 # 027 transfers.manage grants to roles 1, 2, 5 +
                                 # 031 needs.manage grants to roles 1, 2, 5 +
                                 # 034 stock.manage grants to roles 1, 2, 5 +
                                 # 035 chain_buy.manage grants to roles 1, 2, 5
    "user_roles": 1,
    "accounts": 23,              # 12 seeded + 11 rev-009 tree nodes
    "app_plugins": 2,
    "plugin_branch_grants": 2,
    "app_config": 6,
    "drugs": 5,
}


def _alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PHARMATAG_DB_URL"] = db_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=SERVER,
        env=env,
        capture_output=True,
        text=True,
    )


def _conn(db_url: str) -> psycopg.Connection:
    return psycopg.connect(db_url, autocommit=True)


def _public_tables(db_url: str) -> set[str]:
    with _conn(db_url) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    return {r[0] for r in rows} - {"alembic_version"}


def _public_enums(db_url: str) -> set[str]:
    with _conn(db_url) as conn:
        rows = conn.execute(
            "SELECT t.typname FROM pg_type t "
            "JOIN pg_namespace n ON t.typnamespace = n.oid "
            "WHERE n.nspname = 'public'"
        ).fetchall()
    return {r[0] for r in rows}


def _seed_counts(db_url: str) -> dict[str, int]:
    with _conn(db_url) as conn:
        return {
            t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in EXPECTED_COUNTS
        }


def _run(db_url: str, sql: str):
    with _conn(db_url) as conn:
        conn.execute(sql)


def test_full_migration_lifecycle_on_throwaway_db():
    dbname = f"pharmatag_edge_{uuid.uuid4().hex[:12]}"
    db_url = BASE_URL.rsplit("/", 1)[0] + "/" + dbname
    alembic_url = ALEMBIC_URL.rsplit("/", 1)[0] + "/" + dbname
    try:
        with _conn(BASE_URL) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {dbname} WITH (FORCE)")
            conn.execute(f"CREATE DATABASE {dbname} TEMPLATE template0")

        # 1. fresh upgrade head (001..005)
        r = _alembic(["upgrade", "head"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr
        assert _public_tables(db_url) == EXPECTED_TABLES
        assert _seed_counts(db_url) == EXPECTED_COUNTS

        # 2. downgrade base leaves nothing behind (no tables, no enum types)
        r = _alembic(["downgrade", "base"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr
        assert _public_tables(db_url) == set()
        leftovers = _public_enums(db_url) & set(_CORE_ENUMS)
        assert leftovers == set(), f"enum types left behind: {leftovers}"

        # 3. re-upgrade is idempotent: same tables, seeds exactly once
        r = _alembic(["upgrade", "head"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr
        assert _public_tables(db_url) == EXPECTED_TABLES
        assert _seed_counts(db_url) == EXPECTED_COUNTS

        # 4. identity sequences not stranded after re-upgrade (rev 004):
        #    a brand-new branch/drug gets max(id)+1, not a seed collision
        with _conn(db_url) as conn:
            (branch_id,) = conn.execute(
                "INSERT INTO branches (pharmacyid, mobile, pharname) "
                "VALUES ('EDGE2', '01111111111', 'Edge') RETURNING id"
            ).fetchone()
            (drug_id,) = conn.execute(
                "INSERT INTO drugs (drugname) VALUES ('Edge Drug') RETURNING id"
            ).fetchone()
        assert branch_id == 2
        assert drug_id == 6
        # clean the edge rows so the remaining steps assert on seed-only state
        with _conn(db_url) as conn:
            conn.execute("DELETE FROM branch_stock WHERE drug_id = %s", (drug_id,))
            conn.execute("DELETE FROM drug_barcodes WHERE drug_id = %s", (drug_id,))
            conn.execute("DELETE FROM drugs WHERE id = %s", (drug_id,))
            conn.execute("DELETE FROM branches WHERE id = %s", (branch_id,))

        # 5. downgrade of 003 removes ONLY its rows (the 5 seed drugs), not
        #    branches/users/roles (rev 002 seeds)
        r = _alembic(["downgrade", "002_seeds"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr
        with _conn(db_url) as conn:
            assert conn.execute("SELECT count(*) FROM drugs").fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM branches").fetchone()[0] == 1
            assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 1

        # 6. upgrade head again restores the drug seeds
        r = _alembic(["upgrade", "head"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr
        assert _seed_counts(db_url)["drugs"] == 5

        # 7. FK orphans impossible: deleting a referenced branch is rejected
        with _conn(db_url) as conn:
            try:
                conn.execute("DELETE FROM branches WHERE id = 1")
                raise AssertionError("expected a foreign-key violation")
            except ForeignKeyViolation:
                pass
            assert conn.execute(
                "SELECT count(*) FROM branches WHERE id = 1"
            ).fetchone()[0] == 1
    finally:
        with _conn(BASE_URL) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {dbname} WITH (FORCE)")

def test_007_seeds_correction_account_for_every_existing_branch():
    """Migration 007 must give EVERY branch that exists at migration time the
    5900 corrections contra (edge pass #9 — a branch-2 approval must not
    silently fall back to branch 1's chart)."""
    dbname = f"pharmatag_edge_{uuid.uuid4().hex[:12]}"
    db_url = BASE_URL.rsplit("/", 1)[0] + "/" + dbname
    alembic_url = ALEMBIC_URL.rsplit("/", 1)[0] + "/" + dbname
    try:
        with _conn(BASE_URL) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {dbname} WITH (FORCE)")
            conn.execute(f"CREATE DATABASE {dbname} TEMPLATE template0")

        # migrate only up to 006, then add a second branch
        r = _alembic(["upgrade", "006_sale_returns"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr
        with _conn(db_url) as conn:
            (branch2,) = conn.execute(
                "INSERT INTO branches (pharmacyid, mobile, pharname) "
                "VALUES ('EDGE2', '01111111111', 'Edge Two') RETURNING id"
            ).fetchone()

        # 007 seeds 5900 for BOTH existing branches
        r = _alembic(["upgrade", "007_stock_corrections"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr
        with _conn(db_url) as conn:
            rows = conn.execute(
                "SELECT branch_id, code FROM accounts WHERE code = '5900'"
            ).fetchall()
            assert sorted(branch_id for branch_id, _ in rows) == [1, branch2]

        # 008 carries on cleanly to head
        r = _alembic(["upgrade", "head"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr
    finally:
        with _conn(BASE_URL) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {dbname} WITH (FORCE)")


def test_010_backfills_seeded_master_fary():
    """Rev 010 gives every SEEDED account the legacy linkage columns the API
    populates on create/update: fary = own code, master = parent code. Root
    accounts (no parent) keep an empty master."""
    dbname = f"pharmatag_edge_{uuid.uuid4().hex[:12]}"
    db_url = BASE_URL.rsplit("/", 1)[0] + "/" + dbname
    alembic_url = ALEMBIC_URL.rsplit("/", 1)[0] + "/" + dbname
    try:
        with _conn(BASE_URL) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {dbname} WITH (FORCE)")
            conn.execute(f"CREATE DATABASE {dbname} TEMPLATE template0")

        r = _alembic(["upgrade", "head"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr

        with _conn(db_url) as conn:
            rows = conn.execute(
                "SELECT code, master, fary FROM accounts "
                "WHERE code IN ('1000','110','100')"
            ).fetchall()
            linkage = {code: (master, fary) for code, master, fary in rows}
            # a leaf under اصول.متداولة: master = parent code, fary = own code
            assert linkage["1000"] == ("110", "1000")
            # an intermediate under اصول: same pattern
            assert linkage["110"] == ("100", "110")
            # a root: fary = own code, master stays empty
            assert linkage["100"] == ("", "100")

        # re-upgrade is idempotent (the backfill only touches empty values)
        r = _alembic(["upgrade", "head"], alembic_url)
        assert r.returncode == 0, r.stdout + r.stderr
        with _conn(db_url) as conn:
            assert conn.execute("SELECT count(*) FROM accounts").fetchone()[0] == 23
    finally:
        with _conn(BASE_URL) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {dbname} WITH (FORCE)")
