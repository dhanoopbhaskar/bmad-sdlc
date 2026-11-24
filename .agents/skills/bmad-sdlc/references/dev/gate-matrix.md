# DEV Gate Matrix (Role Overlay)

Role delta for the Developer. Gate levels, evidence rules, and override effects live in base `gate-matrix.md`; this file adds DEV-specific judgment only.

- `build.ticket`: override only when an evidence pointer exists. Never mark a ticket done on an override alone.
- `build.tests`: override with a reason when no test baseline exists or the test run is unavailable.
- `build.review`: QA owns this decision. An overridden review is not enough for `build.done`.
- `build.done`: QA owns this decision and refuses it unless `build.review` passed. DEV never self-approves.

## Blocked gate handling

When `build.ticket` is blocked, DEV reports the missing build plan or acceptance criteria and stops. The conductor records it with `ticket --id <ticket> --gate ticket --status blocked --reason "<why>"`; DEV never writes the ledger. Wait, run the `role` verb, or override with a reason — never force a revise.

## Handoff

`handoff-protocol.md` §Role transitions is the only transition table, and §Blocked gate handling owns the blocker wording. No session context is passed; the next role reads only the ledger and artifact files.
