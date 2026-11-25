# BMAD-SDLC End-to-End Test Use Case

## Overview
This document describes a comprehensive end-to-end test use case for the `bmad-sdlc` skill, demonstrating the full Software Development Lifecycle from project initiation through delivery closure.

---

## Use Case: "TaskFlow" - A Task Management SaaS Application

### Project Description
**Product Name:** TaskFlow  
**Track:** `greenfield` (new product, no existing repo)  
**Size:** `epic` (multiple epics, several build sessions)  
**BMAD Model:** Current (Sofia/PO with tickets.toml)  

### User Story
> As a product team, we want to build a task management SaaS application called "TaskFlow" that allows teams to organize work into projects, create tasks with assignees and due dates, track progress with Kanban boards, and generate sprint reports.

---

## Phase 1: Project Initiation & Activation

### 1.1 Initial Command
```bash
# Start a new greenfield project
bmad-sdlc "Start a new SaaS product called TaskFlow for team task management. Track: greenfield. Size: epic. Work only in the project root."
```

### 1.2 Expected Activation Sequence (per SKILL.md §On Activation)

1. **Resolve customization** - Read `_bmad/custom/bmad-sdlc.toml` or fallback to `customize.toml`
2. **Run activation steps prepend** - Load persistent facts
3. **Load config** - Run `resolve_config.py` to get project details
4. **Read role selection** - No explicit role provided, will default to PM for plan phase
5. **Detect model** - Run `sdlc_plan.py detect --project-root .`
6. **Load/Create ledger** - Create new ledger at `_bmad-output/sdlc/plan.yaml`
7. **Reconcile** - Not applicable (new ledger)
8. **Run summary** - Get initial position
9. **Load references for current_role (PM)** - Load phase-map.md, gate-matrix.md, handoff-protocol.md + PM overlays
10. **Run activation steps append** - Render menu filtered to PM role

### 1.3 Expected Ledger State After Init
```yaml
schema: bmad-sdlc/1
project: TaskFlow
created: "2026-11-25T10:00:00+00:00"
updated: "2026-11-25T10:00:00+00:00"
bmad:
  model: current
  memlog: _bmad-output/sdlc/.memlog.md
  hub: bmad-help
  output_folder: _bmad-output
  planning_artifacts: _bmad-output/planning-artifacts
  implementation_artifacts: _bmad-output/implementation-artifacts
  test_artifacts: _bmad-output/test-artifacts
active_workstream: ws-001
workstreams:
  ws-001:
    name: TaskFlow
    track: greenfield
    size: epic
    status: active
    started: "2026-11-25T10:00:00+00:00"
    updated: "2026-11-25T10:00:00+00:00"
    current_phase: plan
    artifacts: {}
    phases:
      plan:
        status: active
        gate: required
        evidence: []
        note: ""
      solution:
        status: pending
        gate: conditional
        evidence: []
        note: ""
      build:
        status: pending
        gate: required
        evidence: []
        note: ""
      verify:
        status: pending
        gate: required
        evidence: []
        note: ""
      close:
        status: pending
        gate: optional
        evidence: []
        note: ""
    gates:
      plan:
        requirements: {status: open, level: required, decided_at: null, override_reason: null}
        stories: {status: open, level: required, decided_at: null, override_reason: null}
        sprint: {status: open, level: required, decided_at: null, override_reason: null}
        ux: {status: open, level: conditional, decided_at: null, override_reason: null}
        architecture: {status: open, level: conditional, decided_at: null, override_reason: null}
      solution:
        test_design: {status: open, level: conditional, decided_at: null, override_reason: null}
        framework: {status: open, level: conditional, decided_at: null, override_reason: null}
        ci: {status: open, level: conditional, decided_at: null, override_reason: null}
      verify:
        trace: {status: open, level: required, decided_at: null, override_reason: null}
        nfr: {status: open, level: conditional, decided_at: null, override_reason: null}
        test_review: {status: open, level: conditional, decided_at: null, override_reason: null}
      close:
        retro: {status: open, level: optional, decided_at: null, override_reason: null}
        walkthrough: {status: open, level: optional, decided_at: null, override_reason: null}
    tickets: {}
    decisions: []
    next:
      phase: plan
      action: frame.spec
      skill: bmad-spec
      reason: "Greenfield epic starts with requirements framing"
```

