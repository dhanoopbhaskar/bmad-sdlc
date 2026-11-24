# PM Gate Matrix (Role Overlay)

This overlay provides PM-specific gate considerations. Load after the base gate-matrix.md.

## PM Gate Considerations

| Gate id | PM Notes |
|---|---|
| `plan.requirements` | PM ensures either `frame.spec` or `plan.prd` produces a complete artifact with why, what, constraints, non-goals, success signal, and open questions listed. Do not require both. |
| `plan.stories` | PM ensures stories/tickets are ordered, each has a deliverable and verification, and dependencies are named. For fix tracks, a single ticket or direct build intent satisfies this. |
| `plan.sprint` | PM ensures valid sprint-status.yaml; every story has a legal status; readiness check is PASS or CONCERNS with named risks. |
| `plan.ux` | PM evaluates if UI is material. If CLI-only or backend, skip with reason "not applicable". If UI exists, both DESIGN.md and EXPERIENCE.md must exist and cover primary flows. |
| `plan.architecture` | PM evaluates if 2+ units must adopt a decision. If so, architecture-*.md must exist with shared decisions, trade-offs, and no unresolved contradictions. |

## PM Override Guidance

- Required gates (`plan.requirements`, `plan.stories`, `plan.sprint` for v6 epic/project): Override only with a documented reason that is visible in close summary.
- Conditional gates (`plan.ux`, `plan.architecture`): Can be skipped with reason; record in phase note.
- Optional gates: Skipping is normal; record `skipped` without reason.

## Handoff Rules

- PM → DEV: when every required/conditional `plan.*` gate is decided and `summary.next_action.role` is `dev`
- No session context passed; the next role reads only the ledger and artifact files