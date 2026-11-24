#!/usr/bin/env python3
"""Test that DEV role cannot access plan actions."""
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

def test_dev_cannot_access_plan_actions():
    """DEV role should only see build actions, not plan actions."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        # Initialize a fix project (starts at build)
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Fix Bug",
            "--track", "fix",
            "--size", "one-session",
        )
        
        # Complete plan phase gates
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.requirements.status",
            "--value", "passed",
        )
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.plan.status",
            "--value", "done",
        )
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Next action should be build.ticket
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.ticket", \
            f"Expected build.ticket, got {next_action.get('action')}"
        
        # Check that plan actions are not available
        optional_actions = [a.get("action", "") for a in summary.get("optional_actions", [])]
        plan_actions = [a for a in optional_actions if a.startswith("plan.")]
        assert not plan_actions, f"DEV should not see plan actions: {plan_actions}"
        
        print("✓ DEV cannot access plan actions")

def test_dev_cannot_access_verify_close_actions():
    """DEV role should not see verify/close actions until build is complete."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Fix Bug",
            "--track", "fix",
            "--size", "one-session",
        )
        
        # Complete plan phase
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.requirements.status",
            "--value", "passed",
        )
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.plan.status",
            "--value", "done",
        )
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Should not see verify/close actions
        optional_actions = [a.get("action", "") for a in summary.get("optional_actions", [])]
        verify_actions = [a for a in optional_actions if a.startswith("verify.")]
        close_actions = [a for a in optional_actions if a.startswith("close.")]
        assert not verify_actions, f"DEV should not see verify actions: {verify_actions}"
        assert not close_actions, f"DEV should not see close actions: {close_actions}"
        
        print("✓ DEV cannot access verify/close actions")

if __name__ == "__main__":
    test_dev_cannot_access_plan_actions()
    test_dev_cannot_access_verify_close_actions()
    print("All DEV isolation tests passed!")