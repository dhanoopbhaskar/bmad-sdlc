---
name: bmad-sdlc-setup
description: 'Install or update the BMAD SDLC Conductor module in a project. Use when the user says "install bmad-sdlc", "setup bmad-sdlc", or "configure the SDLC conductor".'
---

# BMAD SDLC Conductor — Setup

Install the conductor into a project's skills directory and register its module metadata. The installer owns `_bmad/_config/`; this skill never edits it.

## Inputs

- `{module-root}` — this module package's root (the parent of this `setup/` directory).
- `{project-root}` — the project that will receive the skill (`_bmad/` lives here).
- Optional argument: a skills directory. Default `.agents/skills`; use `.claude/skills` for Claude Code, `.cline/skills` for Cline, and so on.

## Steps

1. **Confirm the target.** Resolve `{project-root}`. If `_bmad/` is absent, say the project has no BMAD install; the conductor can still be copied, but every BMAD action will be blocked until BMAD is installed. Ask whether to continue.

2. **Choose the skills directory.** Use the argument if given. Otherwise prefer the directory that already contains BMAD skills: `.agents/skills` if it exists, else `.claude/skills` if it exists, else `.agents/skills`.

3. **Copy the skill.** If a copy already exists, show its path and ask before replacing it. A replacement deletes local edits, so do not run `rm -rf` without explicit consent:
   ```bash
   rm -rf "{project-root}/<skills-dir>/bmad-sdlc"
   cp -R "{module-root}/skills/bmad-sdlc" "{project-root}/<skills-dir>/bmad-sdlc"
   ```
   The package already excludes authoring state (`.analysis/`, `.memlog.md`, caches).

4. **Copy the module metadata.** The installer rebuilds `_bmad/_config/` from per-module files, so place it where it expects:
   ```bash
   mkdir -p "{project-root}/_bmad/bmad-sdlc"
   cp "{module-root}/module-help.csv" "{project-root}/_bmad/bmad-sdlc/module-help.csv"
   ```
   Do not write `_bmad/_config/bmad-help.csv`, `skill-manifest.csv`, or `manifest.yaml`; those are installer-managed. The skill's `customize.toml` is the only configuration surface; there is no separate module config file. If the user wants the help entry visible immediately, tell them to re-run the BMAD installer, which will assemble it from `_bmad/bmad-sdlc/module-help.csv`.

5. **Verify.** Run the conductor's detector:
   ```bash
   uv run --no-cache "{project-root}/<skills-dir>/bmad-sdlc/scripts/sdlc_plan.py" \
     detect --project-root "{project-root}"
   ```
   Confirm `skills` includes `bmad-sdlc` and `model` is not `unknown`. If `model` is `unknown`, the project has no recognizable BMAD install; report that and stop before claiming success.

6. **Initialize the plan (optional).** If the user wants the conductor usable immediately and no ledger exists:
   ```bash
   uv run --no-cache "{project-root}/<skills-dir>/bmad-sdlc/scripts/sdlc_plan.py" \
     init --project-root "{project-root}" --name "<project-name>" --track <track> --size <size>
   ```
   Ask for the track and size; the defaults are `feature` and `epic`, with `fix`/`audit` defaulting to `one-session`. On an existing ledger the same command appends a workstream and pauses the previously active one. If the project has a `customize.toml` override with a custom `ledger_path` or `memlog_path`, pass `--plan` and `--memlog` too; the command's defaults mirror the shipped `customize.toml`.

7. **Confirm.** Report:
   - skill path
   - module metadata path
   - detected BMAD model and hub
   - ledger path (or "not initialized")
   - that `_bmad/_config/` was not touched
   - the exact next step: invoke `bmad-sdlc`.

## Update

Re-run the same steps. The `cp -R` replaces the skill; the module metadata is overwritten. The ledger is never touched, so the plan survives updates.

## Uninstall

Remove the skill directory and `_bmad/bmad-sdlc/`. Leave the ledger in place unless the user explicitly asks to delete it; it contains the delivery history.
