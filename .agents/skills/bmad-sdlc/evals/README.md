# bmad-sdlc evals

| File | Purpose |
|---|---|
| `cases.json` | Quality/baseline cases: input, rubric, optional state prefix, optional fixture paths. Routing cases use the skill's headless contract. |
| `queries.json` | Trigger cases: should this description fire? |
| `adapter.json` | opencode invocation, skill discovery path, and provider env passthrough. |

These evals use the stock `bmad-eval-runner` skill. They do not modify it.

## Run

Two constraints shape the command:

- **Write the run outside `.agents/`.** opencode discovers skills by walking up from the working directory. A run folder under `.agents/skills/` lets the `bare` config find the real skill, so the baseline becomes skill-vs-skill.
- **Pass the runtime env.** The runner builds a clean `HOME`; `XDG_DATA_HOME` and `XDG_CONFIG_HOME` let it find the provider auth/config. The adapter lists them under `env_passthrough`.

From the repo root. The first invocation grades the skill's own output (`quality`); the second adds the bare baseline for comparison. `--mode` is a single-value flag: passing it twice keeps only the last value, so run the two modes as separate invocations.

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

Trigger mode:

```bash
XDG_DATA_HOME="$HOME/.local/share" XDG_CONFIG_HOME="$HOME/.config" \
  uv run --no-cache .agents/skills/bmad-eval-runner/scripts/run_triggers.py \
  --skill-path .agents/skills/bmad-sdlc \
  --queries .agents/skills/bmad-sdlc/evals/queries.json \
  --output-dir ~/bmad-evals/bmad-sdlc
```

**Trigger mode is not usable with the stock runner and opencode.** `run_triggers.py` parses Anthropic-style `assistant.message.content[].tool_use` events. Opencode emits `{"type":"tool_use","part":{"type":"tool","tool":"skill","state":{"input":…}}}`, so a real load is reported as 0.0. The trigger query set is still useful for a runtime with a matching parser; do not treat these numbers as verification of description routing and do not tune the description from them until a runner can parse opencode events. Do not edit the vendor runner to work around it.

## Grading

Quality mode captures transcripts; it does not grade them. Spawn the grader from `bmad-eval-runner/references/grader.md` per case, passing the case's rubric, transcript, `cwd/`, and a `grading.json` path beside the transcript. No partial credit; flag weak assertions and any case that read the run metadata. A score without those `grading.json` files is not evidence, so do not quote one. The rubrics assert the persisted state they can observe (a written ledger, its track/size/model, or the absence of one), so a run that prints the right JSON but writes nothing fails.

`scripts/tests/test_sdlc_plan.py` covers the deterministic write loop: set a gate, refuse an override without a reason, reopen a decided gate with a reason, delete a ticket, advance a phase, block `done` on open review, and reject a handoff return. These LLM cases do not cover it. Add an eval case only when the question is about what the model says or chooses; use the unit suite for ledger behavior.

## Case state

- Cases that route, recommend, or start a workstream say `Run headless.` and supply a name, track, and size. The skill's headless contract forbids a menu, so the case cannot hang waiting for an answer.
- `continue-with-ledger` and `status-readonly` stay conversational because they finish without a menu.
- `continue-with-ledger` stages the project's live `_bmad-output/sdlc/plan.yaml` and `.memlog.md`, because the skill reads those paths. Its rubric is state-agnostic: it asserts that the response resumes the staged workstream and its recorded next gate, not a specific `ws-001` state, so ordinary project progress does not break the case. It also asserts that the staged ledger records no new workstream, that no gate was advanced to passed or overridden, and that every file the skill writes outside the harness caches stays under `_bmad-output/sdlc/`. The stock runner stages a fixture only at the path written in `files`; it cannot pin an open `plan.requirements` at a different target path without a harness change.
- `fix-trivial`, `missing-build`, `fix-one-session`, and `feature-one-session` are build-first cases: they supply name/track/size so the headless contract reaches `build.ticket` (or `build.review` for audit), then assert the missing-skill block. A `needs_input` answer is a contract failure for these cases.

## Known limitations

**Case metadata is reachable from the run.** The runner puts `case.json` (including its rubric) in the parent of `cwd/`, and symlinks the whole skill into `cwd/.agents/skills/bmad-sdlc`, so `evals/cases.json` is readable too. A skill that explores the project root can read either and self-grade. The case inputs say "work only in the project root", and `SKILL.md` §Guardrails forbids reading eval metadata; treat a run that did so as contaminated. A harness that isolates the metadata and copies a pruned skill is the real fix.

**The skill symlink can leave the case root.** Because the skill is an absolute symlink, resolving `{project-root}/_bmad/scripts/resolve_customization.py` from the skill directory can land in the authoring repo rather than the case. The rubric now scopes writes to `_bmad-output/sdlc/` and forbids out-of-root reads other than the harness skill, but read scope is only partly observable from a transcript; review it when grading.

**The clean run has no BMAD install.** Every case exercises the `unknown`/fallback path and missing-skill behavior; no case requires `status: ready` with an installed skill. The v6/current happy paths and the installed-model skill mapping are covered by the ledger tests; the `ready` status itself is conductor prose and is not asserted by any test. A case that stages a BMAD install needs a harness that can stage directories, not just individual files.

**Token and tool accounting targets Anthropic-style transcripts.** Opencode emits `step_finish`/`tool_use` events, so `timing.json` may report zero tokens and zero tool calls even when the transcript and artifacts are complete. Treat the token columns as unknown rather than as zero cost.
