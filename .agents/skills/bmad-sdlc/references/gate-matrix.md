# Gate Matrix

This is the reference for gate levels, evidence, pass criteria, and override effects. Load it before presenting a gate or answering why something is blocked.

## Contents

- [Gate table](#gate-table)
- [Gate interaction](#gate-interaction)
- [Override rules](#override-rules)
- [Reopening](#reopening)
- [Phase completion](#phase-completion)

A gate is a checkpoint between the conductor and the human. The ledger records the outcome; the evidence lives in the BMAD artifacts. The conductor never advances a required gate on file presence alone: it reads the artifact and checks the pass criteria.

## Gate table

| Gate id | Level by track and size | Condition | Evidence | Pass criteria |
|---|---|---|---|---|
| `plan.requirements` | required for `epic`/`project`; conditional for `one-session`; optional for `trivial` and any `fix` | `epic`/`project`; `one-session` when the intent is not already well-defined; not required for `trivial` or a `fix` with a clear ticket | `SPEC.md` or a PRD | The artifact states why, what, constraints, non-goals, and a success signal; open questions are listed. |
| `plan.stories` | required for non-`fix` `epic`/`project`; conditional for a non-`fix` `one-session` and a `fix` `epic`/`project`; optional for `trivial` and a `fix` `one-session` | `epic`/`project`; a single ticket satisfies it for `fix`/`one-session` | v6: epics + stories. Current: `tickets.toml` | Stories/tickets are ordered, each has a deliverable and a verification, and dependencies are named. |
| `plan.sprint` | required for v6 `epic`/`project` (not `fix`); optional otherwise | v6 model installed | `sprint-status.yaml` | Valid status file; every story has a legal status; the readiness check is PASS or CONCERNS with named risks. |
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

The `Condition` column guides the human deciding whether a gate applies; the conductor cannot evaluate it. The `Level` column is the resolved answer for the current track, size, and model; the stored level is a cache and `summary` wins if it disagrees.

`build.ticket`, `build.tests`, `build.review`, and `build.done` are per-ticket. Record them under `tickets.<id>.gates` with the `ticket` command; each gate node may carry an `evidence` pointer, and the `done` command resolves it. The ledger stores gate outcomes, not ticket status.

An `audit` has no build tickets: its required code review is the `review` gate on the synthetic `audit` ticket. For an `audit`, every `plan.*` gate resolves to `optional`, `verify.trace` is required regardless of size, and `verify.nfr` / `verify.test_review` are conditional.

## Gate interaction

Present the gate with the summary, its level, the evidence, and the risk of advancing, then the four-way choice. Do not silently pass, and do not ask an open-ended "does this look good?".

The ledger effect of each choice:

1. **Approve** → set the gate `passed`, record `decided_at`, log an event, advance if the phase is complete.
2. **Revise** → return to the action with the user's direction; re-run or patch; re-present the gate.
3. **Run reviewer** → invoke `bmad-review` (or the conditional test review) with the artifact; fold the findings into the summary and re-present. This does not pass the gate by itself.
4. **Skip with override** → require a reason. Set the gate `overridden`, store `override_reason` and `decided_at`, log the override, and continue. A required gate may be overridden; never hide it. (`skipped` is a separate status: use it only for an optional gate or when the phase itself is being skipped.)

## Override rules

- A gate whose evidence pointer is missing is `blocked`, not `open`. Offer either **resolve the artifact/pointer** or **override with a reason**; never advance past it silently.
- Never mark a ticket `done` on an override alone; the artifact must still exist or the user must explicitly accept the gap. The script refuses `done` unless `review` passed (an overridden review is not enough), and refuses to decide `review` before `ticket` is passed or overridden on non-audit work. An overridden ticket gate needs an `evidence` pointer, or the build phase must carry evidence.
- An override always needs a reason. The `set` and `ticket` commands reject an override on a required or conditional gate without `--reason`, and `validate` fails on one that slipped in.
- A required or conditional gate set to `skipped` is an override and also needs a reason.
- Optional gates: skipping is normal; record `skipped` and no reason.
- Required gates: an override is allowed but must be visible in the next status menu and in the close summary.

## Reopening

Changing a decided gate (`passed`, `overridden`, or `skipped`) to any status, including back to `passed`, needs `--reason`. Use `set` for a phase gate, `ticket` for a per-ticket gate, or the `reopen` menu verb.

- `open` returns the gate to work. It is refused while a later ticket gate is decided, or while its phase is `done`/`skipped`; reopen the phase first.
- `blocked` records missing evidence and is not a decision: it carries no `override_reason` or `decided_at`. Any `--reason` required to move a decided gate is logged to the audit trail only.
- A gate on a done workstream cannot be written. Reopen the workstream with `set --workstream <id> --path status --value active --reason <why>`, then reopen its phases and gates in order.
- Reopening a phase from `done`/`skipped` to `active`, `pending`, or `blocked` also needs `--reason`.

## Phase completion

A phase is complete when every required gate is `passed`, `overridden`, or `skipped`; every conditional gate is decided the same way; an overridden or skipped required/conditional gate carries a reason; and no gate in the phase is `blocked`.

`done` closes the workstream only when:

- no required or conditional gate is open, and no gate at any level is blocked, including per-ticket gates and a missing audit review;
- every decided required or conditional gate has an artifact pointer that resolves, or, for a gate with no artifact key, a phase evidence entry that resolves;
- an overridden ticket gate carries its own `evidence` pointer or the build phase carries evidence;
- `plan.ux` has both `DESIGN.md` and `EXPERIENCE.md`;
- an intentional gap carries `--accept-missing-evidence` or `--accept-missing-tickets` plus `--reason`;
- an audit's synthetic ticket is exempt from the ticket-overlay check.

`summary` reports `complete` per phase and `blocking` gate ids. Set a phase `done` only when it is complete; `set phases.<phase>.status done` refuses while a required or conditional gate is open, any gate is blocked, or an earlier phase is undecided. A phase already marked `done`/`skipped` is a cache: `summary` and `done` still see any open gate in it and report the inconsistency. Fix the gates, not the status.

When every phase is complete, `summary` recommends `close.mark_done`. Never close on an override alone. `done` records every overridden or reasoned-skipped gate in the close summary.

A phase may be skipped with a recorded reason once its gates are decided (or it has only optional gates).