### 1.4 Expected Summary Output
- `current_role`: `pm` (phase owner for plan phase)
- `role_source`: `phase`
- `next_action`: `frame.spec` with `role: pm`, `role_allowed: true`
- `phase`: `plan`
- `status`: `ready` (skill installed, role matches)

---

## Phase 2: Plan Phase - Requirements & Framing

### 2.1 Action: `frame.spec` (or `plan.prd`)

**Command:**
```
Select action: frame.spec
```

**Handoff:** 
- Spawns subagent with `bmad-spec` skill
- Passes brief: "TaskFlow - team task management SaaS"
- Subagent produces `SPEC.md` in `_bmad-output/specs/spec-taskflow/`

### 2.2 Gate: `plan.requirements` (Required for epic/project)

**Evidence Required:**
- SPEC.md exists
- States why, what, constraints, non-goals, success signal
- Lists open questions

**Gate Decision:**
```
✓ Approve - SPEC.md is complete and clear
```

**Ledger Update:**
- `gates.plan.requirements.status` → `passed`
- `artifacts.spec` → `_bmad-output/specs/spec-taskflow/SPEC.md`
- `phases.plan.evidence` append artifact path
- Audit trail records gate passage

---

### 2.3 Action: `plan.prd`

**Command:**
```
Select action: plan.prd
```

**Handoff:**
- Spawns subagent with `bmad-agent-pm` (current model) or `bmad-prd` (v6)
- Passes SPEC.md as input
- Subagent produces PRD in `_bmad-output/planning-artifacts/prd-taskflow.md`

### 2.4 Gate: `plan.requirements` (Already passed, but PRD adds detail)

**Note:** `plan.requirements` is satisfied by either `frame.spec` OR `plan.prd` (phase-map.md §Plan phase notes)

---

### 2.5 Action: `plan.ux` (Conditional - UI is material)

**Command:**
```
Select action: plan.ux
```

**Handoff:**
- Spawns subagent with `bmad-ux` skill
- Produces `DESIGN.md` and `EXPERIENCE.md`

### 2.6 Gate: `plan.ux` (Conditional)

**Evidence Required:**
- Both DESIGN.md and EXPERIENCE.md exist
- Cover primary flows
- Design/experience agree

**Gate Decision:**
```
✓ Approve - UX documents complete
```

---

### 2.7 Action: `plan.architecture` (Conditional - 2+ units need shared decisions)

**Command:**
```
Select action: plan.architecture
```

**Handoff:**
- Spawns subagent with `bmad-architecture` skill
- Produces architecture decision records

### 2.8 Gate: `plan.architecture` (Conditional)

**Evidence Required:**
- architecture-*.md files exist
- Shared decisions recorded with trade-offs
- No unresolved contradictions

**Gate Decision:**
```
✓ Approve - Architecture decisions documented
```

---

### 2.9 Action: `plan.stories` (Required for epic/project)

**Command:**
```
Select action: plan.stories
```

**Handoff:**
- Spawns subagent with `bmad-agent-po` (current) or `bmad-create-epics-and-stories` (v6)
- Produces `tickets.toml` with epic → stories → tickets breakdown

**Expected Ticket Structure:**
```toml
# tickets.toml
[initiative.taskflow]
name = "TaskFlow MVP"
requirements = ["R1", "R2", "R3", "R4"]

[initiative.taskflow.epics.auth]
name = "Authentication & Authorization"
requirements = ["R1"]

[initiative.taskflow.epics.auth.tickets.t1]
title = "User registration with email verification"
deliverable = "Auth API + registration UI"
verification = "E2E test: register → verify email → login"
dependencies = []

[initiative.taskflow.epics.auth.tickets.t2]
title = "JWT-based login/logout"
deliverable = "Login API + session management"
verification = "Unit tests + E2E login flow"
dependencies = ["t1"]

[initiative.taskflow.epics.projects]
name = "Project & Task Management"
requirements = ["R2", "R3"]

[initiative.taskflow.epics.projects.tickets.t3]
title = "Create/List projects"
deliverable = "Project CRUD API + UI"
verification = "API tests + UI tests"
dependencies = []

[initiative.taskflow.epics.projects.tickets.t4]
title = "Kanban board with drag-drop"
deliverable = "Board UI + task move API"
verification = "E2E drag-drop test"
dependencies = ["t3"]

[initiative.taskflow.epics.reporting]
name = "Sprint Reporting"
requirements = ["R4"]

[initiative.taskflow.epics.reporting.tickets.t5]
title = "Sprint velocity report"
deliverable = "Report API + dashboard"
verification = "API tests + visual regression"
dependencies = ["t4"]
```

