# bmad-sdlc — Design and Build Plan

**Status:** agreed, in build
**Created:** 2026-11-12
**Purpose:** a single front-door skill that conducts the whole BMAD SDLC across product, design, architecture, development, testing, and close-out, with a plan that survives session restarts.

> **Resume here.** If a new session picks this up, read this document, then read `_bmad-output/sdlc/plan.yaml` and `_bmad-output/sdlc/.memlog.md`. Continue at the gate named by the ledger's `next_action`; the build record in `docs/bmad-sdlc-build.memlog.md` is the completed build history, not the resume index. Do not re-litigate the decisions in [Decision log](#decision-log) unless the user asks.

---

## 1. Problem

BMAD installs many focused skills. The user must know which one to run at each point, remember what is done, pass context between sessions, and keep the roles (PM, UX, architect, developer, test architect) coordinated. `bmad-help` recommends a next skill from a static catalog but keeps no durable state and does not drive the work. `bmad-sprint-planning` tracks stories only. `bmad-build` handles one ticket. `bmad-loop` automates dev/review only.

## 2. Goal

One skill, `bmad-sdlc`, that the user invokes for the entire lifecycle. It:

1. Detects the track (greenfield, feature, fix, audit) and right-sizes the process.
2. Knows the BMAD model installed (v6 epics/sprint-status vs current Sofia/tickets) and routes to the right skills.
3. Owns a durable per-product plan in `_bmad-output/sdlc/plan.yaml`, with BMAD artifacts as the source of truth for ticket status.
4. Presents a two-level menu (phase → action), so the user never has to remember skill names.
5. Hands each phase to a fresh-context subagent where possible, then validates the artifact and asks at the gate.
6. Enforces required gates but lets the user override with a logged reason.
7. Covers the whole SDLC: frame/plan, solution/test setup, build, verify, close.

## 3. Non-goals

- Replacing BMAD skills. `bmad-sdlc` routes and coordinates; it does not reimplement PRD, architecture, build, or testing.
- A fully unattended factory. The user chose "ask at every gate".
- A second ticket tracker. BMAD artifacts remain the source of truth for story/ticket status.
- A general-purpose project manager outside software delivery.
- Editing installer-managed `_bmad/_config/` files. Registration is additive and reversible.

## 4. Decision log

Decisions made with the user on 2026-11-12. Each is binding for this build unless explicitly reopened.

| # | Decision | Choice |
|---|---|---|
| D1 | Operating model | **Hybrid conductor.** Advances work, pauses at human gates, hands off to skills. |
| D2 | Scope | **Adaptive full SDLC.** Tracks: greenfield, feature, fix, audit. |
| D3 | State model | **Thin ledger + artifacts.** Ledger stores position, decisions, gates, pointers. Artifacts are truth. |
| D4 | Gate policy | **Enforce required gates, allow override.** Override is logged with a reason. |
| D5 | Role presentation | **Neutral conductor + role labels.** One voice; each action names its owning role. |
| D6 | Packaging | **Both.** Local skill now, reusable module packaging after. |
| D7 | Handoff | **Fresh subagent per skill** where available; inline and user-run fallbacks. |
| D8 | Ledger granularity | **Per product, multi-workstream.** One file with many initiatives/workstreams. |
| D9 | Interaction | **Menu-driven.** Two levels: phase, then action. |
| D10 | Guardrails | **Ask at every gate.** Plus consent for irreversible actions. |
| D11 | bmad-loop role | **Build-first, loop optional.** Use `bmad-build`; offer `bmad-loop` for batches. |
| D12 | Advisory skills | **Optional at relevant gates.** Party mode, elicitation, deep recon, CIS. |
| D13 | Tracks | **All four.** Greenfield, feature, fix, audit. |
| D14 | Default gates | **Lean required, conditional rest.** Required: spec/PRD, epics+stories, sprint plan (v6), build ticket, code review, trace. Conditional: UX, architecture, test design/framework/CI. Optional: the rest. *Review refinement:* levels are resolved from track/size/model, so `trivial` skips planning and trace, and `audit` starts at review. |
| D15 | Unit of advancement | **Persona-dependent, per BMAD docs.** See §6. |
| D16 | End of flow | **Retro per epic, then continue** to the next epic/initiative. |
| D17 | Ledger location | **`_bmad-output/sdlc/`, committed.** |
| D18 | Name | **`bmad-sdlc`.** |
| D19 | BMAD version target | **Version-adaptive.** Detect v6 vs current and route accordingly. |
| D20 | Ticket source of truth | **BMAD artifacts.** Ledger stores only the SDLC overlay. |
| D21 | Menu structure | **Two-level: phase then action.** |
| D22 | Gate UX | **Summary + four-way choice** (approve / revise / run reviewer / skip-with-override). |
| D23 | Design doc location | **`docs/` + `_bmad-output/sdlc/`.** |
| D24 | Review passes (2026-11-12) | **Gate state is authoritative, levels are derived.** See `docs/bmad-sdlc-build.memlog.md` for the corrections from the review passes. |

