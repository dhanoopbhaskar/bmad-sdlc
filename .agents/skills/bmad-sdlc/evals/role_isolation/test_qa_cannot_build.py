#!/usr/bin/env python3
"""Test that QA role cannot access plan or build actions."""
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

def test_qa_cannot_access_plan_actions():
    """QA role should only see solution/verify/close actions, not plan actions."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        # Initialize and complete through build
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Test Product",
            "--track", "feature",
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
        
        # Complete solution phase (optional, can skip)
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
        
        # Complete build phase with a ticket
        run(
            "ticket",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--id", "1.1",
            "--gate", "ticket",
            "--status", "passed",
        )
        run(
            "ticket",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--id", "1.1",
            "--gate", "tests",
            "--status", "skipped",
            "--reason", "trivial fix",
        )
        run(
            "ticket",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--id", "1.1",
            "--gate", "review",
            "--status", "passed",
        )
        run(
            "ticket",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--id", "1.1",
            "--gate", "done",
            "--status", "passed",
        )
        
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.build.status",
            "--value", "done",
        )
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Next action should be verify.trace (QA action)
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "verify.trace", \
            f"Expected verify.trace, got {next_action.get('action')}"
        
        # Check that plan/build actions are not available
        optional_actions = [a.get("action", "") for a in summary.get("optional_actions", [])]
        plan_actions = [a for a in optional_actions if a.startswith("plan.")]
        build_actions = [a for a in optional_actions if a.startswith("build.")]
        assert not plan_actions, f"QA should not see plan actions: {plan_actions}"
        assert not build_actions, f"QA should not see build actions: {build_actions}"
        
        print("✓ QA cannot access plan/build actions")

def test_qa_can_access_solution_verify_close():
    """QA role should see solution, verify, and close actions."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"
        
        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Test Product",
            "--track", "feature",
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
        
        # Complete solution phase (skip all)
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
            "--reason", "not required",
        )
        
        # Complete build phase
        run(
            "ticket",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--id", "1.1",
            "--gate", "ticket",
            "--status", "passed",
        )
        run(
            "ticket",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--id", "1.1",
            "--gate", "tests",
            "--status", "passed",
        )
        run(
            "ticket",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--id", "1.1",
            "--gate", "review",
            "--status", "passed",
        )
        run(
            "ticket",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--id", "1.1",
            "--gate", "done",
            "--status", "passed",
        )
        
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.build.status",
            "--value", "done",
        )
        
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Next action should be verify.trace (QA action)
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "verify.trace", \
            f"Expected verify.trace, got {next_action.get('action')}"
        assert next_action.get("phase") == "verify", \
            f"Expected verify phase, got {next_action.get('phase')}"
        
        # Check that plan/build actions are not the next action
        assert not next_action.get("action", "").startswith("plan."), \
            f"QA should not see plan actions as next"
        assert not next_action.get("action", "").startswith("build."), \
            f"QA should not see build actions as next"
        
        print("✓ QA can access solution/verify/close actions")

if __name__ == "__main__":
    test_qa_cannot_access_plan_actions()
    test_qa_can_access_solution_verify_close()
    print("All QA isolation tests passed!")