### 2.10 Gate: `plan.stories` (Required)

**Evidence Required:**
- tickets.toml exists
- Stories/tickets ordered with deliverables and verification
- Dependencies named

**Gate Decision:**
```
✓ Approve - Ticket breakdown complete
```

---

### 2.11 Action: `plan.sprint` (Required for v6 epic/project; optional for current)

**Command:**
```
Select action: plan.sprint
```

**Handoff:**
- Spawns subagent with `bmad-agent-po` or `bmad-sprint-planning`
- Produces `sprint-status.yaml` (v6) or updates `tickets.toml` with sprint assignments (current)

### 2.12 Gate: `plan.sprint` (Required for v6, optional for current)

**Gate Decision:**
```
✓ Approve - Sprint plan ready
```

---

### 2.13 Phase Complete: Plan → Solution

**Condition:** All required/conditional gates in plan phase are passed or overridden
- `plan.requirements`: passed ✓
- `plan.stories`: passed ✓
- `plan.sprint`: passed ✓
- `plan.ux`: passed ✓ (or skipped with reason)
- `plan.architecture`: passed ✓ (or skipped with reason)

**Action:** Set `phases.plan.status` = `done`, `phases.solution.status` = `active`

---

## Phase 3: Solution Phase - Test Strategy & Setup

### 3.1 Action: `solution.test_design` (Conditional - no test baseline, high risk)

**Command:**
```
Select action: solution.test_design
```

**Handoff:**
- Spawns subagent with `bmad-tea` (current) or `bmad-testarch-test-design` (v6)
- Produces test design document

### 3.2 Gate: `solution.test_design` (Conditional)

**Evidence Required:**
- Test design document exists
- Risks ranked
- Test levels and environments named
- Coverage targets exist

**Gate Decision:**
```
✓ Approve - Test design complete
```

---

### 3.3 Action: `solution.framework` (Conditional - no framework installed)

**Command:**
```
Select action: solution.framework
```

**Handoff:**
- Spawns subagent with `bmad-tea` or `bmad-testarch-framework`
- Scaffolds test framework (Playwright/Cypress)

### 3.4 Gate: `solution.framework` (Conditional)

**Evidence Required:**
- Framework scaffold exists
- Project can run framework's smoke test

**Gate Decision:**
```
✓ Approve - Test framework running
```

---

### 3.5 Action: `solution.ci` (Conditional - no CI quality pipeline)

**Command:**
```
Select action: solution.ci
```

**Handoff:**
- Spawns subagent with `bmad-tea` or `bmad-testarch-ci`
- Creates CI config with test execution

### 3.6 Gate: `solution.ci` (Conditional)

**Evidence Required:**
- CI config exists
- Tests run in CI
- Pipeline fails on test failure

**Gate Decision:**
```
✓ Approve - CI pipeline configured
```

---

### 3.7 Phase Complete: Solution → Build

**Condition:** All solution gates decided (passed/overridden/skipped)
- `solution.test_design`: passed ✓
- `solution.framework`: passed ✓
- `solution.ci`: passed ✓

**Action:** Set `phases.solution.status` = `done`, `phases.build.status` = `active`

---

## Phase 4: Build Phase - Implementation (Per Ticket)

### 4.1 Build Loop: Process Each Ticket

For each ticket in `tickets.toml` (in dependency order):

#### Ticket T1: User Registration

**4.1.1 Action: `build.atdd` (Optional - ATDD for high-risk tickets)**
```
Select action: build.atdd
```
- Spawns subagent with `bmad-tea` for acceptance test design
- Produces Given/When/Then acceptance criteria

**4.1.2 Action: `build.ticket` (Required per ticket)**
```
Select action: build.ticket
Ticket: t1 (User registration with email verification)
```
- Spawns subagent with `bmad-build` (DEV role)
- DEV implements the ticket
- Produces build plan with acceptance criteria
- Evidence: `_bmad-output/implementation-artifacts/story-t1-plan.md`

**4.1.3 Gate: `build.ticket` (Required per ticket)**
```
Evidence: Build plan with Given/When/Then ACs, named files, verification
Decision: ✓ Approve
```
- Records gate under `tickets.t1.gates.ticket`
- Actor: `dev` (builder)

**4.1.4 Action: `build.tests` (Conditional - project has tests)**
```
Select action: build.tests
Ticket: t1
```
- Runs project test runner
- New/changed tests pass
- No existing tests loosened

