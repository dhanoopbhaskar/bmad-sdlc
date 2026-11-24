#!/usr/bin/env python3
"""Test auto-detect: fix track starts with DEV."""
import json
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sdlc_plan.py"
REPO_ROOT = Path(__file__).resolve().parents[7]

def run(*args: str, cwd: Path | None = None) -> dict:
    result = subprocess.run(
        ["uv", "run", "--no-cache", str(SCRIPT), *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if not result.stdout.strip():
        raise AssertionError(f"no JSON output; stderr={result.stderr}")
    return json.loads(result.stdout)

def test_fix_one_session_dev_first():
    """Fix one-session should start with DEV (build.ticket)."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Bug Fix",
            "--track", "fix",
            "--size", "one-session",
        )
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Plan phase skipped
        plan_phase = None
        for phase in summary.get("phases", []):
            if phase.get("phase") == "plan":
                plan_phase = phase
                break
        assert plan_phase is not None
        assert plan_phase.get("status") == "skipped"
        
        # Next action is build.ticket (DEV role)
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.ticket"
        assert next_action.get("phase") == "build"
        
        print("✓ Fix one-session starts with DEV")

def test_fix_epic_pm_then_dev():
    """Fix epic should start with PM (plan.stories), then DEV."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Big Fix",
            "--track", "fix",
            "--size", "epic",
        )
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Plan phase active (not skipped for epic fix)
        workstream = summary.get("workstream", {})
        assert workstream.get("current_phase") == "plan"
        
        # Next action should be plan.stories (PM action for fix epic)
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "plan.stories"
        
        print("✓ Fix epic starts with PM")

def test_fix_can_bypass_plan_for_direct_build():
    """Fix can start directly at build if plan.stories is optional."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Direct Fix",
            "--track", "fix",
            "--size", "one-session",
        )
        
        # plan.requirements is optional for fix one-session
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        
        # Should be build.ticket since plan is skipped
        assert next_action.get("action") == "build.ticket"
        
        # Verify plan.requirements is not required
        open_gates = summary.get("open_gates", [])
        assert "plan.requirements" not in open_gates, \
            f"plan.requirements should not be required for fix one-session: {open_gates}"
        
        print("✓ Fix can bypass plan for direct build")

if __name__ == "__main__":
    test_fix_one_session_dev_first()
    test_fix_epic_pm_then_dev()
    test_fix_can_bypass_plan_for_direct_build()
    print("All fix DEV first tests passed!")