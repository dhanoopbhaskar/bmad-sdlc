# Headless mode

Load this file when `{workflow.ask_at_every_gate}` is false or the user says "headless". It replaces the interactive menu; it does not relax the gates or the isolation rules in `SKILL.md` §Guardrails. Scratch stays under `{project-root}`; never write it to the system temp directory.

## Contents

- [Status](#status)
- [Defaults](#defaults)
- [Missing skills](#missing-skills)
- [Emitted block](#emitted-block)

## Status

- **Stop at the next gate; never auto-approve.** Log an override only with a supplied reason.
- `status` is one of:
  - `ready` — the next action is legal to run for `current_role`;
  - `blocked` — a missing skill, a blocked gate, or a role mismatch;
  - `needs_input` — an unknown name, no ledger for a status-only request, or a paused workstream;
  - `done` — the workstream is closed.
- Headless still stops before it decides a gate: when `next_action.gate` is set, that gate is awaiting a human, so do not pass it in the same turn.
- A role mismatch is `blocked`, never `ready`, even if the action's skill is installed. Set `status: blocked` and `blocked_by` to the actions `current_role` may not run, starting with `next_action.action`. The role-mismatch fields are in `references/handoff-protocol.md` §Headless JSON.

## Defaults

- Default track and size only when no signal exists (`fix`/`audit` → `one-session`; otherwise the configured default). An unknown name → `status: needs_input`, stop without writing. Track is `greenfield|feature|fix|audit`; size is `trivial|one-session|epic|project`.
- Model `unknown` → record it and block skill-dependent actions. Known signals → create/add the workstream and emit the next action.

## Missing skills

- Missing `next_action.skill` → `status: blocked`, name the install step, keep the action id. A manifest-only skill (`skill_manifest_only: true`) is blocked for the same reason: the name exists but no readable `SKILL.md` does. `close.mark_done` and `<phase>.unblock` are conductor actions with no skill; they are not blocked for that reason.

## Emitted block

Emit exactly one JSON block. It is a projection of `summary` (`references/ledger-schema.md` §Summary shape) plus the headless keys. This list is the field set; no other file restates it.

Always keep these summary keys:

`project`, `ledger`, `memlog`, `active_workstream`, `workstream`, `workstreams`, `phase`, `next_phase`, `next_action`, `optional_actions`, `open_gates`, `blocked_gates`, `locked_phases`, `phases`, `workstreams_detail`, `decisions`, `cached_next_action`, `next_action_stale`.

Always add: `status`, `model`, `track`, `size`, `current_role`, `assumptions`.

Add when blocked: `blocked_by`, and `pointer` when one artifact unblocks the first entry.

Omit these keys entirely: `required_open`, `conditional_open`, `optional_open` (the per-level tallies are derivable from `phases[]`), `tickets` (ticket detail stays in the ledger), and `actions` (menu filtering does not apply here).

`assumptions` is always an array; `track` and `size` come from `summary.workstream` when a workstream is active, otherwise from the top-level `summary.track`/`summary.size` after close. Copy every list you keep verbatim — never filter, reorder, or drop a gate. `current_role`, each action's `role`/`role_free`/`role_allowed`, and `phases[].role` are information here, not a filter.
