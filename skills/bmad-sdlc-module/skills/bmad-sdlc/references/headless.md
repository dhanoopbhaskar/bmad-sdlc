# Headless mode

Load this file when `{workflow.ask_at_every_gate}` is false or the user says "headless". It replaces the interactive menu; it does not relax the gates or the isolation rules in `SKILL.md` §Guardrails. Scratch stays under `{project-root}`; never write it to the system temp directory.

## Contents

- [Status](#status)
- [Defaults](#defaults)
- [Missing skills](#missing-skills)
- [Emitted block](#emitted-block)

## Status

- **Stop at the next gate; never auto-approve.** Log an override only with a supplied reason.
- `status` is `ready` (the next action is legal to run for `current_role`), `blocked` (missing skill, blocked gate, or a role mismatch), `needs_input` (unknown name, no ledger for a status-only request, or paused), or `done` (closed). Headless still stops before it decides a gate: when `next_action.gate` is set, that gate is awaiting a human, so do not pass it in the same turn.
- A role mismatch is `blocked`, never `ready`: when `next_action.role_allowed` is false, emit `status: blocked` with `blocked_by` naming the action, even if the action's skill is installed. The exact block shape is in `references/handoff-protocol.md` §Headless JSON.

## Defaults

- Default track and size only when no signal exists (`fix`/`audit` → `one-session`; otherwise the configured default). An unknown name → `status: needs_input`, stop without writing. Track is `greenfield|feature|fix|audit`; size is `trivial|one-session|epic|project`.
- Model `unknown` → record it and block skill-dependent actions. Known signals → create/add the workstream and emit the next action.

## Missing skills

- Missing `next_action.skill` → `status: blocked`, name the install step, keep the action id. A manifest-only skill (`skill_manifest_only: true`) is blocked for the same reason: the name exists but no readable `SKILL.md` does. `close.mark_done` and `<phase>.unblock` are conductor actions with no skill; they are not blocked for that reason.

## Emitted block

Emit one JSON block: `summary`'s field set (`references/ledger-schema.md` §Summary shape) plus `status`, `model`, `track`, `size`, `current_role`, `blocked_by` (when blocked), and `assumptions`; read `phase`, `next_action`, and `optional_actions` from it. `assumptions` is always an array; `track` and `size` come from `summary.workstream` when a workstream is active, otherwise from the top-level `summary.track`/`summary.size` after close. Copy every summary list you keep verbatim — never filter, reorder, or drop a gate. Role filtering applies only to the interactive menu: `current_role`, each action's `role`/`role_free`/`role_allowed`, and `phases[].role` are information here, not a filter. Omit the per-level gate lists (`required_open`, `conditional_open`, `optional_open`) and ticket detail.