**4.1.5 Gate: `build.tests` (Conditional)**
```
Evidence: Test run output
Decision: ✓ Approve
```
- Actor: `dev`

**4.1.6 Action: `build.review` (Required per ticket - QA role)**
```
Select action: build.review
Ticket: t1
```
- **Role handoff:** DEV → QA (different roles!)
- Spawns subagent with `bmad-code-review` or `bmad-build` built-in review
- QA reviews the code

**4.1.7 Gate: `build.review` (Required per ticket)**
```
Evidence: Code review findings
Decision: ✓ Approve (findings triaged, in-scope fixed, deferred recorded)
```
- Actor: `qa` (reviewer - different from builder!)

**4.1.8 Action: `build.done` (Required per ticket after review - QA role)**
```
Select action: build.done
Ticket: t1
```
- QA approves done transition
- Evidence recorded

**4.1.9 Gate: `build.done` (Required per ticket)**
```
Evidence: Ticket evidence recorded, human approved done transition
Decision: ✓ Approve
```
- Actor: `qa` (approver - different from builder AND reviewer!)
- Ticket status in BMAD artifacts updated to `done`

---

### Repeat for Tickets T2, T3, T4, T5...

**Key Guardrails Enforced:**
- ✅ No self-approval: DEV builds, QA reviews, QA approves done
- ✅ Per-ticket gates recorded with actors
- ✅ Each ticket has build plan with ACs
- ✅ Tests pass before review
- ✅ Review findings triaged before done

---

### 4.2 Phase Complete: Build → Verify

**Condition:** All tickets have `build.done` = passed
- All tickets built, tested, reviewed, and approved

**Action:** Set `phases.build.status` = `done`, `phases.verify.status` = `active`

---

## Phase 5: Verify Phase - Quality Gates

### 5.1 Action: `verify.e2e` (Optional - generate E2E tests)
```
Select action: verify.e2e
```
- Spawns subagent with `bmad-qa-generate-e2e-tests`
- Generates automated API and E2E tests for implemented features

### 5.2 Action: `verify.automate` (Optional - expand test automation)
```
Select action: verify.automate
```
- Spawns subagent with `bmad-tea` 
- Expands test automation coverage

### 5.3 Action: `verify.test_review` (Conditional - test quality in doubt)
```
Select action: verify.test_review
```
- Spawns subagent with `bmad-tea` or `bmad-testarch-test-review`
- Reviews test quality (coverage, isolation, determinism)

### 5.4 Gate: `verify.test_review` (Conditional)
```
Evidence: Test review report
Decision: ✓ Approve
```

### 5.5 Action: `verify.nfr` (Conditional - perf/security/reliability requirements exist)
```
Select action: verify.nfr
```
- Spawns subagent with `bmad-tea` or `bmad-testarch-nfr`
- Audits NFR evidence

### 5.6 Gate: `verify.nfr` (Conditional)
```
Evidence: NFR evidence (performance benchmarks, security scan, reliability tests)
Decision: ✓ Approve
```

### 5.7 Action: `verify.trace` (Required for epic/project - THE quality gate)
```
Select action: verify.trace
```
- Spawns subagent with `bmad-tea` or `bmad-testarch-trace`
- Generates traceability matrix
- Maps every requirement/ticket to tests
- Produces gate decision

### 5.8 Gate: `verify.trace` (Required for epic/project)
```
Evidence: Traceability matrix + gate decision
Criteria: Every requirement/ticket maps to test or explicit gap; gate PASS or CONCERNS with named gaps
Decision: ✓ Approve (PASS - all requirements traced)
```

---

### 5.9 Phase Complete: Verify → Close

**Condition:** All verify gates decided
- `verify.trace`: passed ✓ (REQUIRED)
- `verify.nfr`: passed ✓ (or skipped with reason)
- `verify.test_review`: passed ✓ (or skipped with reason)

**Action:** Set `phases.verify.status` = `done`, `phases.close.status` = `active`

---

## Phase 6: Close Phase - Delivery Closure

### 6.1 Action: `close.walkthrough` (Optional - human review)
```
Select action: close.walkthrough
```
- Spawns subagent with `bmad-walkthrough`
- Human reviews: purpose, hot spots, how to test

### 6.2 Gate: `close.walkthrough` (Optional)
```
Evidence: Walkthrough completed
Decision: ✓ Approve
```

