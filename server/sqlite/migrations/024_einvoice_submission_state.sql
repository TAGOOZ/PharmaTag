-- PharmaTag core rev 024 — SQLite twin of alembic 024_einvoice_submission_state.py
-- Submission retry bookkeeping on einvoice_log (S4.2, ticket #29): the
-- worker's scheduling state; resubmission never touches counter/uuid/qr_data.

ALTER TABLE einvoice_log ADD COLUMN attempts        INTEGER NOT NULL DEFAULT 0;
ALTER TABLE einvoice_log ADD COLUMN next_attempt_at TEXT;
ALTER TABLE einvoice_log ADD COLUMN last_error      TEXT NOT NULL DEFAULT '';
