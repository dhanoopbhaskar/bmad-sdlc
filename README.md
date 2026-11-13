# bmad-sdlc

One front door for the entire BMAD software development lifecycle.

Instead of choosing among `bmad-prd`, `bmad-architecture`, `bmad-create-epics-and-stories`, `bmad-build`, `bmad-testarch-*`, and `bmad-retrospective`, invoke **`bmad-sdlc`** and follow the menu. It knows where the work is, what is next, which BMAD skill owns it, and what must be true before advancing — and it persists that knowledge so a new session resumes without re-interviewing you.

---

## What `bmad-sdlc` does

- **Detects the installed model** — v6 (epics + `sprint-status.yaml`) or current (Sofia + `tickets.toml`).
- **Keeps a durable plan** — a committed ledger at `_bmad-output/sdlc/plan.yaml` plus an append-only `.memlog.md`.
- **Presents a two-level menu** — phase first (Plan / Solution / Build / Verify / Close), then the legal actions for that phase, each with its role, skill, and gate.
- **Hands off in fresh context** — seeds a subagent with the objective, inputs, settled decisions, expected output, and gate criteria; validates the artifact before accepting it.
- **Gates every phase** — summary + `Approve / Revise / Run reviewer / Skip with override`. Overrides require a reason: the helper rejects an override that has none, and `validate` fails on any that slipped through.
- **Right-sizes the gates** — a trivial fix goes build → review → done; an audit starts at review; epic/project gets the full gate set. Gate levels are resolved from track, size, and model.
- **Records per-ticket gates** — `ticket`, `tests`, `review`, and `done` live under `tickets.<id>.gates`, while BMAD artifacts remain the status truth.
- **Treats BMAD artifacts as truth** — the ledger stores the SDLC overlay and pointers, not ticket statuses. The conductor re-reads `sprint-status.yaml` or `tickets.toml` on every activation.
- **Covers four tracks** — greenfield, feature, fix, and audit.
- **Degrades honestly** — a missing skill is reported and the action is blocked; it is never silently substituted or faked.

---

## What BMAD is

BMAD is an **agentic agile delivery framework**: named personas own phases, each persona advances a different unit of work, and each phase leaves artifacts the next phase consumes. The core loop is **Clarify → Plan → Build and verify → Learn and adjust**, right-sized into trivial, one-session, epic, and project. `docs/bmad-sdlc.md` §5–§6 has the path and persona tables.

The repository has **v6.12.4** installed (`bmad-help`, epics/stories, `sprint-status.yaml`), while the current BMAD docs describe a newer model (`bmad` hub, Sofia `bmad-agent-po`, `tickets.toml`). `bmad-sdlc` detects which one is present and routes accordingly.

---

## Install

The skill is already installed locally at `.agents/skills/bmad-sdlc/`.

To install it into another project, load **`skills/bmad-sdlc-module/setup/SKILL.md`**. It is the only step list: it copies the skill, places the module metadata, runs the detector, and optionally initializes the ledger. The shipped `customize.toml` is the base configuration; overrides go in `_bmad/custom/bmad-sdlc.toml` (team) or `.user.toml` (personal). There is no separate module config file. The setup skill never edits `_bmad/_config/`; re-run the BMAD installer to publish the help entry.

### Requirements

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) (the ledger helper declares `ruamel.yaml` via a PEP 723 header).
- A BMAD install for the actual delivery work. The conductor can plan without it, but actions are blocked until the target skills exist.
- A harness that can load skills and, ideally, spawn subagents. Without subagents, it falls back to inline or user-run handoffs.

---

## Use

Invoke the skill:

```text
bmad-sdlc
```

Then use the menu, or the five verbs the examples use:

```text
start
continue / next
status
run <action id>
done
```

The full verb set, argument syntax, and ledger effects are in `menu.md` §Verbs.

### Examples

- **"Start a new SaaS product"** → detects `greenfield` / `project`, creates the ledger, offers the plan menu starting with brief/PRD.
- **"Add SSO to our app"** → detects `feature` / `epic`, points at the existing repo, starts at `frame.spec` or `plan.prd`.
- **"Fix the login bug"** → detects `fix`, sizes `trivial` or `one-session`, short-circuits to `build.ticket`.
- **"Where are we?"** → loads the ledger, reconciles artifacts, shows `status`.
- **"Continue"** → resumes at the recommended action.
- **"Audit our tests"** → detects `audit`, starts at `build.review`, then `verify.trace`; `verify.test_review` and `verify.nfr` are conditional.

---

## Persistence

Two layers, both committed: the plan and its audit trail.

| File | Purpose |
|---|---|
| `_bmad-output/sdlc/plan.yaml` | Runtime ledger: active workstream, phase/gate state, decisions, artifact pointers |
| `_bmad-output/sdlc/.memlog.md` | Append-only audit trail of every gate, override, and correction |

The design document and decision log live in [`docs/bmad-sdlc.md`](docs/bmad-sdlc.md).

A fresh session reads the ledger, re-runs detection, reconciles the BMAD artifacts, and resumes at the recommended action. No re-interviewing. This repo's live workstream and current position are reported by `summary`, not copied here, so the README cannot go stale.

---

## Repository layout

```text
.agents/skills/bmad-sdlc/
  SKILL.md                       # activation, conductor loop, gates, resumption
  customize.toml                 # workflow customization surface
  references/
    phase-map.md                 # tracks, sizing, roles, per-track flows
    gate-matrix.md               # required/conditional/optional gates + evidence
    ledger-schema.md             # plan.yaml shape, ownership, resume semantics
    version-adapters.md          # v6 vs current detection + skill mapping
    handoff-protocol.md          # subagent brief, return contract, fallbacks
    menu.md                      # dashboard, phase menu, action menu, verbs
  assets/plan-template.yaml
  evals/                         # cases, trigger queries, adapter, run notes
  scripts/sdlc_plan.py           # detect/init/validate/summary/set/append/ticket/done/migrate/resize/reconcile/verify-return/log
  scripts/tests/test_sdlc_plan.py

skills/bmad-sdlc-module/
  README.md
  module.yaml                    # module metadata
  module-help.csv                # help catalog entry
  setup/SKILL.md                 # bmad-sdlc-setup
  scripts/package.sh             # rebuild the distributable copy
  skills/bmad-sdlc/              # generated copy (do not edit by hand)

docs/bmad-sdlc.md                # design + build plan + decision log
docs/bmad-sdlc-build.memlog.md   # authoring memory (outside the skill tree)
_bmad-output/sdlc/               # runtime ledger + audit trail
```

---

## Verify

The ledger regression suite and the exact commands are in `AGENTS.md` §Running and verifying; the eval commands and their limitations are in `evals/README.md`. No installer-managed `_bmad/` files are modified. Run `detect` to read the current model, hub, and test style rather than relying on a recorded example.

---

## Key design decisions

See `docs/bmad-sdlc.md` §4 for the binding decision log. Two choices shape the repository: the flow ends per epic (retro, then the next epic), and packaging ships both the local skill and the reusable module.

---

## License

MIT — see [`LICENSE`](LICENSE).
