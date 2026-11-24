#!/usr/bin/env python3
"""Test auto-detect: feature track PM then DEV transition."""
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

def test_feature_pm_then_dev_transition():
    """Feature track: PM does plan, then transitions to DEV for build."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "New Feature",
            "--track", "feature",
            "--size", "epic",
        )
        
        # Initially in PM role (plan phase)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action", "").startswith("frame.") or \
               next_action.get("action", "").startswith("plan."), \
            f"Expected PM action, got {next_action.get('action')}"
        
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
        
        # Now should transition to solution phase (still PM for solution setup)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("phase") == "solution", \
            f"Expected solution phase, got {next_action.get('phase')}"
        
        # Complete solution phase (skip for simplicity)
        for gate in ("test_design", "framework", "ci"):
            run(
                "set",
                "--plan", str(ledger),
                "--workstream", "ws-001",
                "--path", f"gates.solution.{gate}.status",
                "--value", "skipped",
                "--reason", "not applicable",
            )
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.solution.status",
            "--value", "skipped",
        )
        
        # Now should be in build phase (DEV role)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.ticket", \
            f"Expected build.ticket (DEV), got {next_action.get('action')}"
        assert next_action.get("phase") == "build", \
            f"Expected build phase, got {next_action.get('phase')}"
        
        print("✓ Feature: PM → DEV transition works")

def test_feature_one_session_pm_then_dev():
    """Feature one-session: PM does frame.spec, then DEV builds."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "One Session Feature",
            "--track", "feature",
            "--size", "one-session",
        )
        
        # Should start with PM action (frame.spec)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "frame.spec", \
            f"Expected frame.spec, got {next_action.get('action')}"
        
        # Complete frame.spec (plan.requirements gate)
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.requirements.status",
            "--value", "passed",
        )
        
        # Plan.stories is optional for one-session fix/feature
        # Next should be build.ticket (DEV role)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        # For one-session feature after requirements, can go to build
        assert next_action.get("action") in ("build.ticket", "plan.stories"), \
            f"Expected build.ticket or plan.stories, got {next_action.get('action')}"
        
        print("✓ Feature one-session: PM → DEV transition works")

if __name__ == "__main__":
    test_feature_pm_then_dev_transition()
    test_feature_one_session_pm_then_dev()
    print("All feature PM→DEV tests passed!")