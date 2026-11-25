# bmad-sdlc Design Documents

## Architecture Decisions

### Decision 1: Conductor Pattern (2024-01-15)
**Status:** Accepted

We chose a conductor pattern where a single skill orchestrates the entire BMAD delivery lifecycle rather than having users manually invoke individual skills.

**Context:** Users needed to know which BMAD skills to invoke at each phase, track progress, and validate gates.

**Decision:** Create `bmad-sdlc` as a conductor skill that:
- Reads the ledger to determine current position
- Presents a two-level menu (phase → action)
- Routes to appropriate skills via subagents
- Validates artifacts and gates

**Consequences:**
- Users have a single entry point
- Progress persists across sessions
- Gate enforcement is automatic

---

### Decision 2: Ledger Schema (2024-01-20)
**Status:** Accepted

We chose YAML as the ledger format with a specific schema for workstreams, phases, gates, and decisions.

**Decision:** Ledger structure:
- `schema`: Version identifier (bmad-sdlc/1)
- `active_workstream`: Current ws-NNN
- `workstreams`: Map of ws IDs to their state
- Each workstream has phases, gates, tickets, and decisions

**Consequences:**
- Human-readable and git-friendly
- Supports branching and merging
- Easy to validate with Python scripts

---

## Build Plan

### Phase 1: Core Conductor (Completed)
- [x] Ledger schema definition
- [x] Summary command for current state
- [x] Phase mapping and role resolution
- [x] Gate matrix implementation

### Phase 2: Integration (Completed)
- [x] Skill detection and routing
- [x] Subagent handoff protocol
- [x] Artifact validation
- [x] Override reasoning requirements

### Phase 3: Edge Cases (Completed)
- [x] Track-based gate level adjustments
- [x] Size-based phase skipping
- [x] Multi-workstream support
- [x] Headless operation mode

## Gate Matrix

| Phase | Gate | Level | Owner |
|-------|------|-------|-------|
| plan | requirements | required | pm |
| plan | stories | required | pm |
| plan | sprint | required | pm |
| plan | ux | conditional | pm |
| plan | architecture | conditional | pm |
| build | ticket | required | dev |
| build | tests | conditional | dev |
| build | review | required | qa |
| build | done | required | qa |
| verify | trace | required | qa |
| verify | nfr | conditional | qa |
| verify | test_review | conditional | qa |
| close | retro | optional | qa |
| close | walkthrough | optional | qa |

## Track Overrides

### Feature Track
- Solution phase gates default to "overridden"
- Tests validated during verify.trace
- NFR testing deferred to production

### Fix Track
- Single ticket, trivial size
- Flow: build.ticket → build.review → build.done

### Audit Track
- Starts at verify.trace
- Skips planning phases

## Version Adapters

### v6 Model
- Uses `sprint-status.yaml` for stories/tickets
- Personas: PM/PO, DEV, QA
- Skills: bmad-create-epics-and-stories, bmad-sprint-planning, bmad-build

### Current Model
- Uses `tickets.toml` for stories/tickets
- Persona agents: bmad-agent-po, bmad-agent-pm, etc.
- Supports Sofia's workflow concepts

## Future Considerations

1. **Multi-project workspaces**: Support orchestrating multiple projects from a single ledger
2. **AI-assisted estimation**: Integrate cost tracking and estimate refinement
3. **Continuous delivery**: Auto-deploy when gates pass for greenfield projects