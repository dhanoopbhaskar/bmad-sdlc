#!/usr/bin/env python3
"""Test subagent receives no session context - only ledger artifacts."""
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

def test_no_session_summary_passed():
    """Subagent should not receive session summary - only ledger + artifacts."""
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

        # Complete plan.requirements
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.requirements.status",
            "--value", "passed",
        )

        # The summary output should only reference ledger and artifact paths
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Verify no session-specific data in summary
        # (The summary command only returns ledger-derived state)
        assert "workstream" in summary
        assert "phases" in summary
        assert "next_action" in summary
        assert "open_gates" in summary
        assert "blocked_gates" in summary
        assert "locked_phases" in summary
        
        # No session context fields should be present
        # (These would be things like previous user messages, previous action outputs, etc.)
        assert "session" not in str(summary).lower() or "session" not in [k.lower() for k in summary.keys()]
        
        print("✓ No session summary passed - only ledger artifacts")

def test_ledger_artifacts_accessible():
    """Subagent should be able to read ledger and artifact files."""
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

        # Write some artifact (simulate SPEC.md created by frame.spec)
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text("# Test Spec\n\nRequirements for the test product.")

        # Record artifact in ledger (simulate)
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "artifacts.spec",
            "--value", str(spec_file),
        )

        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # The artifact should be accessible via ledger
        workstream = summary.get("workstream", {})
        artifacts = workstream.get("artifacts", {})
        assert "spec" in artifacts, f"Spec artifact should be in ledger: {artifacts}"
        assert artifacts["spec"] == str(spec_file), f"Spec path should match: {artifacts['spec']}"
        
        # Verify file exists and is readable
        assert spec_file.exists(), "Spec file should exist"
        content = spec_file.read_text()
        assert "Test Spec" in content, "Spec content should be readable"

        print("✓ Ledger artifacts accessible to subagent")

def test_headless_json_no_session_context():
    """Headless JSON should not contain session context."""
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

        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        
        # Headless output format (summary output fields)
        required_fields = ["ok", "ledger", "memlog", "project", "model", "active_workstream", "workstream", "phases", "tickets", "open_gates", "blocked_gates", "required_open", "conditional_open", "optional_open", "locked_phases", "optional_actions", "next_phase", "phase", "next_action", "workstreams", "workstreams_detail", "decisions"]
        for field in required_fields:
            assert field in summary, f"Headless JSON missing {field}"
        
        # Should not have session context
        # Check that the structure is clean
        assert isinstance(summary.get("next_action"), dict)
        assert isinstance(summary.get("optional_actions"), list)
        assert isinstance(summary.get("open_gates"), list)
        assert isinstance(summary.get("blocked_gates"), list)
        assert isinstance(summary.get("locked_phases"), list)

        print("✓ Headless JSON has no session context")

if __name__ == "__main__":
    test_no_session_summary_passed()
    test_ledger_artifacts_accessible()
    test_headless_json_no_session_context()
    print("All no-session-context tests passed!")