### 6.3 Action: `close.retro` (Optional - recommended per epic)
```
Select action: close.retro
```
- Spawns subagent with `bmad-retrospective`
- Reviews epic against evidence (spec, stories, diffs, commits, sprint status)
- Produces retrospective with findings, action items, acceptance verdict

### 6.4 Gate: `close.retro` (Optional)
```
Evidence: Retro document + verdict
Criteria: Findings cite evidence; action items have owners; verdict accept/reject
Decision: ✓ Approve (Accept)
```

### 6.5 Action: `close.mark_done` (Role-free - any role can run)
```
Select action: close.mark_done
```
- Runs `sdlc_plan.py done` 
- Validates all close criteria (gate-matrix.md §Phase completion)
- Closes workstream

**Close Validation Checks:**
- ✅ No required/conditional gate open
- ✅ No gate at any level blocked
- ✅ Every passed required/conditional gate has resolving artifact pointer
- ✅ Overridden gates have reasons recorded
- ✅ UX has both DESIGN.md and EXPERIENCE.md
- ✅ Build phase: all tickets have approved build.done gates

### 6.6 Workstream Complete

**Final Ledger State:**
```yaml
workstreams:
  ws-001:
    status: done
    current_phase: close
    phases:
      plan: {status: done, ...}
      solution: {status: done, ...}
      build: {status: done, ...}
      verify: {status: done, ...}
      close: {status: done, ...}
    decisions:
      - {at: "...", decision: "Closed workstream", reason: "All gates passed, trace PASS, retro accept"}
```

---

## Headless Mode Test Scenario

### Automated CI/CD Integration

```bash
# Run in headless mode for CI
bmad-sdlc --headless "Continue TaskFlow. Work only in project root."
```

### Expected Headless Output (per headless.md §Emitted block)

```json
{
  "status": "ready",
  "model": "current",
  "track": "greenfield",
  "size": "epic",
  "current_role": "dev",
  "role_source": "phase",
  "project": "TaskFlow",
  "ledger": "_bmad-output/sdlc/plan.yaml",
  "memlog": "_bmad-output/sdlc/.memlog.md",
  "active_workstream": "ws-001",
  "workstream": { ... },
  "workstreams": ["ws-001"],
  "phase": "build",
  "next_phase": "verify",
  "next_action": {
    "phase": "build",
    "gate": "build.ticket",
    "action": "build.ticket",
    "skill": "bmad-build",
    "skill_installed": true,
    "ticket": "t3",
    "role": "dev",
    "role_free": false,
    "role_allowed": true,
    "reason": "Next ready ticket: Create/List projects",
    "source": "computed"
  },
  "optional_actions": [],
  "open_gates": [
    "build.ticket",
    "build.tests",
    "build.review",
    "build.done"
  ],
  "blocked_gates": [],
  "locked_phases": [],
  "phases": [
    {"phase": "plan", "status": "done", "role": "pm", "blocking": [], "open_gates": [], "complete": true},
    {"phase": "solution", "status": "done", "role": "qa", "blocking": [], "open_gates": [], "complete": true},
    {"phase": "build", "status": "active", "role": "dev", "blocking": [], "open_gates": ["build.ticket", "build.tests", "build.review", "build.done"], "complete": false},
    {"phase": "verify", "status": "pending", "role": "qa", "blocking": [], "open_gates": [], "complete": false},
    {"phase": "close", "status": "pending", "role": "qa", "blocking": [], "open_gates": [], "complete": false}
  ],
  "workstreams_detail": [...],
  "decisions": [...],
  "cached_next_action": {...},
  "next_action_stale": false,
  "assumptions": ["BMAD current model detected", "bmad-build installed", "Tickets t1,t2 done"]
}
```

---

## Role-Based Access Test Scenarios

### Scenario 1: QA Tries to Run DEV Action (Should Block)
```bash
bmad-sdlc --role qa "Continue TaskFlow"
```
**Expected:** `status: blocked`, `blocked_by: ["build.ticket"]`, `next_action.role_allowed: false`

### Scenario 2: PM Runs Plan Action (Should Allow)
```bash
bmad-sdlc --role pm "Continue TaskFlow"
```
**Expected:** `status: ready`, `next_action.role_allowed: true` for plan actions

### Scenario 3: Explicit Role Override with Handoff
```
Current role: dev
User: "role qa Taking over for review"
```
**Expected:** Ledger records `role_override: qa` with reason, audit trail logs handoff

---

## Error Handling Test Scenarios

