# Handoff Protocol

BMAD recommends a fresh chat for each workflow to avoid context mixing. The conductor honors that: it owns the ledger, not the execution.

## Contents

- [Ladder](#ladder)
- [Brief template (rung 1, fresh subagent)](#brief-template-rung-1-fresh-subagent)
- [Fallback prompts (rung 3, user-run)](#fallback-prompts-rung-3-user-run)
  - [User-run, planning action](#user-run-planning-action)
  - [User-run, build action](#user-run-build-action)
- [Return contract](#return-contract)
- [Validation checklist](#validation-checklist)
- [Role transitions](#role-transitions)
  - [Handoff rules](#handoff-rules)
  - [Transition table](#transition-table)
- [Headless JSON](#headless-json)
- [Blocked gate handling](#blocked-gate-handling)
- [Subagent lifecycle](#subagent-lifecycle)
- [What the conductor keeps](#what-the-conductor-keeps)
- [Parallelism](#parallelism)

## Ladder

Start at the rung named by `{workflow.handoff_preference}` and descend to the first rung that is available:

1. **Fresh subagent** (`prefer`) — spawn a subagent seeded with the brief in §Brief template. It loads the target skill and does the work. The conductor's context stays clean.
2. **Inline skill load** (`inline`) — load the target skill into the current session and run it. There is no template for this rung: use the same brief inline. Warn the user that context is shared; prefer inline only for small steps.
3. **User-run handoff** (`user`) — print a ready-to-paste prompt plus the artifact paths. The two prompt templates in §Fallback prompts are ready to paste. The user runs the matching prompt in a fresh session and returns with the artifact. The conductor validates on return.
4. **Blocked** — if none apply, mark the action `blocked` with a reason and the exact install/prompt needed.

Do not run a phase yourself when the resolved preference or ladder points to a fresh subagent; when the preference is `inline`, load the target skill's `SKILL.md` and follow it rather than improvising. The conductor is a coordinator, not a substitute for the specialist skill.

## Brief template (rung 1, fresh subagent)

Give the subagent this, filled in. Keep it short; paths carry the detail. Seed the subagent with the target skill's directory path and tell it to read `SKILL.md` first; if the harness supports loading a skill by name, name the skill; otherwise the path is enough.

```text
You are running <skill-name> for the bmad-sdlc conductor.

Workstream: <id> — <name>
Track: <greenfield|feature|fix|audit>
Size: <trivial|one-session|epic|project>
Phase: <plan|solution|build|verify|close>
Role: <pm|dev|qa>
Action: <action id, e.g., plan.stories>

Objective:
<one or two sentences: what must be true when this finishes>

Inputs (read before acting):
- <absolute path>
- <absolute path>

Settled decisions / constraints (do not relitigate):
- <decision>
- <constraint>

Expected output:
- <artifact path or format>
- <evidence the gate needs>

Gate criteria:
- <criterion>
- <criterion>

Rules:
- Follow the target skill's instructions completely.
- Do not modify <resolved ledger path> or <resolved audit trail (memlog) path>.
- Do not commit, push, merge, or install dependencies unless the brief says so.
- If a required input is missing or contradictory, stop and return status "blocked" with the question.

Return exactly this JSON:
{
  "status": "<done|blocked|needs_input>",
  "role": "<pm|dev|qa>",
  "action": "<action id you ran>",
  "artifacts": [{"path": "...", "kind": "..."}],
  "evidence": ["..."],
  "decisions": [{"decision": "...", "reason": "..."}],
  "open_questions": ["..."],
  "next_recommendation": "..."
}
```

Fill every `<...>` placeholder; never copy one literally. The subagent gets this brief plus its `Role:` and `Action:` lines, and `--role <role> --plan <ledger> --workstream <id>`. There is no `--action` flag and no session summary: it reads only the ledger and artifact files.

## Fallback prompts (rung 3, user-run)

### User-run, planning action

```text
/bmad-prd
Create the PRD for <workstream name>. Read these inputs:
- <brief/spec path>
- <research path>
Constraints: <...>
Write the result to <planning_artifacts>/prd-<slug>/prd-<slug>.md.
When done, summarize: status, path, open questions.
```

### User-run, build action

```text
/bmad-build
Build <ticket ref / story 1.2> for <workstream name>.
Read the ticket and epic here: <path>.
Acceptance criteria and verification are in the ticket.
Constraints: <...>
Do not push or merge. When done, report the plan path, tests run, and review findings.
```

## Return contract

The conductor accepts a result only when:

- `status` is `done`, and
- `role` and `action` name the acting role and the action it ran, and match `--expect-role` / `--expect-action` when supplied, and
- the returned role owns the returned action (a role-free action is exempt), and
- at least one artifact is claimed and exists on disk, is non-empty, and is inside `{project-root}`, and
- no artifact is the ledger or the audit trail, and
- the gate criteria are evidenced (not merely asserted): the `evidence` list is present, non-empty, and every entry exists inside `{project-root}`, and
- `open_questions` is empty, or `verify-return --accept-questions` records them as accepted in the audit trail, and
- the ledger and audit trail are unchanged: their SHA-256 digests match the pre-handoff values.

Hash both files before spawning the subagent, then pass the digests (SHA-256) to the validator. Use the platform's tool (`shasum -a 256` on macOS, `sha256sum` on Linux). A probe call without the flags reports the `ledger_sha256` / `memlog_sha256` fields, but it is not an acceptance: `verify-return` requires both `--expect-*` flags to accept a return. Its `digest_check` field is `passed`, `failed`, or `not_run`; only `passed` means both digests matched. Pass `--expect-role <role> --expect-action <action id>` to reject a return from the wrong role, for the wrong action, or both.

```bash
ledger_before=$(shasum -a 256 {workflow.ledger_path} | cut -d' ' -f1)
memlog_before=$(shasum -a 256 {workflow.memlog_path} | cut -d' ' -f1)
```

A subagent must never write either file. `verify-return` rejects the return on a hash mismatch; the git-based `ledger_touched` flag is advisory only because an untracked or already-dirty ledger cannot be attributed to the handoff.

Run `verify-return` with `--memlog {workflow.memlog_path}` so a custom audit path is checked. `--allow-empty-artifacts` is only for an action whose brief explicitly produces no file; it requires `--reason`, is logged, and does not waive missing evidence.

If `status` is `blocked` or `needs_input`, do not mark the workstream, phase, or ticket `done`. Record the blocker, present it to the user, and offer: answer and retry, switch to inline, or skip with override.

If the subagent claims success but the artifact is missing, treat it as `blocked` and say what is missing. Never trust a claim over the filesystem.

## Validation checklist

Before accepting any handoff, confirm §Return contract is satisfied, then check:

1. **Scope** matches the action; a PRD is not a spec, a story is not an epic.
2. **No unapproved irreversible actions**: check `git status` and recent commits if the action could have changed them.
3. **Ledger untouched**: the ledger and audit hashes still match the values captured before the handoff; any mismatch is a rejected return, not a warning.
4. **Decisions** proposed by the subagent are appended to `decisions` and logged, not silently adopted.

## Role transitions

The trigger is always `next_action.role_allowed: false`; the table explains when that happens. A phase boundary fires when the phase is marked `done` in the ledger, not when a gate is merely passed. This table and §Handoff rules are the only statement of the transitions; the role overlays link here.

### Handoff rules

- Hand off when `next_action.role_allowed` is `false` — a role mismatch — regardless of whether a gate just passed. A blocked foreign gate needs a handoff with no pass at all.
- The next role reads **only** the ledger and artifact files — no session context, no summaries.
- Rollback: when the next role's entry gate fails, the **conductor** (never the handed-off role) records it and re-runs `summary` to re-resolve the role. Use `ticket --id <ticket> --gate <gate> --status blocked --reason "<gate> failed: <pointer>"` for a per-ticket gate, and `set --workstream <id> --path gates.<phase>.<gate>.status --value blocked --reason "<gate> failed: <pointer>"` for a phase gate. Named gates and valid ids: `gate-matrix.md` §Gate table.

### Transition table

| From | To | Boundary | Condition |
|---|---|---|---|
| PM | QA | plan → solution | Every required/conditional `plan.*` gate is decided and `phases.plan` is `done`; solution is not skipped. |
| PM | DEV | plan → build | Solution is skipped or optional for the track/size, so the next action is `build.*`. |
| QA | DEV | solution → build | Every `solution.*` gate is decided and `phases.solution` is `done` or `skipped`. |
| DEV | QA | build, per ticket | That ticket's `build.ticket` is decided and its `build.review` is open or blocked; `phases.build` stays active. |
| DEV | QA | build → verify | Every ticket's `build.done` is decided and `phases.build` is `done`. |
| QA | PM | close → plan | `close.correct_course` triggers a replan, or a new epic needs planning; reopen `plan` with a reason. |
| QA | DEV | verify → build | `verify.trace` or `verify.nfr` finds gaps or failures that need code changes; reopen `build` with a reason. |
| DEV | PM | build → plan | Blocked on a missing or incomplete spec: `plan.requirements` is `blocked`; reopen `plan` with a reason. |
| any | any | rollback | The entry gate fails; the conductor records it blocked and re-runs `summary`. Reopening the target phase is what moves the role back. |

Within one role the phase advances without a handoff: `solution → verify → close` is all QA, and one ticket follows another within DEV. Between one ticket's `build.ticket` and its `build.review` the state is the per-ticket row above; QA does not wait for the whole Build phase.

## Headless JSON

`references/headless.md` §Emitted block owns the block's field set; build that block, then apply the role-mismatch fields below. This example shows only the role-mismatch subset, not a second shape:

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

`blocked_by` is an ordered array of **action ids** — the actions `current_role` may not run — starting with `next_action.action`. `pointer` names the artifact that unblocks the first one. `next_action` is retained so the consumer can see the mismatch. **No `next_role` field** — read `next_action.role`. A role mismatch is `status: "blocked"` even when the skill is installed; never emit `ready` for an action `current_role` may not run.

## Blocked gate handling

When a role is blocked by incomplete work from a previous role:

- **DEV says**: "Blocked: waiting for PM to complete the spec at /path/to/SPEC.md → PM: `plan.requirements` gate not passed"
- The conductor records the blocked gate with the `--reason` above; the handed-off role never writes the ledger.
- **No forced revise** — wait, run the `role` verb, or override with a reason.
- **Ledger gate stays**: `plan.requirements` = `blocked` with the pointer recorded in the audit trail.

## Subagent lifecycle

- Per-action spawn (fresh subagent per action)
- Role's references loaded (base + role overlay)
- No session summary passed — only ledger artifacts
- Subagent returns JSON per §Return contract, including its `role` and `action` fields

## What the conductor keeps

The conductor keeps only:

- the ledger and the audit trail
- the current workstream's phase/gate position
- the settled decisions and constraints
- the pointers to artifacts

It does not keep the full text of every artifact in context. Re-read what the next action needs.

## Parallelism

- Plan actions may run in parallel when they share inputs and do not depend on each other (e.g., research + brief). The conductor asks once, before launching them together.
- Build actions run one ticket per session. Parallel tickets are allowed only when their boundaries are explicit and the user accepts the merge risk.
- The script serializes ledger and audit writes with a sibling `.lock` file. Never run two actions that write the same artifact or the same ledger section concurrently.
