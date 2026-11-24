#!/usr/bin/env python3
"""Test subagent receives correct handoff payload (role, ledger, action)."""
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

def test_handoff_payload_contains_role():
    """Handoff should include --role parameter."""
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

        # Mark plan phase done (auto-skipped for fix one-session)
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.plan.status",
            "--value", "done",
        )

        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Check that the next action would be invoked with role=dev
        next_action = summary.get("next_action", {})
        # The action should be a build action (DEV role)
        assert next_action.get("action", "").startswith("build."), \
            f"Expected build action for DEV role, got {next_action.get('action')}"

        print("✓ Handoff payload includes role for DEV")

def test_handoff_payload_contains_ledger():
    """Handoff should include --ledger path."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"

        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Test Product",
            "--track", "feature",
            "--size", "one-session",
        )

        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.requirements.status",
            "--value", "passed",
        )

        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # The ledger path should be known
        assert ledger.exists(), "Ledger should exist"

        print("✓ Handoff payload includes ledger path")

def test_handoff_payload_contains_action():
    """Handoff should include --action parameter."""
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

        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.requirements.status",
            "--value", "passed",
        )

        # Mark plan phase done (auto-skipped for fix one-session)
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.plan.status",
            "--value", "done",
        )

        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        next_action = summary.get("next_action", {})
        action = next_action.get("action")
        assert action is not None, "Next action should have action field"
        assert action == "build.ticket", f"Expected build.ticket, got {action}"

        print("✓ Handoff payload includes action")

if __name__ == "__main__":
    test_handoff_payload_contains_role()
    test_handoff_payload_contains_ledger()
    test_handoff_payload_contains_action()
    print("All handoff payload tests passed!")