# BMAD-SDLC End-to-End Test Suite

This directory contains a comprehensive test suite for validating the `bmad-sdlc` skill's complete Software Development Lifecycle conductor workflow.

## Test Suite Structure

```
bmad-sdlc/
├── test_e2e_usecase.md          # Complete use case documentation
├── run_e2e_test.py              # Automated test runner
├── test_e2e_cases.json          # Eval cases for bmad-eval-runner
├── test_fixtures/               # Pre-staged ledger fixtures
│   ├── plan_phase_complete.yaml
│   ├── plan_phase_complete.memlog.md
│   ├── build_phase_complete.yaml
│   ├── build_phase_complete.memlog.md
│   ├── workstream_complete.yaml
│   └── workstream_complete.memlog.md
└── TEST_SUITE_README.md         # This file
```

## Quick Start

### Prerequisites

- Python 3.11+
- `uv` package manager
- OpenCode with BMAD skills installed

### Run All Tests (Automated)

```bash
cd /Users/dhanoopbhaskar/git/bmad-sdlc
uv run --no-cache python run_e2e_test.py
```

### Run with bmad-eval-runner (Quality Mode)

```bash
XDG_DATA_HOME="$HOME/.local/share" XDG_CONFIG_HOME="$HOME/.config" \
  uv run --no-cache .agents/skills/bmad-eval-runner/scripts/run_evals.py \
  --cases test_e2e_cases.json \
  --skill-path .agents/skills/bmad-sdlc \
  --output-dir ~/bmad-evals/test-e2e \
  --mode quality
```

### Run Unit Tests

```bash
uv run --no-cache python -m unittest discover \
  -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'
```

## Test Coverage

The test suite validates the complete SDLC lifecycle:

| Phase | Tests | Key Validations |
|-------|-------|-----------------|
| **Init** | Project initialization | Ledger creation, track/size/model detection, role assignment |
| **Plan** | Requirements → UX → Architecture → Stories → Sprint | Gate evidence, actor recording, phase completion |
| **Solution** | Test Design → Framework → CI | QA role ownership, conditional gates |
| **Build** | 5 tickets × 4 gates each | DEV/QA role separation, no self-approval, per-ticket gates |
| **Verify** | Trace (required) + NFR + Test Review | Traceability as quality gate, all evidence |
| **Close** | Walkthrough → Retro → Mark Done | Close criteria validation, workstream closure |

### Guardrail Tests

- Role-based action gating (PM/DEV/QA)
- No self-approval (builder ≠ reviewer ≠ approver)
- Override requires reason
- Scope capture (out-of-scope requests logged)
- Headless mode JSON contract
- Resume from existing ledger
- Consent before irreversible actions

### Special Track Tests

- **Greenfield Epic** (full lifecycle)
- **Fix Trivial** (short-circuit path)
- **Audit** (QA-only, synthetic ticket)
- **Feature One-Session** (planning-light)

## Fixtures

The `test_fixtures/` directory contains pre-staged ledger states for testing mid-lifecycle scenarios:

| Fixture | Phase | Use Case |
|---------|-------|----------|
| `plan_phase_complete.*` | Solution | Test solution phase with plan done |
| `build_phase_complete.*` | Verify | Test verify phase with all tickets done |
| `workstream_complete.*` | Done | Test close phase and resume |

### Using Fixtures

```bash
# Copy fixture to test project
cp test_fixtures/plan_phase_complete.yaml test_e2e_project/_bmad-output/sdlc/plan.yaml
cp test_fixtures/plan_phase_complete.memlog.md test_e2e_project/_bmad-output/sdlc/.memlog.md

# Run test from that state
cd test_e2e_project
bmad-sdlc "Continue TaskFlow. Work only in the project root."
```

## Test Scenarios Documented in `test_e2e_usecase.md`

The main use case document (`test_e2e_usecase.md`) provides:

1. **Complete narrative** of the TaskFlow SaaS project
2. **Step-by-step commands** for each phase
3. **Expected ledger states** after each gate
4. **Headless mode JSON** output specification
5. **Role-based access** test scenarios
6. **Error handling** test scenarios
7. **Verification checklist** for manual validation

## Running in CI/CD

### GitHub Actions Example

