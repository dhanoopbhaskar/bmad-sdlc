# Ledger Schema

The ledger is the conductor's durable memory. It lives at `{workflow.ledger_path}` (default `{project-root}/_bmad-output/sdlc/plan.yaml`) and is committed to git. The append-only audit trail is `{workflow.memlog_path}` (default `{project-root}/_bmad-output/sdlc/.memlog.md`). Both paths are customizable. Pass `--plan` to every call; `init` records the audit path in `bmad.memlog`, and `--memlog` overrides it.

**Ownership:** BMAD artifacts are the source of truth for ticket/story status. The ledger stores only the SDLC overlay: position, gate outcomes, decisions, and pointers. Never copy ticket statuses into the ledger; read them from `sprint-status.yaml` (v6) or `tickets.toml` / build plans (current).

An audit workstream has one synthetic ticket, `audit`. Its `review` gate is required; `ticket`, `tests`, and `done` are `skipped` because an audit reviews existing work rather than building a ticket.

## Shape

```yaml
schema: bmad-sdlc/1
project: bmad-sdlc
created: 2026-11-12T16:00:00+05:30
updated: 2026-11-12T16:42:00+05:30

bmad:
  model: v6                         # v6 | current | unknown
  memlog: _bmad-output/sdlc/.memlog.md
  hub: bmad-help                    # bmad | bmad-help | null
  output_folder: _bmad-output
  planning_artifacts: _bmad-output/planning-artifacts
  implementation_artifacts: _bmad-output/implementation-artifacts
  test_artifacts: _bmad-output/test-artifacts

active_workstream: ws-001

workstreams:
  ws-001:
    name: bmad-sdlc
    track: feature                  # greenfield | feature | fix | audit
    size: epic                      # trivial | one-session | epic | project
    status: active                  # active | paused | done
    started: 2026-11-12T16:00:00+05:30
    updated: 2026-11-12T16:42:00+05:30
    current_phase: plan             # plan | solution | build | verify | close

    artifacts:                      # pointers only; null means not produced yet
      spec: _bmad-output/specs/spec-bmad-sdlc/SPEC.md
      prd: null
      ux: null
      architecture: null
      stories: null
      tickets: null
      sprint_plan: null
      test_design: null
      test_framework: null
      ci: null
      trace: null

    phases:
      plan:
        status: active              # pending | active | done | skipped | blocked
        gate: required              # required | conditional | optional
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

    gates:                          # nested by phase; ids are phase + "." + name
      plan:
        requirements:
          status: passed            # open | passed | overridden | skipped
          level: required           # required | conditional | optional
          decided_at: 2026-11-12T16:10:00+05:30
          override_reason: null
        stories:
          status: open
          level: required
          decided_at: null
          override_reason: null
        sprint:
          status: open
          level: required
          decided_at: null
          override_reason: null
        ux:
          status: skipped
          level: conditional
          decided_at: 2026-11-12T16:12:00+05:30
          override_reason: null
        architecture:
          status: open
          level: conditional
          decided_at: null
          override_reason: null
      solution:
        test_design: {status: open, level: conditional, decided_at: null, override_reason: null}
        framework: {status: open, level: conditional, decided_at: null, override_reason: null}
        ci: {status: open, level: conditional, decided_at: null, override_reason: null}
      build: {}                    # per-ticket gates live under tickets, not here
      verify:
        trace: {status: open, level: required, decided_at: null, override_reason: null}
        nfr: {status: open, level: conditional, decided_at: null, override_reason: null}
        test_review: {status: open, level: conditional, decided_at: null, override_reason: null}
      close:
        retro: {status: open, level: optional, decided_at: null, override_reason: null}
        walkthrough: {status: open, level: optional, decided_at: null, override_reason: null}

    tickets:
      "1-3-ticket-menu":
        title: "Ticket menu"
        gates:
          ticket: {status: passed, decided_at: 2026-11-12T16:30:00+05:30, override_reason: null}
          tests: {status: passed, decided_at: 2026-11-12T16:40:00+05:30, override_reason: null}
          review: {status: open, decided_at: null, override_reason: null}
          done: {status: open, decided_at: null, override_reason: null}

    decisions:
      - at: 2026-11-12T16:12:00+05:30
        decision: "Skipped UX; this is a CLI-only tool."
        reason: "No user-facing UI."

    next:                           # optional cache
      phase: plan
      action: plan.stories
      skill: bmad-create-epics-and-stories
      reason: "Requirements passed; stories are the next required gate."
```

