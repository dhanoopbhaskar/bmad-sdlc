# Handoff Protocol

BMAD recommends a fresh chat for each workflow to avoid context mixing. The conductor honors that: it owns the plan, not the execution.

## Ladder

Start at the rung named by `{workflow.handoff_preference}` and descend to the first rung that is available:

1. **Fresh subagent** — spawn a subagent seeded with the brief below. It loads the target skill and does the work. The conductor's context stays clean.
2. **Inline skill load** — load the target skill into the current session and run it. Warn that context is shared; prefer inline only for small steps.
3. **User-run handoff** — print a ready-to-paste prompt plus the artifact paths. The user runs it in a fresh session and returns with the artifact. The conductor validates on return.
4. **Blocked** — if none apply, mark the action `blocked` with a reason and the exact install/prompt needed.

Start at `prefer` → rung 1, `inline` → rung 2, `user` → rung 3; rung 4 (`blocked`) is terminal regardless of preference. Do not run a phase yourself when the resolved preference or ladder points to a fresh subagent; when the preference is `inline`, load the target skill's `SKILL.md` and follow it rather than improvising. The conductor is a coordinator, not a substitute for the specialist skill.

## Brief template

Give the subagent this, filled in. Keep it short; paths carry the detail. Seed the subagent with the target skill's directory path and tell it to read `SKILL.md` first; if the harness supports loading a skill by name, name it, otherwise the path is enough.

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
- Do not modify {workflow.ledger_path} or {workflow.memlog_path}.
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

## Return contract

The conductor accepts a result only when:

- `status` is `done`, and
- at least one artifact is claimed, it exists on disk, is non-empty, and is inside `{project-root}`, and
- no artifact is the ledger or the audit trail, and
- the gate criteria are evidenced (not merely asserted): a supplied `evidence` list is non-empty and every entry exists inside `{project-root}`, and
- `open_questions` is empty, or `verify-return --accept-questions` records them as accepted in the audit trail.

Run `verify-return` with `--memlog {workflow.memlog_path}` so a custom audit path is checked. `--allow-empty-artifacts` is only for an action whose brief explicitly produces no file; it does not waive missing evidence.

If `status` is `blocked` or `needs_input`, do not update the ledger to `done`. Record the blocker, present it to the user, and offer: answer and retry, switch to inline, or skip with override.

If the subagent claims success but the artifact is missing, treat it as `blocked` and say what is missing. Never trust a claim over the filesystem.

## Validation checklist

Before accepting any handoff, confirm the return contract above is satisfied, then check:

1. **Scope** matches the action; a PRD is not a spec, a story is not an epic.
2. **No ledger edits** by the subagent; `ledger_touched` is advisory, so confirm the ledger content is unchanged.
3. **No unapproved irreversible actions**: check `git status` and recent commits if the action could have changed them.
4. **Decisions** proposed by the subagent are appended to `decisions` and logged, not silently adopted.
5. **Open questions** are surfaced at the gate, or accepted explicitly.

## Fallback prompts

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

## What the conductor keeps

The conductor keeps only:

- the ledger and the audit trail
- the current workstream's phase/gate position
- the settled decisions and constraints
- the pointers to artifacts

It does not keep the full text of every artifact in context. Re-read what the next action needs.

## Parallelism

- Plan actions may run in parallel when they share inputs and do not depend on each other (e.g., research + brief). The conductor asks once.
- Build actions run one ticket per session. Parallel tickets are allowed only when their boundaries are explicit and the user accepts the merge risk.
- The script serializes ledger and audit writes with a sibling `.lock` file, but never run two actions that write the same artifact or the same ledger section concurrently.
