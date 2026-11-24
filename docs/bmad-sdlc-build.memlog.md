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
- (correction) the 14, 29, 54, and 70 test counts below are historical. The authoritative current count is in §8.6; `AGENTS.md` §Running and verifying has the command that produces it.
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
| `prepass-prompt-metrics.py` | 2,495 SKILL.md tokens (budget 2,500) and 4,412 `ledger-schema.md` tokens (multi-branch budget 4,500) — both within budget, above the desired 1,500 tier |
| `scan-path-standards.py` | pass — the authoring `.memlog.md` moved to `docs/bmad-sdlc-build.memlog.md` and is excluded from packaging |
| Eval beat | The ten quality cases run headless for the routing cases and reach `build.ticket`; the audit case reports `blocked` when no review skill is installed, and `continue-with-ledger` resumes the staged workstream and its recorded gate. Quality mode captures transcripts but does not grade them, so a score is only valid with its grader output beside the run; do not cite a rubric count without that artifact. Trigger mode remains unusable with the stock opencode adapter (tool-event shape), and case metadata can be read from above `cwd`; the skill's guardrails forbid reading it. See `.agents/skills/bmad-sdlc/evals/README.md`. |
| Analyze lenses | **fair** — 0 critical / 8 high / 15 medium / 7 low; the high findings and the gate/path issues are fixed |
| Second review pass | Blocking state-machine and eval issues fixed; 54 ledger tests passed. |
| Third review pass | Guardrails, evidence, routing, the audit trail, and doc drift fixed; 70 ledger tests pass. |

The build-process memlog records the decisions, the build event, the lint gate, the review, and the fixes. It records how the build was done; resume from the ledger, not from this file.

#### 8.2 Review fixes (2026-11-12)

- **Audit and state machine.** Audit uses a synthetic ticket and advances through verify; phase completion is computed from phase and ticket gates; `blocked` is a legal gate status; ticket gates are ordered; `init` appends/pauses workstreams; `fix`/`audit` default to one-session; `resize` removes a no-longer-needed audit ticket and reopens phases whose new levels demand gates.
- **Gate state is authoritative, levels are derived.** `summary`/`done` see gates in a phase marked done/skipped; `set phases.*.status=done` refuses while an earlier or own gate is open; `set` rejects derived fields (`phases.*.gate`, `gates.*.level`) and node writes without `--replace --reason`; `resize`/`migrate`/`bmad.model` rewrite levels and repair skipped phases.
- **Evidence and the audit trail.** `verify-return` checks the configured `--memlog` and requires a file; `done` re-checks artifact and phase evidence, refuses a blocked phase, and reports ledger tickets missing from BMAD artifacts (with explicit accept flags); every `set`/`append`/`ticket`/`done`/`resize`/`reconcile` write reaches the audit trail, including a custom `--memlog` recorded at `init`; writes preserve the file mode and roll back the ledger if the audit append fails.
- **Routing.** `fix`/`audit` ignore `--default-size`; `bmad-spec` aliases to `bmad-agent-po` under the current model; `locked_phases` covers every later phase, not only those with no gates of their own; `complete` chains from earlier phases so `close` cannot look done at activation.

#### 8.3 Round-6 review fixes (2026-11-13)

The round-6 review (86 findings across the five lenses) closed every behavior finding. The main changes: a recorded or replacement `memlog` cannot equal the ledger (which previously deadlocked every write); paused workstreams refuse `set`/`append`/`ticket`; model downgrades and model changes that reopen phases need `--reason`; ticket deletion and whole-ticket replacement respect decided gates; phase evidence and directories no longer satisfy per-gate artifacts; `verify-return` requires an evidence key and a rationale for an empty artifact list; `summary --project-root` reports `skill_installed`; `reconcile --write` blocks open gates and lists decided ones in `requires_reason`; `migrate` reopens phases it invalidates; malformed config is reported; and `set`/`ticket` keep their JSON error contract.

