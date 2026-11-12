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
