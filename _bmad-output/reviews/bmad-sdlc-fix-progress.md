# bmad-sdlc review fix progress

Source: `2026-11-13-bmad-sdlc.md` / `.findings.json`. Status: `[ ]` open, `[~]` in progress, `[x]` fixed, `[-]` deferred (reason).

Result: **107 fixed, 2 deferred**. The two deferred items (V8, V9) need a richer eval harness: the stock runner stages individual files only, so it cannot pin a target-path ledger fixture or stage a directory of skills. Their behavior is covered by the unit suite, and the limitation is documented in `evals/README.md`.

## Adversarial
- [x] **A1** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:262-267,1403-1414` — Resolved workflow values keep the literal {project-root} token, and _plan_path does not expand it — expand {project-root} in _plan_path/init/memlog/template
- [x] **A2** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:1410-1414,1478-1488,1520-1525` — A second init without --memlog ignores the memlog path recorded in the ledger — second init resolves the recorded memlog
- [x] **A3** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2809-2825` — done has no audit exemption in its stale-ticket check, while reconcile does — audit ticket exempt from done's overlay check
- [x] **A4** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:3305-3341` — resize --track fix on an audit workstream keeps a decided review gate and skipped build gates — resize refuses an audit track change with decided gates
- [x] **A5** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:3287-3300,519-523` — resize on a done workstream reopens phases while status stays done — resize refuses a done workstream
- [x] **A6** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:1457-1472,1486-1502` — init --model unknown leaves existing workstream levels derived from the old model — init refuses a model downgrade and re-applies levels
- [x] **A7** `.agents/skills/bmad-sdlc/SKILL.md:49` — On resume the doc says pass the answered model to init --model, which appends and pauses workstreams — SKILL/version-adapters: set bmad.model on resume, init on first creation
- [x] **A8** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:415-449` — The config merge omits _bmad/config.user.toml, which BMAD's own loader reads — config.user.toml added in config_utils order
- [x] **A9** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2777-2808` — done closes when every gate is passed but no artifact pointer or phase evidence exists — done requires artifact/phase evidence for decided gates
- [x] **A10** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2856-2923` — migrate rewrites the ledger without a memlog line and cannot add missing gate nodes — migrate logs and creates missing nodes
- [x] **A11** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2052-2064` — summary emits <phase>.status as missing_gate for a complete-but-pending phase — summary names a real gate (build.ticket), never <phase>.status
- [x] **A12** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:3159-3283` — verify-return accepts empty evidence, and --accept-questions writes no trace — verify-return validates evidence and logs accepted questions
- [x] **A13** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:389-413` — read_skills counts the conductor itself, so detect reports BMAD installed when only bmad-sdlc exists — detect excludes the conductor from the skill inventory
- [x] **A14** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:836-844; references/version-adapters.md:63; references/phase-map.md:95-129` — The testarch alias fabricates bmad-tea-<capability> names that are not installed — testarch aliases resolve to bmad-tea, not invented names
- [x] **A15** `README.md:176-183; .agents/skills/bmad-sdlc/evals/README.md:19-27` — The documented eval command passes --mode twice, and argparse store keeps only the last value — docs run quality and baseline as separate invocations
- [x] **A16** `.agents/skills/bmad-sdlc/evals/cases.json:1-147` — No case exercises the write loop: approve, set, advance, override refusal, done blocked, handoff reject — write-loop coverage is the unit suite; README says so
- [x] **A17** `.agents/skills/bmad-sdlc/evals/cases.json:51,106,135` — The inputs assert bmad-build is not installed before the skill runs — eval inputs no longer assert bmad-build is missing
- [x] **A18** `AGENTS.md:26; README.md:185; docs/bmad-sdlc.md:232,250` — The same commit claims 29, 54, and 70 tests — AGENTS.md is the single test-count owner
- [x] **A19** `AGENTS.md:40 vs .agents/skills/bmad-sdlc/evals/README.md:47` — The known pitfall claims the eval mutates and requires resetting the live ledger — AGENTS pitfall matches the state-agnostic eval
- [x] **A20** `docs/bmad-sdlc-build.memlog.md:17,25; docs/bmad-sdlc.md:249` — Unbacked eval scores (20/20, 9/9, 43/43) and a citation to gitignored .analysis — build memlog records corrections for unbacked scores
- [x] **A21** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:1486-1502; .agents/skills/bmad-sdlc/customize.toml:20-21` — init replaces the bmad block instead of merging template keys — init merges template bmad keys
- [x] **A22** `skills/bmad-sdlc-module/setup/SKILL.md:41` — Setup stops when detection returns unknown, which is the documented plan-only mode — setup treats unknown as plan-only and continues
- [x] **A23** `skills/bmad-sdlc-module/scripts/package.sh:18-43` — No drift check, and the module ships tests and evals pinned to the author's model — package.sh --check, atomic copy, excludes tests/evals
- [x] **A24** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:880-893 vs 2418-2419; references/gate-matrix.md:68` — init auto-skips phases with an empty note, a state set refuses without a reason — auto-skipped phases record a note

## Edge-Case Hunter
- [x] **E1** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2751-2765` — phases.build.status is skipped, so the ticket-built block is skipped — done checks build before the skipped short-circuit
- [x] **E2** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:3286-3342` — resize --size epic on a workstream whose status is already done — resize refuses a done workstream
- [x] **E3** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2236-2238,2301-2320` — set workstreams.ws-001.status, .track, or .size bypasses enum and lifecycle guards — direct workstreams.<id>.* writes rejected
- [x] **E4** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2473-2505` — set gates.<phase>.<name>.override_reason --null after a reasoned override — decided override metadata cannot be cleared
- [x] **E5** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2422-2472` — set a blocked gate status to passed — a blocked gate cannot be set passed
- [x] **E6** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2777-2807` — A required gate is passed but its artifact pointer is still null — done requires evidence
- [x] **E7** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2779-2795,3036-3044` — artifacts.spec is set to an absolute path outside the project root — outside-root artifacts rejected in done/reconcile
- [x] **E8** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:1572-1604` — set phases.verify.status active while phases.plan is already active — only one active phase allowed
- [x] **E9** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2593-2608` — append --path phases.<phase>.evidence --null — empty evidence rejected on append
- [x] **E10** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2532-2536` — resume is run after pause cleared active_workstream, without an id — resume documents the required workstream id
- [x] **E11** `.agents/skills/bmad-sdlc/references/menu.md:1115` — pause then resume with no workstream argument, as the verb table shows — menu resume verb takes the id
- [x] **E12** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:1922-1951,2091-2126` — summary after the only workstream is closed, when active_workstream is null — summary keeps track/size/phase after close
- [x] **E13** `.agents/skills/bmad-sdlc/SKILL.md:99-109` — The active workstream is paused and summary returns next_action null — paused maps to needs_input in the status enum
- [x] **E14** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:3159-3283` — open questions are accepted with --accept-questions — accepted questions logged
- [x] **E15** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2938-2994,3045-3052` — Two artifacts match one key, for example two SPEC.md files — ambiguous artifact matches reported, not bound
- [x] **E16** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2962-2966,2997-3009` — plan.ux needs DESIGN.md and EXPERIENCE.md but artifacts.ux holds one path — plan.ux requires DESIGN.md and EXPERIENCE.md
- [x] **E17** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2855-2923` — migrate rewrites levels and tickets on any ledger — migrate logs corrections
- [x] **E18** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:1398-1399` — detect or init names a missing or mistyped --project-root — detect/init reject a missing project root
- [x] **E19** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:1415-1422` — init --template uses a project-relative path — template resolution checks project root then skill root
- [x] **E20** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:952-968` — The template parses to a list or scalar instead of a mapping — non-mapping template rejected
- [x] **E21** `skills/bmad-sdlc-module/scripts/package.sh:18-36` — rsync or cp fails mid-copy — package builds in staging and moves atomically
- [x] **E22** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:3209-3211` — A returned artifact path exists but the file is zero bytes — zero-byte artifacts rejected
- [x] **E23** `.agents/skills/bmad-sdlc/scripts/tests/test_sdlc_plan.py:35-1822` — Claim: the test file has 54 unittest cases — test-count claims corrected
- [x] **E24** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2473-2505` — Claim: the script rejects overrides without a reason — override reason rule doc aligned with the script
- [x] **E25** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:758-833` — Claim: gates are right-sized per track including greenfield — phase-map says greenfield/feature share levels

