# Headless mode

Load this file when `{workflow.ask_at_every_gate}` is false or the user says "headless". It replaces the interactive menu; it does not relax the gates or the isolation rules in `SKILL.md` §Guardrails. Scratch stays under `{project-root}` in the `.tmp/` directory beside the ledger; never write it to the system temp directory.

## Status

- **Stop at the next gate; never auto-approve.** Log an override only with a supplied reason.
- `status` is one of:
  - `ready` — run the one `next_action` now, then stop before `next_action.gate` and emit the block. `ready` never authorizes deciding that gate.
  - `blocked` — a missing skill, a blocked gate, a role mismatch, or a corrupt ledger.
  - `needs_input` — an unknown name, no ledger for a status-only request, or a paused workstream.
  - `done` — the workstream is closed.
- A role mismatch is `blocked`, never `ready`, even if the action's skill is installed. Set `status: blocked` and `blocked_by` to the actions `current_role` may not run, starting with `next_action.action`.
- When `status` is `blocked`, record it in the audit trail with `log --type blocked --text "<action>: <reason>"` when the ledger is readable. Do not write a gate decision; for a corrupt ledger, report the block instead of hand-editing.

## Defaults

- Default track and size only when no signal exists (`fix`/`audit` → `one-session`; otherwise the configured default). An unknown name → `status: needs_input`, stop without writing. Track is `greenfield|feature|fix|audit`; size is `trivial|one-session|epic|project`.
- Model `unknown` → record it and block skill-dependent actions. Known signals → create/add the workstream and emit the next action.

## Corrupt ledger

A ledger that `validate` and `migrate` cannot repair has no automatic status. Emit `status: blocked` with `blocked_by: ["ledger.corrupt"]` and `pointer` set to the ledger path. Only a human may reset it (`init --force --reason`, interactive, after a backup); never improvise a reset or fabricate a status.

## Missing skills

- Missing `next_action.skill` → `status: blocked`, name the install step, keep the action id. A manifest-only skill (`skill_manifest_only: true`) is blocked for the same reason: the name exists but no readable `SKILL.md` does. `close.mark_done` and `<phase>.unblock` are conductor actions with no skill; they are not blocked for that reason.

## Emitted block

Emit exactly one JSON block. It is a projection of `summary` (`references/ledger-schema.md` §Summary shape) plus the headless keys. This list is the field set; no other file restates it. Build it from `summary` in memory; if a harness forces a scratch file, write it under `.tmp/` beside the ledger and name it in the response.

Always keep these summary keys:

`project`, `ledger`, `memlog`, `active_workstream`, `workstream`, `workstreams`, `phase`, `next_phase`, `next_action`, `optional_actions`, `open_gates`, `blocked_gates`, `locked_phases`, `phases`, `workstreams_detail`, `decisions`, `cached_next_action`, `next_action_stale`.

Always add: `status`, `model`, `track`, `size`, `current_role`, `role_source`, `assumptions`.

Add when blocked: `blocked_by`, and `pointer` when one artifact unblocks the first entry.

Omit these keys entirely: `required_open`, `conditional_open`, `optional_open` (the per-level tallies are derivable from `phases[]`), `tickets` (ticket detail stays in the ledger), and `actions` (menu filtering does not apply here).

`assumptions` is always an array; `track` and `size` come from `summary.workstream` when a workstream is active, otherwise from the top-level `summary.track`/`summary.size` after close. Copy every list you keep verbatim — never filter, reorder, or drop a gate. `current_role`, each action's `role`/`role_free`/`role_allowed`, and `phases[].role` are information here, not a filter.

A role-mismatch block keeps `next_action` so the consumer can see the mismatch. This example shows only that subset, not a second shape:

```json
{
  "status": "blocked",
  "current_role": "dev",
  "blocked_by": ["build.review"],
  "pointer": "/path/to/review.md",
  "next_action": {
    "phase": "build",
    "gate": "build.T1.review",
    "action": "build.review",
    "role": "qa",
    "role_allowed": false,
    "skill": "bmad-code-review",
    "reason": "build.T1.review is a required open gate.",
    "source": "computed"
  },
  "track": "feature",
  "size": "epic",
  "model": "v6",
  "assumptions": []
}
```

`blocked_by` is an ordered array of **action ids** — the actions `current_role` may not run — starting with `next_action.action`. `pointer` names the artifact that unblocks the first one. **No `next_role` field** — read `next_action.role`.
