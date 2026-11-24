# PM Gate Matrix (Role Overlay)

Role delta for the Product Manager. Every gate level, evidence rule, and override effect lives in base `gate-matrix.md`; this file adds only PM-specific judgment.

- `plan.requirements`: decide after reading the artifact, not on file presence. A `SPEC.md` and a PRD are alternatives, not a pair.
- `plan.stories` / `plan.sprint`: a single ticket or a direct build intent satisfies `plan.stories` for a `fix`; do not ask for a separate sprint plan in the current model.
- `plan.ux` / `plan.architecture`: conditional. Name the condition, record the skip reason in `phases.plan.note`, and let the user decide.
- A required gate override is allowed but must stay visible in the status menu and the close summary.

## Handoff

`handoff-protocol.md` §Role transitions is the only transition table. PM hands off when `next_action.role_allowed` is false after the phase is marked `done`.
