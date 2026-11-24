# DEV Phase Map (Role Overlay)

This overlay file provides DEV-role-specific actions and gates. Load after the base phase-map.md.

## DEV Actions

These are the actions owned by the Developer role:

| Action id | Role | v6 skill | Current-model skill | Gate |
|---|---|---|---|---|
| `build.atdd` | dev | `bmad-testarch-atdd` | `bmad-tea` | — |
| `build.ticket` | dev | `bmad-build` | `bmad-build` | `build.ticket` |
| `build.auto` | dev | `bmad-build-auto` | `bmad-build-auto` | `build.ticket` |
| `build.loop` | dev | `bmad-build-auto` | `bmad-build-auto` | `build.ticket` |
| `build.tests` | dev | project test runner or `bmad-build` | same | `build.tests` |
| `build.review` | dev | `bmad-code-review` or `bmad-build`'s built-in review | same | `build.review` |
| `build.done` | dev | `bmad-sprint-planning` status update, or user | `bmad-agent-po` ("mark story done") | `build.done` |

## DEV Gate Deltas

DEV-specific gate considerations:

- `build.ticket`: Required per ticket. Build plan with acceptance criteria must have Given/When/Then or equivalent; plan names files and verification; no TBDs.
- `build.tests`: Conditional per ticket; optional for `trivial`/`audit`. New/changed tests pass; no existing test is loosened.
- `build.review`: Required per ticket. Findings are triaged; in-scope issues fixed; deferred issues recorded. `bmad-build` already reviews its own work - this is satisfied by built-in review when it ran and findings were triaged.
- `build.done`: Required per ticket after `build.review`; optional for `audit`. Approval to mark ticket done; evidence recorded and human approved.

## Ready-Ticket Sources

- v6: `{implementation_artifacts}/sprint-status.yaml` (`ready-for-dev`, `in-progress`, `review`)
- Current: active initiative's `tickets/tickets.toml` and per-ticket build plan status (`built` → `done`)

## Handoff Points

DEV transitions to QA when:
- All tickets in current sprint/iteration have `build.done` passed
- `build.review` is satisfied (built-in or separate review)

DEV transitions back to PM when:
- Blocked by missing/incomplete spec: `plan.requirements` gate not passed
- New requirements discovered during build that need PM clarification