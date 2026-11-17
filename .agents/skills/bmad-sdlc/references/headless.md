# Headless mode

Load this file when `{workflow.ask_at_every_gate}` is false or the user says "headless". It replaces the interactive menu; it does not relax the gates or the isolation rules in `SKILL.md` §Guardrails. Scratch stays under `{project-root}`; never write it to the system temp directory.

## Contents

- [Status](#status)
- [Defaults](#defaults)
- [Missing skills](#missing-skills)
- [Emitted block](#emitted-block)

## Status

- **Stop at the next gate; never auto-approve.** Log an override only with a supplied reason.
- `status` is `ready` (the next action is legal to run), `blocked` (missing skill or blocked gate), `needs_input` (unknown name, no ledger for a status-only request, or paused), or `done` (closed). Headless still stops before it decides a gate: when `next_action.gate` is set, that gate is awaiting a human, so do not pass it in the same turn.

## Defaults

- Default track and size only when no signal exists (`fix`/`audit` → `one-session`; otherwise the configured default). An unknown name → `status: needs_input`, stop without writing. Track is `greenfield|feature|fix|audit`; size is `trivial|one-session|epic|project`.
- Model `unknown` → record it and block skill-dependent actions. Known signals → create/add the workstream and emit the next action.

## Missing skills

- Missing `next_action.skill` → `status: blocked`, name the install step, keep the action id. `close.mark_done` and `<phase>.unblock` are conductor actions with no skill; they are not blocked for that reason.

## Emitted block

`summary` returns the full field set in `references/ledger-schema.md`; read `phase`, `next_action`, `optional_actions`.

Emit one JSON block: `{status, model, track, size, phase, ledger, memlog, next_action, optional_actions, open_gates, blocked_gates, locked_phases, assumptions}`. `assumptions` is always an array. `track` and `size` come from `summary.workstream` when a workstream is active, otherwise from the top-level `summary.track`/`summary.size` after close. Copy `next_action`, `optional_actions`, `open_gates`, `blocked_gates`, and `locked_phases` verbatim from `summary`; never filter, reorder, or drop a gate. Omit only the per-level gate lists and ticket detail.
