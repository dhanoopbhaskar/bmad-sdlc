# QA Solution Phase (Role Overlay)

QA delta for Solution only. Base `gate-matrix.md` owns levels and evidence.

- `solution.test_design`: rank risks, name test levels and environments, and set coverage targets.
- `solution.framework`: make the project run the framework's smoke test.
- `solution.ci`: run the tests in CI and fail the pipeline on a test failure.
- When the project already has a mature stack, override each gate with a reason, record it in `phases.solution.note`, and only then mark the phase `skipped`. Never skip silently.

The QA → DEV handoff is in `handoff-protocol.md` §Role transitions; it fires when `phases.solution` is `done` or `skipped`.
