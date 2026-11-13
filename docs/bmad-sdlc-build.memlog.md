---
topic: bmad-sdlc conductor skill
goal: one front door for the whole BMAD SDLC with a durable plan
updated: 2026-11-12T20:30
---

- (decision) Hybrid conductor: advances work, pauses at every gate, hands off to specialist skills.
- (decision) Adaptive full SDLC with four tracks: greenfield, feature, fix, audit.
- (decision) Thin ledger plus BMAD artifacts as truth for ticket status; ledger stores the SDLC overlay only.
- (decision) Version-adaptive: v6 (epics plus sprint-status) or current (Sofia plus tickets.toml).
- (decision) Fresh subagent per skill; inline and user-run handoffs as fallbacks.
- (decision) Ledger at _bmad-output/sdlc/plan.yaml, committed; .memlog.md is the append-only audit trail.
- (event) Built SKILL.md, six references, ledger script, five tests, and the reusable module package.
- (event) BMAD lint gate: quick_validate ok; fixed path-standards and workflow-integrity findings.
- (gap) Eval beat not run yet; Analyze lenses and HTML report not run yet.
- (event) analyze: grade fair, 0 critical / 8 high / 15 medium / 7 low, report .analysis/bmad-sdlc/2026-11-12-1628/skill-analysis-report.html
- (event) review: 20/20 quality expectations pass; baseline invalid because every bare run loaded the skill from an ancestor .agents/skills
- (event) fix: pass --plan/--memlog/--template; track-aware gate levels; per-ticket ticket/tests/review/done gates; reconcile and verify-return; atomic memlog writes
- (event) fix: reduced customize.toml to values the skill reads; added ledger_template; removed menu_style and on_complete; headless contract
- (event) fix: quoted-trigger description; eval cases add near-miss triggers and failure-mode rubrics; packaging excludes authoring state
- (event) tests: 14 passing; authoring memlog moved to docs/bmad-sdlc-build.memlog.md
- (event) review: second pass found audit routing, phase completion, blocked-gate, override-enforcement, multi-workstream, and eval-harness defects.
- (event) fix: audit synthetic ticket and verify routing; computed phase completion; close.mark_done + done command; blocked gate status; override and ticket-order enforcement; init appends/pauses workstreams; track-aware fix/audit sizing; doc and eval alignment.
- (event) tests: 29 passing; deterministic gates re-run; SKILL.md trimmed to 2,449 tokens.
- (review) independent pass: adversarial, edge-case, verification-gap, and editorial lenses; quality eval 9/9 cases and 43/43 rubric rows.
- (decision) gate state is authoritative: phase status is a cache, levels are derived, and `set phases.*.status=done` refuses while a gate is open.
- (decision) write safety: `set` validates paths/values, defaults to the active workstream, protects append-only fields, and `init --force` backs up and logs.
- (event) fix: audit review required, ticket status required, `verify-return` requires an artifact, `resize` recomputes levels, `reconcile` reports phase evidence, `summary` keeps its full shape, ledger writes locked.
- (event) fix: alias-aware `missing_core`, nested sprint parsing, `fix/one-session` starts at build; docs, evals, and module copy aligned.
- (event) tests: expanded regression suite; deterministic gates and eval quality suite re-run.
- (review) third independent pass: adversarial, edge-case, verification-gap, and editorial lenses; every code finding reproduced against the CLI.
- (event) fix: verify-return checks the configured memlog and file artifacts; resize removes the audit ticket and reopens skipped phases; model switch reapplies levels; locked_phases and complete chain from earlier phases.
- (event) fix: set rejects --root/workstream mis-scoping, derived fields, node writes without --replace, non-string pointers, and reasons on a passed/open gate; conditional skips need a reason.
- (event) fix: reconcile blocks a passed gate with no evidence and reports ticket overlay drift; done re-checks evidence, blocked phases, and stale ledger tickets; the audit path recorded at init is used by every writer.
- (event) fix: atomic writes preserve the file mode and roll back a failed ledger save; file locking has a Windows fallback; init rejects an empty name and ignores default_size for fix/audit.
- (event) docs: one gate matrix, single reason rule, corrected fix flow, resume banner, eval-claim honesty, and prose fixes.
- (correction) the live audit trail's 52/52 rubric-row claim is marked unbacked; quality mode does not grade.
- (correction) the 20/20 quality-expectation, 9/9 case, and 43/43 rubric-row scores in this log are historical and unbacked by a committed grading.json. Quality mode does not grade. The 2026-11-13 review run graded 10 cases at 60/62 expectations (2 failures: `build.ticket` vs `build.unblock`); its transcripts and grading.json files live under the run directory, and the findings are in `_bmad-output/reviews/`.
- (correction) the Analyze report path under `.analysis/` is gitignored, so the "fair, 0 critical / 8 high / 15 medium / 7 low" grade cannot be audited from the repository.
- (correction) the 14, 29, 54, and 70 test counts below are historical. The authoritative current count is in `AGENTS.md` §Running and verifying.
- (event) 2026-11-13 review fixes: 109 findings from five lenses (adversarial, edge-case, verification-gap, structure, prose); code, docs, evals, and packaging updated; `package.sh --check` added; suite grew to 94 tests.
- (correction) the 2026-11-13 re-check of the two failing eval cases did not complete: the provider returned HTTP 402 Insufficient Balance. The doc fix that keeps the intended action id is therefore not yet verified by a live eval run; re-run `fix-trivial` and `fix-one-session` when credit is available.

