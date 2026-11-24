---
name: bmad-sdlc
description: 'Conducts the BMAD delivery lifecycle from one durable plan. Use when user says "start a new product with BMAD", "continue the SDLC", "where are we in the delivery lifecycle", "run the whole BMAD flow", "audit our tests end to end", or wants one skill to run PRD, architecture, build, and tests. Supports --role=pm|dev|qa for role-specific views.'
---

# BMAD SDLC Conductor

## Overview

**Goal:** one skill for the whole lifecycle: where the work is, what is next, who owns it, and what must be true before advancing. The ledger persists across sessions.

It coordinates BMAD skills rather than replacing them: it routes, validates the artifact, and asks at the gate. BMAD artifacts are the source of truth for ticket/story status; the ledger is an overlay. Track and size change which gates are required, not the loop.

## Role-Based SDLC

The conductor supports three roles that filter the available actions:

- **PM (Product Manager)**: `frame.*`, `plan.*` — owns Plan phase (requirements, UX, architecture, stories, sprint)
- **DEV (Developer)**: `build.*` — owns Build phase (tickets, tests, review, done)
- **QA (Quality)**: `solution.*`, `verify.*`, `close.*` — owns Solution, Verify, and Close phases

### Role Selection

- **Auto-detect** (default): Read current phase from ledger, map to required role
- **Explicit**: `--role=pm|dev|qa` parameter on invocation
- **Headless JSON**: `current_role` field indicates active role

### Role Dispatch Logic

Role is determined by:
1. Explicit `--role` parameter (highest priority)
2. Auto-detect from ledger's current phase (if ledger exists)
3. Default to PM (if no ledger or no active phase)

Action → role lookup uses prefix match (longest prefix wins) via `references/role-config.toml`. Unknown actions → error.

## Resolution rules

- `{skill-root}` is this skill's installed directory; `{project-root}` is the working directory; `{workflow.<name>}` is a field resolved from the `[workflow]` table in `customize.toml`.
- A resolved workflow value may contain `{project-root}`; substitute it before use. The script expands it for `--plan`, `--memlog`, `--template`, and `--project-root`.
- Bare reference paths resolve relative to `{skill-root}`.
- The ledger is `{workflow.ledger_path}`; the audit trail is `{workflow.memlog_path}`.

## Headless

When `{workflow.ask_at_every_gate}` is false or the user says "headless", load `references/headless.md` before acting. The one rule that must never be missed: stop at the next gate; never auto-approve; log an override only with a supplied reason.

## On Activation

Run in order.

1. Resolve customization:
   ```bash
   uv run --no-cache {project-root}/_bmad/scripts/resolve_customization.py \
     --skill {skill-root} --project-root {project-root} --key workflow
   ```
   On failure, read `{skill-root}/customize.toml` and use its defaults.

2. Run `{workflow.activation_steps_prepend}`. Load `{workflow.persistent_facts}`, where `file:` entries load as facts. If headless, load `references/headless.md` now.

3. Load config:
   ```bash
   uv run --no-cache {project-root}/_bmad/scripts/resolve_config.py --project-root {project-root}
   ```
   Resolve names, languages, output folders, and date. Never fabricate project details; on failure use neutral defaults and say so.

4. **Parse role parameter** (if provided):
   - Read `--role=pm|dev|qa` from invocation
   - If not provided, auto-detect from ledger (step 5)
   - Load `references/role-config.toml` for role definitions

