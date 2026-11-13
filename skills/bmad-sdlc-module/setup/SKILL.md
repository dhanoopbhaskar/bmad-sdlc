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

3. **Copy the skill.** If a copy already exists, show its path and ask before replacing it. A replacement deletes local edits, so resolve the target first and refuse anything that is not a `skills/bmad-sdlc` directory:
   ```bash
   target="{project-root}/<skills-dir>/bmad-sdlc"
   case "$target" in
     */skills/bmad-sdlc) ;;
     *) echo "refusing to replace $target" >&2; exit 1 ;;
   esac
   if [[ -e "$target" ]]; then
     mv "$target" "$target.bak-$(date +%Y%m%d%H%M%S)"
   fi
   cp -R "{module-root}/skills/bmad-sdlc" "$target"
   ```
   Delete the backup only after the copy succeeds, and only with the user's consent. The package already excludes authoring state (`.analysis/`, `.memlog.md`, caches, and `evals/`).

4. **Copy the module metadata.** The installer rebuilds `_bmad/_config/` from per-module files, so place the metadata where the installer reads it:
   ```bash
   mkdir -p "{project-root}/_bmad/bmad-sdlc"
   cp "{module-root}/module-help.csv" "{project-root}/_bmad/bmad-sdlc/module-help.csv"
   ```
   Do not write `_bmad/_config/bmad-help.csv`, `skill-manifest.csv`, or `manifest.yaml`; those are installer-managed. The shipped `customize.toml` is the base configuration; team overrides go in `_bmad/custom/bmad-sdlc.toml` and personal ones in `_bmad/custom/bmad-sdlc.user.toml`. There is no separate module config file. If the user wants the help entry visible immediately, tell them to re-run the BMAD installer, which will assemble it from `_bmad/bmad-sdlc/module-help.csv`.

5. **Verify.** Run the conductor's detector:
   ```bash
   uv run --no-cache "{project-root}/<skills-dir>/bmad-sdlc/scripts/sdlc_plan.py" \
     detect --project-root "{project-root}"
   ```
   The detector deliberately excludes the conductor from the `skills` list, so `bmad-sdlc` will not appear there; confirm the skill directory exists and read `model`. If `model` is `unknown`, BMAD is absent or its model is unrecognizable: report that as **plan-only until BMAD is installed** and continue. A plan-only install is valid; only delivery actions stay blocked.

6. **Initialize the plan (optional).** If the user wants the conductor usable immediately and no ledger exists:
   ```bash
   uv run --no-cache "{project-root}/<skills-dir>/bmad-sdlc/scripts/sdlc_plan.py" \
     init --project-root "{project-root}" --name "<project-name>" --track <track> --size <size>
   ```
   Ask for the track and size, defaulting to `feature` and `epic`. A `fix` or `audit` defaults to size `one-session`. On an existing ledger the same command appends a workstream and pauses the previously active one. If `_bmad/custom/bmad-sdlc.toml` (team) or `_bmad/custom/bmad-sdlc.user.toml` (personal) sets `ledger_path` or `memlog_path`, run `_bmad/scripts/resolve_customization.py` and pass the resolved `--plan` and `--memlog`; the command's defaults mirror the shipped `customize.toml`, not the override. Add `_bmad-output/sdlc/*.lock` to the target project's `.gitignore`; the helper leaves its lock files beside the ledger.

7. **Confirm.** Report:
   - skill path and installed version (`<skills-dir>/bmad-sdlc/VERSION` against `{module-root}/module.yaml`)
   - module metadata path
   - detected BMAD model and hub
   - ledger path (or "not initialized")
   - that `_bmad/_config/` was not touched
   - the exact next step: invoke `bmad-sdlc`.

## Update

Re-run the same steps. The `cp -R` replaces the skill; the module metadata is overwritten. The ledger is never touched, so the plan survives updates.

## Uninstall

Remove the skill directory and `_bmad/bmad-sdlc/`. Leave the ledger in place unless the user explicitly asks to delete it; it contains the delivery history.
