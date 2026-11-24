# QA Gate Matrix (Role Overlay)

This overlay provides QA-specific gate considerations. Load after the base gate-matrix.md.

## QA Gate Considerations

| Gate id | QA Notes |
|---|---|
| `solution.test_design` | Conditional for epic/project. Test design must rank risks, name test levels/environments, and have coverage targets. |
| `solution.framework` | Conditional for epic/project. Framework scaffold must run smoke test. |
| `solution.ci` | Conditional for epic/project. CI config must run tests and fail on test failure. |
| `verify.trace` | Required for epic/project/audit; conditional for one-session/fix; optional for trivial. `summary` resolves the level. Traceability matrix + gate decision. Every requirement/ticket maps to test or explicit gap. Gate is PASS or CONCERNS with named gaps. |
| `verify.nfr` | Conditional for epic/project/audit. Performance/security/reliability requirements must have evidence or named gaps. |
| `verify.test_review` | Conditional for epic/project/audit. Coverage, isolation, determinism assessed; blocking issues named. |
| `close.retro` | Optional (recommended per epic). Retro document + verdict; findings cite evidence; action items have owners; verdict accept/reject. |
| `close.walkthrough` | Optional. Walkthrough with purpose, hot spots, and how to test. |

## QA Override Guidance

- `verify.trace`: Required gate. Override only with documented reason; gap must be visible in close summary.
- `verify.nfr`: Conditional. Skip with reason if no NFR requirements exist.
- `verify.test_review`: Conditional. Skip with reason if test quality not in doubt.
- `close.retro`: Optional. Skipping is normal; record `skipped` without reason.
- `close.walkthrough`: Optional. Skipping is normal; record `skipped` without reason.

## Blocked Gate Handling

When `verify.trace` is `blocked`:

- Missing traceability matrix or evidence
- QA reports: "Blocked: waiting for the trace matrix at /path/to/trace.md → `verify.trace` gate not passed"
- The conductor records the gate with `set --value blocked --reason "<why>"`; QA never writes the ledger
- No forced revise — wait, switch role, or override with a reason

## Rollback Rules

If QA's entry gate fails:

- The conductor records the source gate as `blocked` with a reason and pointer to the failed artifact, then re-runs `summary`
- Headless JSON keeps the `summary` shape and adds: `{"status": "blocked", "blocked_by": ["verify.trace"], "pointer": "/path/to/trace.md", "current_role": "qa"}`

## Handoff Rules

- QA → PM: When `close.correct_course` triggers replan or new epic needs planning
- QA → DEV: When `verify.trace` or `verify.nfr` finds gaps requiring build fixes
- No session context passed; next role reads only ledger + artifact files