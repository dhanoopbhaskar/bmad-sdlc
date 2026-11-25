# bmad-sdlc — Design and Build Plan

**Status:** built. Design agreed 2026-11-12; D26 added 2026-11-16; D27–D29 added 2026-11-24.
**Created:** 2026-11-12
**Purpose:** a single front-door skill that conducts the whole BMAD SDLC across product, design, architecture, development, testing, and close-out, with a plan that survives session restarts. The build checklist, builder gate results, and review-fix detail live in `docs/bmad-sdlc-build.memlog.md`; this document keeps the decisions, architecture, acceptance criteria, and risks.

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
- A general-purpose project manager outside software delivery.
- Editing installer-managed `_bmad/_config/` files. Registration is additive and reversible.

## 4. Decision log

D1–D25 were decided with the user on 2026-11-12; D26 was added on 2026-11-16; D27–D29 were added on 2026-11-24. Each is binding for this build unless explicitly reopened.

| # | Decision | Choice |
|---|---|---|
| D1 | Operating model | **Hybrid conductor.** Advances work, pauses at human gates, hands off to skills. |
| D2 | Scope | **Adaptive full SDLC.** Tracks: greenfield, feature, fix, audit. |
| D3 | State model | **Thin ledger + artifacts.** Ledger stores position, decisions, gates, pointers. Artifacts are truth. |
| D4 | Gate policy | **Enforce required gates, allow override.** Override is logged with a reason. |
| D5 | Role presentation | **Neutral conductor + role labels.** One skill and one voice; each action names its owning role. D27's three conductor roles filter that same menu, so the voice stays neutral. |
| D6 | Packaging | **Both.** Local skill now, reusable module packaging after. |
| D7 | Handoff | **Fresh subagent per skill** where available; inline and user-run fallbacks. |
| D8 | Ledger granularity | **Per product, multi-workstream.** One file with many initiatives/workstreams. |
| D9 | Interaction | **Menu-driven.** Two levels: phase, then action. |
| D10 | Guardrails | **Ask at every gate.** Plus consent for irreversible actions. |
| D11 | bmad-loop role | **Build-first, loop optional.** Use `bmad-build`; for batches use `build.loop` (`bmad-build-auto`). Partly superseded by D26. |
| D12 | Advisory skills | **Optional at relevant gates.** Party mode, elicitation, deep recon, CIS. |
| D14 | Default gates | **Lean required, conditional rest.** Required: spec/PRD, epics+stories, sprint plan (v6), build ticket, code review, trace. Conditional: UX, architecture, test design/framework/CI. Optional: the rest. *Review refinement:* levels are resolved from track/size/model, so `trivial` skips planning and trace, and `audit` starts at review. |
| D15 | Unit of advancement | **Persona-dependent, per BMAD docs.** See §5. |
| D16 | End of flow | **Retro per epic, then continue** to the next epic/initiative. |
| D17 | Ledger location | **`_bmad-output/sdlc/`, committed.** |
| D18 | Name | **`bmad-sdlc`.** |
| D19 | BMAD version target | **Version-adaptive.** Detect v6 vs current and route accordingly. |
| D20 | Ticket source of truth | **BMAD artifacts.** Ledger stores only the SDLC overlay. |
| D22 | Gate UX | **Summary + four-way choice** (approve / revise / run reviewer / skip-with-override). |
| D23 | Design doc location | **`docs/` + `_bmad-output/sdlc/`.** |
| D24 | Review passes (2026-11-12) | **Gate state is authoritative, levels are derived.** See `docs/bmad-sdlc-build.memlog.md` for the corrections from the review passes. |
| D25 | Module and concurrency | **Module ships as `skills/bmad-sdlc-module/` with `module-help.csv`; the ledger supports one active workstream at a time.** |
| D26 | `bmad-loop` mapping (2026-11-16 review) | **Never name it as a skill.** `bmad-loop` is an orchestrator package, not an installed skill; `build.loop` resolves to `bmad-build-auto` and is offered only for batches the user asks for. |
| D27 | Role split (2026-11-24) | **Three conductor roles: PM, DEV, QA.** `references/role-config.toml` is the single source of ownership (prefixes, phase mapping, track override for `audit`); `summary` reports `current_role`, `role_source`, and per-action `role`/`role_allowed`. Persona labels stay in `phase-map.md` for the skill each action calls; the conductor role decides who may run it. |
| D28 | Role decisions (2026-11-24 round 11) | **D1:** QA owns `build.review` and `build.done`; DEV builds, QA reviews and approves done, and the audit action override is redundant. **D2:** the role is persisted per workstream as `role_override`, written by the `role` verb with a logged reason; `--role` is a per-read view; `resume`, `resize`, and `done` clear the override. **D3:** conductor-only actions (`close.mark_done`, `<phase>.unblock`) are role-free and open to every role, so no role is named as closer. |
| D29 | Contract and ownership corrections (2026-11-24 round 12) | **Headless:** `headless.md` §Emitted block is the only field set; it keeps the position keys and omits the per-level tallies, ticket detail, and the action catalog. **Blocked:** `blocked_by` is an ordered array of action ids starting with `next_action.action`. **Roles:** `role-config.toml` is required (no in-script fallback) and carries no `name`/`references` keys; an unknown `role_override` fails `validate` and `summary`. **Ownership:** every gate write stores `actor` on the node; the ticket's builder cannot decide its `review` or `done`; a phase advance by a foreign role needs a reason; `verify-return` requires the returned role to own the returned action. **Menu:** `summary.actions[]` carries a `role` for every action so the gateless ones are filterable. |