## 5. What BMAD actually says (grounding)

From `docs.bmad-method.org` (current) and the installed v6.12.4 skills:

- The delivery loop is **Clarify → Plan → Build and verify → Learn and adjust**. Every path runs the same loop; bigger work enters earlier.
- Four right-sized paths: **trivial** (edit → verify), **one-session** (intent → Build), **epic** (spec → stories → Build × stories → integrate → retro), **project** (shared contracts → epics repeated → integrated product).
- **Personas advance different units.** This is the key correction to a naive "story is the unit" design.
- Current model: `bmad` hub, `bmad-agent-po` (Sofia) owns the ticket tree (`tickets.toml`, `R<n>` requirements), `bmad-build` builds one ticket per session and leaves status at `built`; the human or orchestrator marks it `done`; `bmad-retrospective` closes an epic.
- Installed v6.12.4 model: `bmad-help` hub, `bmad-create-epics-and-stories`, `bmad-sprint-planning` writes `sprint-status.yaml`, `bmad-build` syncs sprint status.

## 6. Unit of advancement (persona-dependent)

The conductor does **not** force one unit. It tracks the artifact each persona owns and advances the smallest unit that persona owns.

| Persona | Role label | Advances | Primary artifacts |
|---|---|---|---|
| Mary — Analyst | `analyst` | documents | brief, PRFAQ, BRD, research |
| John — Product Manager | `product-manager` | documents | PRD and other planning docs |
| Sally — UX Designer | `ux-designer` | documents | `DESIGN.md`, `EXPERIENCE.md`, `ux-*.md` |
| Winston — Architect | `architect` | decisions | `architecture-*.md` |
| Sofia — Product Owner (current model) | `product-owner` | the ticket tree | initiative → epics → `tickets.toml`; `R<n>` requirements |
| Amelia — Developer | `developer` | one ticket per build session | build plan with status `built` → `done` |
| Murat — Test Architect | `test-architect` | test artifacts per ticket/epic | test design, ATDD red tests, automation, trace gate |
| Retrospective | `quality` | one epic | retro document + verdict |

In the v6 model, the Product Owner role is split across `bmad-create-epics-and-stories` (epics/stories) and `bmad-sprint-planning` (tracking).

## 7. Architecture

```
.agents/skills/bmad-sdlc/
  SKILL.md                     # entry: activation, loop, menu, gates, handoff
  customize.toml               # workflow customization surface
  references/
    phase-map.md               # phases, tracks, sizing, personas, per-track flows
    gate-matrix.md             # required/conditional/optional gates + evidence
    ledger-schema.md           # plan.yaml schema, ownership, resume semantics
    version-adapters.md        # v6 vs current detection + skill mapping
    handoff-protocol.md        # subagent brief, return contract, fallbacks
    menu.md                    # dashboard, phase menu, action menu, verbs
  assets/
    plan-template.yaml         # initial ledger template
  evals/
    cases.json                 # quality/baseline cases
    queries.json               # trigger cases
    adapter.json               # opencode invocation + env passthrough
    README.md                  # run notes and known limitations
  scripts/
    sdlc_plan.py               # detect/init/validate/summary/set/append/ticket/done/migrate/resize/reconcile/verify-return/log
    tests/test_sdlc_plan.py
docs/bmad-sdlc.md              # this document
docs/bmad-sdlc-build.memlog.md # authoring memory (outside the skill tree)
_bmad-output/sdlc/plan.yaml    # runtime ledger for this repo
_bmad-output/sdlc/.memlog.md   # append-only audit trail
```

