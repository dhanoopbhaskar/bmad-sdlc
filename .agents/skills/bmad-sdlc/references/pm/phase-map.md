# PM Phase Map (Role Overlay)

PM delta only. Base `phase-map.md` owns the action tables; `role-config.toml` owns ownership.

- PM runs `frame.*` and `plan.*`. `frame.spec` or `plan.prd` satisfies `plan.requirements`; never require both.
- Read the artifact before deciding: why, what, constraints, non-goals, success signal, and open questions.
- `plan.stories` is satisfied by one ticket or a direct build intent for a `fix`; the current model's ticket tree is the sprint plan.
- `plan.ux` and `plan.architecture` are conditional. Name the condition; override with a reason when it does not apply.
- PM hands off when `next_action.role_allowed` is false after the phase is marked `done` (`handoff-protocol.md` §Role transitions).
