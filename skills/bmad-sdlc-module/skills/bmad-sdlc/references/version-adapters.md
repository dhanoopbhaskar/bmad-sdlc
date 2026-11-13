# Version Adapters

BMAD is moving from the v6 flow (`bmad-help`, epics/stories, `sprint-status.yaml`) to the current flow (`bmad` hub, Sofia the Product Owner, `tickets.toml`). The conductor must work on both without pretending a missing skill exists.

## Detection

Run:

```bash
uv run --no-cache {skill-root}/scripts/sdlc_plan.py detect --project-root {project-root}
```

The output includes:

- `model`: `v6`, `current`, or `unknown`
- `hub`: `bmad`, `bmad-help`, or null
- `test_style`: `bmad-tea`, `bmad-testarch`, or `unknown`
- `skills`: every installed BMAD skill directory except the conductor itself (`bmad-sdlc`)
- `missing_core`: required skills that are absent
- `paths`: resolved output/planning/implementation/test folders

Detection is **project-local**: `detect` scans `{project-root}` and `{project-root}/_bmad/_config/skill-manifest.csv`. Skills visible in the session but not installed under the project are not project installations; do not treat any of them as an installation.

Detection order:

1. `bmad-agent-po` present → **current**.
2. `bmad-create-epics-and-stories` or `bmad-sprint-planning` present → **v6**.
3. BMAD skills present but neither signal → **unknown**; ask the user (or, in headless mode, record `unknown` and block skill-dependent actions).
4. No BMAD skills under the project root → **unknown**; the conductor can still plan, but every skill-dependent action is `blocked` until BMAD is installed.

Tell the user the detected model once, plainly. Do not make them choose unless detection is `unknown`. Never write a model the detector did not confirm unless the user explicitly answers the question. On first creation pass `--model` to `init`; on an existing ledger record the answer with `set --path bmad.model`. Never claim a skill is available because it appears elsewhere in the session.

## Skill mapping

| Capability | v6 | Current |
|---|---|---|
| Hub | `bmad-help` | `bmad` |
| Analyst documents | `bmad-product-brief`, `bmad-prfaq`, `bmad-agent-analyst` | `bmad-agent-analyst` |
| PRD | `bmad-prd`, `bmad-agent-pm` | `bmad-agent-pm` |
| Other planning docs | `bmad-prd` variants | `bmad-agent-pm`, `bmad-facilitate` |
| UX | `bmad-ux` | `bmad-ux` |
| Architecture | `bmad-architecture` | `bmad-architecture` |
| Ticket tree | `bmad-create-epics-and-stories` + `bmad-sprint-planning` | `bmad-agent-po` |
| Build | `bmad-build` | `bmad-build` |
| Unattended build | `bmad-build-auto` | `bmad-build-auto` |
| Code review | `bmad-code-review` | `bmad-code-review` |
| Walkthrough | `bmad-walkthrough` | `bmad-walkthrough` |
| QA e2e | `bmad-qa-generate-e2e-tests` | `bmad-qa-generate-e2e-tests` |
| Retrospective | `bmad-retrospective` | `bmad-retrospective` |
| Test architecture | `bmad-testarch-*` | `bmad-tea` (one agent covers every capability) |
| Mid-flight change | `bmad-correct-course` | `bmad-agent-po` (replan) |

## Alias resolution

For every action, resolve the skill in this order:

1. The model-specific skill from the table.
2. A known alias in the same family:
   - `bmad-spec` ↔ `bmad-agent-po`
   - `bmad-prd` ↔ `bmad-agent-pm`
   - `bmad-create-epics-and-stories` ↔ `bmad-agent-po`
   - `bmad-sprint-planning` ↔ `bmad-agent-po`
   - `bmad-testarch-*` ↔ `bmad-tea` (never invent `bmad-tea-<capability>`)
   - `bmad-product-brief` / `bmad-prfaq` ↔ `bmad-agent-analyst`
3. A direct equivalent the user names.
4. Otherwise, **blocked**: say which capability is missing, why it matters, and how to install it.

Never call a skill that is not installed. Never claim an artifact was produced by a skill that did not run. The current model ships one test-architecture agent, `bmad-tea`; resolving a capability to `bmad-tea-trace` or any other invented `bmad-tea-*` name is a missing-skill error, not an alias.

## Missing-skill behavior

| Situation | Behavior |
|---|---|
| Core skill missing (e.g., no `bmad-build`) | Mark the action blocked in the report. Say: "`bmad-build` is not installed under this project. Re-run the BMAD installer for this project, then return." Do not invent an installer command. Record the missing skill in the phase note; do not mark the phase `blocked` (that replaces the action with `<phase>.unblock`). |
| Audit review skill missing | If neither `bmad-code-review` nor `bmad-build`'s built-in review is available, block `build.review` and name the install step. |
| Test skills missing | `solution` and `verify` gates become `blocked` unless the user accepts a manual substitute (e.g., run the project's own test suite) and records an override. |
| Hub missing but focused skills present | Use the conductor's own menu; do not require `bmad-help`. |
| Model `unknown` | Ask one question: "Which BMAD flow is installed — v6 (epics + sprint-status) or current (Sofia + tickets.toml)?" Record the answer with `init --model` on first creation, or `set --path bmad.model` on an existing ledger. In headless mode, record `unknown` and block skill-dependent actions. |
| No BMAD at all | Offer to stop so the user can install BMAD, or run in "plan-only" mode with every gate marked `blocked`. Never fake progress. |

## Current-model notes

- `bmad-agent-po` owns the ticket tree: initiative → epics → `tickets.toml`. There is no separate sprint-planning step; the ticket tree is the plan.
- `bmad-build` reads a ticket entry and writes `story-<slug>-plan.md` beside `tickets.toml`; the plan carries status `built` until a human or orchestrator marks it `done`.
- "Mark story 1.2 done" is a `bmad-agent-po` action, not a `bmad-build` action.
- Epic closure is Sofia's, informed by `bmad-retrospective`.
- Shared decisions across epics may call `bmad-architecture`; do not invent an architecture step when only one unit exists.

## v6 notes

- `bmad-create-epics-and-stories` writes epics and stories; `bmad-sprint-planning` checks readiness and writes `sprint-status.yaml`.
- `bmad-build` syncs sprint status as it works.
- `bmad-retrospective` reads `sprint-status.yaml` to detect the epic and unfinished stories.
- Story statuses: `backlog`, `ready-for-dev`, `in-progress`, `review`, `done`. Legal transitions are BMAD's, not the conductor's.

## Version change mid-workstream

If the user upgrades BMAD during a workstream:

1. Re-run `detect`.
2. If the model changed, do not rewrite history. Add a decision: `"BMAD model changed from v6 to current at <date>; artifacts before this point remain in the v6 layout."`
3. Reconcile pointers: old `sprint-status.yaml` stays a pointer; new `tickets.toml` becomes the active source.
4. Continue with the new model's skills. Never convert artifacts silently; offer the installed `bmad` hub's migration command if the user wants a migration, and record the model change with `set --path bmad.model`.
