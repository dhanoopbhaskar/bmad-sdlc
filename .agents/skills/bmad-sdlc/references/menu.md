# Menu

The conductor is menu-driven. Every activation and every transition ends with a menu, so the user never has to remember a skill name.

## Contents

- [Dashboard](#dashboard)
- [Phase menu](#phase-menu)
- [Action menu](#action-menu)
- [Verbs](#verbs)
- [Status view](#status-view)
- [After an action](#after-an-action)
- [Tone](#tone)

## Dashboard

Render it first, and keep it scannable. Compute each row's totals from `summary.phases[]` (`required_open`, `conditional_open`, `optional_open`), not from this example: the flat top-level lists are totals and include per-ticket gates. Mark a `blocked` gate distinctly from `open`.

When no ledger exists, do not render the phase menu. Show the short status (no ledger, no active workstream) and offer to start one; that satisfies the status-only path without inventing a workstream.

```text
bmad-sdlc — <project>
Model: v6 (bmad-help) · Role: PM (phase) · Active: ws-001 <name> · Track: feature · Size: epic

Phase      Role   Status    Gate          Open
Plan       PM     active    required      <n required>, <n conditional>
Solution   QA     pending   conditional   <n conditional>
Build      DEV    pending   required      <n required>, <n conditional>
Verify     QA     pending   required      <n required>, <n conditional>
Close      QA     pending   optional      <n optional>

Next recommended: plan.stories — break the spec into epics and stories
                  (pm · bmad-create-epics-and-stories)
```

Show `optional_actions` separately; they are offered, never required. `close.mark_done` appears as the next action once every required/conditional gate is decided and no gate at any level is blocked; it is role-free, so any role may close.

If there are multiple workstreams, add one line per workstream below the active one, using `summary.workstreams_detail` (id, name, track, size, status, role, next action):

```text
Other workstreams:
ws-002 <name> (paused, feature, epic, pm)
ws-003 <name> (done, fix, qa)
```

## Phase menu

```text
Choose a phase:
  1. Plan      — frame, requirements, UX, architecture, stories, sprint plan
  2. Solution  — test design, framework, CI
  3. Build     — ATDD, build tickets, tests, code review, done
  4. Verify    — e2e, automation, test review, NFR, trace
  5. Close     — walkthrough, retrospective, mark done
  6. Status    — full status and artifact paths
  7. Switch    — change active workstream
  8. Help      — what the conductor is doing and why
  q. Quit
```

Mark the current phase with `→`. Mark locked phases with `·` and the missing required gate. Mark a phase whose `phases[].role` is not `current_role` with `⇄`. `⇄` means another role owns the phase by default; it is not a lock. Selecting it offers a handoff or the `role` verb, and when the phase also holds actions `current_role` owns (Build holds QA's `build.review` and `build.done`), list those actions and run them as `current_role`. Never run an action owned by another role.

## Action menu

After a phase is chosen, show its actions. List every entry in `summary.actions[]` whose `phase` matches, whose `role` equals `current_role`, plus every `role_free` action (`advisory.*`, `close.mark_done`, `<phase>.unblock`). `summary.actions[]` is the filter: it carries a `role` for every action, including the gateless ones (`frame.*`, `build.atdd`, `verify.e2e`, `close.correct_course`) that `next_action` never names. Show the role, skill, and gate state. Headless mode replaces this menu with the block in `headless.md` §Emitted block.

```text
Plan — choose an action (PM):
  1. plan.prd            [required]  pm · bmad-prd
     Update the PRD with the new checkout flow
     Gate: plan.requirements (open)
  2. plan.stories        [required]  pm · bmad-create-epics-and-stories
     Break the spec into epics and stories
     Gate: plan.stories (open)
  3. plan.ux             [conditional]  pm · bmad-ux
     UI is material — DESIGN.md and EXPERIENCE.md
     Gate: plan.ux (skipped: CLI only)
  4. Back
  q. Quit
```

Only list actions that are legal for the track and size. Mark the recommended action with `→`. Put required actions before optional ones, and the recommended action first within its group.

## Verbs

Natural language works, but these verbs are stable:

| Verb | Meaning |
|---|---|
| `start` | Create a workstream (asks name, track, size if not given). |
| `continue` / `next` | Take the recommended action. |
| `status` | Show the dashboard and full artifact paths. |
| `phase <name>` | Jump to a phase menu. |
| `run <action id>` | Run a specific action (e.g., `run plan.stories`). |
| `skip` | Mark the current gate `skipped`; requires a reason when the gate is required or conditional. |
| `override <reason>` | Set the current gate `overridden` with the reason supplied inline. |
| `revise` | Return to the last action with new direction. |
| `review` | Run `bmad-review` on the current artifact. |
| `switch <workstream>` | Change the active workstream; the previous active one is paused. |
| `role <pm\|dev\|qa> <reason>` | Persist this workstream's role (`role_override`) with a logged reason; the next `summary` reports `role_source: override`. `role --clear` returns to phase detection. |
| `resize <track> <size>` | Change track or size; recomputes every level and phase gate; clears `role_override`. |
| `pause` / `resume <workstream>` | Change workstream status; resume needs the id because pause clears `active_workstream`. |
| `done` | Mark the workstream done once every required/conditional gate is decided and no gate is blocked. |
| `reopen <gate> <reason>` | Return a decided gate to `open`; requires a reason. If the gate's phase or workstream is `done`, reopen that first. |
| `help` | Explain the current position and the legal moves. |
| `quit` | Exit; every write is already recorded. |

If the user types a skill name directly (e.g., `bmad-prd`), treat it as `run plan.prd` and confirm the mapping.

## Status view

`status` shows the dashboard rows, then per workstream: `current_role` with `role_source` (and any `role_override`), artifact paths, every gate with its level, status, and `decided_at`, ticket gate state, decisions, and overrides with reasons. Show `blocked` gates with the missing path, and show `reconcile`'s `missing_evidence`, `phases_to_block`, and `ambiguous_pointers` (several files match one artifact key). A `<phase>.unblock` next action means the phase is blocked with no gate left to show; the clearing procedure is in `ledger-schema.md` §Summary shape. Read ticket status from `sprint-status.yaml` or `tickets.toml` every time. If the read fails, say so and show the last known state; do not invent.

## After an action

Every action ends with the same three beats:

1. **Result** — what was produced, where, and what it means.
2. **Gate** — present the four-way choice (Approve / Revise / Run reviewer / Skip with override) and its ledger effect from `gate-matrix.md` §Gate interaction.
3. **Menu** — the next legal actions, with the recommendation and any `optional_actions`.

Do not dump the whole artifact. Summarize the evidence and point to the path.

## Tone

- Short lines. The menu is a control surface, not prose.
- No time estimates.
- State the detected model and track once; do not repeat them on every turn.
