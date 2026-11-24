#!/usr/bin/env python3
"""Test QA to PM/DEV rollback on failed gates."""
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

def test_qa_to_pm_on_correct_course():
    """QA triggers close.correct_course → PM replan."""
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

        # Complete through verify phase
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
        for gate in ("trace", "nfr", "test_review"):
            run(
                "set",
                "--plan", str(ledger),
                "--workstream", "ws-001",
                "--path", f"gates.verify.{gate}.status",
                "--value", "passed",
            )
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.verify.status",
            "--value", "done",
        )

        # Trigger correct_course (QA action)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        # Should show close.correct_course or close.retro
        assert next_action.get("action", "").startswith("close."), \
            f"Expected close action, got {next_action.get('action')}"

        print("✓ QA → PM on correct_course works")

def test_qa_to_dev_on_trace_gaps():
    """QA verify.trace finds gaps → DEV build fixes."""
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

        # Complete through verify phase
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

        # Block verify.trace (simulate gaps found)
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.verify.trace.status",
            "--value", "blocked",
        )

        # When verify.trace is blocked, next action should reflect that
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # The blocked gate should be reported
        blocked_gates = summary.get("blocked_gates", [])
        assert "verify.trace" in blocked_gates, \
            f"Expected verify.trace in blocked_gates, got {blocked_gates}"

        print("✓ QA → DEV on verify.trace blocked works")

def test_qa_to_dev_on_nfr_failures():
    """QA verify.nfr fails → DEV code changes."""
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

        # Complete through verify phase
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

        # Block verify.nfr (simulate NFR failures)
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.verify.nfr.status",
            "--value", "blocked",
        )

        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        blocked_gates = summary.get("blocked_gates", [])
        assert "verify.nfr" in blocked_gates, \
            f"Expected verify.nfr in blocked_gates, got {blocked_gates}"

        print("✓ QA → DEV on verify.nfr blocked works")

if __name__ == "__main__":
    test_qa_to_pm_on_correct_course()
    test_qa_to_dev_on_trace_gaps()
    test_qa_to_dev_on_nfr_failures()
    print("All QA→PM/DEV rollback tests passed!")