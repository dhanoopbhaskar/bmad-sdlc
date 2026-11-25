# QA Phase Map (Role Overlay)

QA delta only. Base `phase-map.md` owns the action tables; `role-config.toml` owns ownership.

- QA runs `solution.*`, `verify.*`, `close.*`, plus `build.review` and `build.done` on every track. `close.mark_done` is role-free.
- Build is a mixed phase: QA enters it for `build.review` and `build.done` only. The `⇄` marker means another role owns the phase, not that QA must stay out.
- `build.review`: findings are triaged, in-scope issues fixed, deferred issues recorded. Record which review satisfied the gate.
- `build.done`: the ticket's evidence is recorded and the human approved the transition.
- `verify.trace`: every requirement or ticket maps to a test or an explicit gap; the result is PASS or CONCERNS with named gaps.
- QA hands off when `next_action.role_allowed` is false; within QA a phase advances without one.
