#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Copy bmad-sdlc skill to sdlc-plugins with module metadata for agent plugin spec.

Safely updates the target directory without destroying git history.
"""

import json
import shutil
import sys
from pathlib import Path


IGNORE_PATTERNS = (
    ".analysis",
    ".memlog.md",
    "evals",
    "__pycache__",
    "*.pyc",
    ".DS_Store",
    ".git",  # Never copy .git from source
)


def should_ignore(name: str) -> bool:
    for pattern in IGNORE_PATTERNS:
        if pattern.endswith("*"):
            if name.startswith(pattern[:-1]):
                return True
        elif name == pattern:
            return True
    return False


def copy_tree_safe(src: Path, dst: Path) -> None:
    """Copy directory tree, skipping ignored patterns, without removing dst first."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if should_ignore(item.name):
            continue
        dst_item = dst / item.name
        if item.is_dir():
            copy_tree_safe(item, dst_item)
        else:
            shutil.copy2(item, dst_item)


def remove_orphaned_files(src: Path, dst: Path) -> list[str]:
    """Remove files in dst that no longer exist in src (respecting ignore patterns)."""
    removed = []
    if not dst.exists():
        return removed
    for item in dst.iterdir():
        if should_ignore(item.name):
            continue
        src_item = src / item.name
        if not src_item.exists():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed.append(str(item.relative_to(dst.parent)))
    return removed


def is_git_repo(path: Path) -> bool:
    """Check if path is a git repository (has .git directory)."""
    return (path / ".git").exists()


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    source_skill = repo_root / ".agents" / "skills" / "bmad-sdlc"
    target_plugins = Path("/Users/dhanoopbhaskar/git/sdlc-plugins/plugins/bmad/skills")
    target_skill = target_plugins / "bmad-sdlc"

    if not source_skill.exists():
        print(f"Error: Source skill not found at {source_skill}", file=sys.stderr)
        return 1

    # Safety check: warn if target is a git repo but continue (we preserve .git)
    if target_plugins.exists() and is_git_repo(target_plugins):
        print(f"Note: Target {target_plugins} is a git repository — preserving .git and updating tracked files.")

    # Ensure target parent exists
    target_plugins.mkdir(parents=True, exist_ok=True)

    # Copy skill directory (merge, don't destroy)
    print(f"Syncing {source_skill} -> {target_skill}")
    copy_tree_safe(source_skill, target_skill)

    # Remove orphaned files in target that no longer exist in source
    orphans = remove_orphaned_files(source_skill, target_skill)
    if orphans:
        print(f"Removed orphaned files: {', '.join(orphans)}")

    # Read version
    version_file = target_skill / "VERSION"
    version = version_file.read_text().strip() if version_file.exists() else "0.0.0"

    # Create assets directory if not exists
    assets_dir = target_skill / "assets"
    assets_dir.mkdir(exist_ok=True)

    # Create/overwrite module.yaml
    module_yaml = f"""code: sdlc
name: BMAD SDLC Conductor
description: "One skill for the whole BMAD software development lifecycle. Detects project model, keeps a durable ledger, presents a phase/action menu with gates, hands off to the right skill, and validates artifacts."
module_version: {version}
default_selected: false
module_greeting: >
  BMAD SDLC installed — the conductor skill that runs the full BMAD delivery
  lifecycle from a single durable ledger. It detects your project model (v6 or
  current), presents a two-level menu filtered by role, hands each phase to the
  correct skill in a fresh context, validates the artifact, and asks at every
  gate. Run `bmad-sdlc` to start.
"""
    module_yaml_path = assets_dir / "module.yaml"
    module_yaml_path.write_text(module_yaml)
    print(f"Created {module_yaml_path}")

    # Create/overwrite module-help.csv
    module_help_csv = """module,skill,display-name,menu-code,description,action,args,phase,preceded-by,followed-by,required,output-location,outputs
BMAD SDLC Conductor,bmad-sdlc,Start New SDLC,S1,"Start a new product with BMAD SDLC — detect model, create ledger, enter plan phase.",start,"{-H: headless mode}|{--role: pm|dev|qa}|{--name: workstream name}|{--track: greenfield|feature|fix|audit}|{--size: trivial|one-session|epic|project}",anytime,,,false,{project-root}/_bmad-output/sdlc,plan.yaml + .memlog.md
BMAD SDLC Conductor,bmad-sdlc,Continue SDLC,S2,"Continue an existing SDLC workstream — reconcile, show menu, pick action.",continue,"{-H: headless mode}|{--role: pm|dev|qa}",anytime,,,false,{project-root}/_bmad-output/sdlc,updated plan.yaml
BMAD SDLC Conductor,bmad-sdlc,Show Status,S3,"Show current workstream status, phase, gates, and next action.",status,"{-H: headless mode}|{--role: pm|dev|qa}",anytime,,,false,stdout,JSON summary
BMAD SDLC Conductor,bmad-sdlc,Reconcile Ledger,RL,"Reconcile ledger against BMAD artifacts (sprint-status.yaml, tickets.toml).",reconcile,"{-H: headless mode}",anytime,,,false,{project-root}/_bmad-output/sdlc,reconciliation report
BMAD SDLC Conductor,bmad-sdlc,Plan Stories,PS,"Run bmad-create-epics-and-stories for the active workstream.",plan.stories,"{-H: headless mode}",plan,,bmad-create-epics-and-stories,false,{project-root}/docs/epics,epics.md + stories.md
BMAD SDLC Conductor,bmad-sdlc,Create Architecture,CA,"Run bmad-architecture for the active workstream.",solution.architecture,"{-H: headless mode}",solution,,bmad-architecture,false,{project-root}/docs/architecture,ARCHITECTURE.md
BMAD SDLC Conductor,bmad-sdlc,Build Ticket,BT,"Run bmad-build for a ticket in the active workstream.",build.ticket,"{ticket-id: ticket to build}|{-H: headless mode}",build,,bmad-build,false,{project-root}/_bmad-output/sdlc,ticket artifacts
BMAD SDLC Conductor,bmad-sdlc,Review Build,RB,"Run bmad-code-review for a completed ticket.",build.review,"{ticket-id: ticket to review}|{-H: headless mode}",build,bmad-code-review,bmad-build,false,{project-root}/_bmad-output/sdlc,review findings
BMAD SDLC Conductor,bmad-sdlc,Run Tests,RT,"Run bmad-qa-generate-e2e-tests for the active workstream.",verify.tests,"{-H: headless mode}",verify,,bmad-qa-generate-e2e-tests,false,{project-root}/tests,e2e tests
BMAD SDLC Conductor,bmad-sdlc,Mark Done,MD,"Mark a ticket done after build.done gate passes.",ticket.done,"{ticket-id: ticket to close}|{-H: headless mode}",build,,,false,{project-root}/tickets.toml,updated tickets
BMAD SDLC Conductor,bmad-sdlc,Close Workstream,CW,"Close the active workstream when all phases are complete.",close.mark_done,"{-H: headless mode}|{--reason: closure reason}",close,,,false,{project-root}/_bmad-output/sdlc,closed ledger
BMAD SDLC Conductor,bmad-sdlc,Switch Role,SR,"Persist a role change for the active workstream.",role,"{role: pm|dev|qa} {reason}",anytime,,,false,{project-root}/_bmad-output/sdlc,role_override updated
"""
    module_help_path = assets_dir / "module-help.csv"
    module_help_path.write_text(module_help_csv)
    print(f"Created {module_help_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())