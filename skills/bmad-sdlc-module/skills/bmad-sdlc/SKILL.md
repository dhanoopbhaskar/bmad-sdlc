---
name: bmad-sdlc
description: 'Conducts the BMAD delivery lifecycle from one durable ledger. Use when user says "start a new product with BMAD", "continue the SDLC", "where are we in the delivery lifecycle", "run the whole BMAD flow", "audit our tests end to end", or wants one skill to run PRD, architecture, build, and tests. Supports role-specific views (`--role`), with PM, DEV, and QA as the shipped roles.'
---

# BMAD SDLC Conductor

## Overview

**Goal:** one skill for the whole lifecycle: where the work is, what is next, who owns it, and what must be true before advancing. The ledger persists across sessions.

It coordinates BMAD skills rather than replacing them: it routes, validates the artifact, and asks at the gate. BMAD artifacts are the source of truth for ticket/story status; the ledger records SDLC state only. Track and size change which gates are required, not the loop.

### Vocabulary

| Term | Values | Meaning |
|---|---|---|
| Workstream | `ws-NNN` | One unit of delivery. Only one is `active`; others are `paused` or `done`. |
| Track | `greenfield`, `feature`, `fix`, `audit` | Why the work exists; changes the gate levels. |
| Size | `trivial`, `one-session`, `epic`, `project` | How much work it is; changes the gate levels. |
| Phase | `plan`, `solution`, `build`, `verify`, `close` | Position in the lifecycle. |
| Action | e.g. `plan.stories`, `build.ticket` | A routable skill invocation owned by one role. |
| Gate | e.g. `plan.requirements` | A checkpoint with level `required`, `conditional`, or `optional` and status `open`, `passed`, `overridden`, `skipped`, or `blocked`. |
| Role | `pm`, `dev`, `qa` | Who owns an action. `summary` resolves the current role. |

## Role-Based SDLC

Three roles split the actions; `references/role-config.toml` is the single source of ownership, including role ids, prefixes, phase mappings, and track overrides. `pm`, `dev`, and `qa` are the shipped defaults. The role split exists so no single role builds, reviews, and approves the same ticket.

`summary` reports `current_role`, `role_source`, and per-action `role`/`role_allowed`. Resolve a role from those fields, never by re-deriving it from an action id. The resolution ladder is documented in the `role-config.toml` header and implemented by the script; only one role may be current at a time.

## Resolution rules

- `{skill-root}` is this skill's installed directory; `{project-root}` is the working directory; `{workflow.<name>}` is a field resolved from the `[workflow]` table in `customize.toml`.
- A resolved workflow value may contain `{project-root}`; substitute it before use. The script expands it for `--plan`, `--memlog`, `--template`, and `--project-root`.
- Bare reference paths resolve relative to `{skill-root}`.
- The ledger is `{workflow.ledger_path}`; the audit trail is `{workflow.memlog_path}`.

## Precedence

When two sources disagree, this file and the reference the current step named define intent; `gate-matrix.md` defines the gate table and level rules; `summary` is authoritative at runtime because it resolves levels from track, size, and model. Report drift as a finding instead of silently picking a side.

## Headless

When `{workflow.ask_at_every_gate}` is false or the user says "headless", load `references/headless.md` before acting. The one rule that must never be missed: stop at the next gate; never auto-approve; log an override only with a supplied reason.

## On Activation

Run in order.

1. Resolve customization:
   ```bash
   uv run --no-cache {project-root}/_bmad/scripts/resolve_customization.py \
     --skill {skill-root} --project-root {project-root} --key workflow
   ```
   On failure, read `{skill-root}/customize.toml` and use its defaults. A missing `{project-root}/_bmad/scripts` resolver is that failure: read the file in place. Never build a `..` path out of `{skill-root}` or search above `{project-root}`.

2. Run `{workflow.activation_steps_prepend}`. Load `{workflow.persistent_facts}`, where `file:` entries load as facts.

3. Load config:
   ```bash
   uv run --no-cache {project-root}/_bmad/scripts/resolve_config.py --project-root {project-root}
   ```
   Resolve names, languages, output folders, and date. Never fabricate project details; on failure use neutral defaults and say so.

4. **Read the role selection** (if the user supplied one):
   - Accept `--role=<role>`, `--role <role>`, or an input line `Role: <role>`; normalize case. The valid roles are the ids in `references/role-config.toml`; reject any other value with an error.
   - A one-off request is passed to step 8's `summary`; a standing role change is the `role <role> <reason>` verb, which persists `role_override` and logs the reason.
   - Do not resolve the role yet: step 8's `summary` returns it.

