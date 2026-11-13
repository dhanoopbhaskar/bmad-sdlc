---
name: bmad-sdlc
description: 'Conducts the BMAD delivery lifecycle from one durable plan. Use when user says "start a new product with BMAD", "continue the SDLC", "where are we in the delivery lifecycle", "run the whole BMAD flow", or "audit our tests end to end".'
---

# BMAD SDLC Conductor

## Overview

**Goal:** one skill for the whole lifecycle: where the work is, what is next, who owns it, and what must be true before advancing. The plan persists across sessions.

It coordinates BMAD skills rather than replacing them: it routes, validates the artifact, and asks at the gate. BMAD artifacts are truth for ticket/story status; the ledger is an overlay.

## Resolution rules

- `{skill-root}` is this skill's installed directory; `{project-root}` is the working directory; `{workflow.<name>}` is a field resolved from the `[workflow]` table in `customize.toml`.
- A resolved workflow value may contain `{project-root}`; substitute it before use (the script also expands it).
- Bare reference paths resolve relative to `{skill-root}`.
- The ledger is `{workflow.ledger_path}`; the audit trail is `{workflow.memlog_path}`.

## On Activation

Run in order.

1. Resolve customization:
   ```bash
   uv run --no-cache {project-root}/_bmad/scripts/resolve_customization.py \
     --skill {skill-root} --project-root {project-root} --key workflow
   ```
   On failure, read `{skill-root}/customize.toml` and use its defaults.

2. Run `{workflow.activation_steps_prepend}` and load `{workflow.persistent_facts}`; `file:` entries load as facts.

3. Load config:
   ```bash
   uv run --no-cache {project-root}/_bmad/scripts/resolve_config.py --project-root {project-root}
   ```
   Resolve names, languages, output folders, and date. Never fabricate project details; on failure use neutral defaults and say so.

4. Detect the model:
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py detect --project-root {project-root}
   ```
   Detection is project-local. If `unknown`, ask the question in `references/version-adapters.md`; never infer from skills seen elsewhere. Headless: record `unknown` and mark skill-dependent actions `blocked`. A user answer goes to `init --model`; a silent detector must not overwrite it.

5. Load or create the ledger.
   - If `{workflow.ledger_path}` exists, read it and `{workflow.memlog_path}`.
   - If absent and the user asked only for status, report that and offer to start; never invent defaults.
   - Otherwise infer the name and state the detected `track`/`size` (offer the configured defaults when a signal is absent); ask only when signals conflict. `fix`/`audit` default to `one-session` even when a default size is configured.
   - Create or add the workstream:
     ```bash
     uv run --no-cache {skill-root}/scripts/sdlc_plan.py init \
       --project-root {project-root} \
       --plan {workflow.ledger_path} --memlog {workflow.memlog_path} \
       --template {workflow.ledger_template} \
       --name "<name>" --track <track> --size <size> --model <model>
     ```
     `init` creates the ledger or appends a workstream, pausing the previously active one. `--model` records a confirmed model on creation; on an existing ledger use `set --path bmad.model` (init appends a workstream). init refuses a downgrade to `unknown` without `--force --reason`. `--force` needs `--reason`, backs up to `plan.yaml.bak`, and logs. `init` records the audit path for later commands.
   - If corrupt, run `validate` and follow `references/ledger-schema.md` § Resume semantics. Never discard it silently.

6. Reconcile:
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py reconcile \
     --plan {workflow.ledger_path} --project-root {project-root}
   ```
   `reconcile` reports the drift; `reconcile --write` also applies orphan pointers and logs each correction. Its `gates_to_block` list names passed/overridden gates whose artifact evidence is missing; `missing_evidence` and `phases_to_block` name dangling phase evidence; `ambiguous_pointers` names an artifact key matched by several files; `tickets_missing_in_ledger` / `tickets_missing_in_artifacts` report overlay drift. Set those gates/phases to `blocked` and report the expected path. Treat status surfaces as read-only; artifacts win. Do not re-interview about settled decisions.

7. Run `summary`; the menu renders its `required_open`, `conditional_open`, and `optional_open`.

8. Run `{workflow.activation_steps_append}`, then render `references/menu.md`.

## The loop