5. Detect the model:
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py detect --project-root {project-root}
   ```
   Detection is project-local; never infer from skills seen elsewhere. Write the model only when detection confirmed it or the user answered; `--reason` to downgrade or reopen a phase. A silent detector never overwrites it.

6. Load or create the ledger.
   - If `{workflow.ledger_path}` exists, read it and `{workflow.memlog_path}`.
   - If absent but artifacts exist, offer to reconstruct the ledger and log a decision; never start a blank plan over real artifacts.
   - If absent and the user asked only for status, report that and offer to start; if they accept, ask for the name, track, and size. Never invent a phase or workstream, and do not ask about the BMAD model until the user chooses to start; then ask the question in `references/version-adapters.md` §Missing-skill behavior.
   - Otherwise infer the name and state the detected `track` and `size`; when a signal is absent, name the configured default. Ask only when signals conflict. Sizing defaults: `references/phase-map.md` §Sizing.
   - Create or add the workstream:
     ```bash
     uv run --no-cache {skill-root}/scripts/sdlc_plan.py init \
       --project-root {project-root} \
       --plan {workflow.ledger_path} --memlog {workflow.memlog_path} \
       --template {workflow.ledger_template} \
       --name "<name>" --track <track> --size <size> --model <model> \
       --default-track {workflow.default_track} \
       --default-size {workflow.default_size}
     ```
     `init` creates the ledger or appends a workstream, pausing the previously active one. `init` records the audit path for later commands.
   - If corrupt, run `validate` and follow `references/ledger-schema.md` §Resume semantics. Never discard it silently.

7. **Auto-detect role from ledger** (if no explicit --role):
   - Read current phase from ledger (`workstreams.<id>.current_phase`)
   - Map phase to role via `references/role-config.toml` `[phase_roles]`
   - Default to `pm` if no active phase or ledger doesn't exist

8. **Load role-specific references**:
   - Load base: `references/phase-map.md`, `references/gate-matrix.md`, `references/handoff-protocol.md`
   - Load role overlay: `references/<role>/phase-map.md`, `references/<role>/gate-matrix.md`
   - Overlay wins on conflicts (base loaded first, then role overlay)

9. Reconcile:
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py reconcile \
     --plan {workflow.ledger_path} --project-root {project-root}
   ```
   Follow `references/ledger-schema.md` §Resume semantics for `gates_to_block`, `missing_evidence`, `phases_to_block`, and drift. Treat ticket status as read-only; artifacts win. Do not re-interview about settled decisions.

10. Run `summary` with the step 9 flags; the menu renders the per-phase `required_open`, `conditional_open`, and `optional_open` from `summary.phases[]` (the flat top-level lists are totals that include per-ticket gates). `next_action.skill_installed: false` or `next_action.skill_manifest_only: true` triggers the missing-skill rule. Filter actions by current role.

11. Run `{workflow.activation_steps_append}`, then render `references/menu.md` (filtered by role).

## The loop

1. The user picks a phase and action, or accepts the recommendation.
2. **Filter actions by current role**: Only show actions owned by the current role (per `references/role-config.toml` action_prefix matching).
3. Resolve the action from `references/phase-map.md` (base + role overlay). Every action names its owner; missing skill: resolve an alias; if none, follow `references/version-adapters.md` §Missing-skill behavior.
4. **Role transition check**: If the chosen action belongs to a different role, confirm handoff or switch role explicitly.
5. Prepare the handoff per `references/handoff-protocol.md` (base + role overlay), starting at `{workflow.handoff_preference}`; prefer a fresh subagent. Record the ledger and audit-trail SHA-256 digests.
   - Subagent receives: `--role=<role> --ledger=<path> --action=<action>` — nothing else
   - No session summary passed — only ledger artifacts
