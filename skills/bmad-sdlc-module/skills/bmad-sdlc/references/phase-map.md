# Phase Map

This is the reference for track, size, phase, action, and legal-now questions. Load it whenever the user picks a phase.

Gate levels are resolved by `scripts/sdlc_plan.py` from track, size, and model; `summary` is authoritative. The tables below summarize the resolver. `resize` recomputes them after a size or track change.

## Contents

- [Track detection](#track-detection)
- [Sizing](#sizing)
- [Role labels](#role-labels)
- [Plan phase](#plan-phase)
- [Solution phase](#solution-phase)
- [Build phase](#build-phase)
- [Verify phase](#verify-phase)
- [Close phase](#close-phase)
- [Advisory actions](#advisory-actions)
- [Per-track flows](#per-track-flows)

## Track detection

Ask the user only when the signals conflict. Otherwise state the detected track and proceed.

| Track | Signals |
|---|---|
| `greenfield` | No product artifacts, no epics/tickets, no application code, or the user says "new product", "from scratch", "SaaS idea". |
| `feature` | Existing product or repo; a new capability is requested; planning artifacts exist but the requested work is not in them yet. |
| `fix` | A defect, regression, incident, or small change with a known target; no new capability. |
| `audit` | The request is to review existing code/tests/quality, not to add a feature. |

Tie-breakers: a "fix" that changes a contract is a `feature`. A "feature" with no existing repo is `greenfield`. An "audit" that produces fixes becomes `fix` after the audit.

## Sizing

BMAD's four right-sized paths. Size decides how many actions and gates apply, not a different system.

| Size | Signal | Path |
|---|---|---|
| `trivial` | Obvious, low risk, one small edit, reviewer can self-check. | Short-circuit: `build.ticket` → `build.review` → `build.done`. Skip planning and verification gates. |
| `one-session` | One coherent implementation unit, roughly one Build session. | `frame.spec` (or direct intent) → `build.ticket` → `build.review` → `build.done` → `verify.*` as needed. |
| `epic` | One outcome needing several Build sessions. | Plan → stories → Build × stories → verify → retro. |
| `project` | Several epics or roughly 20+ sessions, or multiple teams/systems. | Shared contracts (PRD, UX, architecture) → epics repeated → integrated product. |

When unsure, start one size smaller and promote. The user can resize at any gate.

## Role labels

This table adds the persona name and the unit each role advances.

| Label | Persona | Owns |
|---|---|---|
| `analyst` | Mary | research, brief, PRFAQ, BRD |
| `product-manager` | John | PRD and other planning documents |
| `ux-designer` | Sally | `DESIGN.md`, `EXPERIENCE.md` |
| `architect` | Winston | architecture spine and shared decisions |
| `product-owner` | Sofia (current model) | initiative → epics → tickets, `R<n>` requirements; in v6 this is split across epics/stories and sprint planning |
| `developer` | Amelia | one ticket per Build session |
| `test-architect` | Murat | test design, ATDD, automation, NFR, trace |
| `quality` | Retrospective / review | walkthrough, retro, code review |

## Plan phase

Frame the intent, then define and divide the work. Actions are independent tools, not a mandatory sequence; pick what the gap calls for.

| Action id | Role | v6 skill | Current-model skill | Gate | Level (see `gate-matrix.md`) |
|---|---|---|---|---|---|
| `frame.brainstorm` | analyst | `bmad-brainstorming` | `bmad-brainstorming` | — | optional |
| `frame.forge` | analyst | `bmad-forge-idea` | `bmad-forge-idea` | — | optional |
| `frame.research` | analyst | `bmad-deep-recon` | `bmad-deep-recon` | — | optional |
| `frame.brief` | analyst | `bmad-product-brief` or `bmad-agent-analyst` | `bmad-agent-analyst` | — | optional |
| `frame.prfaq` | analyst | `bmad-prfaq` or `bmad-agent-analyst` | `bmad-agent-analyst` | — | optional |
| `frame.spec` | analyst | `bmad-spec` | `bmad-spec` or `bmad-agent-po` | `plan.requirements` | `required` epic/project; `conditional` one-session; `optional` fix/trivial |
| `plan.prd` | product-manager | `bmad-prd` or `bmad-agent-pm` | `bmad-agent-pm` | `plan.requirements` | same gate as `frame.spec` (PRD form) |
| `plan.ux` | ux-designer | `bmad-ux` | `bmad-ux` | `plan.ux` | `conditional` unless trivial or fix → `optional` |
| `plan.architecture` | architect | `bmad-architecture` | `bmad-architecture` | `plan.architecture` | `conditional` epic/project (not fix); else `optional` |
| `plan.stories` | product-owner | `bmad-create-epics-and-stories` | `bmad-agent-po` (slice/refine/incept) | `plan.stories` | `required` non-fix epic/project; `conditional` non-fix one-session and fix epic/project; `optional` trivial and one-session fix |
| `plan.sprint` | product-owner | `bmad-sprint-planning` | `bmad-agent-po` (tickets.toml is the plan) | `plan.sprint` | `required` v6 epic/project (not fix); else `optional` |

Notes:

- `plan.requirements` is satisfied by `frame.spec` or `plan.prd`. Do not require both.
- `plan.ux` and `plan.architecture` are conditional. The conductor names the condition; the user can skip with an override.
- In the current model, `plan.stories` and `plan.sprint` collapse into Sofia's ticket tree (`tickets.toml`). Do not ask for a separate sprint plan.
- `plan.stories` for a `fix` may be a single ticket or a direct build intent; record that in the ledger note. A one-session fix treats it as optional and starts at `build.ticket`.
- A `fix` or `audit` with no size defaults to `one-session`. A fix never inherits the epic planning set.
- An audit has no build tickets. Its required code review is the `review` gate on the synthetic `audit` ticket; `verify.test_review`, `verify.nfr`, and `verify.trace` follow.
- **Required before conditional.** `summary`'s `next_action` recommends a required gate before a conditional one. Conditional gates are not locked out: `optional_actions` exposes them, and the user may take UX, architecture, or test setup before stories. The per-track flows show a natural order, not a lock.

## Solution phase

Decide how the work will be verified before building. Conditional by default; required when the project has no baseline.

| Action id | Role | v6 skill | Current-model skill | Gate | Level (see `gate-matrix.md`) |
|---|---|---|---|---|---|
| `solution.test_design` | test-architect | `bmad-testarch-test-design` | `bmad-tea-test-design` | `solution.test_design` | `conditional` epic/project (not fix); else `optional` |
| `solution.framework` | test-architect | `bmad-testarch-framework` | `bmad-tea-framework` | `solution.framework` | `conditional` epic/project (not fix); else `optional` |
| `solution.ci` | test-architect | `bmad-testarch-ci` | `bmad-tea-ci` | `solution.ci` | `conditional` epic/project (not fix); else `optional` |

If the project already has a mature test stack and CI, skip the phase with a recorded reason. Do not skip silently.

## Build phase

The unit is **one ticket per Build session**. The conductor picks ready tickets from the BMAD artifacts; it does not invent them.

| Action id | Role | v6 skill | Current-model skill | Gate | Level (see `gate-matrix.md`) |
|---|---|---|---|---|---|
| `build.atdd` | test-architect | `bmad-testarch-atdd` | `bmad-tea-atdd` | — | `conditional`: acceptance tests before code |
| `build.ticket` | developer | `bmad-build` | `bmad-build` | `build.ticket` | `required` per ticket |
| `build.auto` | developer | `bmad-build-auto` | `bmad-build-auto` | `build.ticket` | `optional`: unattended single ticket |
| `build.loop` | developer | `bmad-loop` | `bmad-loop` | `build.ticket` | `optional`: batch of ready tickets |
| `build.tests` | developer | project test runner or `bmad-build` | same | `build.tests` | `conditional` per ticket (project has tests); `optional` for trivial/audit |
| `build.review` | quality | `bmad-code-review` or `bmad-build`'s built-in review | same | `build.review` | `required` per ticket |
| `build.done` | product-owner | `bmad-sprint-planning` status update, or user | `bmad-agent-po` ("mark story done") | `build.done` | `required` per ticket after review; `optional` for audit |

Ready-ticket sources:

- v6: `{implementation_artifacts}/sprint-status.yaml` (`ready-for-dev`, `in-progress`, `review`).
- Current: the active initiative's `tickets/tickets.toml` and the per-ticket build plan status (`built` → `done`).

`bmad-build` already reviews its own work. `build.review` is satisfied by that built-in review when it ran and its findings were triaged; run `bmad-code-review` as a separate pass when the change is risky, the built-in review was skipped, or the user asks. Record which one satisfied the gate.

## Verify phase

| Action id | Role | v6 skill | Current-model skill | Gate | Level (see `gate-matrix.md`) |
|---|---|---|---|---|---|
| `verify.e2e` | test-architect | `bmad-qa-generate-e2e-tests` | `bmad-qa-generate-e2e-tests` | — | `optional` |
| `verify.automate` | test-architect | `bmad-testarch-automate` | `bmad-tea-automate` | — | `optional`: heavier coverage |
| `verify.test_review` | test-architect | `bmad-testarch-test-review` | `bmad-tea-test-review` | `verify.test_review` | `conditional` epic/project/audit (not fix); else `optional` |
| `verify.nfr` | test-architect | `bmad-testarch-nfr` | `bmad-tea-nfr` | `verify.nfr` | `conditional` epic/project/audit (not fix); else `optional` |
| `verify.trace` | test-architect | `bmad-testarch-trace` | `bmad-tea-trace` | `verify.trace` | `required` epic/project/audit; `conditional` fix/one-session; `optional` trivial |

`verify.trace` is the required quality gate for the workstream. It produces coverage and a gate decision; a failing gate blocks close unless overridden.

## Close phase

| Action id | Role | v6 skill | Current-model skill | Gate | Level (see `gate-matrix.md`) |
|---|---|---|---|---|---|
| `close.walkthrough` | quality | `bmad-walkthrough` | `bmad-walkthrough` | `close.walkthrough` | `optional` |
| `close.retro` | quality | `bmad-retrospective` | `bmad-retrospective` | `close.retro` | `optional` per epic; recommended |
| `close.correct_course` | product-owner | `bmad-correct-course` | `bmad-agent-po` (replan) | — | `optional`: significant mid-flight change |
| `close.mark_done` | product-owner | `sdlc_plan.py done`, or user | same | — | no gate; requires every required/conditional gate decided |

If the workstream has more epics, close the epic and return to `plan.stories` for the next one. Do not end the workstream at the first retro.

## Advisory actions

Offer these at the moment they add value; never force them.

| Action id | Skill | When |
|---|---|---|
| `advisory.party` | `bmad-party-mode` | A decision needs several perspectives. |
| `advisory.elicitation` | `bmad-advanced-elicitation` | A draft is fine but might be better. |
| `advisory.review` | `bmad-review` | An artifact needs an independent review lens. |
| `advisory.context` | `bmad-project-context` | The repo has no `AGENTS.md` context block, or it is stale. |
| `advisory.deep_recon` | `bmad-deep-recon` | A decision needs evidence, not opinion. |

## Per-track flows

Each arrow is an action id. Bracketed actions are conditional or optional; `|` separates alternatives; `× <unit>` repeats the action per unit; a parenthetical narrows or names an alternative.

### Greenfield

```
[frame.brainstorm] → [frame.forge] → [frame.research] → [frame.brief | frame.prfaq]
→ plan.prd → [plan.ux] → [plan.architecture] → plan.stories → plan.sprint
→ [solution.test_design] → [solution.framework] → [solution.ci]
→ per epic: [build.atdd] → build.ticket × stories → [build.tests] → build.review → build.done × stories
→ [verify.e2e] → [verify.automate] → [verify.test_review] → [verify.nfr] → verify.trace
→ [close.walkthrough] → [close.retro] → next epic or done
```

### Feature

```
frame.spec (or plan.prd update) → [plan.architecture delta] → plan.stories (or one ticket)
→ plan.sprint update → [build.atdd] → build.ticket → [build.tests] → build.review → build.done
→ [verify.e2e] → verify.trace → [close.retro]
```

### Fix

```
[frame.spec (bug intent)] → [plan.stories: one ticket or direct build intent] → [build.atdd] → build.ticket
→ [build.tests] → build.review → build.done → [verify.e2e] → [verify.trace]
```

Size `trivial` skips straight to `build.ticket` → `build.review` → `build.done`; verification gates are optional.

### Audit

```
build.review (code review) → verify.trace → [verify.test_review] → [verify.nfr]
→ [close.walkthrough]
```

An audit that finds work to fix transitions to `fix` with the findings as the intent.
