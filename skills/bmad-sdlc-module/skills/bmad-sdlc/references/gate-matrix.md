# Gate Matrix

This is the reference for gate levels, evidence, pass criteria, and override effects. Load it before presenting a gate or answering why something is blocked.

A gate is a checkpoint between the conductor and the human. The ledger records the outcome; the evidence lives in the BMAD artifacts. The conductor never advances a required gate on file presence alone: it reads the artifact and checks the pass criteria. Role ownership is in `role-config.toml`; read `next_action.action` and `next_action.role` rather than deriving either from a gate id. Every gate write records the acting role on the node (`actor`) and in the audit line.

## Gate table

The `Level` column is the resolved requirement for the current track, size, and model. `summary` computes it and wins if a stored value disagrees. The `Condition` column is the human judgment the conductor cannot compute; it does not repeat the size rule.

| Gate id | Level | Condition | Evidence | Pass criteria |
|---|---|---|---|---|
| `plan.requirements` | required for `epic`/`project`; conditional for `one-session`; optional for `trivial` and any `fix` | The intent is not already well-defined | `SPEC.md` or a PRD | The artifact states why, what, constraints, non-goals, and a success signal; open questions are listed. |
| `plan.stories` | required for non-`fix` `epic`/`project`; conditional for a non-`fix` `one-session` and a `fix` `epic`/`project`; optional otherwise | The work needs more than one build unit | v6: epics + stories. Current: `tickets.toml` | Stories/tickets are ordered, each has a deliverable and a verification, and dependencies are named. |
| `plan.sprint` | required for v6 `epic`/`project` (not `fix`); optional otherwise | The v6 model is installed | `sprint-status.yaml` | Valid status file; every story has a legal status; the readiness check is PASS or CONCERNS with named risks. |
| `plan.ux` | conditional unless `trivial`, `fix`, or `audit`, then optional | UI is material to the product | `DESIGN.md` + `EXPERIENCE.md` | Both documents exist and cover the primary flows; design/experience agree. |
| `plan.architecture` | conditional for `epic`/`project` (not `fix` or `audit`); optional otherwise | 2+ units must adopt a decision | `architecture-*.md` | Shared decisions are recorded with trade-offs; no unresolved contradiction across units. |
| `solution.test_design` | conditional for `epic`/`project` (not `fix`); optional otherwise | No test baseline, high risk, or multi-surface | Test design document | Risks are ranked; test levels and environments are named; coverage targets exist. |
| `solution.framework` | conditional for `epic`/`project` (not `fix`); optional otherwise | No framework installed | Framework scaffold | The project can run the framework's smoke test. |
| `solution.ci` | conditional for `epic`/`project` (not `fix`); optional otherwise | No CI quality pipeline | CI config | Tests run in CI; the pipeline fails on test failure. |
| `build.ticket` | required per ticket | Always | Build plan with acceptance criteria | ACs are Given/When/Then or equivalent; the plan names files and verification; no TBDs. |
| `build.tests` | conditional per ticket; optional for `trivial`/`audit` | Project has tests | Test run output | New/changed tests pass; no existing test is loosened to make them pass. |
| `build.review` | required per ticket | Always | Code review findings | Findings are triaged; in-scope issues fixed; deferred issues recorded. |
| `build.done` | required per ticket after `build.review`; optional for `audit` | After `build.review` | Approval to mark the ticket done | The ticket's evidence is recorded and a human approved the done transition. |
| `verify.trace` | required for `epic`/`project` and `audit`; conditional for `one-session`/`fix`; optional for `trivial` | Always for `epic`/`project`/`audit` | Traceability matrix + gate decision | Every requirement/ticket maps to a test or an explicit gap; the gate is PASS or CONCERNS with named gaps. |
| `verify.nfr` | conditional for `epic`/`project`/`audit` (not `fix`); optional otherwise | Performance/security/reliability requirements exist | NFR evidence | Each NFR has evidence or a named gap. |
| `verify.test_review` | conditional for `epic`/`project`/`audit` (not `fix`); optional otherwise | Test quality is in doubt | Test review report | Coverage, isolation, and determinism are assessed; blocking issues named. |
| `close.retro` | optional (recommended per epic) | Epic finished | Retro document + verdict | Findings cite evidence; action items have owners; verdict is accept/reject. |
| `close.walkthrough` | optional | A human should review the change | Walkthrough | The user has seen purpose, hot spots, and how to test. |

`build.ticket`, `build.tests`, `build.review`, and `build.done` are per-ticket. Record them under `tickets.<id>.gates` with the `ticket` command; each gate node may carry an `evidence` pointer and an `actor` (the role that decided it), and the `done` command resolves the pointer. The ledger stores gate outcomes, not ticket status.

