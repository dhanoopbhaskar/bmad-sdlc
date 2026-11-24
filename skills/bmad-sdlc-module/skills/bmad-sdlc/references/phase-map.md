# Phase Map

This is the reference for track, size, phase, action, and legal-now questions. Load it whenever the user picks a phase.

Gate levels are derived; `summary` wins (`SKILL.md` §Precedence). `resize` recomputes them after a size or track change. `greenfield` and `feature` share the same levels; only `fix`, `audit`, and the `trivial` size narrow them.

**Required before conditional.** `summary`'s `next_action` recommends a required gate before a conditional one. Conditional gates are available early: the user may run one by name before the stories gates, and `optional_actions` lists the open optional gates. The per-track flows show a natural order, not a lock.

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
| `trivial` | Obvious, low risk, one small edit, reviewable in one pass by an independent role. | Short-circuit: `build.ticket` → `build.review` → `build.done`. Skip planning and verification gates. |
| `one-session` | One coherent implementation unit, roughly one Build session. | See §Per-track flows. |
| `epic` | One outcome needing several Build sessions. | See §Per-track flows. |
| `project` | Several epics or about 20 or more sessions, or multiple teams/systems. | See §Per-track flows. |

When two sizes both fit, choose the smaller and promote later. The user can resize at any gate. A `fix` or `audit` with no explicit size is `one-session`, even when a configured default size exists. The `audit` track ignores size: `verify.trace` stays required even at `trivial`.

## Role labels

This table names each persona and what the persona owns. These labels are the voice the skill uses; which conductor role (PM, DEV, QA) may run the action is resolved from the action id by `role-config.toml` and shown in each action table's `Role` column. The `Role` column is a view of that file, not a second source: on disagreement, `role-config.toml` wins.

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

| Action id | Role | Persona | v6 skill | Current-model skill | Gate |
|---|---|---|---|---|---|
| `frame.brainstorm` | pm | analyst | `bmad-brainstorming` | `bmad-brainstorming` | — |
| `frame.forge` | pm | analyst | `bmad-forge-idea` | `bmad-forge-idea` | — |
| `frame.research` | pm | analyst | `bmad-deep-recon` | `bmad-deep-recon` | — |
| `frame.brief` | pm | analyst | `bmad-product-brief` or `bmad-agent-analyst` | `bmad-agent-analyst` | — |
| `frame.prfaq` | pm | analyst | `bmad-prfaq` or `bmad-agent-analyst` | `bmad-agent-analyst` | — |
| `frame.spec` | pm | analyst | `bmad-spec` | `bmad-spec` or `bmad-agent-po` | `plan.requirements` |
| `plan.prd` | pm | product-manager | `bmad-prd` or `bmad-agent-pm` | `bmad-agent-pm` | `plan.requirements` |
| `plan.ux` | pm | ux-designer | `bmad-ux` | `bmad-ux` | `plan.ux` |
| `plan.architecture` | pm | architect | `bmad-architecture` | `bmad-architecture` | `plan.architecture` |
| `plan.stories` | pm | product-owner | `bmad-create-epics-and-stories` | `bmad-agent-po` (slice/refine/incept) | `plan.stories` |
| `plan.sprint` | pm | product-owner | `bmad-sprint-planning` | `bmad-agent-po` (tickets.toml is the plan) | `plan.sprint` |

Notes:

- `plan.requirements` is satisfied by `frame.spec` or `plan.prd`. Do not require both.
- `plan.ux` and `plan.architecture` are conditional. The conductor names the condition; the user can override with a reason when it does not apply.
- In the current model, `plan.stories` and `plan.sprint` collapse into Sofia's ticket tree (`tickets.toml`). Do not ask for a separate sprint plan.
- `plan.stories` for a `fix` is satisfied by either a single ticket or a direct build intent; record which in `phases.plan.note`. A one-session fix treats `plan.stories` as optional and starts at `build.ticket`.
- A fix never inherits the epic planning set.

## Solution phase

Decide how the work will be verified before building. The phase gates are conditional by default; their conditions and resolved levels are in `gate-matrix.md`.

| Action id | Role | Persona | v6 skill | Current-model skill | Gate |
|---|---|---|---|---|---|
| `solution.test_design` | qa | test-architect | `bmad-testarch-test-design` | `bmad-tea` | `solution.test_design` |
| `solution.framework` | qa | test-architect | `bmad-testarch-framework` | `bmad-tea` | `solution.framework` |
| `solution.ci` | qa | test-architect | `bmad-testarch-ci` | `bmad-tea` | `solution.ci` |

If the project already has a mature test stack and CI, override the solution gates with a reason, record it in `phases.solution.note`, and only then mark the phase `skipped`. Do not skip silently.

## Build phase

The unit is **one ticket per Build session**. The conductor picks ready tickets from the BMAD artifacts; it does not invent them.