### 7.1 Activation

1. Resolve `customize.toml` via `resolve_customization.py` (fallback: read the TOML).
2. Load config via `resolve_config.py` (`project_name`, `user_name`, languages, output folders, date).
3. Run `sdlc_plan.py detect` to identify the BMAD model, hub, available skills, and missing skills.
4. If `_bmad-output/sdlc/plan.yaml` is missing, create it (ask track/size/name, or infer; `fix`/`audit` default to `one-session`). If present, read it and the `.memlog.md`. `init` appends a workstream and pauses the previous active one.
5. Reconcile the ledger against BMAD artifacts (artifact wins; missing evidence sets `blocked`). Recompute the next action.
6. Greet and render the dashboard + phase menu.

### 7.2 Core loop

1. User picks a phase, then an action (or accepts the recommendation).
2. Conductor prepares a handoff brief (objective, inputs, constraints, output, gate evidence).
3. Handoff: fresh subagent preferred; inline skill load second; user-run prompt last.
4. Conductor validates the returned artifact/evidence with `verify-return`.
5. Conductor logs the event to `.memlog.md`, updates the ledger, and presents the gate. When a phase is complete, it sets the phase `done`; when every phase is complete, it offers `close.mark_done` and closes with `done`.
6. Gate: summary + four-way choice. On override, record the reason.
7. Repeat until the phase is done; move to the next phase.

### 7.3 Tracks and right-sizing

| Track | Entry point | Default flow |
|---|---|---|
| Greenfield | idea / brief | frame → PRD → UX? → architecture → epics/tickets → sprint plan → solution → build × tickets → verify → retro |
| Feature | existing product + intent | spec/PRD delta → architecture delta? → epic/story or ticket → plan update → build → verify |
| Fix | bug report / small intent | story/ticket → ATDD? → build → tests → review → trace |
| Audit | existing code | code review → trace → test review / NFR (no net-new feature) |

In the flow column, `?` marks an optional step. Sizing: `trivial` short-circuits to `build.ticket` → `build.review` → `build.done`; planning and verification gates are optional. `one-session` goes intent → build → review → done, with verification as needed. `epic` adds spec, stories, per-story build, retro. `project` adds shared contracts and repeats the epic path. A `fix` or `audit` with no size defaults to `one-session`, and a fix never inherits the epic planning set. Gate levels are resolved from track, size, and model, so `summary` never recommends a PRD or a trace matrix for a trivial fix.

### 7.4 Gates

Each phase has gates, and `references/gate-matrix.md` is the single authority for their levels, evidence, and pass criteria. Levels are resolved from track, size, and model by `scripts/sdlc_plan.py`; the table in `gate-matrix.md` is the human-readable copy.

Required gates block advancement unless overridden. Conditional gates are required when their condition is true; because the script cannot evaluate that condition, the conductor asks for a reason on every required or conditional skip. Optional gates are offered and skippable.

Gate interaction: show what the gate requires, what exists, the evidence, and the risk of advancing; then offer **Approve / Revise / Run reviewer / Skip with override**. Every outcome is logged.

### 7.5 Handoff contract

The conductor never silently does a phase in its own context when a fresh subagent is available. It seeds the subagent with:

- skill name + path, workstream id, phase, track, size
- objective and gate criteria
- input artifact paths (absolute)
- settled decisions/constraints (do not relitigate)
- expected output path and format
- return contract: `{status, artifacts, evidence, decisions, open_questions, next_recommendation}`

The subagent must not modify the ledger. The conductor validates artifacts before accepting a result with `verify-return --memlog {workflow.memlog_path}`; artifacts outside `{project-root}` are rejected.

Fallbacks: inline skill load; user-run prompt with a ready-to-paste brief; `blocked` status with a reason.

### 7.6 Ledger contract

`{workflow.ledger_path}` (default `_bmad-output/sdlc/plan.yaml`) stores only what BMAD does not:

