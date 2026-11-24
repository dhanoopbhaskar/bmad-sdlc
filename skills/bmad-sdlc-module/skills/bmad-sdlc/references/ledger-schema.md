# Ledger Schema

The ledger is the conductor's durable memory. It lives at `{workflow.ledger_path}` (default `{project-root}/_bmad-output/sdlc/plan.yaml`) and is committed to git. The append-only audit trail is `{workflow.memlog_path}` (default `{project-root}/_bmad-output/sdlc/.memlog.md`). Both paths are customizable. Pass `--plan` to every command that reads or writes the ledger; `detect` takes only `--project-root`. `init` records the audit path in `bmad.memlog`, and `--memlog` overrides it.

**Ownership:** BMAD artifacts are the source of truth for ticket/story status. The ledger stores only the SDLC overlay: position, gate outcomes, decisions, and pointers. Never copy ticket statuses into the ledger; read them from `sprint-status.yaml` (v6) or `tickets.toml` / build plans (current).

An audit workstream has one synthetic ticket, `audit`. Its `review` gate is required; `ticket`, `tests`, and `done` are `skipped` because an audit reviews existing work rather than building a ticket.

## Contents

- [Shape](#shape)
- [Field rules](#field-rules)
- [Script operations](#script-operations)
- [Resume semantics](#resume-semantics)
- [Multiple workstreams](#multiple-workstreams)

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
          status: passed            # open | passed | overridden | skipped | blocked
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
          ticket: {status: passed, decided_at: 2026-11-12T16:30:00+05:30, override_reason: null, evidence: _bmad-output/implementation-artifacts/story-1-3-plan.md}
          tests: {status: passed, decided_at: 2026-11-12T16:40:00+05:30, override_reason: null, evidence: _bmad-output/test-artifacts/test-run-1-3.txt}
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
| `bmad.model` | `v6`, `current`, or `unknown`. Recorded by `init` from detection; changed with `set`. Do not guess after detection. |
| `artifacts.*` | Absolute path, `{project-root}`-relative path, or null. Pointers, not content. |
| `phases.*.status` | One of `pending`, `active`, `done`, `skipped`, `blocked`. Only one phase is `active` at a time. A `done`/`skipped` status is a cache — see `gate-matrix.md` §Phase completion. Reopening needs `--reason`. |
| `phases.*.note` | Free text. When a phase with a required gate is skipped, its reason goes here. |
| `workstreams.<id>.track` | `greenfield`, `feature`, `fix`, or `audit`. Change with `resize`; `set` rejects it. |
| `workstreams.<id>.size` | `trivial`, `one-session`, `epic`, or `project`. Change with `resize`; `set` rejects it. |
| `workstreams.<id>.status` | `active`, `paused`, or `done`. Resume with `set --workstream <id> --path status --value active` (with `--reason` when reopening a done workstream); close with `done`, never `set`. |
| `workstreams.<id>.current_phase` | Derived position, refreshed by mutating commands. |
| `gates.<phase>.<name>.status` | One of `open`, `passed`, `overridden`, `skipped`, `blocked`. `blocked` means the evidence pointer is missing; it is not a pass. |
| `gates.<phase>.<name>.level` | `required`, `conditional`, or `optional`. **Derived** from track/size/model; the stored value is a cache — `summary` wins (`SKILL.md` §References). `validate` reports drift; `resize` or `migrate` rewrites it. |
| `tickets.<id>.gates.<gate>.status` | One of `open`, `passed`, `overridden`, `skipped`, `blocked`. Gates are `ticket`, `tests`, `review`, `done`. |
| `tickets.<id>.gates.<gate>.evidence` | Optional pointer to the artifact that decided a ticket gate (relative or absolute, inside the project root). `ticket --evidence <path>` writes it; the `done` command resolves it and requires one for an overridden gate. |
| `override_reason` | Required when a required or conditional gate is `overridden` or `skipped`; `set`, `ticket`, and `validate` enforce it as an error. See `gate-matrix.md` §Override rules and §Reopening. |
| `decisions` | Append-only list of `{at, decision, reason}`. `set` refuses to write it; use `append`, which fills `at` when missing. Never edit or delete. |
| `next` | Written by mutating commands after they refresh the workstream. `summary` recomputes and reports `next_action_stale` when a hand edit disagrees on phase, gate, action, or ticket. |

## Script operations

Every operation prints JSON. Mutating operations are atomic and take a file lock around the read-modify-write cycle; reads do not write. Run with `uv run --no-cache`. Exit 0 means `ok: true`; exit 1 means `ok: false` (or a hard error), so `validate && …` and CI checks can use the status.

### Summary shape

`summary` always returns the full shape, including when `active_workstream` is null; a closed workstream still supplies the last recorded `track`, `size`, and `phase`. Phase completion is defined once in `gate-matrix.md` §Phase completion. Use `done` to close; that section lists the refusals and accept flags.

| `summary` field | Meaning |
|---|---|
| `phase`, `next_phase` | The recommended phase; equals `next_action.phase` when there is one. |
| `next_action` | `{phase, gate, action, skill, skill_installed?, skill_manifest_only?, ticket?, role, role_allowed, reason, source}` or null when paused/done. `role` is the action's owner from `role-config.toml`; `role_allowed` is false when it differs from `current_role`. `skill_installed` appears only when `summary` is given `--project-root`. When the first-choice skill is absent, `skill` is rewritten to the first installed alternative and `skill_installed` reports whether that one is installed. `skill_manifest_only` is true when the manifest names the chosen skill but no readable `SKILL.md` exists under a skill directory — warn and offer a repair, since the handoff may fail. |
| `current_role`, `role_source` | The active role and why it was chosen: `explicit` (`--role`), `track`, `phase`, or `default`. |
| `optional_actions` | Open optional actions the user may take now; each carries `role` and `role_allowed`. |
| `open_gates`, `blocked_gates` | Every live open/blocked gate, per-ticket gates included. A phase marked `done`/`skipped` contributes only the gates that contradict its status; `phases[].open_gates` lists every open gate in that phase, whether or not the phase is `done`/`skipped`. |
| `required_open`, `conditional_open`, `optional_open` | Lists of gate ids, split by resolved level. A blocked required or conditional gate appears in both its level list and `blocked_gates`; a blocked optional gate appears only in `blocked_gates` but still blocks its phase. Each phase carries the same three lists, scoped to its own gates. |
| `phases[].blocking` | Gate ids that make the phase incomplete. |
| `locked_phases` | Phases not yet reachable, with the first missing gate. |
| `phases[].complete` | True when `gate-matrix.md` §Phase completion says the phase is complete. |
| `tickets` | Per-ticket gate state (`count`, `open`, `blocked`, `required_open`, `conditional_open`, `items`). |
| `workstreams_detail` | `{id, name, track, size, status, current_phase, next_action}` for every workstream. |
| `ok` | True on success; a failed command exits non-zero with `ok: false` and `error`. |
| `ledger`, `memlog` | Resolved ledger and audit-trail paths. |
| `project`, `model` | Project name and recorded BMAD model. |
| `workstream`, `workstreams`, `active_workstream` | The active workstream record, the id list, and the active id (all null when none is open). |
| `decisions` | The active workstream's append-only decision list. |
| `cached_next_action`, `next_action_stale` | The ledger's stored `next` block, and whether it disagrees with the recomputed `next_action`. |

### Commands

`detect`, `init`, and `summary` run in `SKILL.md` §On Activation. Every command below takes `--plan`; mutating commands also take `--project-root` and `--memlog`.

```bash
# set: omit --workstream to target the active one
... set --plan <ledger> --path gates.plan.requirements.status --value passed
... set --plan <ledger> --path gates.plan.requirements.status --value overridden --reason "accepted"
... set --plan <ledger> --path artifacts.prd --value _bmad-output/prd-checkout/prd-checkout.md
... set --plan <ledger> --path "tickets.1-3-ticket-menu" --delete --reason "withdrawn"

# resize: recomputes levels; --reason when a larger size reopens a phase
... resize --plan <ledger> --workstream ws-001 --size one-session

# append: phase evidence and decisions (append-only)
... append --plan <ledger> --path phases.plan.evidence --value <path>
... append --plan <ledger> --path decisions --value '{"decision":"...","reason":"..."}'

# ticket: per-ticket gate; use this for ids containing dots
... ticket --plan <ledger> --id "1.3" --gate review --status passed --evidence <path>

# done: close; --accept-missing-evidence/--accept-missing-tickets need --reason
... done --plan <ledger> --project-root {project-root}

# migrate: materialize levels on an older ledger; --reason when it reopens a phase
... migrate --plan <ledger> --reason "rebuild gate levels"

# reconcile: read-only; --write applies orphan pointers and blocks
... reconcile --plan <ledger> --project-root {project-root}

# verify-return: pass the pre-handoff hashes; a mismatch rejects the return
... verify-return --plan <ledger> --project-root {project-root} --return-file <json> \
  --expect-ledger-sha <sha256> --expect-memlog-sha <sha256>

# audit trail and validation
... log --plan <ledger> --type event --text "plan.requirements passed"
... validate --plan <ledger>
```

### set rules

- `set` parses `--value` as JSON when possible, otherwise as a string; `--null` sets null.
- Omitting `--workstream` targets the active workstream for workstream-shaped paths; document paths (`schema`, `bmad.*`, `active_workstream`) stay at the root.
- Replacing a whole node (`phases.<phase>`, `tickets.<id>`, a gate node, or a ticket gate node) needs `--replace --reason`. A phase replacement needs `status` and `evidence`; the derived `gate` and a gate node's `level` are carried forward.
- Remove a ticket with `set --path tickets.<id> --delete --reason <why>`; a ticket with a decided gate, or the last ticket of a done build phase, cannot be deleted.
- Create a ticket with the `ticket` command, not with `set`.
- `decisions` and `phases.*.evidence` are append-only through `append`; `--replace` and `--null` are refused there too. Artifact pointers take `set`, not `append`.
- `--plan`, `--memlog`, `--template`, and `--project-root` expand `{project-root}`; every command that resolves a path accepts `--project-root`, and a relative `--plan`/`--memlog` resolves against it. `--memlog` and the recorded `bmad.memlog` must differ from the ledger.
- `schema` is fixed at `bmad-sdlc/1`; `set` refuses any other value.
- A whole-phase replacement must keep every existing `evidence` entry; new entries go through `append`.
- Paused and done workstreams refuse writes; resume a paused one first, or reopen a done one with `--reason`.
- `bmad.model` follows §Resume semantics → Model change.
- Artifact pointers must resolve inside `{project-root}`.

### Hand-edit fallback

If `uv` is unavailable, read and write the YAML directly with the same shape, keep the writes atomic, and take a sibling `.lock` file around the read-modify-write. Apply §Field rules by hand: an override or reasoned skip carries `override_reason`, a decided gate carries `decided_at`, `decisions` stays append-only, and a level is derived from the resolved track/size/model, never hand-written. Log the hand edit to the audit trail, re-read the file, and present no gate from an unvalidated ledger. Never hand-write a derived field (`phases.*.gate`, `gates.*.level`) or a BMAD ticket status. The script is a convenience, not a hard dependency; these rules are the dependency.

## Resume semantics

The ordered activation sequence is in `SKILL.md` §On Activation; it runs `detect`, `reconcile`, `summary`, then the menu. The ledger-only deltas are:

- **Model change.** Use `set --path bmad.model --value <model>` on an existing ledger (pass `--model` to `init` only when creating it). A silent `unknown` must not overwrite a confirmed model. A downgrade, or a change that reopens a phase, needs `--reason`; `init --model unknown` refuses a downgrade without `--force --reason`.
- **Pointer cases.** Artifact exists, pointer missing → `reconcile --write`. Pointer set, artifact missing → under `--write`, reconcile blocks every open required/conditional gate in `gates_to_block` and lists decided gates in `requires_reason`; apply those with `set ... --value blocked --reason <why>`. Phase evidence missing → the phases in `phases_to_block` are blocked the same way. Ticket status disagrees → artifacts win; update the ledger and log the correction. A ticket gate whose evidence pointer is missing → repoint it with `ticket --gate <gate> --status <same> --evidence <path>`, or reopen the gate with `--reason`, then reconcile again. Never substitute a path outside `{project-root}`.
- **Corruption.** Run `validate`, then `migrate`: it creates missing nodes, carries derived fields forward, and reopens a phase whose gates it invalidates. A reopen needs `--reason`, which `migrate` records in the audit trail. If unrepairable, back up to `plan.yaml.bak`, re-run `init --force --reason`, and offer to re-import pointers from the artifacts. Never silently discard the old file.

## Multiple workstreams

- One `active_workstream` at a time. `init` appends a workstream and pauses the previously active one; `--force` recreates the ledger only with `--reason`, after writing `plan.yaml.bak` and a reset event.
- Switch with `set --path active_workstream --value ws-002` (no `--workstream`); the target becomes active and the previous active workstream is paused.
- The status dashboard lists every workstream with track, size, status, and next action.
- `validate` rejects more than one `status: active` workstream and an `active_workstream` that is not active.
- A paused workstream has no `next_action`; resume it before continuing or closing.
- Close with `done`, never a status edit; `gate-matrix.md` §Phase completion owns the refusal conditions. Do not delete a workstream; it is the history.