## Field rules

| Field | Rule |
|---|---|
| `schema` | Must be `bmad-sdlc/1`. |
| `project` | Non-empty string. Defaults to the repo/folder name. |
| `bmad.model` | `v6`, `current`, or `unknown`. Written by `detect`. Do not guess after detection. |
| `artifacts.*` | Absolute path, `{project-root}`-relative path, or null. Pointers, not content. |
| `phases.*.status` | One of `pending`, `active`, `done`, `skipped`, `blocked`. Only one phase is `active` at a time. A `done`/`skipped` status is a cache: `summary` and `done` still report any open required/conditional gate in that phase. |
| `phases.*.note` | Free text. A phase skipped with a required gate records the reason here. |
| `gates.<phase>.<name>.status` | One of `open`, `passed`, `overridden`, `skipped`, `blocked`. `blocked` means the evidence pointer is missing; it is not a pass. |
| `gates.<phase>.<name>.level` | `required`, `conditional`, or `optional`. **Derived** from track/size/model; the stored value is a cache. `summary`/`done` always use the resolver, and `validate` reports drift. `resize` or `migrate` rewrites it. |
| `tickets.<id>.gates.<gate>.status` | One of `open`, `passed`, `overridden`, `skipped`, `blocked`. Gates are `ticket`, `tests`, `review`, `done`. |
| `override_reason` | Required when a required or conditional gate is `overridden` or `skipped`; `set`, `ticket`, and `validate` all enforce it as an error. Not required for `blocked` (the missing pointer is the reason) or for an optional gate. The authoritative rule is `gate-matrix.md` §Override rules. A decided gate's reason and `decided_at` cannot be cleared while the gate is decided. |
| `decisions` | Append-only list of `{at, decision, reason}`. `set` refuses to write it; use `append`, which fills `at` when missing. Never edit or delete. |
| `next` | Written by mutating commands after they refresh the workstream. `summary` recomputes and reports `next_action_stale` only when a hand edit disagrees. |

## Script operations

Every operation prints JSON. Mutating operations are atomic and take a file lock around the read-modify-write cycle; reads do not write. Run with `uv run --no-cache`.

`summary` reports gate levels, `blocking` ids, per-phase `complete`, ticket gates, `blocked_gates`, `optional_actions`, `locked_phases`, `memlog`, `phase`, `workstreams_detail`, and the recomputed `next_action`. It always returns the full shape, including when `active_workstream` is null; a closed workstream still supplies the last recorded `track`, `size`, and `phase`. A phase is `complete` only after every earlier phase is complete, so `close` cannot look done at activation. Use `done` to close a workstream; it refuses while any required or conditional gate is open or blocked, including per-ticket gates and a missing audit review, and it refuses a missing artifact, a decided gate with no artifact or phase evidence, a blocked phase, or a ledger ticket absent from the BMAD artifacts unless the user accepts the gap with `--reason`. An audit's synthetic `audit` ticket is exempt from the ticket-overlay check. An audit's required code review is the `review` gate on that ticket.

