# bmad-sdlc evals

| File | Purpose |
|---|---|
| `cases.json` | Quality/baseline cases: input, rubric, optional state prefix, optional fixture paths. Routing cases use the skill's headless contract. |
| `queries.json` | Trigger cases: should this description fire? |
| `adapter.json` | opencode invocation, skill discovery path, and provider env passthrough. |

These evals use the stock `bmad-eval-runner` skill. They do not modify it.

## Run

**Quality mode captures transcripts; it does not grade them.** A run is evidence only after a grader reads each transcript against its rubric and writes a `grading.json` beside it (§Grading). A score without those files is not evidence.

Two constraints shape the command:

- **Write the run outside `.agents/`.** opencode discovers skills by walking up from the working directory. A run folder under `.agents/skills/` lets the `bare` config find the real skill, so the baseline becomes skill-vs-skill.
- **Pass the runtime env.** The runner builds a clean `HOME`; `XDG_DATA_HOME` and `XDG_CONFIG_HOME` let it find the provider auth/config. The adapter lists them under `env_passthrough`.

From the repo root. The first invocation runs the skill (`quality`); the second adds the bare baseline for comparison. `--mode` is a single-value flag: passing it twice keeps only the last value, so run the two modes as separate invocations.

```bash
XDG_DATA_HOME="$HOME/.local/share" XDG_CONFIG_HOME="$HOME/.config" \
  uv run --no-cache .agents/skills/bmad-eval-runner/scripts/run_evals.py \
  --cases .agents/skills/bmad-sdlc/evals/cases.json \
  --skill-path .agents/skills/bmad-sdlc \
  --output-dir ~/bmad-evals/bmad-sdlc \
  --mode quality

XDG_DATA_HOME="$HOME/.local/share" XDG_CONFIG_HOME="$HOME/.config" \
  uv run --no-cache .agents/skills/bmad-eval-runner/scripts/run_evals.py \
  --cases .agents/skills/bmad-sdlc/evals/cases.json \
  --skill-path .agents/skills/bmad-sdlc \
  --output-dir ~/bmad-evals/bmad-sdlc \
  --mode baseline
```

Trigger mode. **This mode is not usable with the stock runner and opencode:** `run_triggers.py` parses Anthropic-style `assistant.message.content[].tool_use` events, while opencode emits `{"type":"tool_use","part":{"type":"tool","tool":"skill","state":{"input":…}}}`, so a real load is reported as 0.0. The query set is still useful for a runtime with a matching parser; do not treat these numbers as verification of description routing and do not tune the description from them until a runner can parse opencode events. Do not edit the vendor runner to work around it.

```bash
XDG_DATA_HOME="$HOME/.local/share" XDG_CONFIG_HOME="$HOME/.config" \
  uv run --no-cache .agents/skills/bmad-eval-runner/scripts/run_triggers.py \
  --skill-path .agents/skills/bmad-sdlc \
  --queries .agents/skills/bmad-sdlc/evals/queries.json \
  --output-dir ~/bmad-evals/bmad-sdlc
```

## Grading

Spawn the grader from `bmad-eval-runner/references/grader.md` per case, passing the case's rubric, transcript, `cwd/`, and a `grading.json` path beside the transcript. No partial credit; flag weak assertions and any case that read the run metadata. The rubrics assert the persisted state they can observe (a written ledger, its track/size/model, or the absence of one), so a run that prints the right JSON but writes nothing fails.

## Case state

Each case exists to test what the model says or chooses; ledger behavior belongs to `scripts/tests/`, which covers the deterministic write loop and role resolution (`test_sdlc_plan.py`, `test_role_resolution.py`). Add an eval case only when the question is about the model, not about a value the unit suite can assert.