6. Validate the return (write its JSON to a file first) with the recorded digests:
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py verify-return \
     --plan {workflow.ledger_path} --memlog {workflow.memlog_path} \
     --project-root {project-root} --return-file <json> \
     --expect-ledger-sha <sha-before-handoff> \
     --expect-memlog-sha <sha-before-handoff>
   ```
   A `done` return needs one artifact inside `{project-root}` other than the ledger or the audit trail; open questions block it unless accepted. `ok: false` means `blocked`; judge scope and evidence.
7. Record the event, update the ledger, and set per-ticket gates with `ticket`. Use `resize` to change track or size. When `summary` reports a phase `complete`, set it `done`. When all phases are complete, recommend `close.mark_done` and close with `done`.
8. **Auto-handoff on gate pass**: When a gate passes and the next action belongs to a different role, emit headless JSON with `current_role` and `next_action` (role inferred from action). See `references/handoff-protocol.md` for format.
9. Present the gate per `references/gate-matrix.md` (base + role overlay) §Gate interaction.
10. Act on the choice, then re-render the menu (filtered by role).

## Ledger and audit

- Use `scripts/sdlc_plan.py` for reads and writes; pass `--plan`. A command that returns `ok: false` exits non-zero, so `validate && summary` is safe; read the JSON for the reason. If `uv` is unavailable, follow `references/ledger-schema.md` §Hand-edit fallback; never present a gate from an unvalidated ledger.
- Every write logs to the audit trail; `--memlog` overrides the path recorded at `init`. Use `resize` for track/size; `set` rejects those fields.
- Close semantics and the phase-status cache rule: `references/gate-matrix.md` §Phase completion.

## Guardrails

- **Ask at every gate**, optional ones included, in one line.
- **Never mark a ticket `done` without an approved `build.done` gate.**
- **Overrides need a reason.** The script rejects one without it; skipping a required or conditional gate is an override. Marking a gate `blocked` never passes it: resolve it or override with a reason.
- **Reopen with a reason.** Moving a decided gate to open, blocked, or another decision — including back to `passed` — needs `--reason`. A done workstream accepts no gate or phase writes until you reopen it with `--reason`; a paused one refuses writes.
- **Consent before irreversible actions:** commit, push, merge, destructive commands, dependency installs, network calls.
- **`init --force` is destructive.** It needs `--reason`, writes `plan.yaml.bak`, and logs. Never run it headless.
- **Never edit installer-managed `{project-root}/_bmad/_config/` files.**
- **Capture, don't interrupt.** Log out-of-scope requests as `captured: <request>`, echo them at the next gate, and act only when scheduled.
- **Never read, list, or traverse eval metadata.** `case.json`, `prompt.txt`, a rubric, and the skill's own `evals/` directory are harness files, not project inputs; ignore them even above the project root. `ls -R {skill-root}`, a recursive `grep`/`find` over it, and any search whose results include `evals/` are violations; open only the reference file the current step names.
- **Isolation.** `{skill-root}` may be a symlink: never chmod, write, or copy into it, and never build a `..` path out of it. Never write or probe outside `{project-root}`. A missing `_bmad/scripts` resolver means using the shipped defaults; it is not a reason to search above `{project-root}` or through `{skill-root}/..`. Scratch goes in the `.tmp/` directory beside `{workflow.ledger_path}` and is not a deliverable.
- **No silent success.** Report a missing artifact, a success claim without a file, or a missing skill; name any scratch file you leave behind.
- **No scope invention.** Do not add features, tickets, or gates not asked for.
- **Keep the plan portable.** Prefer `{project-root}`-relative paths.

## References

Load only what the current step needs.

| File | Load when |
|---|---|
| `references/phase-map.md` | Track, size, phase, or action; what is next. |
| `references/gate-matrix.md` | Before a gate; why something is blocked; overriding. |
| `references/ledger-schema.md` | Reading, writing, validating, or reconstructing the ledger. |
| `references/version-adapters.md` | Model unknown; hub or skill missing; version questions. |
| `references/handoff-protocol.md` | Before a handoff; validating a return; fallbacks. |
| `references/menu.md` | At activation and after every transition; status or help. |
| `references/headless.md` | Headless mode (`ask_at_every_gate` false or the user says headless). |
| `assets/plan-template.yaml` | Writing or recreating the ledger shape. |
| `references/role-config.toml` | At activation; role definitions, action-to-role mapping, phase-to-role mapping. |
| `references/<role>/phase-map.md` | After base phase-map; role-specific actions and gates (overlay). |
| `references/<role>/gate-matrix.md` | After base gate-matrix; role-specific gate considerations (overlay). |
| `references/qa/solution-phase.md` | QA role in Solution phase. |

**Loading order**: Base files first, then role overlays. Overlay wins on conflicts.

When two sources disagree: this file and the reference the current step named define intent; `gate-matrix.md` defines gate levels; `summary` is authoritative at runtime because it resolves levels from track, size, and model. Report drift as a finding instead of silently picking a side.