## Build record (moved from docs/bmad-sdlc.md)

### Build checklist

- [x] Design decisions captured and persisted (this document)
- [x] Create ledger template `assets/plan-template.yaml`
- [x] Create `scripts/sdlc_plan.py` (detect/init/validate/summary/set/append/ticket/done/migrate/resize/reconcile/verify-return/log)
- [x] Add script tests (initial 14, now 70 passing)
- [x] Write `references/phase-map.md`
- [x] Write `references/gate-matrix.md`
- [x] Write `references/ledger-schema.md`
- [x] Write `references/version-adapters.md`
- [x] Write `references/handoff-protocol.md`
- [x] Write `references/menu.md`
- [x] Write `SKILL.md`
- [x] Write `customize.toml`
- [x] Initialize `_bmad-output/sdlc/plan.yaml` for this repo
- [x] Smoke-test: detect → init → summary → set → validate
- [x] Package as a reusable module (setup skill + module manifest) at `skills/bmad-sdlc-module/`
- [x] Verify no installer-managed files were modified (only `.agents/skills/bmad-sdlc/`, `skills/bmad-sdlc-module/`, `docs/`, `_bmad-output/sdlc/`, `.gitignore`)
- [x] Backfill the build-process `.memlog.md` at `docs/bmad-sdlc-build.memlog.md`
- [x] Run the BMAD lint gate (`quick_validate`, `scan-path-standards`, `scan-scripts`, `prepass-workflow-integrity`, `prepass-prompt-metrics`)
- [x] Run the eval beat (`bmad-eval-runner`, quality mode; cases expanded with failure-mode rubrics)
- [x] Run the Analyze lenses and render the HTML report
- [x] Apply the review fixes (paths, track-aware gates, per-ticket gates, reconcile/verify-return, customization surface, description, packaging)
- [x] Second review pass: audit routing, phase completion, `blocked` gates, override/order enforcement, multi-workstream init, `done`, docs alignment
- [x] Re-run the ledger tests (29 passing) and the BMAD deterministic gates
- [x] Third review pass: gate state is authoritative, levels are derived, write paths/values are validated, `init --force` is safe, `verify-return` requires artifacts, detection aliases and nested sprint status are fixed, `fix/one-session` starts at build, `reconcile` sees phase evidence
- [x] Expanded the ledger regression suite to cover the bypasses and write-safety cases
- [x] Re-ran the ledger tests, deterministic gates, and the eval quality suite

#### 8.1 BMAD builder gates (2026-11-12)

The skill was built before the conductor existed, so the formal `bmad-workflow-builder` loop was applied retroactively to the deterministic gates.