- Cases that route, recommend, or start a workstream say `Run headless.` and supply a name, track, and size. The skill's headless contract forbids a menu, so the case cannot hang waiting for an answer.
- `continue-with-ledger` and `status-readonly` stay conversational because they finish without a menu.
- `continue-with-ledger` stages the committed verify-phase fixture at `evals/_bmad-output/sdlc/plan.yaml` and `.memlog.md`, so the case always resumes the same workstream and open gate. Its rubric is state-agnostic: it asserts that the response resumes the staged workstream and its recorded next gate, not a specific `ws-001` state. It also asserts that the staged ledger records no new workstream, that no gate was advanced to passed or overridden, and that every file the skill writes outside the harness caches stays under `_bmad-output/sdlc/`. The fixture is resolved from `evals/` before the project's live ledger, because `resolve_fixtures` checks the cases directory first.
- Build-first cases (`fix-trivial`, `missing-build`, `fix-one-session`) supply name/track/size so the headless contract reaches `build.ticket` (or `build.review` for audit), then assert the missing-skill block. A `needs_input` answer is a contract failure for these cases. `feature-one-session` is planning-first: feature/one-session opens with `frame.spec`, and its rubric accepts that or `build.ticket`.
- `fix-trivial-ready` stages a fake v6 install and asserts `status: ready`. Its `files` entries are `.agents/skills/<name>/SKILL.md`; `resolve_fixtures` preserves the entry path, so the files land where `detect` scans. See §Known limitations for the fixture and staging constraints.
- `role-explicit-qa` supplies `Role: qa` (the same selection as `--role qa`) on a greenfield epic, and stages the plan skills so only role gating can block. A role-blind implementation reports `ready`; the correct run reports `blocked` with `blocked_by` naming `frame.spec`, and its refusal names both `qa` and `pm`. `role-control-pm` is the control: same fixture and skills without `Role:`, asserting `ready` at `frame.spec` for the PM.
- `role-qa-menu` is interactive, not headless. It stages the verify-phase fixture and asks for the menu with `Role: qa`; the rubric asserts `verify.trace` is offered, DEV-only `build.*` actions are hidden, and the Build phase carries the cross-role `⇄` marker from `phases[].role`.
- `scope-capture`, `force-headless`, and `consent-before-commit` cover the three model-only guardrails no unit test can reach: an out-of-scope request must be logged as `captured:` and not acted on, `init --force` must be refused headless, and a commit-and-push request must wait for consent. Their rubrics assert the transcript and the ledger, not just the JSON shape.
- Headless cases assert the emitted block's key set, not only its values: `required_open`, `conditional_open`, `optional_open`, `tickets`, and `actions` must be absent (`headless.md` §Emitted block). `status-empty` and `role-control-pm` add a derived-status check so a run that echoes a hardcoded `ready` cannot pass. Cases that block or write also assert the audit trail records it.

`Role: <role>` is an accepted input form for the activation role selection, equivalent to `--role <role>`; `SKILL.md` §On Activation step 4 defines it.

## Known limitations

**Case metadata is reachable from the run.** The runner puts `case.json` (including its rubric) in the parent of `cwd/`, and symlinks the whole skill into `cwd/.agents/skills/bmad-sdlc`, so `evals/cases.json` is readable too. The guardrail is about **opening** those files, not about seeing the directory: a skill-root listing may show `evals/`, and `evals/cases.json`, `evals/queries.json`, `evals/adapter.json`, and the staged `_bmad-output` fixture may not be read. A skill that explores the project root can still read them and self-grade, so treat any run that opened one as contaminated. A harness that isolates the metadata and copies a pruned skill is the real fix.

**The skill symlink can leave the case root.** Because the skill is an absolute symlink, resolving `{project-root}/_bmad/scripts/resolve_customization.py` from the skill directory can land in the authoring repo rather than the case. Scrub the `_bmad` path or copy the skill instead of symlinking it; read scope is only partly observable from a transcript, so review it when grading.

**Installed-model coverage is one case.** `fix-trivial-ready` stages a v6 install as individual files, which the runner reproduces as directories, so `detect` reports `v6` and the run reaches `status: ready`. The current-model (`tickets.toml`) happy path and the installed-model alias mapping are still covered only by the ledger tests. A second install fixture is the next step; a case that needs a whole module tree still needs a harness that can stage directories. The runner stages a fixture only at the path written in `files`; a target-path fixture works only when a same-path file exists under `evals/`, which is how the verify-phase ledger is staged (`files: ["_bmad-output/sdlc/plan.yaml"]`).

**Token and tool accounting targets Anthropic-style transcripts.** Opencode emits `step_finish`/`tool_use` events, so `timing.json` may report zero tokens and zero tool calls even when the transcript and artifacts are complete. Treat the token columns as unknown rather than as zero cost.
