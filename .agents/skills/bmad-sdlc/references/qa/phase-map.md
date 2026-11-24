# QA Phase Map (Role Overlay)

Role delta for the Quality role. The base `phase-map.md` action tables carry the `Role` column and `role-config.toml` owns the mapping; this file adds only QA's checks and handoff.

## QA scope

`solution.*`, `verify.*`, `close.*`, plus `build.review` and `build.done` on every track. QA reviews the feature change and approves the done transition, so the role that built a ticket does not also close it. `close.mark_done` is role-free.

## QA checks

- `solution.*`: test design ranks risks and names levels, environments, and coverage targets; the framework scaffold runs a smoke test; CI runs the tests and fails on failure. Skip with a reason when the project already has a mature stack, and record it in `phases.solution.note`.
- `build.review`: findings are triaged, in-scope issues are fixed, and deferred issues are recorded. Record which review satisfied the gate.
- `build.done`: evidence is recorded and the human approved the transition.
- `verify.trace`: every requirement or ticket maps to a test or an explicit gap; the gate is PASS or CONCERNS with named gaps. `verify.nfr` and `verify.test_review` are conditional where the base table says so.

Gate levels, evidence, and override effects: base `gate-matrix.md` §Gate table and §Override rules. The Solution phase walkthrough is in `qa/solution-phase.md`.

## Handoff

`handoff-protocol.md` §Role transitions is the only transition table, and §Headless JSON holds the role-mismatch fields. QA hands off when `next_action.role_allowed` is false; within QA a phase advances without one.
