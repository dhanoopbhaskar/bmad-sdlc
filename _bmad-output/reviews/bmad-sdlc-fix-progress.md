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