D13 merged into D2; D21 merged into D9.

## 5. What BMAD actually says (grounding)

From `docs.bmad-method.org` (current) and the installed v6.12.4 skills:

- The delivery loop is **Clarify → Plan → Build and verify → Learn and adjust**. Every path runs the same loop; bigger work enters earlier.
- Four right-sized paths: **trivial** (edit → verify), **one-session** (intent → Build), **epic** (spec → stories → Build × stories → integrate → retro), **project** (shared contracts → epics repeated → integrated product).
- **Personas advance different units.** This is the key correction to a naive "story is the unit" design. The conductor does **not** force one unit: it tracks the artifact each persona owns and advances the smallest unit that persona owns. The persona labels, the skill each maps to, and what each owns are listed once in `references/phase-map.md` §Role labels. The conductor-role split (PM/DEV/QA), its resolution order, and the persisted role decision live in `references/role-config.toml` (D27, D28).
- Current model: `bmad` hub; `bmad-agent-po` (Sofia) owns the ticket tree (`tickets.toml`, `R<n>` requirements); `bmad-build` builds one ticket per session and leaves status at `built`; the human or orchestrator marks it `done`; `bmad-retrospective` closes an epic.
- Installed v6.12.4 model: `bmad-help` hub; `bmad-create-epics-and-stories`; `bmad-sprint-planning` writes `sprint-status.yaml`; `bmad-build` syncs sprint status. In the v6 model, the Product Owner role is split across `bmad-create-epics-and-stories` (epics/stories) and `bmad-sprint-planning` (tracking).

## 6. Architecture

The annotated repository tree is in `README.md` §Repository layout; the contract lives in `SKILL.md` and its reference files (`SKILL.md` §References lists them). The binding constraints:

| Component | Owner | Binding constraint |
|---|---|---|
| Activation | `SKILL.md` §On Activation | Detection is project-local; a status-only request never creates a ledger; a corrupt ledger is validated and repaired, not discarded. |
| Core loop | `SKILL.md` §The loop; `handoff-protocol.md` | A menu choice, a resolved action, a handoff, `verify-return`, a ledger write, then the four-way gate. |
| Tracks and sizing | `phase-map.md` | Size narrows the action set; a trivial fix is never sent to a PRD. |
| Gates | `references/gate-matrix.md` | `gate-matrix.md` defines gate levels in prose; `summary` resolves track/size/model and wins at runtime (`SKILL.md` §References). Drift is reported, never silently resolved. |
| Handoff | `handoff-protocol.md` | A fresh subagent is preferred; it never edits the ledger; `verify-return` rejects artifacts outside `{project-root}`. |
| Ledger | `ledger-schema.md` | It stores only what BMAD does not; BMAD artifacts stay the source of truth for ticket status; every write is logged. |
| Version adapters | `version-adapters.md` | Detection is project-local; the model is never guessed; a missing skill is blocked, never substituted with an invented name. |
| Guardrails | `SKILL.md` §Guardrails | Every override is logged; irreversible actions need consent; a success claim is checked against the filesystem. |

## 7. Acceptance criteria

1. A user who knows nothing about BMAD can invoke `bmad-sdlc` and get a correct next action with a menu.
2. The skill detects v6 vs current and routes to skills that actually exist; missing skills produce a clear, actionable message.
3. The ledger persists position, gates, decisions, and overrides across sessions; a fresh session can resume without re-interviewing the user.
4. BMAD artifacts remain the source of truth for ticket status; the ledger never silently diverges.
5. Every phase transition passes through a gate with the four-way choice.
6. Handoffs use fresh context when available and always validate the returned artifact.
7. All four tracks (greenfield, feature, fix, audit) are reachable.
8. An audit advances from `build.review` through `verify.*` to `close.mark_done`; a trivial fix does not loop on `build.ticket`.
9. No installer-managed file is modified; the local skill works immediately, and the module packaging is additive.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Version drift between docs and installed skills | Version adapter + availability-driven aliases; never hard-code a skill that is absent. |
| Ledger drift from BMAD artifacts | Artifacts are truth; reconcile on every activation; ledger stores only pointers. |
| Over-orchestration / too many prompts | Lean required gates; optional gates are one keystroke to skip; the `trivial` size short-circuits. |
| Subagent unavailability | Inline and user-run fallbacks; mark blocked with a reason. |
| Skill name collisions with future BMAD releases | `bmad-sdlc` is descriptive; module packaging uses its own prefix. |
| Context-rot in long runs | Fresh subagent per skill; `SKILL.md` and the reference files loaded JIT. |