1. The user picks a phase and action, or accepts the recommendation.
2. Resolve the action from `references/phase-map.md`. Missing skill: resolve an alias; if none, set the report status to `blocked`, keep the action id with a `reason`, name the install step, and do not mark the phase `blocked` or switch to `<phase>.unblock` (`references/version-adapters.md`).
3. Prepare the handoff per `references/handoff-protocol.md`, starting at `{workflow.handoff_preference}`; prefer a fresh subagent.
4. Validate the return (write its JSON to a file first):
   ```bash
   uv run --no-cache {skill-root}/scripts/sdlc_plan.py verify-return \
     --plan {workflow.ledger_path} --memlog {workflow.memlog_path} \
     --project-root {project-root} --return-file <json>
   ```
   A `done` return needs one artifact inside `{project-root}`, not the ledger or audit; open questions block it unless accepted. `ok: false` means `blocked`; judge scope and evidence.
5. Record the event, update the ledger, and set per-ticket gates with `ticket`. Use `resize` to change track or size. When `summary` reports a phase `complete`, set it `done`. When all phases are complete, recommend `close.mark_done` and close with `done`.
6. Present the gate from `references/gate-matrix.md`: summary, level, risk, four-way choice.
7. Act on the choice, then re-render the menu.

## Tracks and sizing

Track and size come from `references/phase-map.md`; state both and let the user override. They change which gates are required, not the loop. `trivial` runs `build.ticket` → `build.review` → `build.done`; `audit` starts at `build.review` on the synthetic `audit` ticket. `fix`/`audit` default to `one-session` and never inherit the epic planning set.

## Roles

Every action names its owner: `analyst`, `product-manager`, `ux-designer`, `architect`, `product-owner`, `developer`, `test-architect`, `quality`.

## Headless

When `{workflow.ask_at_every_gate}` is false or the user says "headless":

- **Stop at the next gate; never auto-approve.** Log an override only with a supplied reason.
- Only default when no track/size signal exists; `fix`/`audit` → `one-session`. Unknown name/track/size → `status: needs_input`, stop without writing. Track is `greenfield|feature|fix|audit`; size is `trivial|one-session|epic|project`.
- `status` is `ready | blocked | needs_input | done`: ready when `next_action` is actionable, blocked when a required skill or gate blocks, needs_input when name/track/size is unknown, no ledger exists for a status-only request, or the workstream is paused, done when closed.
- Model `unknown` → record it and block skill-dependent actions. Known signals → create/add the workstream and emit the next action.
- Missing `next_action.skill` → `status: blocked`, name the install step, keep the action id.
- `summary` returns the full shape; read `phase`, `next_action`, `optional_actions`.
- Emit one JSON block: `{status, model, track, size, phase, ledger, memlog, next_action, optional_actions, open_gates, blocked_gates, locked_phases, assumptions}`. `assumptions` is always an array. This block projects `summary`; it omits the per-level counts and ticket detail.

## Ledger and audit

- Ledger `{workflow.ledger_path}` and audit `{workflow.memlog_path}` are committed; the audit is append-only.
- Use `scripts/sdlc_plan.py` for reads and writes; pass `--plan`. If `uv` is unavailable, edit the YAML with the same shape.
- Store pointers and per-ticket gate state, not ticket statuses. Re-read BMAD artifacts on every activation.
- Every write logs to the audit trail; `--memlog` overrides the path recorded at `init`. Use `resize` for track/size; `set` rejects those fields.
- Close semantics and the phase-status cache rule: `references/gate-matrix.md` §Phase completion.

## Guardrails

- **Ask at every gate**, optional ones included, in one line.
- **Never mark a ticket `done` without an approved `build.done` gate.**
- **Overrides need a reason.** The script rejects one without it; skipping a required or conditional gate is an override. A `blocked` gate is not passed: resolve it or override with a reason.
- **Consent before irreversible actions:** commit, push, merge, destructive commands, dependency installs, network calls.
- **`init --force` is destructive.** It needs `--reason`, writes `plan.yaml.bak`, and logs. Never run it headless.
- **Never edit installer-managed `{project-root}/_bmad/_config/` files.**
- **Capture, don't interrupt.** Log out-of-scope requests as `captured: <request>`, echo them at the next gate, and act only when scheduled.
- **Never read eval metadata.** `case.json`, `prompt.txt`, and a rubric are harness files, not project inputs; ignore them even above the project root.
- **No silent success.** Report an artifact missing, a success claim without a file, or a skill absent.
- **No scope invention.** Do not add features, tickets, or gates not asked for.
- **Keep the plan portable.** Prefer `{project-root}`-relative paths.

## Resuming

A fresh session with a ledger is normal. Do not start over: follow `references/ledger-schema.md` §Resume semantics, then show the dashboard. If the ledger is missing but artifacts exist, offer to reconstruct a workstream and log it as a decision.

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