5. Detect the model:
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py detect --project-root {project-root}
   ```
   Detection is project-local; model rules, aliases, and the no-silent-overwrite rule are in `references/version-adapters.md` §Detection.

6. Load or create the ledger.
   - If `{workflow.ledger_path}` exists, read it and `{workflow.memlog_path}`.
   - If absent but artifacts exist, offer to reconstruct the ledger and log a decision; never start a blank ledger over real artifacts.
   - If absent and the user asked only for status, report that and offer to start; if they accept, ask for the name, track, and size. Never invent a phase or workstream, and do not ask about the BMAD model until the user chooses to start; then ask the question in `references/version-adapters.md` §Missing-skill behavior. **Stop here when no ledger exists**: do not run steps 7–10 against a missing file.
   - Otherwise infer the name and state the detected `track` and `size`; when a signal is absent, name the configured default. Ask only when signals conflict. Sizing defaults: `references/phase-map.md` §Sizing.
   - Create the ledger (pass `--model`):
     ```bash
     uv run --no-cache {skill-root}/scripts/sdlc_plan.py init \
       --project-root {project-root} \
       --plan {workflow.ledger_path} --memlog {workflow.memlog_path} \
       --template {workflow.ledger_template} \
       --name "<name>" --track <track> --size <size> --model <model> \
       --default-track {workflow.default_track} \
       --default-size {workflow.default_size}
     ```
   - Append a workstream to an existing ledger (omit `--model`; change a model with `set --path bmad.model --value <model> --reason <why>` first):
     ```bash
     uv run --no-cache {skill-root}/scripts/sdlc_plan.py init \
       --project-root {project-root} \
       --plan {workflow.ledger_path} --memlog {workflow.memlog_path} \
       --name "<name>" --track <track> --size <size> \
       --default-track {workflow.default_track} \
       --default-size {workflow.default_size}
     ```
     `init` creates the ledger or appends a workstream, pausing the previously active one. `init` records the audit path for later commands.
   - If corrupt, run `validate` and follow `references/ledger-schema.md` §Resume semantics. Never discard it silently.

7. Reconcile (only when a ledger exists):
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py reconcile \
     --plan {workflow.ledger_path} --project-root {project-root}
   ```
   Follow `references/ledger-schema.md` §Resume semantics for `gates_to_block`, `missing_evidence`, `phases_to_block`, and drift. Treat ticket status as read-only; artifacts win. Do not re-interview about settled decisions.

8. Run `summary` (only when a ledger exists):
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py summary \
     --plan {workflow.ledger_path} --project-root {project-root} [--role <role>]
   ```
   `summary.current_role` is authoritative and `role_source` says why (`explicit`, `override`, `track`, `phase`, `default`). `next_action.role_allowed: false` means the next action belongs to another role: confirm the handoff or run the `role` verb before acting. A role-free next action (`role_free: true`, `role: null`) may be run by any role. `summary.actions[]` lists every action with its `role`, `role_free`, and `role_allowed`, including advisory actions; `phases[]` carries the per-phase gate lists. `next_action.skill_installed: false` or `next_action.skill_manifest_only: true` triggers the missing-skill rule.

9. **Load references for `summary.current_role`**:
   - Base: `references/phase-map.md`, `references/gate-matrix.md`, `references/handoff-protocol.md`
   - Overlay: `references/<role>/phase-map.md`, `references/<role>/gate-matrix.md`, where `<role>` is the id `summary.current_role` reports
   - When the role is `qa` and the phase is `solution`, also load `references/qa/solution-phase.md`
   - Overlays add role deltas; gate levels and the next action come from `summary`.

10. Run `{workflow.activation_steps_append}`, then render `references/menu.md` filtered to `current_role` (`summary.actions[]` names each action's owner; `role_free` actions are open to every role). In headless mode, emit the block in `references/headless.md` §Emitted block. Build that block from `summary` in memory: when you must stage scratch, use the `.tmp/` directory beside `{workflow.ledger_path}`, never the system temp directory. If the emitted status is `blocked`, record it:
    ```bash
    uv run --no-cache {skill-root}/scripts/sdlc_plan.py log \
      --plan {workflow.ledger_path} --type blocked \
      --text "<action>: <reason>"
    ```

## The loop

1. The user picks a phase and action, or accepts the recommendation.
2. **Filter the menu to `current_role`**: use `summary.actions[]`; offer `role_free` actions to any role.
3. Resolve the action from `references/phase-map.md` (base + role overlay). Every action names its persona and its conductor role (`summary` reports the role); missing skill: resolve an alias; if none, follow `references/version-adapters.md` §Missing-skill behavior.
4. **Role check, then handoff**: if the chosen action's `role` is not `current_role` and it is not `role_free`, confirm a handoff, or persist a role change with the `role` verb and a reason. Only then prepare the handoff per `references/handoff-protocol.md` (base + role overlay), starting at `{workflow.handoff_preference}`; prefer a fresh subagent. Record the ledger and audit-trail SHA-256 digests. The brief, its flags, and the artifact rule live in that file; pass nothing else.
5. Validate the return (write its JSON to a file first) with the recorded digests:
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py verify-return \
     --plan {workflow.ledger_path} --memlog {workflow.memlog_path} \
     --project-root {project-root} --return-file <json> \
     --expect-ledger-sha <sha-before-handoff> \
     --expect-memlog-sha <sha-before-handoff> \
     --expect-role <role> --expect-action <action-id>
   ```
   Acceptance criteria: `references/handoff-protocol.md` §Return contract. An `ok: false` response means the return was rejected: treat the action as `blocked` and judge scope and evidence.