| `summary` field | Meaning |
|---|---|
| `phase`, `next_phase` | The recommended phase; equals `next_action.phase` when there is one. |
| `next_action` | `{phase, gate, action, skill, ticket?, reason, source}` or null when paused/done. |
| `optional_actions` | Open optional actions the user may take now. |
| `open_gates`, `blocked_gates` | Every open/blocked gate, including gates in a phase marked `done`/`skipped`. |
| `required_open`, `conditional_open`, `optional_open` | The same gates split by resolved level. |
| `locked_phases` | Phases not yet reachable, with the first missing gate. |
| `phases[].complete` | True only when the phase has no blocking gate. |
| `tickets` | Per-ticket gate state (`count`, `open`, `blocked`, `required_open`, `conditional_open`, `items`). |
| `workstreams_detail` | `{id, name, track, size, status, current_phase, next_action}` for every workstream. |
| `memlog` | Resolved audit-trail path. |

```bash
# Detect the installed model and skills
uv run --no-cache {skill-root}/scripts/sdlc_plan.py detect --project-root {project-root}

# Create the ledger (first run only). Always pass the resolved paths.
# A relative --template resolves against {project-root} first, then the skill
# root; an absolute path avoids the ambiguity.
uv run --no-cache {skill-root}/scripts/sdlc_plan.py init \
  --project-root {project-root} \
  --plan {workflow.ledger_path} --memlog {workflow.memlog_path} \
  --template {workflow.ledger_template} \
  --name "My Product" --track greenfield --size project --model v6

# Read the position (computed next action, gate levels, locks, ticket gates)
uv run --no-cache {skill-root}/scripts/sdlc_plan.py summary \
  --plan {workflow.ledger_path}

# Set a value (examples). Omitting --workstream targets the active one.
uv run --no-cache {skill-root}/scripts/sdlc_plan.py set --plan <ledger> \
  --workstream ws-001 --path phases.plan.status --value done   # only when complete
uv run --no-cache {skill-root}/scripts/sdlc_plan.py set --plan <ledger> \
  --workstream ws-001 --path gates.plan.requirements.status --value passed \
  --memlog {workflow.memlog_path}
uv run --no-cache {skill-root}/scripts/sdlc_plan.py set --plan <ledger> \
  --workstream ws-001 --path gates.plan.requirements.status --value overridden \
  --reason "design doc accepted" --memlog {workflow.memlog_path}
uv run --no-cache {skill-root}/scripts/sdlc_plan.py set --plan <ledger> \
  --workstream ws-001 --path artifacts.prd --value _bmad-output/prd-checkout/prd-checkout.md
uv run --no-cache {skill-root}/scripts/sdlc_plan.py set --plan <ledger> \
  --workstream ws-001 --path tickets --null --replace --reason "reset ticket map"

# set rejects derived state (phases.<phase>.gate, gates.*.level) and whole-node
# writes without --replace --reason. --root is for document paths only;
# --workstream is for workstream fields. --reason is only for an override or skip.
# A decided gate's override_reason and decided_at cannot be cleared, a blocked
# gate cannot be set passed, and only one phase may be active at a time.
# Pausing clears active_workstream; resume with --workstream <id> --path status
# --value active so a new session has an unambiguous target.

# Resize (recomputes every level and phase gate)
uv run --no-cache {skill-root}/scripts/sdlc_plan.py resize --plan <ledger> \
  --workstream ws-001 --size one-session --memlog {workflow.memlog_path}

# Append evidence or a decision (decisions are append-only)
uv run --no-cache {skill-root}/scripts/sdlc_plan.py append --plan <ledger> \
  --workstream ws-001 --path phases.plan.evidence --value <path>
uv run --no-cache {skill-root}/scripts/sdlc_plan.py append --plan <ledger> \
  --workstream ws-001 --path decisions --value '{"decision":"...","reason":"..."}'

# Record a per-ticket gate (use this for ids containing dots)
uv run --no-cache {skill-root}/scripts/sdlc_plan.py ticket --plan <ledger> \
  --workstream ws-001 --id "1.3" --gate review --status passed
uv run --no-cache {skill-root}/scripts/sdlc_plan.py ticket --plan <ledger> \
  --workstream ws-001 --id "1.3" --gate review --status overridden \
  --reason "accepted risk"

# Close the workstream once every required/conditional gate is decided.
# done also re-checks artifact/phase evidence and the ticket overlay; if a gap
# is intentional, add --accept-missing-evidence or --accept-missing-tickets
# together with --reason.
uv run --no-cache {skill-root}/scripts/sdlc_plan.py done --plan <ledger> \
  --workstream ws-001 --memlog {workflow.memlog_path}

# Materialize gate levels and a tickets map on an older ledger
uv run --no-cache {skill-root}/scripts/sdlc_plan.py migrate --plan <ledger>

# Reconcile pointers and phase evidence (read-only by default)
uv run --no-cache {skill-root}/scripts/sdlc_plan.py reconcile \
  --plan <ledger> --project-root {project-root}

# Apply orphan artifact pointers and log each correction
uv run --no-cache {skill-root}/scripts/sdlc_plan.py reconcile \
  --plan <ledger> --project-root {project-root} --write \
  --memlog {workflow.memlog_path}

# Validate a handoff return. A done return needs an artifact; a supplied
# evidence list must be non-empty and resolve inside the project root. Open
# questions block unless --accept-questions is passed, which logs the accepted
# questions to the audit trail.
uv run --no-cache {skill-root}/scripts/sdlc_plan.py verify-return \
  --plan <ledger> --memlog {workflow.memlog_path} \
  --project-root {project-root} --return-file <json>

# Audit trail
uv run --no-cache {skill-root}/scripts/sdlc_plan.py log --plan <ledger> \
  --memlog {workflow.memlog_path} --type event --text "plan.requirements passed"

# Validate
uv run --no-cache {skill-root}/scripts/sdlc_plan.py validate --plan <ledger>
```

