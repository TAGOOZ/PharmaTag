"""Alias module — re-exports chain-buy models for logistics plugin naming.

Ticket #36 specifies `server/app/models/logistics.py (or chain_buy.py)`.
Canonical models live in `chain_buy.py`; this alias keeps the alternative
import path working.
"""
from app.models.chain_buy import ChainBuyOrder, DeadStockExchange  # noqa: F401

__all__ = ["ChainBuyOrder", "DeadStockExchange"]
