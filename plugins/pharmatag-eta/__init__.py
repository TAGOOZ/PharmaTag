"""Stub `pharmatag-eta` plugin (A10 pilot; ticket #3 AC3).

Proves the plugin seams end-to-end: a bundled, in-process plugin (A12) whose
manifest validates against core and whose `sale.saved` hooks are wired by the
registry and gated per-branch. The real e-invoicing logic (serializers, signers,
counters/hash, submission jobs) is Phase 4; this stub only records its
in_txn / after_commit observation through the core audit seam, so the bus
contract is exercised without any plugin tables or schema changes.

A09: eta is explicitly STRICT — a broken eta install may block a sale. The stub
declares its in_txn hook strict (this is the seam where a counter/hash failure
would abort the sale), while staying best-effort in practice because audit()
through core services is reliable.
"""
from app.core.audit import audit
from app.core.db import atomic
from app.core.events import AFTER_COMMIT, IN_TXN, SALE_SAVED
from app.plugins.manifest import (
    CORE_VERSION,
    SDK_VERSION,
    HookSpec,
    PluginManifest,
)

manifest = PluginManifest(
    slug="pharmatag-eta",
    version="0.0.1",
    name_ar="الفوترة الإلكترونية",
    name_en="E-invoicing (ETA)",
    core_requires=f">={CORE_VERSION},<1.0.0",
    sdk_version=SDK_VERSION,
)


async def _record(ctx, action: str) -> None:
    await audit(
        ctx.session,
        branch_id=ctx.branch_id,
        user_id=ctx.user_id,
        entity="plugin_eta",
        entity_id=ctx.sale.id,
        action=action,
        namee="pharmatag-eta",
        typevalue=f"sale {ctx.sale.id}",
    )


async def handle_sale_in_txn(ctx) -> None:
    """in_txn: joins the sale's transaction — commits/rolls back WITH it."""
    await _record(ctx, "in_txn")


async def handle_sale_after_commit(ctx) -> None:
    """after_commit: the core transaction is done; this write owns its own
    transaction (the shape of a later enqueue-submission job, here just an
    audit row proving the hook ran on committed state)."""
    async with atomic(ctx.session):
        await _record(ctx, "after_commit")


hooks = {
    SALE_SAVED: [
        HookSpec(handler=handle_sale_in_txn, phase=IN_TXN, strict=True, name="eta.in_txn"),
        HookSpec(
            handler=handle_sale_after_commit,
            phase=AFTER_COMMIT,
            strict=False,
            name="eta.after_commit",
        ),
    ]
}