#!/usr/bin/env python3
"""Test auto-detect: audit track starts with QA."""
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

def test_audit_starts_with_qa():
    """Audit track should start with QA (build.review for audit ticket)."""
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
        assert plan_phase.get("status") == "skipped"

        # Next action is build.review with audit ticket (QA action)
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.review"
        assert next_action.get("ticket") == "audit"

        print("✓ Audit starts with QA role")

def test_audit_qa_then_verify():
    """Audit: QA does build.review, then verify.* actions."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"

        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Quality Audit",
            "--track", "audit",
        )

        # Complete build.review for audit
        run(
            "ticket",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--id", "audit",
            "--gate", "review",
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

        # Should be in verify phase with QA actions
        next_action = summary.get("next_action", {})
        assert next_action.get("action", "").startswith("verify.") or \
               next_action.get("action", "").startswith("solution."), \
            f"Expected QA action, got {next_action.get('action')}"

        print("✓ Audit: QA → verify transition works")

if __name__ == "__main__":
    test_audit_starts_with_qa()
    test_audit_qa_then_verify()
    print("All audit QA first tests passed!")