`set` parses `--value` as JSON when possible, otherwise as a string. Use `--null` to set null. Omitting `--workstream` targets the active workstream for workstream-shaped paths; document paths (`schema`, `bmad.*`, `active_workstream`, `workstreams.*`) stay at the root. Replacing a whole map (`tickets`, `gates.<phase>`, `phases`, `artifacts`, a ticket gate node) needs `--replace --reason`. `decisions` and `phases.*.evidence` are append-only through `append`.

If `uv` is unavailable, read and write the YAML directly with the same shape, keep the writes atomic, and take a sibling `.lock` file around the read-modify-write. The script is a convenience, not a hard dependency.

## Resume semantics

The ordered activation sequence is in `SKILL.md` §On Activation; it runs `detect`, `reconcile`, `summary`, then the menu. The ledger-only deltas are:

- **Model change.** Use `set --path bmad.model --value <model>` on an existing ledger (pass `--model` to `init` only when creating it). A silent `unknown` must not overwrite a confirmed model, and `init --model unknown` refuses a downgrade without `--force --reason`.
- **Pointer cases.** Artifact exists, pointer missing → `reconcile --write`. Pointer set, artifact missing → set the affected gate(s) from `gates_to_block` to `blocked` and report the expected path. Phase evidence missing → set the phase(s) in `phases_to_block` to `blocked`. Ticket status disagrees → artifacts win; update the ledger and log the correction. Never substitute a path outside `{project-root}`.
- **Corruption.** Run `validate`. If unrepairable, back up to `plan.yaml.bak`, re-run `init --force --reason`, and offer to re-import pointers from the artifacts. Never silently discard the old file.

## Multiple workstreams

- One `active_workstream` at a time. `init` appends a workstream and pauses the previously active one; `--force` recreates the ledger only with `--reason`, after writing `plan.yaml.bak` and a reset event.
- Switch with `set --path active_workstream --value ws-002` (no `--workstream`); the target becomes active and the previous active workstream is paused.
- The status dashboard lists every workstream with track, size, status, and next action.
- `validate` rejects more than one `status: active` workstream and an `active_workstream` that is not active.
- A paused workstream has no `next_action`; resume it before continuing or closing.
- A workstream is `done` when every required and conditional gate is decided (passed, overridden, or skipped with a reason), every decided gate has artifact or phase evidence, and no epic remains open; use `done`, not a manual status edit. Do not delete it; it is the history.
