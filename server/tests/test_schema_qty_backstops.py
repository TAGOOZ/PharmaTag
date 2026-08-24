"""Schema backstops from the #32 audit (ticket #57).

CHECK (qty >= 0) on stock_batches.qty and branch_stock.qty: PG migration
rev 029 + SQLite twin rebuild (029_*.sql). The app-level guards
(_decrement_source_batch / _adjust_branch_stock) hold today; these tests pin
the race BACKSTOP at the DB layer by issuing raw SQL writes that bypass every
app guard, on both twins.
"""
from pathlib import Path
from sqlite3 import connect
from sys import executable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal
from tests import transfers_test_utils as u

SERVER = Path(__file__).resolve().parents[1]


async def _seed_stock(client):
    """One branch with a drug carrying 5 units in one batch."""
    branch = await u._make_branch()
    drug = await u._make_drug_with_stock(
        branch_id=branch, stock_qty="5", batches=[("5", "2.0000", None)]
    )
    return branch, drug


async def _raw_update(sql: str) -> None:
    async with SessionLocal() as session:
        await session.execute(text(sql))
        await session.commit()


async def test_pg_rejects_negative_batch_qty(client):
    branch, drug = await _seed_stock(client)
    with pytest.raises(IntegrityError):
        await _raw_update(
            "UPDATE stock_batches SET qty = -1 "
            f"WHERE branch_id = {branch} AND drug_id = {drug}"
        )


async def test_pg_rejects_negative_branch_stock_qty(client):
    branch, drug = await _seed_stock(client)
    with pytest.raises(IntegrityError):
        await _raw_update(
            "UPDATE branch_stock SET qty = -1 "
            f"WHERE branch_id = {branch} AND drug_id = {drug}"
        )


def _sqlite_twin_db(tmp_path: Path) -> Path:
    """Apply the full migrations-twin chain (001..029) to a scratch DB."""
    db = tmp_path / "twin.db"
    script = SERVER / "sqlite" / "runner.py"
    code = (
        "import sys; sys.path.insert(0, %r); import runner; runner.run(%r)"
        % (str(script.parent), str(db))
    )
    res = subprocess_run([executable, "-c", code])
    assert res.returncode == 0, res.stderr
    return db


def subprocess_run(args):
    import subprocess

    return subprocess.run(args, capture_output=True, text=True)


def test_sqlite_twin_rejects_negative_batch_qty(tmp_path):
    db = _sqlite_twin_db(tmp_path)
    conn = connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO stock_batches (branch_id, drug_id, randomid, qty, cost, vat, price)"
        " VALUES (1, 1, 'backstop', 5, 20000, 1400, 30000)"
    )
    with pytest.raises(Exception, match="CHECK"):
        conn.execute("UPDATE stock_batches SET qty = -1 WHERE randomid = 'backstop'")


def test_sqlite_twin_rejects_negative_branch_stock_qty(tmp_path):
    db = _sqlite_twin_db(tmp_path)
    conn = connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO branch_stock (branch_id, drug_id, qty, minimum) VALUES (1, 1, 5, 0)"
    )
    with pytest.raises(Exception, match="CHECK"):
        conn.execute("UPDATE branch_stock SET qty = -1 WHERE branch_id = 1")


def test_parity_script_green_in_suite():
    """The constraint-level parity guard itself must pass inside the suite."""
    res = subprocess_run([executable, str(SERVER / "scripts" / "parity_check.py")])
    assert res.returncode == 0, res.stdout + res.stderr
    assert "PARITY OK" in res.stdout
