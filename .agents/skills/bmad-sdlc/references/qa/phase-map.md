# QA Phase Map (Role Overlay)

This overlay file provides QA-role-specific actions and gates. Load after the base phase-map.md.

## QA Actions

These are the actions owned by the Quality role:

| Action id | Role | v6 skill | Current-model skill | Gate |
|---|---|---|---|---|
| `solution.test_design` | qa | `bmad-testarch-test-design` | `bmad-tea` | `solution.test_design` |
| `solution.framework` | qa | `bmad-testarch-framework` | `bmad-tea` | `solution.framework` |
| `solution.ci` | qa | `bmad-testarch-ci` | `bmad-tea` | `solution.ci` |
| `verify.e2e` | qa | `bmad-qa-generate-e2e-tests` | `bmad-qa-generate-e2e-tests` | — |
| `verify.automate` | qa | `bmad-testarch-automate` | `bmad-tea` | — |
| `verify.test_review` | qa | `bmad-testarch-test-review` | `bmad-tea` | `verify.test_review` |
| `verify.nfr` | qa | `bmad-testarch-nfr` | `bmad-tea` | `verify.nfr` |
| `verify.trace` | qa | `bmad-testarch-trace` | `bmad-tea` | `verify.trace` |
| `close.walkthrough` | qa | `bmad-walkthrough` | `bmad-walkthrough` | `close.walkthrough` |
| `close.retro` | qa | `bmad-retrospective` | `bmad-retrospective` | `close.retro` |
| `close.correct_course` | qa | `bmad-correct-course` | `bmad-agent-po` (replan) | — |
| `close.mark_done` | qa | `sdlc_plan.py done`, or user | same | — |

## QA Gate Deltas

QA-specific gate considerations:

- `solution.test_design`: Conditional for epic/project. Test design document must have ranked risks, test levels/environments, and coverage targets.
- `solution.framework`: Conditional for epic/project. Framework scaffold must run smoke test.
- `solution.ci`: Conditional for epic/project. CI config must run tests and fail on failure.
- `verify.e2e`: Generate automated e2e tests for implemented features.
- `verify.automate`: Expand test automation coverage for codebase.
- `verify.test_review`: Conditional for epic/project/audit. Test review report must assess coverage, isolation, determinism.
- `verify.nfr`: Conditional for epic/project/audit. NFR evidence for performance, security, reliability.
- `verify.trace`: Required for epic/project/audit; conditional for one-session/fix; optional for trivial. `summary` resolves the level. Traceability matrix + gate decision. Every requirement/ticket maps to test or explicit gap; gate PASS or CONCERNS with named gaps.
- `close.retro`: Optional (recommended per epic). Retro document + verdict with cited evidence, action items with owners, verdict accept/reject.
- `close.walkthrough`: Optional. Walkthrough document with purpose, hot spots, and how to test.
- `close.correct_course`: Sprint change proposal across PRD, epics, architecture, UX.
- `close.mark_done`: Close workstream when all phases complete.

## Handoff Points

Role follows the phase: reopen the target phase (or mark the gate `blocked` with a reason) and re-run `summary`; the new `current_role` decides who may act.

QA transitions to PM when:
- `close.correct_course` triggers a replan (reopen `plan`)
- A new epic needs planning

QA transitions to DEV when:
- `verify.trace` finds gaps requiring build fixes (reopen `build`)
- NFR failures require code changes (reopen `build`)