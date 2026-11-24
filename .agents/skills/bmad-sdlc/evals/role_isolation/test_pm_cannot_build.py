#!/usr/bin/env python3
"""Test that PM role cannot access build actions."""
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

def test_pm_cannot_access_build_actions():
    """PM role should only see plan actions, not build actions."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        # Initialize a greenfield project
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Test Product",
            "--track", "greenfield",
            "--size", "epic",
        )
        
        # Set PM role by passing plan.requirements as passed
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.requirements.status",
            "--value", "passed",
        )
        
        # Get summary - should show PM actions only
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Check that next_action is a plan action (not build)
        next_action = summary.get("next_action", {})
        assert next_action.get("action", "").startswith("plan."), \
            f"Expected plan action, got {next_action.get('action')}"
        
        # Check that build actions are not in optional_actions
        optional_actions = [a.get("action", "") for a in summary.get("optional_actions", [])]
        build_actions = [a for a in optional_actions if a.startswith("build.")]
        assert not build_actions, f"PM should not see build actions: {build_actions}"
        
        print("✓ PM cannot access build actions")

def test_pm_cannot_access_verify_close_actions():
    """PM role should not see verify/close actions."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Test Product",
            "--track", "greenfield",
            "--size", "epic",
        )
        
        # Complete plan phase
        for gate in ("requirements", "stories", "sprint"):
            run(
                "set",
                "--plan", str(ledger),
                "--workstream", "ws-001",
                "--path", f"gates.plan.{gate}.status",
                "--value", "passed",
            )
        for gate in ("ux", "architecture"):
            run(
                "set",
                "--plan", str(ledger),
                "--workstream", "ws-001",
                "--path", f"gates.plan.{gate}.status",
                "--value", "skipped",
                "--reason", "not applicable",
            )
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.plan.status",
            "--value", "done",
        )
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Next action should be solution phase, not verify/close
        next_action = summary.get("next_action", {})
        assert next_action.get("phase") == "solution", \
            f"Expected solution phase, got {next_action.get('phase')}"
        assert not next_action.get("action", "").startswith("verify."), \
            f"PM should not see verify actions"
        assert not next_action.get("action", "").startswith("close."), \
            f"PM should not see close actions"
        
        print("✓ PM cannot access verify/close actions")

if __name__ == "__main__":
    test_pm_cannot_access_build_actions()
    test_pm_cannot_access_verify_close_actions()
    print("All PM isolation tests passed!")