| Gate | Result |
|---|---|
| `quick_validate.py` | pass — no errors |
| `prepass-workflow-integrity.py` | pass — no issues (after adding `## Overview`) |
| `scan-scripts.py` | pass — no findings (after switching to `json.dumps` and `sys.exit`) |
| `prepass-prompt-metrics.py` | 2,497 SKILL.md tokens; budget 2,500 — within budget, above the desired 1,500 tier |
| `scan-path-standards.py` | pass — the authoring `.memlog.md` moved to `docs/bmad-sdlc-build.memlog.md` and is excluded from packaging |
| Eval beat | The ten quality cases run headless for the routing cases and reach `build.ticket`; the audit case reports `blocked` when no review skill is installed, and `continue-with-ledger` resumes the staged workstream and its recorded gate. Quality mode captures transcripts but does not grade them, so a score is only valid with its grader output beside the run; do not cite a rubric count without that artifact. Trigger mode remains unusable with the stock opencode adapter (tool-event shape), and case metadata can be read from above `cwd`; the skill's guardrails forbid reading it. See `.agents/skills/bmad-sdlc/evals/README.md`. |
| Analyze lenses | **fair** — 0 critical / 8 high / 15 medium / 7 low; the high findings and the gate/path issues are fixed |
| Second review pass | Blocking state-machine and eval issues fixed; 54 ledger tests passed. |
| Third review pass | Guardrails, evidence, routing, the audit trail, and doc drift fixed; 70 ledger tests pass. |

The build-process memlog records the decisions, the build event, the lint gate, the review, and the fixes. It is the resume trail for the next builder session.

#### 8.2 Review fixes (2026-11-12)

- **Audit and state machine.** Audit uses a synthetic ticket and advances through verify; phase completion is computed from phase and ticket gates; `blocked` is a legal gate status; ticket gates are ordered; `init` appends/pauses workstreams; `fix`/`audit` default to one-session; `resize` removes a no-longer-needed audit ticket and reopens phases whose new levels demand gates.
- **Gate state is authoritative, levels are derived.** `summary`/`done` see gates in a phase marked done/skipped; `set phases.*.status=done` refuses while an earlier or own gate is open; `set` rejects derived fields (`phases.*.gate`, `gates.*.level`) and node writes without `--replace --reason`; `resize`/`migrate`/`bmad.model` rewrite levels and repair skipped phases.
- **Evidence and the audit trail.** `verify-return` checks the configured `--memlog` and requires a file; `done` re-checks artifact and phase evidence, refuses a blocked phase, and reports ledger tickets missing from BMAD artifacts (with explicit accept flags); every `set`/`append`/`ticket`/`done`/`resize`/`reconcile` write reaches the audit trail, including a custom `--memlog` recorded at `init`; writes preserve the file mode and roll back the ledger if the audit append fails.
- **Routing.** `fix`/`audit` ignore `--default-size`; `bmad-spec` aliases to `bmad-agent-po` under the current model; `locked_phases` covers every later phase, not only those with no gates of their own; `complete` chains from earlier phases so `close` cannot look done at activation.

#### 8.3 Round-6 review fixes (2026-11-13)

The round-6 review (86 findings across the five lenses) closed every behavior finding. The main changes: a recorded or replacement `memlog` cannot equal the ledger (which previously deadlocked every write); paused workstreams refuse `set`/`append`/`ticket`; model downgrades and model changes that reopen phases need `--reason`; ticket deletion and whole-ticket replacement respect decided gates; phase evidence and directories no longer satisfy per-gate artifacts; `verify-return` requires an evidence key and a rationale for an empty artifact list; `summary --project-root` reports `skill_installed`; `reconcile --write` blocks open gates and lists decided ones in `requires_reason`; `migrate` reopens phases it invalidates; malformed config is reported; and `set`/`ticket` keep their JSON error contract.

The suite grew to 181 cases, including the previously untested project-size route, sprint-status overlay, evidence validation, done's no-artifact branch, migrate repair, `resize --track audit`, the first-init rollback, framework discovery, and the reconcile write contract. Documentation follows the round-6 structure and prose findings: §7 is a table, the gate-matrix rules moved above the procedure, reference navigation is consistent, and the eval caveat sits under the command it invalidates. The gate-table level column stays as the concrete authority (structure S12 deferred). `.agents/skills/bmad-sdlc/VERSION` and `module.yaml` are 0.2.1.