```yaml
name: BMAD-SDLC E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install uv
        run: pip install uv
      - name: Run unit tests
        run: uv run --no-cache python -m unittest discover -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'
      - name: Run e2e tests
        run: uv run --no-cache python run_e2e_test.py
        env:
          XDG_DATA_HOME: ${{ runner.temp }}/.local/share
          XDG_CONFIG_HOME: ${{ runner.temp }}/.config
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: ruamel` | Use `uv run --no-cache` not plain `python3` |
| Ledger validation fails | Check `test_fixtures/` for correct structure |
| Skill not found | Ensure BMAD skills installed in `.agents/skills/` |
| Headless mode returns `needs_input` | Provide name, track, size in command |
| Role gating not working | Verify `role-config.toml` is readable |

### Debug Commands

```bash
# Validate ledger structure
uv run --no-cache .agents/skills/bmad-sdlc/scripts/sdlc_plan.py validate \
  --plan test_e2e_project/_bmad-output/sdlc/plan.yaml

# Get summary
uv run --no-cache .agents/skills/bmad-sdlc/scripts/sdlc_plan.py summary \
  --plan test_e2e_project/_bmad-output/sdlc/plan.yaml \
  --project-root test_e2e_project

# Detect model
uv run --no-cache .agents/skills/bmad-sdlc/scripts/sdlc_plan.py detect \
  --project-root test_e2e_project
```

## Expected Test Artifacts

After a full successful run, the test project should contain:

```
test_e2e_project/_bmad-output/
├── sdlc/
│   ├── plan.yaml          # Final ledger (committed)
│   └── .memlog.md         # Audit trail (committed)
├── planning-artifacts/
│   ├── prd-taskflow.md
│   ├── tickets.toml
│   └── sprint-status.yaml
├── specs/
│   └── spec-taskflow/
│       └── SPEC.md
├── implementation-artifacts/
│   ├── story-t1-plan.md
│   ├── story-t2-plan.md
│   ├── story-t3-plan.md
│   ├── story-t4-plan.md
│   ├── story-t5-plan.md
│   ├── t1-review.md
│   ├── t2-review.md
│   ├── t3-review.md
│   ├── t4-review.md
│   ├── t5-review.md
│   ├── walkthrough.md
│   └── retrospective.md
├── test-artifacts/
│   ├── test-design.md
│   ├── test-framework/
│   ├── ci-config.yml
│   ├── traceability-matrix.md
│   ├── nfr-evidence.md
│   ├── test-review.md
│   ├── test-run-t1.txt
│   ├── test-run-t2.txt
│   ├── test-run-t3.txt
│   ├── test-run-t4.txt
│   └── test-run-t5.txt
├── ux/
│   ├── DESIGN.md
│   └── EXPERIENCE.md
└── architecture/
    └── architecture-taskflow.md
```

## Success Criteria

All tests pass when:

1. ✅ All 6 phases execute in correct order
2. ✅ All required gates pass with proper evidence
3. ✅ Role separation enforced (DEV ≠ QA for review/done)
4. ✅ Ledger accurately reflects SDLC position at each step
5. ✅ Audit trail contains complete decision history
6. ✅ Headless mode emits correct JSON structure
7. ✅ No guardrail violations occur
8. ✅ Final `close.mark_done` succeeds with all criteria met
9. ✅ Artifacts match expected structure and content
10. ✅ Resume from ledger works correctly in new session

## Extending the Test Suite

To add new test cases:

1. Add fixture to `test_fixtures/` if needed
2. Add case to `test_e2e_cases.json` with rubric
3. Add test function to `run_e2e_test.py`
4. Document in `test_e2e_usecase.md`

## References

- [BMAD-SDLC Skill Documentation](../.agents/skills/bmad-sdlc/SKILL.md)
- [Phase Map](../.agents/skills/bmad-sdlc/references/phase-map.md)
- [Gate Matrix](../.agents/skills/bmad-sdlc/references/gate-matrix.md)
- [Ledger Schema](../.agents/skills/bmad-sdlc/references/ledger-schema.md)
- [Headless Mode](../.agents/skills/bmad-sdlc/references/headless.md)
- [Role Config](../.agents/skills/bmad-sdlc/references/role-config.toml)