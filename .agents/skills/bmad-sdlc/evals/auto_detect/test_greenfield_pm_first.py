#!/usr/bin/env python3
"""Test auto-detect role from ledger phase - greenfield starts with PM."""
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

def test_greenfield_starts_with_pm():
    """Greenfield project should start with PM role (plan phase)."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        # Initialize greenfield project
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "New Product",
            "--track", "greenfield",
            "--size", "epic",
        )
        
        # Get summary - should be in plan phase (PM role)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Check current phase is plan
        workstream = summary.get("workstream", {})
        assert workstream.get("current_phase") == "plan", \
            f"Expected plan phase, got {workstream.get('current_phase')}"
        
        # Next action should be frame.spec or plan.prd (PM actions)
        next_action = summary.get("next_action", {})
        assert next_action.get("action", "").startswith("frame.") or \
               next_action.get("action", "").startswith("plan."), \
            f"Expected PM action, got {next_action.get('action')}"
        
        print("✓ Greenfield starts with PM role")

def test_feature_starts_with_pm():
    """Feature project should start with PM role (plan phase)."""
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
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        workstream = summary.get("workstream", {})
        assert workstream.get("current_phase") == "plan", \
            f"Expected plan phase, got {workstream.get('current_phase')}"
        
        next_action = summary.get("next_action", {})
        assert next_action.get("action", "").startswith("frame.") or \
               next_action.get("action", "").startswith("plan."), \
            f"Expected PM action, got {next_action.get('action')}"
        
        print("✓ Feature starts with PM role")

def test_fix_starts_with_dev():
    """Fix track with one-session should start with DEV role (build phase)."""
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
        
        # For fix/one-session, plan phase is skipped, starts at build
        workstream = summary.get("workstream", {})
        # Plan phase should be skipped
        plan_phase = None
        for phase in summary.get("phases", []):
            if phase.get("phase") == "plan":
                plan_phase = phase
                break
        assert plan_phase is not None, "Plan phase not found"
        assert plan_phase.get("status") == "skipped", \
            f"Expected plan skipped, got {plan_phase.get('status')}"
        
        # Next action should be build.ticket (DEV action)
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.ticket", \
            f"Expected build.ticket, got {next_action.get('action')}"
        
        print("✓ Fix/one-session starts with DEV role")

def test_fix_trivial_starts_with_dev():
    """Fix track with trivial size should start with DEV role (build phase)."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Trivial Fix",
            "--track", "fix",
            "--size", "trivial",
        )
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.ticket", \
            f"Expected build.ticket, got {next_action.get('action')}"
        
        print("✓ Fix/trivial starts with DEV role")

def test_audit_starts_with_qa():
    """Audit track should start with QA role (build.review for audit)."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Quality Audit",
            "--track", "audit",
        )
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Plan phase skipped for audit
        plan_phase = None
        for phase in summary.get("phases", []):
            if phase.get("phase") == "plan":
                plan_phase = phase
                break
        assert plan_phase is not None, "Plan phase not found"
        assert plan_phase.get("status") == "skipped", \
            f"Expected plan skipped, got {plan_phase.get('status')}"
        
        # Next action should be build.review with audit ticket (QA action)
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.review", \
            f"Expected build.review, got {next_action.get('action')}"
        assert next_action.get("ticket") == "audit", \
            f"Expected audit ticket, got {next_action.get('ticket')}"
        
        print("✓ Audit starts with QA role")

if __name__ == "__main__":
    test_greenfield_starts_with_pm()
    test_feature_starts_with_pm()
    test_fix_starts_with_dev()
    test_fix_trivial_starts_with_dev()
    test_audit_starts_with_qa()
    print("All auto-detect tests passed!")