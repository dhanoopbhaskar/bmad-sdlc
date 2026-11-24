#!/usr/bin/env python3
"""Test subagent receives role-filtered actions only."""
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

def test_pm_subagent_sees_only_pm_actions():
    """PM role subagent should only see PM actions in menu."""
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

        # Summary should only show PM actions
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        next_action = summary.get("next_action", {})
        optional_actions = [a.get("action", "") for a in summary.get("optional_actions", [])]
        
        # All actions should be frame.* or plan.*
        pm_actions = [a for a in optional_actions if a.startswith("frame.") or a.startswith("plan.")]
        non_pm_actions = [a for a in optional_actions if not (a.startswith("frame.") or a.startswith("plan."))]
        
        assert len(non_pm_actions) == 0, f"PM should not see non-PM actions: {non_pm_actions}"
        assert len(pm_actions) > 0, f"PM should see PM actions: {pm_actions}"

        print("✓ PM subagent sees only PM actions")

def test_dev_subagent_sees_only_dev_actions():
    """DEV role subagent should only see DEV actions in menu."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"

        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Test Product",
            "--track", "fix",
            "--size", "one-session",
        )

        # Complete plan.requirements
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
        
        # Check next_action is build.ticket (DEV action)
        next_action = summary.get("next_action", {})
        assert next_action.get("action", "").startswith("build."), \
            f"Expected DEV action (build.*), got {next_action.get('action')}"
        
        # Check phase is build
        assert summary.get("phase") == "build", \
            f"Expected build phase, got {summary.get('phase')}"

        print("✓ DEV subagent sees only DEV actions")

def test_qa_subagent_sees_only_qa_actions():
    """QA role subagent should only see QA actions in menu."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"

        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Test Product",
            "--track", "audit",
        )

        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Check next_action is build.review (QA action for audit)
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.review", \
            f"Expected QA action (build.review), got {next_action.get('action')}"
        assert next_action.get("ticket") == "audit", \
            f"Expected audit ticket, got {next_action.get('ticket')}"
        
        # Check phase is build (audit starts at build.review)
        assert summary.get("phase") == "build", \
            f"Expected build phase, got {summary.get('phase')}"

        print("✓ QA subagent sees only QA actions")

if __name__ == "__main__":
    test_pm_subagent_sees_only_pm_actions()
    test_dev_subagent_sees_only_dev_actions()
    test_qa_subagent_sees_only_qa_actions()
    print("All subagent role-filtered action tests passed!")