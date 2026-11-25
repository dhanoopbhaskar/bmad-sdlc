# PM Gate Matrix (Role Overlay)

PM delta only. Base `gate-matrix.md` owns levels, evidence, and override effects.

- Decide `plan.requirements` after reading the artifact, not on file presence. A `SPEC.md` and a PRD are alternatives, not a pair.
- `plan.stories` / `plan.sprint`: one ticket or a direct build intent satisfies `plan.stories` for a `fix`; do not ask for a separate sprint plan in the current model.
- `plan.ux` / `plan.architecture` are conditional: name the condition, use `overridden` with a reason when it does not apply, and record the reason in `phases.plan.note`.
- A required-gate override stays visible in the status menu and the close summary.

PM hands off per `handoff-protocol.md` §Role transitions when `next_action.role_allowed` is false after the phase is `done`.