The suite grew to 181 cases, including the previously untested project-size route, sprint-status overlay, evidence validation, done's no-artifact branch, migrate repair, `resize --track audit`, the first-init rollback, framework discovery, and the reconcile write contract. Documentation follows the round-6 structure and prose findings: §7 is a table, the gate-matrix rules moved above the procedure, reference navigation is consistent, and the eval caveat sits under the command it invalidates. The gate-table level column stays as the concrete authority (structure S12 deferred). `.agents/skills/bmad-sdlc/VERSION` and `module.yaml` are 0.2.1.

#### 8.4 Round-7 review fixes (2026-11-16)

Round 7 re-ran the quality suite against HEAD (the round-6 run predated the 2026-11-13 20:23 commit) and graded every case with a fresh grader. 71/74 rubric rows passed; the three failures were one over-strict rubric row and two literal isolation violations. The 181 unit tests pass, and the packaged copy was in sync.

Fixes: `ledger-schema.md` §Summary now documents what `summary` actually emits for gates in a done/skipped phase, and §Hand-edit fallback requires the field rules plus a logged hand edit; `SKILL.md` allows scratch only beside the ledger (`_bmad-output/sdlc/.tmp/`), requires naming scratch files, copies `next_action`/`optional_actions`/`open_gates`/`blocked_gates`/`locked_phases` verbatim from `summary`, and no longer presents a gate from an unvalidated hand edit; `build.loop` resolves to `bmad-build-auto` because `bmad-loop` is a tool, not a skill (D26, open question closed); `default_size` and the `init` fallback are `one-session`, matching `phase-map.md` §Sizing; the description covers the "one skill to run PRD, architecture, build, and tests" query. Eval contract: the three shape-only rows were tightened, every ledger-writing case gained a block-vs-`summary` fidelity row, and the new `fix-trivial-ready` case stages a v6 install as files so `status: ready` is exercised for the first time.

Grading that round exposed a helper bug the suite had missed: `optional_actions` offered actions from phases `summary` simultaneously reported in `locked_phases` (for example `close.retro` while close waited on `build.ticket`). `optional_actions` now walks phases in order and stops offering once a phase is locked, mirroring the `locked_phases` rule, with a regression test for both the locked and unlocked states. The suite is 182 cases; VERSION and `module.yaml` are 0.2.2.

#### 8.5 Round-8 review fixes (2026-11-17)

Round 8 reviewed the whole skill package with the five lenses and ran the 11 quality evals. The 87/90 row count recorded here was not backed by grading artifacts on disk and is withdrawn. Round 9 re-ran the same 11 cases immediately before fixing: 110/112 expectations passed; the two failures were `status-empty` (it deferred size instead of naming the configured default) and `fix-trivial-ready` (a symlinked skill path resolved outside the project root). Every behavioral finding was reproduced before fixing.

Helper: `verify-return` accepts `--expect-ledger-sha`/`--expect-memlog-sha` and rejects a handoff that edited either file (git status stays advisory and now sees untracked files); `done` rejects a second close, refuses a decided gate with no artifact key and no phase evidence, refuses a custom path without `--project-root`, requires a passed review for a passed or overridden ticket `done`, and validates ticket-gate evidence, which `ticket --evidence` now writes; `resize` refuses paused workstreams and audit track changes that would strand real tickets; `migrate` requires `--reason` when it reopens a phase; `init` keeps the ledger and audit trail inside the project root and always records a relative `bmad.memlog`; `set` pins `schema`, refuses evidence loss on a whole-phase replace, and the mutating commands accept `--project-root`; `summary` reports the latest-updated workstream when none is active, compares the full next-action identity for `next_action_stale`, and resolves installed skill alternatives (`bmad-agent-pm`, `bmad-build` for review, `bmad-tea`); `detect` reports manifest names with no readable `SKILL.md` as `manifest_only` while still counting the installer's declaration.

Docs: corrected the `summary --plan` activation command and the `init --default-track/--default-size` call, the audit level cells, the conditional-gate reason wording, the plan-only wording, the ledger/memlog terminology, the status line and D11, and merged §6 into §5. The eval README no longer says quality mode grades, and the rubric now copies `optional_actions` verbatim. The suite is 202 cases; VERSION and `module.yaml` are 0.3.0.

#### 8.6 Round-9 review fixes (2026-11-17)