Marking a phase `done` or `skipped` by a role other than the phase's owner needs `--reason`, and the audit line names the actor: a phase advance is what hands the workstream to the next role.

An `audit` has no build tickets: its required code review is the `review` gate on the synthetic `audit` ticket. For an `audit`, every `plan.*` gate resolves to `optional`, `verify.trace` is required regardless of size, and `verify.nfr` / `verify.test_review` are conditional.

## Gate interaction

Present the gate with the summary, its level, the evidence, and the risk of advancing, then the four-way choice. Do not silently pass, and do not ask an open-ended "does this look good?".

The ledger effect of each choice:

1. **Approve** → set the gate `passed`, record `decided_at`, log an event, advance if the phase is complete.
2. **Revise** → return to the action with the user's direction; re-run or patch; re-present the gate.
3. **Run reviewer** → invoke `bmad-review` (or the conditional test review) with the artifact; fold the findings into the summary and re-present. This does not pass the gate by itself.
4. **Skip with override** → require a reason and set the gate `overridden`; store `override_reason` and `decided_at`, log the override, and continue. `skipped` is a different status and is only for an optional gate that does not apply; it needs no reason.

## Override rules

- A gate whose evidence pointer is missing is `blocked`, not `open`. Offer either **resolve the artifact/pointer** or **override with a reason**; never advance past it silently.
- Never mark a ticket `done` on an override alone; the artifact must still exist or the user must explicitly accept the gap. The script refuses `done` unless `review` passed (an overridden review is not enough), and refuses to decide `review` before `ticket` is passed or overridden on non-audit work. An overridden ticket gate needs an `evidence` pointer, or the build phase must carry evidence.
- An override always needs a reason. The `set` and `ticket` commands reject an override on a required or conditional gate without `--reason`, and `validate` fails on one that slipped in.
- `skipped` is only for an optional gate that does not apply; it needs no reason. Declining a required or conditional gate is `overridden` with a reason. The commands refuse `skipped` on a required or conditional gate.
- Required gates: an override is allowed but must be visible in the next status menu and in the close summary.

## Reopening

Changing a decided gate (`passed`, `overridden`, or `skipped`) to any status, including back to `passed`, needs `--reason`. Use `set` for a phase gate, `ticket` for a per-ticket gate, or the `reopen` menu verb.

- `open` returns the gate to work. It is refused while a later ticket gate is decided, or while its phase is `done`/`skipped`; reopen the phase first.
- `blocked` records missing evidence and is not a decision: it carries no `override_reason` or `decided_at`. Any `--reason` required to move a decided gate is logged to the audit trail only.
- A gate on a done workstream cannot be written. Reopen the workstream with `set --plan <ledger> --workstream <id> --path status --value active --reason <why>`, then reopen its phases and gates in order.
- Reopening a phase from `done`/`skipped` to `active`, `pending`, or `blocked` also needs `--reason`.
- `reconcile --write` returns a gate it blocked to `open` once the artifact resolves; if it reports a decided gate in `requires_reason`, reopen that gate with `set --plan <ledger> --path gates.<phase>.<gate>.status --value blocked --reason <why>`.

## Phase completion

A phase is complete when every required and conditional gate is `passed` or `overridden`, every such override or reasoned skip carries a reason, optional gates are either decided or left open, and no gate in the phase is `blocked`.

`done` closes the workstream only when:

- no required or conditional gate is open, and no gate at any level is blocked, including per-ticket gates and a missing audit review;
- every passed required or conditional gate has an artifact pointer that resolves, or, for a gate with no artifact key, a phase evidence entry that resolves. An overridden gate is an accepted gap: its reason is the record, and the close summary lists it. A pointer for an optional gate that was never decided is not part of the close contract;
- an overridden ticket gate carries its own `evidence` pointer or the build phase carries evidence;
- `plan.ux` has both `DESIGN.md` and `EXPERIENCE.md`;
- an intentional gap carries `--accept-missing-evidence` or `--accept-missing-tickets` plus `--reason`; with no ticket built, the waiver records the gap and leaves `phases.build` open rather than claiming it finished;
- an audit's synthetic ticket is exempt from the ticket-overlay check.

`summary` reports `complete` per phase and `blocking` gate ids. Set a phase `done` only when it is complete; `set phases.<phase>.status done` refuses while a required or conditional gate is open, any gate is blocked, or an earlier phase is undecided. A phase already marked `done`/`skipped` is a cache: `summary` and `done` still see any open gate in it and report the inconsistency. Fix the gates, not the status.

When every phase is complete, `summary` recommends `close.mark_done`. An override is a recorded decision, not a pass; the close note lists it. `close.mark_done` is role-free: every role may run it, and the close note records the acting role, the phases `done` advanced, and every override or reasoned skip. A phase may be skipped with a recorded reason once its gates are decided (or it has only optional gates).
