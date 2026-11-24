# DEV Gate Matrix (Role Overlay)

This overlay provides DEV-specific gate considerations. Load after the base gate-matrix.md.

## DEV Gate Considerations

| Gate id | DEV Notes |
|---|---|
| `build.ticket` | Per-ticket gate. Build plan must have acceptance criteria in Given/When/Then format; names files and verification; no TBDs. |
| `build.tests` | Per-ticket gate. Conditional; optional for `trivial`/`audit`. New/changed tests pass; no existing test loosened. Run project test runner. |
| `build.review` | Per-ticket gate. Required. Satisfied by `bmad-build` built-in review when findings triaged; run `bmad-code-review` separately for risky changes. Record which satisfied the gate. |
| `build.done` | Per-ticket gate. Required after `build.review`; optional for `audit`. Evidence recorded; human approved the done transition. |

## DEV Override Guidance

- `build.ticket`: Override with reason only if evidence pointer exists. Never mark done on override alone.
- `build.tests`: Override with reason if no test baseline exists or test run unavailable.
- `build.review`: Override needs reason. An overridden review is not enough for `build.done` - the artifact must exist or gap explicitly accepted.
- `build.done`: Refuses unless `build.review` passed (overridden review not enough). Overridden ticket gate needs evidence pointer or build phase carries evidence. The conductor asks the human and records the gate; DEV never self-approves.

## Blocked Gate Handling

When `build.ticket` is `blocked`:
- Missing build plan or acceptance criteria
- DEV reports: "Blocked: waiting for complete build plan at /path/to/plan.md → build.ticket gate not passed"
- The conductor records the gate with `set --value blocked --reason "<why>"`; DEV never writes the ledger
- No forced revise — wait, switch role, or override with a reason

## Handoff Rules

- DEV → QA: when every ticket has `build.done` passed and `summary.next_action.role` is `qa`
- DEV → PM: when blocked by a missing spec; the conductor reopens `plan` with a reason and re-runs `summary`
- No session context passed; the next role reads only the ledger and artifact files