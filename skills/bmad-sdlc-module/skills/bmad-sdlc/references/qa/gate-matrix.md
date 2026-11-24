# QA Gate Matrix (Role Overlay)

Role delta for the Quality role. Every gate level, evidence rule, and override effect lives in base `gate-matrix.md`; this file adds QA-specific judgment only.

- `verify.trace`: required where the base table says required. Override only with a documented reason; the gap must be visible in the close summary.
- `verify.nfr`: conditional. Skip with a reason when no NFR requirements exist.
- `verify.test_review`: conditional. Skip with a reason when test quality is not in doubt.
- `build.review` / `build.done`: QA's decisions on every track. `build.done` refuses unless `build.review` passed; an overridden review is not enough.
- `close.retro` / `close.walkthrough`: optional. Skipping is normal; record `skipped` without a reason.

## Blocked and rollback

When `verify.trace` is blocked, QA names the missing matrix or evidence and stops. The conductor records the blocked gate and the pointer; the handed-off role never writes the ledger.

Rollback keeps the shape in `handoff-protocol.md` §Headless JSON: `status: blocked`, `current_role`, an ordered `blocked_by` array, `pointer`, and the retained `next_action`. Do not add a second blocked shape here. Handoff rules: `handoff-protocol.md` §Role Transitions.
