# Menu

The conductor is menu-driven. Every activation and every transition ends with a menu, so the user never has to remember a skill name.

## Dashboard

Render this first. Keep it scannable.

```text
bmad-sdlc — <project>
Model: v6 (bmad-help) · Active: ws-001 <name> · Track: feature · Size: epic

Phase      Status    Gate          Open
Plan       active    required      2 required, 2 conditional
Solution   pending   conditional   3 conditional
Build      pending   required      —
Verify     pending   required      1 required, 2 conditional
Close      pending   optional      2 optional

Next recommended: plan.stories — break the spec into epics and stories
                  (product-owner · bmad-create-epics-and-stories)
```

Render the counts from `summary` (`required_open`, `conditional_open`, `optional_open`), not from this example. Those lists include per-ticket gates, so the Build row's counts are meaningful. `plan.sprint` is required only for v6 `epic`/`project`; a `fix`/`trivial` workstream starts in Build. Mark a `blocked` gate distinctly from `open`.

Show `optional_actions` separately; they are offered, never required. `close.mark_done` appears as the next action once every required/conditional gate is decided.

If there are multiple workstreams, add one line per workstream below the active one, using `summary.workstreams_detail` (id, name, track, size, status, next action):

```text
Other workstreams: ws-002 <name> (paused, feature, epic), ws-003 <name> (done, fix)
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
  q. Save and quit
```

Mark the current phase with `→`. Mark locked phases with `·` and the missing required gate.

## Action menu

After a phase is chosen, show its actions. Include the role, skill, and gate state.

```text
Plan — choose an action:
  1. plan.prd            [required]  product-manager · bmad-prd
     Update the PRD with the new checkout flow
     Gate: plan.requirements (open)
  2. plan.stories        [required]  product-owner · bmad-create-epics-and-stories
     Break the spec into epics and stories
     Gate: plan.stories (open)
  3. plan.ux             [conditional]  ux-designer · bmad-ux
     UI is material — DESIGN.md and EXPERIENCE.md
     Gate: plan.ux (skipped: CLI only)
  4. Back
  q. Save and quit
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
| `skip` | Skip the current gate; asks for a reason when the gate is required or conditional. |
| `override <reason>` | Same as skip, with the reason supplied inline. |
| `revise` | Return to the last action with new direction. |
| `review` | Run `bmad-review` on the current artifact. |
| `switch <workstream>` | Change the active workstream; the previous active one is paused. |
| `resize <track> <size>` | Change track or size; recomputes every level and phase gate. |
| `pause` / `resume` | Change workstream status; state is persisted either way. |
| `done` | Mark the workstream done once every required/conditional gate is decided. |
| `help` | Explain the current position and the legal moves. |
| `quit` | Save and exit; the ledger is already written. |

If the user types a skill name directly (e.g., `bmad-prd`), treat it as `run plan.prd` and confirm the mapping.

## Status view

`status` shows the dashboard rows, then per workstream: artifact paths, every gate with its level, status, and `decided_at`, ticket gate state, decisions, and overrides with reasons. Show `blocked` gates with the missing path, and `missing_evidence`/`phases_to_block` from `reconcile`. A `phase.unblock` next action means that phase is blocked with no gate left to show: resolve the blocker or override with a reason. Read ticket status from `sprint-status.yaml` or `tickets.toml` every time. If the read fails, say so and show the last known state; do not invent.

## After an action

Every action ends with the same three beats:

1. **Result** — what was produced, where, and what it means.
2. **Gate** — the four-way choice:
   - **Approve** — set the gate `passed`, record `decided_at`, log an event, advance if the phase is complete.
   - **Revise** — return to the action with the user's direction; re-run or patch; re-present the gate.
   - **Run reviewer** — invoke `bmad-review` (or the conditional test review); fold the findings into the summary and re-present. This does not pass the gate by itself.
   - **Skip with override** — require a reason when the gate is required or conditional; set the gate `overridden`, store the reason and `decided_at`, log it, and continue. The gate reference is `gate-matrix.md` §Gate interaction.
3. **Menu** — the next legal actions, with the recommendation and any `optional_actions`.

Do not dump the whole artifact. Summarize the evidence and point to the path.

## Tone

- Short lines. The menu is a control surface, not prose.
- No time estimates.
- State the detected model and track once; do not repeat them on every turn.
- Offer advisory actions only when `{workflow.include_advisory_skills}` is true.