### Scenario 1: Missing Skill
- If `bmad-build` not installed
- `status: blocked`
- `blocked_by: ["build.ticket"]`
- Clear install guidance provided

### Scenario 2: Corrupt Ledger
- Manual edit breaks ledger structure
- `validate` fails
- `migrate` attempts repair
- If unrecoverable: `status: blocked`, `blocked_by: ["ledger.corrupt"]`

### Scenario 3: Gate Override Without Reason
- User tries to override required gate without `--reason`
- Script rejects with error
- Audit trail not polluted

### Scenario 4: Self-Approval Attempt
- DEV tries to approve `build.review` for their own ticket
- Script refuses, records actor mismatch
- Requires QA role for review/done gates

---

## Verification Checklist

### Functional Requirements ✅
- [ ] Project initiation creates ledger with correct track/size/model
- [ ] Plan phase actions route to correct skills (PM role)
- [ ] Gates enforce evidence requirements before passage
- [ ] Solution phase sets up test strategy (QA role)
- [ ] Build phase processes tickets one at a time (DEV role)
- [ ] Per-ticket gates: ticket → tests → review → done
- [ ] Role separation: DEV builds, QA reviews, QA approves done
- [ ] Verify phase runs traceability as quality gate (QA role)
- [ ] Close phase validates all criteria before marking done
- [ ] Ledger persists across sessions
- [ ] Audit trail records all decisions and gate outcomes

### Guardrails ✅
- [ ] Ask at every gate (four-way choice)
- [ ] One role at a time (role filtering works)
- [ ] No self-approval (builder ≠ reviewer ≠ approver)
- [ ] Never mark done without approved build.done gate
- [ ] Phase advances follow gate-matrix rules
- [ ] No gate from unvalidated ledger
- [ ] Consent before irreversible actions
- [ ] No silent success (missing artifacts reported)
- [ ] No scope invention (only scheduled work)
- [ ] Ledger stays portable (relative paths)

### Headless Mode ✅
- [ ] Emits correct JSON block with exact key set
- [ ] Stops at next gate (never auto-approves)
- [ ] Reports blocked status with blocked_by array
- [ ] Scratch files stay in .tmp/ beside ledger
- [ ] Audit trail records blocked events

### Role Management ✅
- [ ] PM owns frame.*, plan.* actions
- [ ] DEV owns build.* actions (except review/done)
- [ ] QA owns build.review, build.done, solution.*, verify.*, close.*
- [ ] Audit track belongs entirely to QA
- [ ] Role override persists with logged reason
- [ ] close.mark_done and phase.unblock are role-free

---

## Running the Test

### Manual Interactive Test
```bash
cd /path/to/test/project
bmad-sdlc "Start a new SaaS product called TaskFlow for team task management. Track: greenfield. Size: epic."
# Follow menu prompts through all phases
```

### Headless Automated Test
```bash
cd /path/to/test/project
XDG_DATA_HOME="$HOME/.local/share" XDG_CONFIG_HOME="$HOME/.config" \
  uv run --no-cache .agents/skills/bmad-eval-runner/scripts/run_evals.py \
  --cases test_e2e_cases.json \
  --skill-path .agents/skills/bmad-sdlc \
  --output-dir ~/bmad-evals/test-e2e \
  --mode quality
```

### Unit Test Suite
```bash
uv run --no-cache python -m unittest discover \
  -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'
```

---

## Expected Artifacts at Completion

```
_bmad-output/
├── sdlc/
│   ├── plan.yaml          # Final ledger (committed)
│   └── .memlog.md         # Audit trail (committed)
├── planning-artifacts/
│   ├── prd-taskflow.md
│   ├── tickets.toml
│   └── sprint-status.yaml (v6 only)
├── specs/
│   └── spec-taskflow/
│       └── SPEC.md
├── implementation-artifacts/
│   ├── story-t1-plan.md
│   ├── story-t2-plan.md
│   └── ...
├── test-artifacts/
│   ├── test-design.md
│   ├── test-framework/ (Playwright/Cypress)
│   ├── ci-config.yml
│   ├── traceability-matrix.md
│   └── nfr-evidence.md
├── ux/
│   ├── DESIGN.md
│   └── EXPERIENCE.md
└── architecture/
    └── architecture-*.md
```

---

## Success Criteria

The end-to-end test **PASSES** if:

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

---

*This use case validates the complete BMAD-SDLC conductor workflow from greenfield project initiation through delivery closure, exercising all roles, gates, phases, and guardrails.*