- project + detected BMAD model + paths
- workstreams: track, size, status, current phase
- phase status + gate outcomes/overrides, with a resolved `level` per gate and `blocked` for missing evidence
- per-ticket gate state under `tickets` (`ticket`, `tests`, `review`, `done`); an audit uses the synthetic `audit` ticket for its required review
- artifact **pointers** (not ticket statuses)
- decisions log
- last computed next action, with a stale-cache flag

BMAD artifacts remain truth for ticket/story status. On every activation, run `reconcile`, re-read the status surfaces, and apply the deltas. `{workflow.memlog_path}` is the append-only audit trail. `summary` computes phase completion, blocking gates, optional actions, and the next action; `done` closes a workstream only when every required/conditional gate is decided and every decided gate has artifact or phase evidence.

### 7.7 Version adapters

Detection is project-local. Skills visible in the session but absent under `{project-root}/.agents/skills` or the project manifest are not installations.

1. `bmad-agent-po` present → **current** model (`tickets.toml`).
2. `bmad-create-epics-and-stories` present → **v6** model (`sprint-status.yaml`).
3. Otherwise ambiguous → ask the user; never write an unconfirmed model.

Skill aliases are resolved by availability: `bmad-prd` vs `bmad-agent-pm`; `bmad-create-epics-and-stories` vs `bmad-agent-po`; `bmad-sprint-planning` vs Sofia's `tickets.toml`; `bmad-testarch-*` vs the single `bmad-tea` agent. A missing skill resolves to a listed alias when one is installed; otherwise the action is blocked with an install hint. Never invent `bmad-tea-<capability>` names.

### 7.8 Guardrails

- Ask at every gate.
- Consent before irreversible actions: commit, push, merge, destructive commands, dependency installs, network calls.
- Never mark a ticket `done` without an approved `build.done` gate.
- Capture out-of-scope requests in the audit trail instead of silently dropping or pivoting.
- Never edit installer-managed `_bmad/_config/` files.
- Keep `_bmad-output/sdlc/` committed; artifacts follow existing BMAD output rules.

## 8. Build record

The build checklist, the BMAD builder gate results, and the review-fix detail live in `docs/bmad-sdlc-build.memlog.md`. This document keeps the decisions (§4), architecture (§7), acceptance criteria (§9), and risks (§10). The verification surface is in `AGENTS.md` §Running and verifying.

## 9. Acceptance criteria

1. A user who knows nothing about BMAD can invoke `bmad-sdlc` and get a correct next action with a menu.
2. The skill detects v6 vs current and routes to skills that actually exist; missing skills produce a clear, actionable message.
3. The ledger persists position, gates, decisions, and overrides across sessions; a fresh session can resume without re-interviewing the user.
4. BMAD artifacts remain the source of truth for ticket status; the ledger never silently diverges.
5. Every phase transition passes through a gate with the four-way choice.
6. Handoffs use fresh context when available and always validate the returned artifact.
7. All four tracks (greenfield, feature, fix, audit) are reachable.
8. An audit advances from `build.review` through `verify.*` to `close.mark_done`; a trivial fix does not loop on `build.ticket`.
9. No installer-managed file is modified; the local skill works immediately, and the module packaging is additive.

## 10. Risks and open questions

| Risk | Mitigation |
|---|---|
| Version drift between docs and installed skills | Version adapter + availability-driven aliases; never hard-code a skill that is absent. |
| Ledger drift from BMAD artifacts | Artifacts are truth; reconcile on every activation; ledger stores only pointers. |
| Over-orchestration / too many prompts | Lean required gates; optional gates are one keystroke to skip; the `trivial` size short-circuits. |
| Subagent unavailability | Inline and user-run fallbacks; mark blocked with a reason. |
| Skill name collisions with future BMAD releases | `bmad-sdlc` is descriptive; module packaging uses its own prefix. |
| Context-rot in long runs | Fresh subagent per skill; step files and references loaded JIT. |

Open questions (deferred, not blocking):

- Should the module ship as a `bmad-builder` module under `skills/` or as a `_bmad/bmad-sdlc/` module with `module-help.csv`?
- Should the ledger support multiple active workstreams simultaneously, or one active at a time with a queue?
- Should `bmad-loop` be offered automatically for batches of ready tickets, or only on request?
