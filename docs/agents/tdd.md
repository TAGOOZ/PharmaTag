# Test-driven development (tdd skill)

Load the `tdd` skill and follow it for every slice with logic to verify: money, stock, events, ETA, reports. Discipline summarized in `AGENTS.md` → **Testing discipline**:

- **Vertical, not horizontal.** One test → one minimal implementation → repeat (tracer bullets). Never write all tests first, then all code.
- **Tests describe behavior, not implementation.** Integration-style through public interfaces; they read like a spec and must survive internal refactors. No mocking collaborators just to isolate internals; no testing private methods.
- **Invariant tests** for money/stock/ETA slices: SUM debit = SUM credit, journal balanced, audit_log + sync_log outbox rows written atomically with the write.
- **Never refactor while RED.** Before writing the first test, confirm with the user which behaviors matter most.
- Prefer **deep modules** (small interface, deep implementation) so tests exercise a lot of behaviour per unit of interface — see the tdd skill's `deep-modules.md` and `interface-design.md`.