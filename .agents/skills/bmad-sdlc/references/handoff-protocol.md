# Handoff Protocol

BMAD recommends a fresh chat for each workflow to avoid context mixing. The conductor honors that: it owns the plan, not the execution.

## Contents

- [Ladder](#ladder)
- [Brief template (rung 1, fresh subagent)](#brief-template-rung-1-fresh-subagent)
- [Fallback prompts (rung 3, user-run)](#fallback-prompts-rung-3-user-run)
- [Return contract](#return-contract)
- [Validation checklist](#validation-checklist)
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
- Do not modify <resolved ledger path> or <resolved audit path>.
- Do not commit, push, merge, or install dependencies unless the brief says so.
- If a required input is missing or contradictory, stop and return status "blocked" with the question.

Return exactly this JSON:
{
  "status": "done | blocked | needs_input",
  "artifacts": [{"path": "...", "kind": "..."}],
  "evidence": ["..."],
  "decisions": [{"decision": "...", "reason": "..."}],
  "open_questions": ["..."],
  "next_recommendation": "..."
}
```

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
- at least one artifact is claimed and exists on disk, is non-empty, and is inside `{project-root}`, and
- no artifact is the ledger or the audit trail, and
- the gate criteria are evidenced (not merely asserted): the `evidence` list is present, non-empty, and every entry exists inside `{project-root}`, and
- `open_questions` is empty, or `verify-return --accept-questions` records them as accepted in the audit trail, and
- the ledger and audit trail are unchanged: their SHA-256 digests match the pre-handoff values.

Hash both files before spawning the subagent, then pass the digests (SHA-256) to the validator. Use the platform's tool (`shasum -a 256` on macOS, `sha256sum` on Linux). A probe call without the flags reports the `ledger_sha256` / `memlog_sha256` fields, but it is not an acceptance: `verify-return` requires both `--expect-*` flags to accept a return. Its `digest_check` field is `passed`, `failed`, or `not_run`; only `passed` means both digests matched.

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

---

## Artifact-Driven Handoff Protocol (Role-Based)

This section defines the role transition rules for the PM/DEV/QA split.

### Handoff Rules

- Handoff triggered **only** when a gate passes and the next action's role differs from `current_role` (`next_action.role_allowed: false`).
- Next role reads **only** the ledger + artifact files — no session context, no summaries.
- Subagent receives the §Brief template above plus `Role: <role>` and `--role=<role> --plan=<ledger> --workstream=<id> --action=<action>` — nothing else.
- Rollback: when the next role's entry gate fails, the **conductor** (never the handed-off role) records it with `set --workstream <id> --path gates.<phase>.<gate>.status --value blocked --reason "<gate> failed: <pointer>"`, then re-runs `summary` to re-resolve the role.

### Role Transitions

| From Role | To Role | Trigger | Condition |
|---|---|---|---|
| PM | DEV | plan phase complete | Every required/conditional `plan.*` gate decided; `next_action.phase` is no longer `plan` |
| DEV | QA | `build.done` | Every ticket in the sprint has `build.done` = `passed` |
| DEV | PM | `plan.requirements` | `blocked` (waiting for spec) |
| QA | PM | `close.correct_course` | Triggers replan |
| QA | DEV | `verify.trace` | Finds gaps requiring build fixes |
| QA | DEV | `verify.nfr` | Finds NFR failures requiring code changes |

### Headless JSON (Extended)

When a role transition happens in headless mode, emit the block defined in `references/headless.md` §Emitted block with the role fields below. This example is abridged; the emitted block keeps every summary list:

```json
{
  "status": "ready",
  "current_role": "dev",
  "next_action": {
    "phase": "build",
    "gate": "build.ticket",
    "action": "build.ticket",
    "role": "dev",
    "role_allowed": true,
    "skill": "bmad-build",
    "reason": "Build the next ready ticket.",
    "source": "computed"
  },
  "track": "feature",
  "size": "epic",
  "model": "v6",
  "assumptions": []
}
```

For a blocked handoff, keep the same shape with `"status": "blocked"` and add `"blocked_by"` and `"pointer"`. **No `next_role` field** — read `next_action.role` (from `role-config.toml`; an audit's `build.review` belongs to QA, not DEV).

### Blocked Gate Handling

When a role is blocked by incomplete work from a previous role:

- **DEV says**: "Blocked: waiting for PM to complete the spec at /path/to/SPEC.md → PM: `plan.requirements` gate not passed"
- The conductor records the blocked gate with the `--reason` above; the handed-off role never writes the ledger.
- **No forced revise** — wait, switch role, or override with a reason.
- **Ledger gate stays**: `plan.requirements` = `blocked` with the pointer recorded in the audit trail.

### Subagent Lifecycle

- Per-action spawn (fresh subagent per action)
- Role's references loaded (base + role overlay)
- No session summary passed — only ledger artifacts
- Subagent returns JSON per §Return contract
