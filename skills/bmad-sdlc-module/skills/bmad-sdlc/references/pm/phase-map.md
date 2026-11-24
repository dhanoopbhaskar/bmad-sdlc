# PM Phase Map (Role Overlay)

Role delta for the Product Manager. The base `phase-map.md` action tables carry the `Role` column and `role-config.toml` owns the mapping; this file adds only what PM must check and where it hands off.

## PM scope

`frame.*` and `plan.*` in the Plan phase. `frame.spec` or `plan.prd` satisfies `plan.requirements`; never require both.

## PM checks

- `plan.requirements`: the artifact states why, what, constraints, non-goals, and a success signal; open questions are listed.
- `plan.stories`: stories/tickets are ordered, each has a deliverable and a verification, and dependencies are named. A fix may satisfy this with one ticket or a direct build intent.
- `plan.sprint` (v6): `sprint-status.yaml` is valid and every story has a legal status. In the current model, Sofia's ticket tree is the plan.
- `plan.ux`: skip with a reason when UI is not material; otherwise `DESIGN.md` and `EXPERIENCE.md` must both exist.
- `plan.architecture`: skip with a reason unless 2+ units must adopt a decision; otherwise the decisions and trade-offs are recorded with no unresolved contradiction.

Gate levels and override effects: base `gate-matrix.md` §Gate table and §Override rules.

## Handoff

`handoff-protocol.md` §Role transitions is the only transition table; PM hands off when `next_action.role_allowed` is false after the phase is marked done.