| Action id | Role | Persona | v6 skill | Current-model skill | Gate |
|---|---|---|---|---|---|
| `build.atdd` | dev | test-architect | `bmad-testarch-atdd` | `bmad-tea` | — |
| `build.ticket` | dev | developer | `bmad-build` | `bmad-build` | `build.ticket` |
| `build.auto` | dev | developer | `bmad-build-auto` | `bmad-build-auto` | — |
| `build.loop` | dev | developer | `bmad-build-auto` | `bmad-build-auto` | — |
| `build.tests` | dev | developer | project test runner or `bmad-build` | same | `build.tests` |
| `build.review` | qa | quality | `bmad-code-review` or `bmad-build`'s built-in review | same | `build.review` |
| `build.done` | qa | product-owner | `bmad-sprint-planning` status update, or user | `bmad-agent-po` ("mark story done") | `build.done` |

`build.auto` and `build.loop` carry no gate of their own: they are unattended batch runs of `build.ticket`, so each built ticket still needs its own `build.ticket` gate with Given/When/Then ACs and a named verification. Neither appears as a gate action, and running one records nothing until the per-ticket `build.ticket` gate is set.

Ready-ticket sources:

- v6: `{implementation_artifacts}/sprint-status.yaml` (`ready-for-dev`, `in-progress`, `review`).
- Current: the active initiative's `tickets/tickets.toml` and the per-ticket build plan status (`built` → `done`).

`bmad-build` already reviews its own work. `build.review` is satisfied by that built-in review when it ran and its findings were triaged; run `bmad-code-review` as a separate pass when the change is risky, the built-in review was skipped, or the user asks. Record which one satisfied the gate.

`build.review` and `build.done` belong to QA: the DEV session produces the change and its tests, then QA decides the review and the done transition. Build is therefore a **mixed phase** for QA: it is DEV's phase by mapping, but it holds the two QA gates. A QA session that needs `build.review` or `build.done` enters Build and runs only those actions; the `⇄` marker means "another role owns the phase", not "keep out". Build advances to Verify only after QA has decided every ticket's `build.done` and `phases.build` is `done`.

`build.loop` (batches) resolves to `bmad-build-auto`: `bmad-loop` is an orchestrator tool installed as a separate package, not a skill, so never name it as one.

## Verify phase

| Action id | Role | Persona | v6 skill | Current-model skill | Gate |
|---|---|---|---|---|---|
| `verify.e2e` | qa | test-architect | `bmad-qa-generate-e2e-tests` | `bmad-qa-generate-e2e-tests` | — |
| `verify.automate` | qa | test-architect | `bmad-testarch-automate` | `bmad-tea` | — |
| `verify.test_review` | qa | test-architect | `bmad-testarch-test-review` | `bmad-tea` | `verify.test_review` |
| `verify.nfr` | qa | test-architect | `bmad-testarch-nfr` | `bmad-tea` | `verify.nfr` |
| `verify.trace` | qa | test-architect | `bmad-testarch-trace` | `bmad-tea` | `verify.trace` |

`verify.trace` is the quality gate that matters most for the workstream. The action produces coverage and a gate decision; a failing gate blocks close unless overridden.

## Close phase

| Action id | Role | Persona | v6 skill | Current-model skill | Gate |
|---|---|---|---|---|---|
| `close.walkthrough` | qa | quality | `bmad-walkthrough` | `bmad-walkthrough` | `close.walkthrough` |
| `close.retro` | qa | quality | `bmad-retrospective` | `bmad-retrospective` | `close.retro` |
| `close.correct_course` | qa | product-owner | `bmad-correct-course` | `bmad-agent-po` (replan) | — |
| `close.mark_done` | role-free | product-owner | `sdlc_plan.py done`, or user | same | — |

If the workstream has more epics, close the epic and return to `plan.stories` for the next one. Do not end the workstream at the first retro.

## Advisory actions

Offer these at the moment they add value; never force them. Only offer them when `{workflow.include_advisory_skills}` is true.

| Action id | Skill | When |
|---|---|---|
| `advisory.party` | `bmad-party-mode` | A decision needs several perspectives. |
| `advisory.elicitation` | `bmad-advanced-elicitation` | A draft is fine but might be better. |
| `advisory.review` | `bmad-review` | An artifact needs an independent review lens. |
| `advisory.context` | `bmad-project-context` | The repo has no `AGENTS.md` context block, or it is stale. |
| `advisory.deep_recon` | `bmad-deep-recon` | A decision needs evidence, not opinion. |

## Per-track flows

Each element in these flows is an action id. Bracketed actions are conditional or optional; `|` separates alternatives; `× <unit>` repeats the action per unit; a parenthetical narrows or names an alternative.

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

### Audit

```
build.review (code review) → verify.trace → [verify.test_review] → [verify.nfr]
→ [close.walkthrough]
```

An audit that finds work to fix transitions to `fix` with the findings as the intent.
