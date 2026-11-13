# bmad-sdlc

One front door for the entire BMAD software development lifecycle.

Instead of choosing among `bmad-prd`, `bmad-architecture`, `bmad-create-epics-and-stories`, `bmad-build`, `bmad-testarch-*`, and `bmad-retrospective`, invoke **`bmad-sdlc`** and follow the menu. It knows where the work is, what is next, which BMAD skill owns it, and what must be true before advancing — and it persists that knowledge so a new session resumes without re-interviewing you.

---

## What BMAD is

BMAD is an **agentic agile delivery framework**: named personas own phases, and each phase leaves artifacts the next phase consumes. The core loop is **Clarify → Plan → Build and verify → Learn and adjust**, right-sized into four paths:

| Path | Shape |
|---|---|
| **Trivial** | change → edit → verify |
| **One-session** | intent → Build → result |
| **Epic** | spec → stories → Build × stories → integrate → retrospective |
| **Project** | shared contracts → epics repeated → integrated product |

The critical detail: **there is no single 'unit of work'.** Each persona advances a different thing.

| Persona | Advances |
|---|---|
| Analyst / PM / UX / Architect | documents (brief, PRD, UX, architecture) |
| Product Owner | the ticket tree — initiative → epics → tickets |
| Developer | one ticket per Build session |
| Test Architect | test artifacts per ticket/epic |
| Retrospective | one epic |

The repository has **v6.12.4** installed (`bmad-help`, epics/stories, `sprint-status.yaml`), while the current BMAD docs describe a newer model (`bmad` hub, Sofia `bmad-agent-po`, `tickets.toml`). `bmad-sdlc` detects which one is present and routes accordingly.

---

## What `bmad-sdlc` does

- **Detects the installed model** — v6 (epics + `sprint-status.yaml`) or current (Sofia + `tickets.toml`).
- **Keeps a durable plan** — a committed ledger at `_bmad-output/sdlc/plan.yaml` plus an append-only `.memlog.md`.
- **Presents a two-level menu** — phase first (Plan / Solution / Build / Verify / Close), then the legal actions for that phase, each with its role, skill, and gate.
- **Hands off in fresh context** — seeds a subagent with the objective, inputs, settled decisions, expected output, and gate criteria; validates the artifact before accepting it.
- **Gates every phase** — summary + `Approve / Revise / Run reviewer / Skip with override`. Overrides require a reason: the helper rejects an override that has none, and `validate` reports any that slipped through.
- **Right-sizes the gates** — a trivial fix goes build → review → done; an audit starts at review; epic/project gets the full gate set. Gate levels are resolved from track, size, and model.
- **Records per-ticket gates** — `ticket`, `tests`, `review`, and `done` live under `tickets.<id>.gates`, while BMAD artifacts remain the status truth.
- **Treats BMAD artifacts as truth** — the ledger stores the SDLC overlay and pointers, not ticket statuses. The conductor re-reads `sprint-status.yaml` or `tickets.toml` on every activation.
- **Covers four tracks** — greenfield, feature, fix, and audit.
- **Degrades honestly** — a missing skill is reported and the action is blocked; it is never silently substituted or faked.

---

## Install

The skill is already installed locally at `.agents/skills/bmad-sdlc/`.

To install it into another project, load **`skills/bmad-sdlc-module/setup/SKILL.md`**. It is the only step list: it copies the skill, places the module metadata, runs the detector, and optionally initializes the ledger. `customize.toml` is the only configuration surface; there is no separate module config file. The setup skill never edits `_bmad/_config/`; re-run the BMAD installer to publish the help entry.

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

The full verb set, signatures, and ledger effects are in `menu.md` §Verbs.

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

A fresh session reads the ledger, re-runs detection, reconciles the BMAD artifacts, and resumes at the recommended action. No re-interviewing. The ledger is already initialized for this repo (`ws-001`, track `feature`, size `epic`), with the bootstrap decision recorded.

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

```bash
# Detect the installed model and skills
uv run --no-cache .agents/skills/bmad-sdlc/scripts/sdlc_plan.py detect --project-root .

# Validate the ledger
uv run --no-cache .agents/skills/bmad-sdlc/scripts/sdlc_plan.py validate \
  --plan _bmad-output/sdlc/plan.yaml

# Summarize the current position
uv run --no-cache .agents/skills/bmad-sdlc/scripts/sdlc_plan.py summary \
  --plan _bmad-output/sdlc/plan.yaml

# Run the ledger helper tests
uv run --no-cache python -m unittest discover \
  -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'

# Run the evals (output outside the repo so the bare baseline stays bare).
# --mode takes one value; run each mode separately.
XDG_DATA_HOME="$HOME/.local/share" XDG_CONFIG_HOME="$HOME/.config" \
  uv run .agents/skills/bmad-eval-runner/scripts/run_evals.py \
  --cases .agents/skills/bmad-sdlc/evals/cases.json \
  --skill-path .agents/skills/bmad-sdlc \
  --output-dir ~/bmad-evals/bmad-sdlc \
  --mode quality

XDG_DATA_HOME="$HOME/.local/share" XDG_CONFIG_HOME="$HOME/.config" \
  uv run .agents/skills/bmad-eval-runner/scripts/run_evals.py \
  --cases .agents/skills/bmad-sdlc/evals/cases.json \
  --skill-path .agents/skills/bmad-sdlc \
  --output-dir ~/bmad-evals/bmad-sdlc \
  --mode baseline
```

Read `evals/README.md` §Known limitations before quoting a result: quality mode
does not grade, the bare baseline needs its own run, and trigger mode returns
0.0 under opencode.

The detector reports **v6**, hub `bmad-help`, test style `bmad-tea`. The ledger regression suite is the authoritative check (see `AGENTS.md` §Running and verifying). No installer-managed `_bmad/` files are modified.

---

## Key design decisions

| Decision | Choice |
|---|---|
| Operating model | Hybrid conductor: advances work, pauses at human gates, hands off to skills |
| State model | Thin ledger + artifacts; BMAD artifacts are truth |
| Gate policy | Enforce required gates, allow logged overrides |
| Role presentation | Neutral conductor + role labels |
| Interaction | Menu-driven, two levels (phase → action) |
| Handoff | Fresh subagent per skill, with inline and user-run fallbacks |
| Ledger granularity | Per product, multi-workstream |
| Version target | Adaptive: v6 and current |
| End of flow | Retro per epic, then continue |
| Packaging | Local skill now + reusable module |

---

## License

MIT — see [`LICENSE`](LICENSE).
