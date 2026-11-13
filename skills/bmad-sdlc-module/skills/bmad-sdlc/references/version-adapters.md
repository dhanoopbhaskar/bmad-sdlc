# Version Adapters

BMAD is moving from the v6 flow (`bmad-help`, epics/stories, `sprint-status.yaml`) to the current flow (`bmad` hub, Sofia the Product Owner, `tickets.toml`). The conductor must work on both without pretending a missing skill exists.

## Contents

- [Detection](#detection)
- [Skill mapping](#skill-mapping)
- [Alias resolution](#alias-resolution)
- [Missing-skill behavior](#missing-skill-behavior)
- [Current-model notes](#current-model-notes)
- [v6 notes](#v6-notes)
- [Version change mid-workstream](#version-change-mid-workstream)

## Detection

Run:

```bash
uv run --no-cache {skill-root}/scripts/sdlc_plan.py detect --project-root {project-root}
```

The output includes:

- `model`: `v6`, `current`, or `unknown`
- `hub`: `bmad`, `bmad-help`, or null
- `test_style`: `bmad-tea`, `bmad-testarch`, or `unknown`. It matches an exact `bmad-tea` directory; a fabricated `bmad-tea-<capability>` name is not an install.
- `skills`: every installed BMAD skill directory except the conductor itself (`bmad-sdlc`)
- `missing_core`: required skills that are absent
- `paths`: resolved output/planning/implementation/test folders
- `config_errors`: malformed `{project-root}/_bmad/config*.toml` files; `init` refuses to record paths while any is present

Detection is **project-local**: `detect` scans the skill directories in `sdlc_plan.py` (`SKILL_DIRS`: `.agents`, `.claude`, `.cline`, `.bob`, `.agent`, `.adal`) and `{project-root}/_bmad/_config/skill-manifest.csv`. Skills visible in the session but not installed under the project are not project installations; do not treat any of them as an installation.

Detection order:

1. `bmad-agent-po` present → **current**.
2. `bmad-create-epics-and-stories` or `bmad-sprint-planning` present → **v6**.
3. BMAD skills present but neither signal → **unknown**; ask the user (or, in headless mode, record `unknown` and block skill-dependent actions).
4. No BMAD skills under the project root → **unknown**; the conductor can still plan, but every skill-dependent action is `blocked` until BMAD is installed.

Tell the user the detected model once, plainly. Do not make them choose unless detection is `unknown`. Write a model only when the detector confirmed it or the user answered the question explicitly. Never claim a skill is available because it appears elsewhere in the session.

## Skill mapping

Per-action resolution — PRD, UX, architecture, stories, sprint, tests, build, review, walkthrough, retrospective, and mid-flight change — is in the `v6` and `Current` columns of `phase-map.md`; the `Current` skill is also the alias when the model's skill is absent. Only these capabilities have no per-action row:

| Capability | v6 | Current |
|---|---|---|
| Hub | `bmad-help` | `bmad` |
| Analyst documents | `bmad-product-brief`, `bmad-prfaq`, `bmad-agent-analyst` | `bmad-agent-analyst` |

## Alias resolution

For every action, resolve the skill in this order:

1. The model-specific skill from `phase-map.md` or the table above.
2. The `Current` skill in the same row; `bmad-testarch-*` capabilities resolve to `bmad-tea`.
3. A direct equivalent the user names.
4. Otherwise, **blocked**: say which capability is missing, why it matters, and how to install it.

Never call a skill that is not installed. Never claim an artifact was produced by a skill that did not run. The current model ships one test-architecture agent, `bmad-tea`; resolving a capability to `bmad-tea-trace` or any other invented `bmad-tea-*` name is a missing-skill error, not an alias.

## Missing-skill behavior

| Situation | Behavior |
|---|---|
| Core skill missing (e.g., no `bmad-build`) | Set `status` to `blocked` in the emitted block. Say: "`bmad-build` is not installed under this project. Re-run the BMAD installer for this project, then return." Do not invent an installer command. Record the reason with `set --workstream <id> --path phases.<phase>.note --value "missing: bmad-build"`; do not mark the phase `blocked` (that replaces the action with `<phase>.unblock`). |
| Audit review skill missing | If neither `bmad-code-review` nor `bmad-build`'s built-in review is available, block `build.review` and name the install step. |
| Test skills missing | `solution` and `verify` gates become `blocked` unless the user accepts a manual substitute (e.g., run the project's own test suite) and records an override. |
| Hub missing but focused skills present | Use the conductor's own menu; do not require `bmad-help`. |
| Model `unknown` | Ask one question: "Which BMAD flow is installed — v6 (epics + sprint-status) or current (Sofia + tickets.toml)?" Record the answer with `init --model` on first creation, or `set --path bmad.model` on an existing ledger; that `set` needs `--reason` to downgrade a confirmed model or to reopen a phase. In headless mode, record `unknown` and block skill-dependent actions. |
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
