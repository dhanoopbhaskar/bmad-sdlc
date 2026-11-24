# DEV Phase Map (Role Overlay)

Role delta for the Developer. The base `phase-map.md` action tables carry the `Role` column and `role-config.toml` owns the mapping; this file adds only DEV's per-ticket work and handoff.

## DEV scope

`build.atdd`, `build.ticket`, `build.auto`, `build.loop`, and `build.tests`. `build.review` and `build.done` belong to QA: DEV builds and tests, QA reviews and approves the done transition.

## Per-ticket gate deltas

- `build.ticket`: required per ticket. The build plan has Given/When/Then (or equivalent) acceptance criteria, names the files and verification, and has no TBDs.
- `build.tests`: conditional per ticket, optional for `trivial`/`audit`. New or changed tests pass; no existing test is loosened.
- `build.review`: QA's gate. DEV supplies the reviewed change; QA records the decision. A built-in `bmad-build` review can satisfy it when its findings were triaged.
- `build.done`: QA's gate, required after `build.review`, optional for `audit`. DEV never self-approves.

Expected output, evidence, and override effects: base `gate-matrix.md` §Gate table and §Override rules.

## Ready-ticket sources

- v6: `{implementation_artifacts}/sprint-status.yaml` (`ready-for-dev`, `in-progress`, `review`).
- Current: the active initiative's `tickets/tickets.toml` and the per-ticket build plan status (`built` → `done`).

## Handoff

`handoff-protocol.md` §Role Transitions is the only transition table. DEV hands off to QA when every ticket's `build.done` is decided and `phases.build` is `done`; it hands back to PM when `plan.requirements` is blocked. Rollback uses the `ticket` command for per-ticket gates; DEV never writes a foreign gate without a recorded reason.
