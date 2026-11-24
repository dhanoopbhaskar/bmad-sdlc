# PM Phase Map (Role Overlay)

This overlay file provides PM-role-specific actions and gates. Load after the base phase-map.md.

## PM Actions

These are the actions owned by the Product Manager role:

| Action id | Role | v6 skill | Current-model skill | Gate |
|---|---|---|---|---|
| `frame.brainstorm` | pm | `bmad-brainstorming` | `bmad-brainstorming` | — |
| `frame.forge` | pm | `bmad-forge-idea` | `bmad-forge-idea` | — |
| `frame.research` | pm | `bmad-deep-recon` | `bmad-deep-recon` | — |
| `frame.brief` | pm | `bmad-product-brief` or `bmad-agent-analyst` | `bmad-agent-analyst` | — |
| `frame.prfaq` | pm | `bmad-prfaq` or `bmad-agent-analyst` | `bmad-agent-analyst` | — |
| `frame.spec` | pm | `bmad-spec` | `bmad-spec` or `bmad-agent-po` | `plan.requirements` |
| `plan.prd` | pm | `bmad-prd` or `bmad-agent-pm` | `bmad-agent-pm` | `plan.requirements` |
| `plan.ux` | pm | `bmad-ux` | `bmad-ux` | `plan.ux` |
| `plan.architecture` | pm | `bmad-architecture` | `bmad-architecture` | `plan.architecture` |
| `plan.stories` | pm | `bmad-create-epics-and-stories` | `bmad-agent-po` (slice/refine/incept) | `plan.stories` |
| `plan.sprint` | pm | `bmad-sprint-planning` | `bmad-agent-po` (tickets.toml is the plan) | `plan.sprint` |

## PM Gate Deltas

PM-specific gate considerations:

- `plan.requirements`: Satisfied by `frame.spec` or `plan.prd`. PM should verify the artifact exists and is complete.
- `plan.ux`: Optional for CLI-only tools. PM can skip with reason if UI is not material.
- `plan.architecture`: Conditional. PM should engage architect if 2+ units need to adopt a decision.
- `plan.stories`: Required for epic/project tracks. PM ensures stories are ordered with deliverables and verification.
- `plan.sprint`: Required for v6 model. PM ensures valid sprint-status.yaml with proper story statuses.

## Handoff Points

PM transitions to DEV when:
- `plan.requirements` is passed (SPEC.md or PRD exists)
- `plan.stories` is passed (epics/stories complete) OR track=fix with one-session size
- `plan.sprint` is passed (for v6 model)

PM transitions to QA when:
- Build phase is complete (all tickets done)
- `verify.trace` is ready for review