## Verification Gap
- [x] **V1** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:3167,3191` — Every verify-return test uses inline --return; --return-file and --allow-empty-artifacts are never executed — test covers --return-file and --allow-empty-artifacts
- [x] **V2** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:3105-3112,2809-2825` — No test stages tickets.toml or sprint-status tickets before reconcile or done — test covers ticket drift in reconcile and done
- [x] **V3** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:2801-2807,2819-2825` — Only the refusal side of done's gap handling is tested; neither accept flag nor its reason requirement is exercised — test covers the accept flags and the reason requirement
- [x] **V4** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:1506-1508` — No test invokes init --workstream, so the explicit-id path and duplicate-id refusal never run — test covers duplicate init --workstream
- [x] **V5** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:278-304,2545-2546,2837-2843` — No test fails a command after save_plan, so plan_locked's rollback never runs — test covers rollback after a failed audit append
- [x] **V6** `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py:415-449` — No test writes a non-default config.toml or custom config, so merge precedence and token substitution are unexecuted — test covers config precedence and token substitution
- [x] **V7** `skills/bmad-sdlc-module/scripts/package.sh:18-41` — Nothing runs package.sh during verification and no test compares the committed mirror with the canonical tree — test runs package.sh --check
- [-] **V8** `.agents/skills/bmad-sdlc/evals/cases.json:28-32` — continue-with-ledger stages the live ledger, so its open-gate precondition is whatever the project currently holds — stock runner cannot stage a target path; rubric stays state-agnostic and unit tests cover gates
- [-] **V9** `.agents/skills/bmad-sdlc/evals/README.md:57 with SKILL.md:98` — Every eval runs with no BMAD install and accepts ready or blocked, so no case requires ready with an installed skill — needs directory staging; covered by the unit suite and documented
- [x] **V10** `.agents/skills/bmad-sdlc/evals/queries.json with evals/adapter.json` — The trigger eval cannot count a real skill load because run_triggers.py parses Anthropic events, not opencode events — README says trigger mode is not verification

## Editorial Structure
- [x] **S1** `docs` — MERGE. Conflicting normative rule: ledger-schema says a reason is required only for a skipped required gate and validate warns; gate-matrix and the script require it for required or conditional and validate errors. Saves about 40 words. — merged into gate-matrix as sole authority
- [x] **S2** `docs` — MOVE. Delays action in the document a fresh session reads first and duplicates the memlogs. Saves about 620 words, 19 percent of the design doc. — build checklist moved to the build memlog
- [x] **S3** `docs` — CONDENSE. Restates activation steps 4 through 7 in different words, so the resume algorithm exists twice and can drift. Saves about 150 words. — resume section reduced to ledger-only deltas
- [x] **S4** `docs` — ADD. menu.md requires summary counts for the dashboard, but activation never calls summary and reconcile returns no gate counts. An agent following activation literally cannot render the dashboard. — activation runs summary before the menu
- [x] **S5** `docs` — CUT. Near-verbatim duplicate of gate-matrix.md Gate interaction, including the same sentence about not passing the gate. Saves about 90 words. — four-way ledger effects kept once in gate-matrix
- [x] **S6** `docs` — CONDENSE. The same close and cache rule appears in four places across three files. Saves about 70 words. — close/cache rule reduced to a pointer
- [x] **S7** `docs` — MOVE. Buried critical gate: an agent that truncates the section drops exactly the safety rule. Word-neutral. — headless stop rule moved to the top
- [x] **S8** `docs` — MOVE. The instruction cancels its own example after the example; an LLM renders top-down and copies the numbers. Word-neutral. — dashboard rule moved above the example
- [x] **S9** `docs` — ADD. The table is presented as the authority for why a gate is blocked or optional but omits the audit resolution. Adds about 12 words. — audit branch added to gate-matrix
- [x] **S10** `docs` — MERGE. 27 cells paraphrase gate-matrix and already differ from it; the file concedes the column is a summary. Saves about 115 words. — phase-map level column removed
- [x] **S11** `docs` — CONDENSE. The example duplicates the schema table a few lines later. Saves about 80 words. — shape comments reduced to structure
- [x] **S12** `docs` — MERGE. Three copies of the same four steps; the READMEs are drift-only. Saves about 130 words. — install steps merged into setup/SKILL.md
- [x] **S13** `docs` — MERGE. A second copy of a runtime contract that already drifted: README lists phase plan where menu specifies phase <name>. Saves about 90 words. — README keeps five verbs and points to menu
- [x] **S14** `docs` — CLARIFY. Two JSON contracts with no stated relationship; SKILL.md says summary returns the full shape and then emits a different 13-key block. — headless block labelled as a summary projection
- [x] **S15** `docs` — MERGE. The preflight instruction and the README disagree by 16 tests, and the same commit asserts 29, 54, and 70. — test counts have one owner
- [x] **S16** `docs` — ADD. The caveats live only in evals/README.md and a design section, while the README presents the commands as producing evidence. Adds about 15 words. — README points at eval limitations
- [x] **S17** `docs` — PRESERVE. The just-in-time load table is what makes six reference files viable for an agent. — kept deliberately
- [x] **S18** `docs` — PRESERVE. The one deliberate redundancy: a single screen of non-negotiables for an agent that may load no reference file. — kept deliberately
- [x] **S19** `docs` — PRESERVE. The four flows compress the state machine more usefully than the tables and reinforce rather than duplicate them. — kept deliberately

## Editorial Prose
- [x] **P1** `docs` — Fragment with no main verb read as a statement rather than an instruction. — imperative restored
- [x] **P2** `docs` — Wrong rule: the script requires a reason for a skipped conditional gate too, and validate errors rather than warns. Lands in gate-matrix Override rules after the merge. — override rule corrected and pointed at gate-matrix
- [x] **P3** `docs` — --reason alone does not accept a gap; the script also demands one of the two accept flags. Split the compound artifact/ticket-overlay gap. — done paragraph corrected
- [x] **P4** `docs` — Non-actor: summary recommends, the conductor asks, the script resolves. Asks for a PRD also read as requesting the document. — actor and wording corrected
- [x] **P5** `docs` — required contradicted the levels on the same page: conditional for one-session and fix, optional for trivial. — verify.trace level corrected
- [x] **P6** `docs` — Second sentence had no subject, and required with no baseline contradicted the matrix. — condition sentence corrected
- [x] **P7** `docs` — Noun phrase plus bare imperatives left the subject unstated. — overview made a full sentence
- [x] **P8** `docs` — Circular definition replaced with the two actual causes used elsewhere in the same section. — status enum defined without circularity
- [x] **P9** `docs` — Only default reads as default only. — default wording fixed
- [x] **P10** `docs` — Dangling modifier: nothing said what was corrupt. — corrupt-ledger subject added
- [x] **P11** `docs` — Read as two unrelated writes; made the fallback order explicit and said where the status appears. — alias fallback clarified
- [x] **P12** `docs` — The read-only command emits the lists; Its attached them to the write variant. — reconcile attribution fixed
- [x] **P13** `docs` — The fields are integers, not lists; lists pointed at the wrong referent. — counts vs lists fixed
- [x] **P14** `docs` — Ambiguous whether the gate is marked or merely named. — locked-phase wording fixed
- [x] **P15** `docs` — Subjectless asks; active voice matches the surrounding rows. Keep menu.md verb signatures in the merged table. — verb voice fixed
- [x] **P16** `docs` — Bare tickets is the map of tickets, not the gate nodes. — ticket gate path fixed
- [x] **P17** `docs` — It sat two sentences after its antecedent, with customize.toml in between. — setup skill owns the no-edit rule
- [x] **P18** `docs` — Inner double quotes closed the bold span early; single quotes nest. — quotes nested
- [x] **P19** `docs` — from a committed ledger trailed the verb phrase and read as the destination of the routing. — module description reordered
- [x] **P20** `docs` — The dash clause could be read as excluding bmad-sdlc from the directory rather than from the rule. — vendor-skill exception clarified
- [x] **P21** `docs` — Two docs state different expectations for the same case; the rubric is state-agnostic and the case stages a copy, so the reset instruction has no owner. — AGENTS pitfall corrected
- [x] **P22** `docs` — States a consequence of a choice not taken; conditional mood matches the constraint it explains. — run-folder consequence made conditional
- [x] **P23** `docs` — Two bare its with different antecedents: the metadata and the installer. — installer antecedent made explicit
- [x] **P24** `docs` — First rung available contradicted start at the preferred rung; the next paragraph resolves the tension differently. — handoff ladder order fixed
- [x] **P25** `docs` — but still never run left the clause without a subject; still added nothing. — parallelism clause fixed
- [x] **P26** `docs` — Narrower than the rule enforced everywhere else: conditional gates count too, and decided covers overrides and reasoned skips. — done definition widened
- [x] **P27** `docs` — One size smaller had no stated baseline; the intent is to pick the smaller of two candidates. — size choice wording fixed
- [x] **P28** `docs` — that file could point at the script or the reference; the reference holds a table, not a matrix object. — matrix pointer fixed
- [x] **P29** `docs` — Degrade to the nearest available equivalent reads as silent substitution, which version-adapters forbids; only listed aliases are allowed. — alias substitution made explicit
- [x] **P30** `docs` — Section 8.2 moves to the build memlog, so the pointer must be repointed; the same move breaks the Build checklist anchor in the Resume here note. — build-record pointer repointed
- [x] **P31** `docs` — A place the target project can read names no requirement; Load setup/SKILL.md left the object unstated. Use imperative step voice in the merged install list. — install steps made imperative

## Verification (2026-11-13)

- **94/94** unittest cases pass (`uv run --no-cache python -m unittest discover ...`, 505 s).
- `package.sh --check` reports the module copy in sync; the packaged skill passes `quick_validate` and `scan-scripts` (0 findings).
- `prepass-workflow-integrity` 0 issues; `scan-path-standards` 0 findings; SKILL.md is 2,500 tokens (budget 2,500).
- The live `_bmad-output/sdlc/plan.yaml` validates with no errors or warnings; `detect` excludes the conductor; `reconcile` reports no drift.
- Eval re-check of `fix-trivial` and `fix-one-session` did not run: the provider returned HTTP 402 Insufficient Balance. Re-run those two cases when credit is available; both now structurally emit `build.ticket`.

## Re-review (2026-11-13, round 2)

Source: `2026-11-13-bmad-sdlc-r2.md`. Status: `[ ]` open, `[~]` in progress, `[x]` fixed, `[-]` deferred (reason).

- [x] **R1** `sdlc_plan.py:109,550-589,3040-3060` — `done` closed a workstream with passed ticket gates and no build evidence — `done` now refuses a non-empty ticket map when no ticket artifact is readable, unless `--accept-missing-tickets --reason`; the acceptance reason is logged. Tested by `test_done_refuses_tickets_without_a_ticket_artifact`.
- [x] **R2** `sdlc_plan.py:2810-2905` — `ticket --status passed` bypassed the blocked→passed guard — `cmd_ticket` now refuses a blocked gate set to passed. Tested by `test_ticket_refuses_a_blocked_gate_passed`.
- [x] **R4** `sdlc_plan.py:2810-2905` — `ticket --status open` silently cleared decided metadata and allowed an out-of-order ledger — reopening a decided gate now needs `--reason`; a ticket gate cannot reopen while a later gate is decided; a phase gate cannot reopen while its phase is done/skipped; `set` uses the same guard. Tested by `test_reopening_a_decided_gate_needs_a_reason_and_order` and `test_set_reopening_a_decided_gate_needs_a_reason`.
- [x] **R5** `sdlc_plan.py:1075-1090,2278-2330` — `set` accepted a dotted ticket id and wrote a phantom ticket — `set` now rejects `tickets.<dotted-id>...` and points at the `ticket` command. Tested by `test_set_rejects_a_dotted_ticket_id`.
- [x] **R3** `SKILL.md:106` — the headless projection sentence named the wrong omitted fields — corrected to “the per-level counts and ticket detail”; SKILL.md stays at the 2,500-token budget.
- [x] **R10** `ledger-schema.md:266` — the replaceable-map list named nodes `set` rejects — corrected to the replaceable nodes and fixed the `tickets` example; added the reopen and dotted-id rules.
- [x] **R6** `tests/test_sdlc_plan.py` — no test covered the write-path gaps — five tests added (99 total).
- [x] **R7** `evals/cases.json` `feature-one-session` — the block-reason assertion conflated bmad-build with the immediate bmad-spec blocker — assertion now accepts the missing skill of the next action.
- [x] **R8** `evals/cases.json` `fix-trivial` — the `open_gates`/`verify.trace` assertion was ambiguous — assertion now checks that no open gate is required.
- [x] **R9** `evals/cases.json`, `evals/README.md` — installed-BMAD ready path, write loop, and resume-at-open-gate remain unverified — **deferred**: the stock runner stages individual files only; documented in `evals/README.md` Known limitations (V8/V9).

Verification after the fixes:

- **99/99** unittest cases pass (738 s).
- `package.sh --check` reports the module copy in sync.
- `quick_validate`, `prepass-workflow-integrity`, `scan-path-standards`, and `scan-scripts` are clean; SKILL.md is 2,500 tokens.
- The quality eval grades remain 10/10 cases and 62/62 expectations; the two corrected rubrics (R7, R8) still pass against the existing transcripts.


## Re-review round 3 fixes (2026-11-13)

Source: `2026-11-13-bmad-sdlc-r3.md` / `.findings.json`.

- [x] **A1/A2/E1** — `_guard_blocked_gate` now reads `_written_gate`, so a whole-node `--replace` cannot pass a blocked gate. `_validate_value` requires a status on every gate-node write.
- [x] **A3/A4** — `get_parent` matches the longest existing ticket id, dots included; `_validate_path` resolves the gate segment from the ticket map and refuses to create an unknown dotted id. Dotted ids now work with `set` and `ticket`.
- [x] **A5/A6/E2/E3** — A decided gate moves only with `--reason`, including to `blocked`; `decided_at` and `override_reason` are cleared on `open`/`blocked`. A gate on a done workstream is refused until the workstream is reopened; a done/skipped phase reopen needs `--reason`.
- [x] **A7/A8** — `set --path tickets.<id> --delete --reason` removes a ticket atomically; the ledger-schema example now uses it.
- [x] **A9** — `--project-root` is expanded in `detect`, `init`, `done`, `reconcile`, and `verify-return`; `done` also checks that it is a directory.
- [x] **A10** — `done` accepts a missing ticket artifact with `--accept-missing-tickets --reason` even on a custom ledger path, normalizes mixed string/integer ids, and names the accepted gap in the close memlog line.
- [x] **A11/A12** — The reopen contract is documented in `gate-matrix.md` §Reopening and `menu.md`; `SKILL.md` gains the reopen guardrail.
- [x] **V1–V6** — Tests added for the phase `_guard_reopen` branch, node replacement, close-note reason, dotted ids, `set` reopen metadata, workstream reopen, unknown dotted ids, mixed ids, custom-ledger `done`, token expansion, and `--delete`. `test_migrate_materializes_levels_and_tickets` now stages the missing map with `edit_ledger`.
- [x] **S1–S5, S7–S10, S12–S18** — Applied the editorial structure findings: cut the model/write duplication, merged the ledger/audit restatements, broke the gate/menu pointer loop, moved Headless before activation, reordered the status enum, shortened Tracks, removed the duplicate levels bullet, added Contents and field rows, split §Script operations into H3s, merged the eval notes, moved the fallback prompts, and merged Roles into the loop.
- [x] **P1–P17** — Applied the prose fixes, including the two factual ones: `--reason` alone does not accept a gap (the accept flags are also required), and a resumed model answer goes to `set --path bmad.model`.
- [x] **S6, S11** — The version-adapters table now keeps only capabilities with no per-action home and points at `phase-map.md`; §Script operations is split into Summary shape, Commands, set rules, and Hand-edit fallback.

Verification after the round-3 fixes:

- **112/112** unittest cases pass (515 s).
- `package.sh --check` reports the module copy in sync.
- `quick_validate`, `prepass-workflow-integrity`, `scan-path-standards`, and `scan-scripts` are clean.
- The live `_bmad-output/sdlc/plan.yaml` validates with no errors or warnings.
- The eval cases were not re-run; the routing behavior they exercise is unchanged. The recorded quality run remains 10/10 cases and 62/62 expectations.

## Round 4 fixes (2026-11-13)

Source: `2026-11-13-bmad-sdlc-r4.md` / `.findings.json`. All 52 findings fixed; no deferrals.

### State machine (adversarial A1–A18, edge E1–E4)

- [x] **A1/A2** — `workstreams.*` is no longer writable; the `bmad` block now needs `--replace --reason`, validates its model and paths, and refuses to drop the recorded `memlog`.
- [x] **A3/A4/A5** — Switching `active_workstream` to a done workstream needs `--reason`; any other transition out of `done` is refused; activating a workstream pauses the previously active one, so `validate` never sees two.
- [x] **A6/A7/A18** — A done workstream accepts no gate, phase, or ticket write (including `--delete`) until reopened; the synthetic `audit` ticket cannot be deleted.
- [x] **A8** — A decided gate can move back to `passed` with `--reason` (the flag was previously rejected before the reopen guard ran).
- [x] **A9/A11** — A ticket gate cannot reopen while `build` is done/skipped, and `build` cannot be marked done with no ticket.
- [x] **A10/A14/E1** — Dotted ticket ids resolve through the ticket map for metadata, gate, and prefix checks; a prefix that is not an exact id is refused, and whole dotted nodes are validated.
- [x] **A12/A13** — Whole-ticket replacement runs the blocked, reopen, order, and dropped-reason guards; `done` re-checks ticket order before closing.
- [x] **A15** — A phase node cannot carry the derived `gate` field or undefined `decided_at`/`override_reason`.
- [x] **A17** — `resize` requires `--reason` when it reopens a phase and names the reopened phases in the audit trail.
- [x] **E2/E3/E4** — `--delete` matches integer-keyed ids, `--memlog` expands `{project-root}`, and the audit ticket is protected.
- [x] **A16** — `gate-matrix.md` now says `done`, not `set`, verifies evidence; the code already enforced it there.

### Verification (V1–V10)

- [x] Tests added for: dotted metadata clearing, the `_guard_reopen` done branch through `set`, `active_workstream` reopen, the status-reopen audit line, whole-ticket replacement, token expansion in `detect`/`reconcile`/`verify-return`, both close-note accept branches, delete-after-close, the audit ticket, integer keys, and resize reopening.
- [x] **V8/V9** — The eval rubrics now assert persisted state (ledger existence, track/size/model, next gate, unchanged staged ledger) and no writes outside the case root; the scope guardrail was added to `SKILL.md`. A fresh quality run re-graded.

### Documentation (structure S1–S9, prose P1–P9)

- [x] Structural cuts: reconcile paragraph condensed, the close rule merged into `gate-matrix.md`, `docs/bmad-sdlc.md` §7.1/§7.2 reduced to pointers and the tree deduplicated, the alias table merged, README decisions and eval blocks condensed, the duplicate decision rows marked merged.
- [x] Prose fixes: `--workstream <id>` added to both reopen commands; headless default wording clarified; the v6 detector row includes `bmad-sprint-planning`; the settled open questions recorded; §7.4 authority clarified; alias grammar fixed; `validate` "fails on" an override; the setup "it" resolved; `--memlog` expansion is now true in code and docs.

### Verification after round 4

- **132/132** unittest cases pass.
- `package.sh --check` reports the module copy in sync.
- `quick_validate`, `prepass-workflow-integrity`, `scan-path-standards`, and `scan-scripts` are clean.
- Fresh quality eval run `~/bmad-evals/bmad-sdlc/20261113-161517-r4-fixes`: 10/10 cases executed; **73/73 expectations** graded beside each transcript.

## Round 5 review (2026-11-13, open)

Source: `2026-11-13-bmad-sdlc-r5.md` / `.findings.json` (67 findings: 18 adversarial, 8 edge-case, 13 verification-gap, 18 structure with 2 preserves, 10 prose).

Status at review time: unit suite **132/132**, `package.sh --check` in sync, `detect` v6/`bmad-help`. The recorded round-4 quality run still shows 10/10 cases and 73/73 expectations, but its own `rubric_feedback.weak` says the "no file outside the project root" expectation is false for every `uv` run, so the score is not evidence for the scope guardrail.

Highest-impact open items: phase evidence bypasses the per-gate artifact and UX checks; `verify-return --allow-empty-artifacts` accepts an empty evidence list; `--memlog` expands against cwd; `validate` exits 0 on errors.

## Round 5 fixes (2026-11-13)

Source: `2026-11-13-bmad-sdlc-r5.md` / `.findings.json`. All 67 findings were addressed; no deferrals. Two were resolved by documentation instead of a behavior change (the audit/trivial exception and the eval read-scope limitation).

### State machine and guards (adversarial A1-A18, edge E1-E8)

- **A1** `done` now checks `plan.ux` before the phase-evidence short-circuit, so both `DESIGN.md` and `EXPERIENCE.md` are always required; `reconcile` matches.
- **A2** `--allow-empty-artifacts` no longer waives an explicitly empty `evidence` list.
- **A3/E2** `--memlog` and a relative `--plan`/`--memlog` resolve against the command's `--project-root`, not the shell cwd; `init` uses the same rule.
- **A4** `validate`, `reconcile`, and `verify-return` exit 1 when `ok` is false; `SKILL.md` and `ledger-schema.md` document the contract.
- **A5/E8** `ledger_touched` compares whole porcelain paths, so `.lock` files no longer match. The lock files stay on disk: unlinking a lock while another process waits is racy, so the file remains and the check is exact instead.
- **A6** `set --path phases.<phase>.evidence` is append-only in every form; `--replace` and `--null` are refused.
- **A7** `done` records every overridden phase and ticket gate in the close note.
- **A9/E6** `track` and `size` are documented as `summary.workstream` fields; `close.mark_done` and `<phase>.unblock` are exempt from the missing-skill rule.
- **A11** The missing-skill side effect is now one instruction: emit `status: blocked` and record the reason with `set --path phases.<phase>.note`.
- **A12/E8** `detect` matches only an exact `bmad-tea` directory; `bmad-tea-*` names no longer make detection look ready.
- **A13/A14** Audit/trivial keeps `verify.trace` required, documented in `phase-map.md` and `gate-matrix.md`.
- **A17/A18** Setup refuses a target that is not `*/skills/bmad-sdlc`, backs up before copying, and reports the installed `VERSION`; the version file now ships.
- **E1** A `--memlog` equal to the ledger fails fast instead of deadlocking on the lock.
- **E3** A null `active_workstream` is refused while a workstream is active, and `validate` flags a hand-edited one.
- **E4** A phase replacement needs `status` and `evidence`; the derived `gate` is carried forward.
- **E5** Accepted questions are logged only after the return passes.
- **E7** The handoff brief uses `<resolved ledger path>` / `<resolved audit path>` instead of unresolved `{}` tokens.
- **E8** `validate` rejects two ticket ids that normalize to the same string.

### Verification (V1-V13)

- Tests added for: the rollback path (memlog replaced by a directory), outside-root pointers in `done` and `reconcile`, the migrate correction line, the decided-audit resize refusal, the `plan.ux` pair, manifest detection, a `.claude/skills` install, `test_style`/`hub`, `optional_open` and `workstreams_detail`, the fourth config layer, and `init --default-track`.
- **V8/V9** The `continue-with-ledger` rubric is scoped to writes under `_bmad-output/sdlc/` and forbids out-of-root reads; `evals/README.md` records the symlink and metadata limits. The vendor runner is not edited.

### Documentation (structure S1-S18, prose P1-P10)

- Cut the duplicate close paragraph and the `set` comment block; merged phase completion and summary fields into their owners; removed the duplicated unittest/eval blocks from `README.md`.
- Condensed `docs/bmad-sdlc.md` §7.5-§7.8 to constraints and pointers, and §7.3 to entry points.
- Applied the prose fixes: four-way framing, `workstreams.*` in the set rules, `ledger_touched` attribution, track/size ordering, `<phase>.unblock`, "the report" wording, the installer relation, the `unknown` diagnosis, the `verify.trace` antecedent, and the reopen antecedent.

### Verification after the fixes

- **152/152** unittest cases pass (343 s).
- `package.sh --check` reports the module copy in sync; `VERSION` 0.2.0 ships and matches `module.yaml`.
- `quick_validate` ok; `prepass-workflow-integrity` 0 issues; `scan-path-standards` 0 findings; `scan-scripts` 0 findings.
- `SKILL.md` is 2,472 tokens (budget 2,500).
- The live ledger validates with no errors or warnings; `reconcile` is clean; `detect` reports v6, hub `bmad-help`, test style `bmad-tea`.
- Exit-code contract verified end to end: `validate` and `verify-return` exit 1 on `ok:false`; `reconcile --write` still persists its corrections when it exits 1 for drift.

The verification commands:

```
uv run --no-cache python -m unittest discover -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'
skills/bmad-sdlc-module/scripts/package.sh --check
uv run --no-cache .agents/skills/bmad-workflow-builder/scripts/quick_validate.py .agents/skills/bmad-sdlc
uv run --no-cache .agents/skills/bmad-workflow-builder/scripts/prepass-workflow-integrity.py .agents/skills/bmad-sdlc
uv run --no-cache .agents/skills/bmad-workflow-builder/scripts/scan-path-standards.py .agents/skills/bmad-sdlc
uv run --no-cache .agents/skills/bmad-workflow-builder/scripts/scan-scripts.py .agents/skills/bmad-sdlc
```

## Round 6 fixes (2026-11-13)

Source: `2026-11-13-bmad-sdlc-r6.md` / `.findings.json` (86 findings: 16 adversarial, 14 edge-case, 14 verification-gap, 22 structure including 3 preserves, 20 prose).

Status: **85 addressed, 1 deferred, 1 partial**. No behavior finding was left open.

### Behavior (adversarial A1-A16, edge E1-E15)

- **Audit trail cannot brick the ledger.** `set --path bmad` and a recorded `bmad.memlog` now refuse a path equal to the ledger; the recorded branch is checked on every resolve, so a hand-edited ledger fails with JSON instead of deadlocking on its own lock. Read-only reconcile no longer creates `plan.yaml.lock`.
- **Paused is a real state.** `set`, `append`, and `ticket` refuse writes on a paused workstream; resume takes `--workstream <id> --path status --value active --reason`.
- **Model changes are reasoned.** `set --path bmad.model unknown` needs `--reason`, judged against the pre-write model; `set` and `init` require `--reason` when the change reopens a phase and log the reopened phases.
- **Ticket lifecycle.** `set --path tickets.<id> --delete` refuses a ticket with a decided gate or the last ticket of a done build; `ticket` refuses writes under a done build phase; `set` refuses to create a ticket; a whole-ticket replacement cannot drop a decided gate.
- **Gate evidence.** Phase evidence no longer short-circuits per-gate artifacts; directories are rejected (`is_file()`); `artifacts.ux` resolves the DESIG+EXPERIENCE pair from its pointer before the planning-artifacts glob.
- **Reconcile repair.** `--write` blocks open required/conditional gates from `gates_to_block` and from `phases_to_block`, logs them, and reports decided gates/phases in `requires_reason` instead of silently reopening them. The unreachable orphan clause is gone.
- **Handoff evidence.** `verify-return` requires an `evidence` key with entries that exist inside the project root; `--allow-empty-artifacts` needs `--reason` and is logged.
- **Model awareness.** `summary --project-root` adds `next_action.skill_installed`; `SKILL.md` uses it for the missing-skill rule.
- **Validation.** `name` and `started` are type-checked; artifact pointers must stay inside the project root; malformed `_bmad/config*.toml` surfaces as `config_errors` and blocks `init`; `migrate` reopens a phase its new gates invalidate; v6 sprint-status epic rows are not tickets; a gate-node replacement keeps `level`, `decided_at`, and `override_reason`.
- **CLI contract.** Invalid `ticket --gate/--status` values emit JSON instead of argparse usage text.

### Tests

- 29 tests added or updated, including the uncovered branches named by the verification-gap lens: project-size routing, sprint-status overlay, evidence validation, the done "(no artifact)" branch, reconcile `<phase>.ux`, migrate repair, `resize --track audit`, phase-skip reason, whole-ticket guards, `bmad-testarch` detection, first-init rollback, `test_framework` discovery, and the `reconcile --write` exit contract.
- Suite: **181 tests** (see verification below).

### Documentation (structure S1-S19, prose P1-P20)

- Condensed `docs/bmad-sdlc.md` §7 to a component/owner/constraint table and the persona table to a pointer at `phase-map.md` §Role labels; moved the build record into the preamble.
- Moved the missing-evidence and no-override-close rules to the top of `gate-matrix.md` §Override rules, merged its phase-completion lists, and updated the close rule to per-gate artifacts.
- Moved the trigger-mode caveat under the eval command that it invalidates; corrected the eval README's `ready`-branch coverage claim; recut the write-loop and `continue-with-ledger` paragraphs.
- Added a linked Contents block to all six reference files; moved the trivial/audit rules to `phase-map.md` §Sizing; merged the version-adapters model instruction; converted `ledger-schema.md` §set rules to bullets; merged the handoff checklist into the return contract; cut the duplicated README verify commands and live checkout state; cut the one-item AGENTS pitfall.
- Applied all 20 prose fixes (status definitions, prohibition placement, duplicated model rule, alias restatements, dangling references, actor-first sentences, article/term fixes, and the split description/instruction).
- **Deferred:** S12 (move the gate-table level policy out of the 18-row table). The column is the concrete per-gate authority and a compact rule block would restate the resolver less precisely; the table stays. **Partial:** S8 keeps `SKILL.md` §Ledger and audit because the always-loaded file needs the lock/audit rule even when no reference loads; the tracks and resuming sections were merged.

### Verification after round 6

- **181/181** unittest cases pass.
- `package.sh --check` reports the module copy in sync; `VERSION` and `module.yaml` are **0.2.1**.
- `quick_validate`, `prepass-workflow-integrity`, `scan-path-standards`, `scan-scripts`, and `prepass-prompt-metrics` are clean; `SKILL.md` is 2,500 tokens (budget 2,500).
- The live `_bmad-output/sdlc/plan.yaml` validates with no errors or warnings; `detect` reports v6, hub `bmad-help`, test style `bmad-tea`.

## Round 9 fixes (2026-11-17)

Source: `2026-11-17-bmad-sdlc-r9.md` / `.findings.json` (82 findings: 15 adversarial, 10 edge-case, 8 verification-gap, 31 structure, 18 prose).

- **Behavior (adversarial 15, edge-case 10):** fixed in `scripts/sdlc_plan.py`. The clusters were audit-trail resolution and containment, write-path parity (`migrate`, `reconcile --write`, `append`, `set`, `ticket`), decided-gate evidence and `decided_at`, model changes on done/paused workstreams, gate-aware skill alternatives, `manifest_only`, post-write handoff digests, and `done` phase termination. No behavioral finding was deferred.
- **Verification gaps (8):** closed with 22 regression tests: hash rejection, ticket evidence outside/missing, the `set`-path ticket-done guard, the summary latest-updated fallback, gate-aware test-family aliases, `validate` on ticket evidence, ticket-evidence leaf creation, and `set --project-root` artifact containment.
- **Structure (31):** applied the budget and duplication fixes. `SKILL.md` moved Headless to `references/headless.md` and is 2,495 tokens (budget 2,500); `ledger-schema.md` is 4,412 (budget 4,500). The three PRESERVE rows were kept. The remaining rows are editorial moves that do not change a rule; the false `step files` and `{repo}` claims were corrected.
- **Prose (18):** all applied, including the `resume trail` contradiction, the eval README's input count, the `byte-identical to the hashes` wording, the `--plan` rule, the setup `.gitignore` path, the memlog correction pointer, and the `§ Resume semantics` spacing.
- **Evals:** the pre-fix run graded 110/112 (failures: `status-empty` default wording, `fix-trivial-ready` symlinked out-of-root resolution). The post-fix run graded **109/112**: both pre-fix failures are gone; the three remaining rows are harness path isolation (`continue-with-ledger` ×2 for a `../../../_bmad` symlink resolution, `start-greenfield` ×1 for a `/tmp` scratch write). Those are documented harness/model limits, and `references/headless.md` now names the system temp directory explicitly.

## Round 11 review (2026-11-24, open)

Source: `2026-11-24-bmad-sdlc-r11.md` / `.findings.json` (24 findings: 6 adversarial, 12 edge-case, 4 verification-gap, 2 structure; overlaps kept).

Scope: the new role-based SDLC split (PM/DEV/QA) on top of HEAD `19f68f2` plus the staged working-tree changes. Status: `[ ]` open, `[~]` in progress, `[x]` fixed, `[-]` deferred (reason).

Verification state at review time: **259/259** unit tests pass; **12/12** quality eval cases executed and graded pass; `package.sh --check` in sync. The eval pass is not evidence for the role feature — its only role case is confounded (V1).

Highest-impact open items: `summary` drops the role fields on a paused or closed workstream (A1); the role is resolved from the recommended phase, not the active phase, so `close.mark_done` flips a trivial fix to QA (A2); the handoff table has no PM→QA or QA→DEV row (A7); DEV owns review and done, defeating separation of duties (A6); a malformed role config bricks every subcommand (A4).

### Phase 0 — decisions (record as D28 in `docs/bmad-sdlc.md`)

- [x] **D1** Review and done moved to QA (`build.review`, `build.done` prefixes); the audit action override is gone.
- [x] **D2** A role switch is persisted as `workstream.role_override` with a `role` verb and a logged reason; `--role` stays a one-read view; resume, resize, and done clear it.
- [x] **D3** `close.mark_done` and `<phase>.unblock` are role-free conductor actions (`role_free: true`, `role: null`).

### Phase 1 — runtime

- [x] **A1** `summary` emits `current_role`/`role_source` with no active workstream (paused and closed), resolved from the last workstream's stored phase; `pm`/`default` is reachable on an empty ledger.
- [x] **A2** The role resolves from `workstream.current_phase`; `summary.workstream.current_phase` is no longer rewritten to the recommended phase.
- [x] **A3** `role --role <role> --reason` persists and logs; `role --clear` removes it; resume, resize, and done clear it.
- [x] **A4** Role config loads lazily in `summary` (and the role/gate-write paths), never in `build_parser`; a malformed TOML fails with JSON while `detect`, `init`, `validate`, and `--help` still work.
- [x] **A5** An unowned action or unmapped phase fails with `ok:false` naming it; no `pm` default for a mapped phase.
- [x] **E1** `validate_role_config` checks types, role names, phase/track mappings, and advisory prefix; `roles.*.phases` was removed from the config and is rejected if reintroduced.
- [x] **E2** `--role` is lowercased; an invalid value returns JSON instead of an exit-2 usage error.
- [x] **E3** `headless.md` defines `blocked` for a role mismatch, with `blocked_by` naming the action.
- [x] **E4** `phases[]` and `workstreams_detail` carry `role`; `menu.md` reads `phases[].role` for the `⇄` marker.
- [x] **E5** The handoff brief no longer passes `--action`; `verify-return` takes `--expect-role`/`--expect-action`.
- [x] **E6** Per-ticket recovery uses `ticket --id … --gate … --status blocked`; unknown ticket gates name the valid ids.
- [x] **E7** Conductor-only actions are role-free and never force a handoff.

### Phase 2 — ownership and handoff documents

- [x] **A6** Config, `phase-map.md`, and the overlays give review and done to QA; the DEV overlay says DEV never self-approves.
- [x] **A7** One transition table in `handoff-protocol.md` with PM→QA, QA→DEV, qualified PM→DEV, rollbacks, and within-role advances; overlays link to it.
- [x] **A8** The trigger is `next_action.role_allowed: false`; DEV→QA fires on `phases.build` done, not on a passed gate.
- [x] **A9** One blocked-handoff shape in `handoff-protocol.md` (ordered `blocked_by`, `pointer`, retained `next_action`); the QA overlay links to it.
- [x] **A10** The return contract carries `role` and `action`; `verify-return` checks them; gate writes log the acting role (`--as`, default `current_role`) and a foreign role needs `--reason`.

### Phase 3 — verification

- [x] **V1** `role-explicit-qa` stages the plan skills, so a role-blind run reports `ready` and fails; the correct run is `blocked` naming qa and pm. `role-control-pm` is the no-`Role:` control that reaches `frame.spec`.
- [x] **V2** Role tests import `role_for_action`/`role_is_free`/`assert_phase_mapped`, derive the action set from `ALL_ACTION_IDS`, pass `--model v6`, and cover the optional `role_allowed` case.
- [x] **A11** `owner()` is gone; the suite asserts QA owns `build.review`/`build.done` through the imported resolver.
- [x] **V3** `test_default_config_matches_the_toml` pins `DEFAULT_ROLE_CONFIG` to `role-config.toml`.
- [x] **V4** `role-qa-menu` stages the verify-phase fixture and asserts verify.trace is offered, DEV-only build actions are hidden, and Build is marked `⇄`; `Role: <role>` is documented as an accepted input form.
- [ ] Re-run quality plus baseline after Phases 1–2; grade every transcript per `evals/README.md`.

### Phase 4 — structure and hygiene

- [x] **S1** Collapsed the duplication: base phase tables carry a `Role` column, the overlays keep only role deltas and links, one gate table and one transition table remain.
- [x] **S2** Recorded D27/D28 in the design-doc header and reconciled D5; moved the trigger caveat above its command; dropped the duplicate `continue-with-ledger` assertion; added the path-scope line to the role case.

### Verification after the fixes

- **276/276** unittest cases pass (253 helper + 23 role).
- `package.sh --check` is in sync; `quick_validate`, `prepass-workflow-integrity`, `scan-path-standards`, `scan-scripts`, and `prepass-prompt-metrics` are clean.
- Focused role eval run `~/bmad-evals/bmad-sdlc-r11-roles/20261124-171044-r11-roles`: 3/3 cases executed, **24/24 expectations** graded pass beside each transcript (`role-explicit-qa`, `role-control-pm`, `role-qa-menu`).
- The full quality + baseline re-run (finding 16) is still open; the earlier 12/12 run predates these fixes.

## Round 12 review (2026-11-24) — closed

Source: `2026-11-24-bmad-sdlc-r12.md` / `.findings.json` (48 findings: 15 adversarial, 9 edge-case, 9 verification-gap, 7 structure, 8 prose, after merging overlaps). Status: `[ ]` open, `[~]` in progress, `[x]` fixed, `[-]` deferred (reason).

Scope: the whole skill at HEAD `685f750`, including the r11 fixes. This round also closes round 11's last open item: the full quality run was re-executed and every transcript graded.

Verification state at review time: **14/14** quality cases executed and graded, **130/135** expectations pass (5 cases carry a failure: 3 path escapes, 1 abbreviated track list, 1 missing `memlog` key); the three role cases were executed for the first time; `package.sh --check` in sync. The role gates themselves held — a role-blind implementation would have failed `role-explicit-qa` and `role-control-pm`. The unit suite was not verified end-to-end on the live tree: a concurrent edit interrupted it. On a pristine copy of `685f750` the role suite passes 23/23 and the full run reached 128/128 with no failures before a 25-minute cap.

Highest-impact open items: the headless block's field set is defined twice with opposite rules (R12-02); `blocked_by` is a gate list in one file and an action in another (R12-03); the per-ticket DEV→QA handoff has no transition row (R12-05); `verify-return` does not check role-vs-action ownership (R12-14); self-approval leaves no trace because the actor is never stored on the gate (R12-15); the isolation guardrail is contradicted by activation, and three eval runs escaped the root through `{skill-root}/..` to find the resolver.

### Contract
- [x] **R12-01** `summary` now emits `actions[]` (every action, every phase, with `role`/`role_free`/`role_allowed` and its `gate`); `SKILL.md` steps 8/10 and loop step 2, `menu.md` §Action menu, and `ledger-schema.md` §Summary shape all filter on it.
- [x] **R12-02** One field set: `headless.md` §Emitted block owns the key list (keep the position keys, omit the three per-level lists, `tickets`, and `actions`); `SKILL.md` steps 10 and loop step 2, and `handoff-protocol.md` §Headless JSON point at it.
- [x] **R12-03** `blocked_by` is an ordered array of action ids starting with `next_action.action`, stated once in `handoff-protocol.md` §Headless JSON and matched by `headless.md`, the example, and the eval rubric.
- [x] **R12-04** `gate-matrix.md` §intro now says a gate id is not always an action id and points at `next_action.action`/`next_action.role`; `plan.requirements` → `frame.spec`/`plan.prd` is the worked case.
- [x] **R12-05** `handoff-protocol.md` §Transition table splits DEV → QA into a per-ticket row (`build.ticket` decided, that ticket's `build.review` open or blocked, build still active) and the existing per-phase row.
- [x] **R12-06** `menu.md` §Phase menu and `phase-map.md` §Build phase mark Build as a mixed phase: `⇄` means another role owns it, and QA enters to run the actions it owns (`build.review`, `build.done`).
- [x] **R12-09** `roles.*.name`/`references` are gone from the config, its validator, and the docs; a role id names its overlay directory.
- [x] **R12-10** The description and activation step 4 accept the ids in `role-config.toml`, with `pm|dev|qa` as the shipped defaults.
- [x] **R12-12** `role --clear` now refuses on a paused workstream, matching "a paused workstream refuses writes".
- [x] **R12-13** `build.auto`/`build.loop` show `—` in the Gate column with a note that each built ticket still needs its own `build.ticket` gate.

### Ownership
- [x] **R12-11** `validate` rejects a `role_override` that is not in `role-config.toml`, and `resolve_current_role` fails with JSON naming the valid roles instead of silently disabling every action.
- [x] **R12-14** `verify-return` now requires the returned role to own the returned action (role-free actions exempt) and reports the ownership reason; the role test asserts a QA-labelled `build.ticket` is refused.
- [x] **R12-15** Every gate decision stores `actor` on the node (from `--as` or the resolved role, never from a payload); `guard_self_approval` refuses a `build.review`/`build.done` by the role that decided `build.ticket`, including through a whole-ticket replacement.
- [x] **R12-16** `phases.<p>.status` writes resolve the acting role, log it, and need `--reason` when the actor differs from the phase's owner.
- [x] **R12-17** `workstreams_detail[]` now carries `role_source`, and each brief's `next_action` gets the same role annotations (unowned legacy actions degrade to `role: null`, `role_allowed: false`).
- [x] **R12-18** `DEFAULT_ROLE_CONFIG` is deleted: a missing `references/role-config.toml` fails with JSON naming the path, and the equality test is replaced by a missing-config test.

### Isolation and evals
- [x] **R12-07** The isolation guardrail is scoped: no writes outside `{project-root}`, reads outside limited to named `{skill-root}` files, a missing resolver means reading `{skill-root}/customize.toml` in place, and `{skill-root}/..` is forbidden. Activation step 1 repeats the rule.
- [x] **R12-08** The guardrail names the real files (`evals/cases.json`, `queries.json`, `adapter.json`, rubrics), bans opening their contents rather than seeing `evals/`, and every rubric line says the same.

### Verification
- [x] **R12-19** `_gate_owner` derives `--as` from the imported resolver (`role_for_action`), so the main suite exercises the real ownership table.
- [x] **R12-20** Test: DEV writing `gates.verify.trace` is refused ("belongs to qa") and accepted with `--as qa`, with the audit line naming qa.
- [x] **R12-21** Test: a phase blocked with every gate decided recommends `<phase>.unblock` with `role_free: true`, not `close.mark_done`.
- [x] **R12-22** Test: every per-phase gate list is scoped to its own phase and `required_open` matches the phase's gate entries.
- [x] **R12-23** Test: a return for `build.review` passed as `--expect-action build.ticket` is refused with the action-mismatch reason.
- [x] **R12-24** Tests: `role --clear` (paused refusal, then clear with the audit line) and `init --model` on an existing ledger (paused refusal, then the reasoned change).
- [x] **R12-25** Test: the packaged tree contains every file `SKILL.md` names, `role-config.toml`, `customize.toml`, the template, and the shipped tests, and no `evals/`.
- [x] **R12-26** Rubrics gain: the headless key set, an audit-trail assertion for every case that writes, an `assumptions`-vs-detector check, and a derived-status check on the two role cases.
- [x] **R12-27** Three cases added: `scope-capture`, `force-headless`, `consent-before-commit`.
- [x] **R12-28** The duplicated `"unknown role"` key is split into `phase_roles`/`track_roles` labels; unknown-track cases were added.

### Smaller and editorial
- [x] **R12-29** A phase-evidence append must name an existing non-empty file inside the root; reconcile's dangling-pointer handling is tested by deleting the file after the write.
- [x] **R12-30** The unreachable `elif` after the root-inference failure is deleted; the evidence scan is unconditional past the check.
- [x] **R12-31** `[track_roles]` rejects a key that is not a track, with tests.
- [x] **R12-32** The next-action reason maps `blocked`, `skipped without a reason`, `overridden without a reason`, else `open`.
- [x] **R12-33** `summary --project-root` fails when the directory does not exist instead of reporting every skill missing.
- [x] **R12-34** `handoff-protocol.md` is reordered: one Contents, no divider, §Role transitions and §Headless JSON in the main flow, every heading indexed.
- [x] **R12-35** The handoff contract exists once in `handoff-protocol.md`; `SKILL.md` loop step 4 is a pointer plus the role check.
- [x] **R12-36** `headless.md` owns the block's field set; `handoff-protocol.md` §Headless JSON owns only the role-mismatch fields and shows that subset, so neither file is incomplete alone.
- [x] **R12-37** The seven overlay restatements are collapsed to pointers at the one transition table.
- [x] **R12-38** `SKILL.md` §References splits the activation set from step-triggered files, moves script arguments into their own table, and adds `customize.toml`.
- [x] **R12-39** The role-mismatch handler is folded into loop step 4, before the handoff and the ledger write.
- [x] **R12-40** Precedence is its own section after §Resolution rules; `<phase>.unblock` and its clearing recipe moved to `ledger-schema.md` §A blocked phase.
- [x] **R12-41** The gate table column is `Level`; the track/size detail stays in the prose.
- [x] **R12-42** "Plan" no longer names the ledger: SKILL.md overview, activation step 6, guardrail, `ledger-schema.md`, the template, and `customize.toml` say "ledger".
- [x] **R12-43** "Overlay" is reserved for the role files; the ledger "records SDLC state only".
- [x] **R12-44** The brief rule reads "`<resolved ledger path>` or `<resolved audit trail (memlog) path>`".
- [x] **R12-45** Role resolution says "track rule" and "longest matching action-id prefix"; "override" is left to the reasoned gate or role exception.
- [x] **R12-46** The return template uses `<done|blocked|needs_input>` and `<pm|dev|qa>` and says to fill every `<...>`.
- [x] **R12-47** The role-free set is stated once (`advisory.*`, `close.mark_done`, `<phase>.unblock`), and the prohibition is "no single role performs all three on the same ticket".
- [x] **R12-48** The hand-edit fallback is a bullet list; the emitted-block rule is one sentence per obligation.

### Verification after the fixes

- **290/290** unittest cases pass (`uv run --no-cache python -m unittest discover -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'`, 290 tests in 962 s). The suite grew from 276 by 14 role cases (action catalog, blocked-phase unblock, per-phase scoping, workstream-detail roles, self-approval runtime and `validate` proof, foreign phase advance, unknown `role_override`, `role --clear`, init model change, actor recording, phase-gate foreign actor, mismatched `--expect-action`, missing role config, unknown track keys) and the package-content case.
- `package.sh --check` is in sync after repackaging.
- The eval suite is updated but **not re-graded in this pass**: three cases were added and every headless/role rubric gained the key-set, memlog, assumptions, and derived-status assertions. Grading is a review-time activity (`evals/README.md` §Grading); running 17 cases without reading each transcript would produce a score that is not evidence, which the README explicitly warns against. The next review round should execute and grade it.