6. Record the event, update the ledger, and set per-ticket gates with `ticket`. A gate write records the acting role; pass `--as <role> --reason <why>` to attest another role's decision, and a foreign-role decision needs `--reason`. Use `resize` to change track or size. When `summary` reports a phase `complete`, set it `done`. When all phases are complete, recommend `close.mark_done` and close with `done`.
7. Present the gate per `references/gate-matrix.md` (base + role overlay) §Gate interaction.
8. Act on the choice, then re-render the menu filtered to `current_role`.

A phase-boundary handoff fires when the phase is marked `done`, not when a gate merely passes. In headless mode a role mismatch emits the block in `references/headless.md` §Emitted block; interactively ask one line and wait.

## Ledger and audit

- Use `scripts/sdlc_plan.py` for reads and writes; pass `--plan`. A command that returns `ok: false` exits non-zero, so `validate && summary` is safe; read the JSON for the reason. If `uv` is unavailable, follow `references/ledger-schema.md` §Hand-edit fallback; never present a gate from an unvalidated ledger.
- Every write logs to the audit trail; `--memlog` overrides the path recorded at `init`. Use `resize` for track/size; `set` rejects those fields.
- Close semantics and the phase-status cache rule: `references/gate-matrix.md` §Phase completion.

## Guardrails

**Gates and roles**

- **Ask at every gate**, optional ones included, in one line.
- **One role at a time.** Never run an action whose `role` is not `current_role` unless it is `role_free`; confirm a handoff or persist a role change with `role <role> <reason>`.
- **No self-approval.** The role that decided a ticket's `build.ticket` cannot decide that ticket's `build.review` or `build.done`; the script refuses it and records each decider on the gate node.
- **Never mark a ticket `done` without an approved `build.done` gate.**
- **Phase advances and gate decisions follow `gate-matrix.md` §Override rules and §Reopening.** An advance by a foreign role needs a reason; an override, reasoned skip, or reopen needs one; the script rejects a missing reason and names the actor.
- **Never present a gate from an unvalidated ledger.**

**Safety and isolation**

- **Consent before irreversible actions:** commit, push, merge, destructive commands, dependency installs, network calls.
- **`init --force` is destructive.** It needs `--reason`, writes a backup (`plan.yaml.bak`, then a timestamped name so a retry cannot overwrite it), and logs. Never run it headless.
- **Never edit installer-managed `{project-root}/_bmad/_config/` files.**
- **Isolation.** `{skill-root}` may be a symlink: never chmod, write, or copy into it, and never build a `..` path out of it. Never write outside `{project-root}`; reads outside it are limited to the `{skill-root}` files an activation step names. A missing `{project-root}/_bmad/scripts` resolver means reading `{skill-root}/customize.toml` in place (step 1), not searching above `{project-root}` or through `{skill-root}/..`. Scratch goes in the `.tmp/` directory beside `{workflow.ledger_path}` and is not a deliverable.
- **Never read the contents of eval metadata.** The skill's `evals/` directory is harness material, not a project input: do not open `evals/cases.json`, `evals/queries.json`, `evals/adapter.json`, or any rubric. A directory listing that happens to show `evals/` is not a violation; opening those files is, and so is `ls -R {skill-root}` or a recursive `grep`/`find` used to hunt for them. Open only the reference file the current step names.

**Conduct**

- **Capture, don't interrupt.** Log out-of-scope requests as `captured: <request>`, echo them at the next gate, and act only when scheduled.
- **No silent success.** Report a missing artifact, a success claim without a file, or a missing skill; name any scratch file you leave behind.
- **No scope invention.** Do not add features, tickets, or gates not asked for.
- **Keep the ledger portable.** Prefer `{project-root}`-relative paths.

## References

The activation set loads every run. Everything else loads only when the step that needs it names it.

**Activation set** (On Activation step 9, after `summary` reports `current_role`):

- `references/phase-map.md`, `references/gate-matrix.md`, `references/handoff-protocol.md`
- `references/<role>/phase-map.md`, `references/<role>/gate-matrix.md`, and `references/qa/solution-phase.md` for QA in Solution

**Step-triggered**:

| File | Load when |
|---|---|
| `references/ledger-schema.md` | Reading, writing, validating, or reconstructing the ledger. |
| `references/version-adapters.md` | Model unknown; hub or skill missing; version questions. |
| `references/menu.md` | At activation and after every transition; status or help. |
| `references/headless.md` | Headless mode (`ask_at_every_gate` false or the user says headless). |
| `customize.toml` | Only when the step 1 resolver fails; read it in place for defaults. |

**Passed to `sdlc_plan.py`, never read as prose**:

| File | Passed as |
|---|---|
| `references/role-config.toml` | Loaded by the script for role ownership, phase and track mappings. |
| `assets/plan-template.yaml` | `init --template`; the initial ledger shape. |

**Loading order**: base files first, then the role overlays. Overlays add role deltas; gate levels and the next action come from `summary`.
