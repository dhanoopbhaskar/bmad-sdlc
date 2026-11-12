# Gate Matrix

This is the reference for gate levels, evidence, pass criteria, and override effects. Load it before presenting a gate or answering why something is blocked.

A gate is a checkpoint between the conductor and the human. The ledger records the outcome; the evidence lives in the BMAD artifacts. The conductor never advances a required gate on file presence alone: it reads the artifact and checks the pass criteria.

## Gate table

| Gate id | Level by track and size | Condition | Evidence | Pass criteria |
|---|---|---|---|---|
| `plan.requirements` | required for `epic`/`project`; conditional for `one-session`; optional for `trivial` and any `fix` | `epic`/`project`; `one-session` when the intent is not already well-defined; not required for `trivial` or a `fix` with a clear ticket | `SPEC.md` or a PRD | The artifact states why, what, constraints, non-goals, and a success signal; open questions are listed. |
| `plan.stories` | required for non-`fix` `epic`/`project`; conditional for a non-`fix` `one-session` and a `fix` `epic`/`project`; optional for `trivial` and a one-session `fix` | `epic`/`project`; a single ticket satisfies it for `fix`/`one-session` | v6: epics + stories. Current: `tickets.toml` | Stories/tickets are ordered, each has a deliverable and a verification, and dependencies are named. |
| `plan.sprint` | required for v6 `epic`/`project` (not `fix`); optional otherwise | v6 model and `epic`/`project` | `sprint-status.yaml` | Valid status file; every story has a legal status; the readiness check is PASS or CONCERNS with named risks. |
| `plan.ux` | conditional unless `trivial` or `fix`, then optional | UI is material to the product | `DESIGN.md` + `EXPERIENCE.md` | Both documents exist and cover the primary flows; design/experience agree. |
| `plan.architecture` | conditional for `epic`/`project` (not `fix`); optional otherwise | 2+ units must adopt a decision | `architecture-*.md` | Shared decisions are recorded with trade-offs; no unresolved contradiction across units. |
| `solution.test_design` | conditional for `epic`/`project` (not `fix`); optional otherwise | No test baseline, high risk, or multi-surface | Test design document | Risks are ranked; test levels and environments are named; coverage targets exist. |
| `solution.framework` | conditional for `epic`/`project` (not `fix`); optional otherwise | No framework installed | Framework scaffold | The project can run the framework's smoke test. |
| `solution.ci` | conditional for `epic`/`project` (not `fix`); optional otherwise | No CI quality pipeline | CI config | Tests run in CI; the pipeline fails on test failure. |
| `build.ticket` | required per ticket | Always | Build plan with acceptance criteria | ACs are Given/When/Then or equivalent; the plan names files and verification; no TBDs. |
| `build.tests` | conditional per ticket; optional for `trivial`/`audit` | Project has tests | Test run output | New/changed tests pass; no existing test is loosened to make them pass. |
| `build.review` | required per ticket | Always | Code review findings | Findings are triaged; in-scope issues fixed; deferred issues recorded. |
| `build.done` | required per ticket after `build.review`; optional for `audit` | After `build.review` | Approval to mark the ticket done | The ticket's evidence is recorded and a human approved the done transition. |
| `verify.trace` | required for `epic`/`project` and `audit`; conditional for `one-session`/`fix`; optional for `trivial` | Size/track condition | Traceability matrix + gate decision | Every requirement/ticket maps to a test or an explicit gap; the gate is PASS or CONCERNS with named gaps. |
| `verify.nfr` | conditional for `epic`/`project`/`audit` (not `fix`); optional otherwise | Performance/security/reliability requirements exist | NFR evidence | Each NFR has evidence or a named gap. |
| `verify.test_review` | conditional for `epic`/`project`/`audit` (not `fix`); optional otherwise | Test quality is in doubt | Test review report | Coverage, isolation, and determinism are assessed; blocking issues named. |
| `close.retro` | optional (recommended per epic) | Epic finished | Retro document + verdict | Findings cite evidence; action items have owners; verdict is accept/reject. |
| `close.walkthrough` | optional | A human should review the change | Walkthrough | The user has seen purpose, hot spots, and how to test. |

`build.ticket`, `build.tests`, `build.review`, and `build.done` are per-ticket. Record them under `tickets.<id>.gates` with the `ticket` script command. The ledger stores per-ticket gate outcomes and a pointer to the evidence; it does not duplicate ticket status.

An `audit` has no build tickets: its required code review is the `review` gate on the synthetic `audit` ticket. `build.done` is optional for an audit.

## Gate interaction

Present the gate with the four-way choice from `references/menu.md` §After an action: summary, level, evidence, and the risk of advancing. Do not silently pass, and do not ask an open-ended "does this look good?".

The ledger effect of each choice:

1. **Approve** → set the gate `passed`, record `decided_at`, log an event, advance if the phase is complete.
2. **Revise** → return to the action with the user's direction; re-run or patch; re-present the gate.
3. **Run reviewer** → invoke `bmad-review` (or the conditional test review) with the artifact; fold the findings into the summary and re-present. This does not pass the gate by itself.
4. **Skip with override** → require a reason. Set the gate `overridden`, store `override_reason` and `decided_at`, log the override, and continue. A required gate may be overridden; never hide it.

A gate whose evidence pointer is missing is `blocked`, not `open`. Offer either **resolve the artifact/pointer** or **override with a reason**; never advance past it silently.

## Override rules

- An override always needs a reason. The `set` and `ticket` commands reject an override on a required or conditional gate without `--reason`, and `validate` reports one that slipped in.
- A required or conditional gate set to `skipped` is an override and also needs a reason. The conductor cannot evaluate the `Condition` column, so it asks for the reason on every required or conditional skip instead of guessing.
- Optional gates: skipping is normal; record `skipped` and no reason.
- Required gates: an override is allowed but must be visible in the next status menu and in the close summary.
- **Levels are derived.** `gates.*.level` is a cache of the resolver. Editing it does not change enforcement; `validate` reports drift, and `resize` or `migrate` rewrites it.
- Never mark a ticket `done` on an override alone; the artifact must still exist or the user must explicitly accept the gap. The script refuses `done` before a passed `review`, and `review` before a passed `ticket` on non-audit work.

## Phase completion

A phase is `done` when:

- every required gate for that phase is `passed`, `overridden`, or `skipped`, and
- every conditional gate is `passed`, `overridden`, or `skipped` with a reason, and
- no gate in the phase is `blocked`, and
- the phase's evidence pointers are set.

`summary` reports `complete` per phase and `blocking` gate ids. Set a phase `done` only when it is complete; `set phases.<phase>.status done` refuses while a required or conditional gate is open or an earlier phase is undecided. A phase status is a cache: if a phase is already marked `done`/`skipped`, `summary` and `done` still see any open gate in it and report the inconsistency. Fix the gates, not the status.

When every phase is complete, `summary` recommends `close.mark_done`; `sdlc_plan.py done` refuses while any required or conditional gate is open or blocked, including per-ticket gates and a missing audit review. When no gate is open, it marks the workstream done. Never close on an override alone.

A phase may be skipped with a recorded reason once its gates are decided (or it has only optional gates). `reconcile` reports `missing_evidence` and `phases_to_block`; set those phases `blocked` and resolve the path. Reconciliation lives in `references/ledger-schema.md` § Resume semantics.
