<!-- bmad:context -->
<!-- Verified 2026-11-12 against e82c98a. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## bmad-sdlc

A BMAD module built around one conductor skill that routes the whole delivery lifecycle to specialist BMAD skills from a committed ledger, so a session resumes without re-interviewing. Python 3.11+ helper scripts run under `uv` (PEP 723); the rest is Markdown. No build step and no CI. Design, gate matrix, and decision log: `docs/bmad-sdlc.md`. Authoring memory: `docs/bmad-sdlc-build.memlog.md`.

## Policy

- Never edit vendor BMAD skills under `.agents/skills/bmad-*/` — all except `bmad-sdlc`. Customize with a sidecar: `_bmad/custom/<skill>.toml` (team, committed) or `<skill>.user.toml` (personal, ignored).
- Never edit `_bmad/_config/` or `_bmad/config.toml`; the BMAD installer owns them. Team config overrides go in `_bmad/custom/config.toml`.
- Never hand-edit `.github/agents/*.agent.md`; they are rendered from the skills for the `github-copilot` IDE target.
- Commit directly to `main`.
- Commit `_bmad-output/sdlc/plan.yaml` and `.memlog.md`; they are durable state, not scratch output.

## Where things are

- Canonical skill: `.agents/skills/bmad-sdlc/` — `SKILL.md` (activation and conductor loop), `references/` (phase map, gate matrix, ledger schema, version adapters, handoff protocol, menu), `customize.toml` (base config).
- Ledger helper: `.agents/skills/bmad-sdlc/scripts/sdlc_plan.py`; tests in `scripts/tests/`; cases in `evals/`.
- Distributable module: `skills/bmad-sdlc-module/`; install instructions in `setup/SKILL.md`.
- Runtime state: `_bmad-output/sdlc/plan.yaml` and `.memlog.md`. Authoring state: `.analysis/` (gitignored).

## Running and verifying

- Run every helper and test with `uv run --no-cache`; plain `python3` fails with `ModuleNotFoundError: ruamel` because the PEP 723 header supplies the dependency.
- Tests: `uv run --no-cache python -m unittest discover -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'` — 54 tests, ~4 min.
- Detector: `uv run --no-cache .agents/skills/bmad-sdlc/scripts/sdlc_plan.py detect --project-root .`
- Evals: pass `--output-dir ~/bmad-evals/bmad-sdlc` and the `XDG_*` passthrough vars; an output directory under `.agents/skills/` lets the bare baseline discover the real skill.
- No CI exists; these commands are the verification surface.

## Conventions that differ from defaults

- `.agents/skills/bmad-sdlc/` is canonical. `skills/bmad-sdlc-module/skills/bmad-sdlc/` is generated — `package.sh` deletes and re-syncs it, so hand-edits there are lost. Edit the source, then repackage.
- The ledger is an overlay; `sprint-status.yaml` / `tickets.toml` stay the truth for ticket status. Never copy statuses into `plan.yaml`.
- Skill files refer to paths as `{skill-root}` and `{project-root}`; never hardcode absolute paths.
- The module help entry only appears after the BMAD installer assembles `_bmad/bmad-sdlc/module-help.csv`; copying it is not registration.

## Known pitfalls

- The `continue-with-ledger` eval case stages the live ledger and expects `ws-001` / `feature` / `epic` with `plan.requirements` open; restore the ledger before running it.

<!-- /bmad:context -->
