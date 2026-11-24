#!/usr/bin/env python3
"""Test DEV to QA handoff on build.done gate pass."""
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

def test_dev_to_qa_on_build_done():
    """All tickets build.done passed → next action is verify.trace (QA)."""
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

        # Complete solution phase (skip)
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

        # Initially in build phase (DEV role)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.ticket", \
            f"Expected build.ticket initially, got {next_action.get('action')}"

        # Complete a ticket with all build gates
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
            "--reason", "trivial",
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

        # Mark build phase done
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.build.status",
            "--value", "done",
        )

        # Next should be verify.trace (QA role)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "verify.trace", \
            f"Expected verify.trace, got {next_action.get('action')}"
        assert next_action.get("phase") == "verify", \
            f"Expected verify phase, got {next_action.get('phase')}"

        print("✓ DEV → QA handoff on build.done works")

def test_dev_to_qa_multiple_tickets():
    """Multiple tickets all done → QA handoff."""
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

        # Complete plan and solution phases
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

        # Complete multiple tickets
        for ticket_id in ("1.1", "1.2", "2.1"):
            run(
                "ticket",
                "--plan", str(ledger),
                "--workstream", "ws-001",
                "--id", ticket_id,
                "--gate", "ticket",
                "--status", "passed",
            )
            run(
                "ticket",
                "--plan", str(ledger),
                "--workstream", "ws-001",
                "--id", ticket_id,
                "--gate", "tests",
                "--status", "passed",
            )
            run(
                "ticket",
                "--plan", str(ledger),
                "--workstream", "ws-001",
                "--id", ticket_id,
                "--gate", "review",
                "--status", "passed",
            )
            run(
                "ticket",
                "--plan", str(ledger),
                "--workstream", "ws-001",
                "--id", ticket_id,
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

        # Next should be verify.trace (QA role)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "verify.trace", \
            f"Expected verify.trace, got {next_action.get('action')}"
        assert next_action.get("phase") == "verify"

        print("✓ DEV → QA handoff with multiple tickets works")

if __name__ == "__main__":
    test_dev_to_qa_on_build_done()
    test_dev_to_qa_multiple_tickets()
    print("All DEV→QA handoff tests passed!")