Round 9 reviewed the current package with the five lenses and the 11 quality evals; the findings are in `_bmad-output/reviews/2026-11-17-bmad-sdlc-r9.md` and `.findings.json` (82 findings: 15 adversarial, 10 edge-case, 8 verification-gap, 31 structure, 18 prose).

Behavior:

- **Audit trail.** A recorded relative `bmad.memlog` resolves against the project root (or the nearest ancestor that holds it), never against `ledger.parent`; explicit and recorded paths are refused outside a known project root; `set --path bmad --replace` applies the same containment.
- **Write-path parity.** `migrate` and `reconcile --write` skip done/paused workstreams; `append` refuses gate metadata; `ticket --evidence` and `set` require an existing decided gate and enforce project-root containment; whole-ticket and gate-node replacement cannot drop a decided gate's evidence or forge/erase `decided_at`; reopening a gate clears the stale evidence pointer; `set` no longer trusts a stored override reason for a new decision.
- **Lifecycle.** `done` makes every phase terminal; `bmad.model` changes refuse done/paused workstreams and `init` does the same; `validate` rejects a decided gate without `decided_at` and a malformed ticket evidence; `set` type-checks `project`, `created`, `updated`, and `current_phase`.
- **Summary.** Alternatives resolve by gate, so `plan.stories` cannot fall back to `bmad-spec`; `skill_manifest_only` is computed from the chosen skill; `verify-return` reports post-write digests; the synthetic audit ticket carries `decided_at`.
- **Docs.** Moved Headless to `references/headless.md`; `SKILL.md` is 2,495 tokens and `ledger-schema.md` is 4,412; corrected the recorded audit-path wording, the eval README count, the `{repo}` placeholder, the `step files` phrase, the version-adapters column names, the menu track/size wording, the setup `--plan`/`--memlog` invocation and `.gitignore` path, the memlog resume-trail claim, and the stale token counts.

Verification: **224/224** unittest cases pass; `package.sh --check` in sync; validators clean; the re-run quality evals graded **109/112**. The pre-fix failures in `status-empty` and `fix-trivial-ready` are gone. The three remaining failures are path isolation in the harness: `continue-with-ledger` two rows for a `../../../_bmad` resolution through the skill symlink, and `start-greenfield` one row for a scratch file written to `/tmp`. Both are documented harness/model limits, not code paths; the skill's guardrails forbid them and `references/headless.md` now names the system temp directory explicitly.

#### 8.7 Round-11 role-split fixes (2026-11-24)

Round 11 reviewed the PM/DEV/QA split (23 findings) and recorded D28. D1 gives `build.review` and `build.done` to QA, so DEV builds and QA reviews and approves; the audit action override is gone. D2 persists the role per workstream (`role_override`, a `role` verb with a logged reason) and clears it on resume, resize, and done; `--role` stays a one-read view. D3 makes `close.mark_done` and `<phase>.unblock` role-free.

Helper: `summary` resolves the role from the stored `current_phase` and emits `current_role`/`role_source` even with no active workstream; `phases[]` and `workstreams_detail` carry `role`; role config loads lazily and is shape-validated, so a broken `role-config.toml` fails `summary` with JSON but not `detect`, `init`, `validate`, or `--help`; an unowned action or unmapped phase fails naming it; `--role` lowercases and returns JSON on an invalid value; gate writes log the acting role and a foreign role needs `--reason`; `verify-return` checks `--expect-role`/`--expect-action`; unknown ticket gates list the valid ids.

Docs: one transition table (PM→QA, QA→DEV, qualified PM→DEV, rollbacks), one blocked-handoff shape, overlays reduced to role deltas and links, the base action tables carry a `Role` column, D5 reconciled, and the design-doc header records D27/D28. Evals: `role-explicit-qa` stages the plan skills so only role gating blocks and expects `blocked`; `role-control-pm` is the no-`Role:` control; `role-qa-menu` stages a verify-phase fixture and exercises the visible role-filtered menu and `⇄` marker. `continue-with-ledger` now stages a committed fixture rather than the live ledger.

Verification: **276/276** unittest cases pass; `package.sh --check` in sync; validators clean; the focused role eval run graded **24/24** expectations in `~/bmad-evals/bmad-sdlc-r11-roles/20261124-171044-r11-roles`. The full quality + baseline re-run after the fixes is still open.
