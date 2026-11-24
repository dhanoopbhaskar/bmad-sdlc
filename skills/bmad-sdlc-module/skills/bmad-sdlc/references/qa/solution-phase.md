# QA Solution Phase (Role Overlay)

This file provides QA-specific guidance for the Solution phase. The Solution phase decides how work will be verified before building.

## QA Responsibilities in Solution Phase

As the Quality role, you own the test strategy and verification setup:

1. **Test Design** (`solution.test_design`)
   - Identify risks and rank them
   - Define test levels (unit, integration, e2e, contract)
   - Name test environments
   - Set coverage targets
   - Output: Test design document

2. **Test Framework** (`solution.framework`)
   - Set up test framework if not present
   - Configure test runner
   - Ensure smoke test passes
   - Output: Framework scaffold

3. **CI Pipeline** (`solution.ci`)
   - Configure CI quality pipeline
   - Tests run in CI
   - Pipeline fails on test failure
   - Output: CI config

## When to Skip

Skip Solution phase gates when:
- Project already has mature test stack and CI
- Decision to skip recorded in `phases.solution.note` with reason
- Phase marked `skipped` only after gates decided

Do not skip silently.

## QA-Specific Gate Criteria

| Gate | Evidence Required | Pass Criteria (see base `gate-matrix.md`) |
|---|---|---|
| `solution.test_design` | Test design document | Risks ranked; test levels/environments named; coverage targets exist |
| `solution.framework` | Framework scaffold | Project can run framework's smoke test |
| `solution.ci` | CI config | Tests run in CI; pipeline fails on test failure |

## Handoff to Build

`handoff-protocol.md` §Role transitions owns the QA → DEV transition; it fires when `phases.solution` is marked `done` or `skipped`. DEV then reads the test design for ATDD (`build.atdd`), runs tests per ticket (`build.tests`), and reads only the ledger plus artifact files.