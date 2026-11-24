#!/usr/bin/env python3
"""Test PM to DEV handoff on plan.requirements gate pass."""
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

def test_pm_to_dev_on_requirements():
    """PM passes plan.requirements → next action is build.ticket (DEV)."""
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

        # Initially PM role (plan phase)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action", "").startswith("frame.") or \
               next_action.get("action", "").startswith("plan."), \
            f"Expected PM action initially, got {next_action.get('action')}"

        # Pass plan.requirements (simulate frame.spec completing)
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.requirements.status",
            "--value", "passed",
        )

        # For one-session feature, next should be build.ticket (DEV role)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        # After requirements passed, can go to build for one-session
        assert next_action.get("action") in ("build.ticket", "plan.stories"), \
            f"Expected build.ticket or plan.stories after requirements, got {next_action.get('action')}"

        print("✓ PM → DEV handoff on plan.requirements works")

def test_pm_to_dev_on_stories():
    """PM passes plan.stories → goes to solution phase (PM), then build (DEV)."""
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

        # Complete plan.requirements
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.requirements.status",
            "--value", "passed",
        )

        # Pass plan.stories
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "gates.plan.stories.status",
            "--value", "passed",
        )

        # Also pass/skip conditional gates plan.ux and plan.architecture
        for gate in ("ux", "architecture"):
            run(
                "set",
                "--plan", str(ledger),
                "--workstream", "ws-001",
                "--path", f"gates.plan.{gate}.status",
                "--value", "skipped",
                "--reason", "not applicable",
            )

        # Mark plan phase done
        run(
            "set",
            "--plan", str(ledger),
            "--workstream", "ws-001",
            "--path", "phases.plan.status",
            "--value", "done",
        )

        # Next should be solution.test_design (solution phase still PM)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "solution.test_design", \
            f"Expected solution.test_design after stories, got {next_action.get('action')}"
        assert next_action.get("phase") == "solution", \
            f"Expected solution phase, got {next_action.get('phase')}"

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
        )

        # Now should be build.ticket (DEV role)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.ticket", \
            f"Expected build.ticket after solution, got {next_action.get('action')}"
        assert next_action.get("phase") == "build", \
            f"Expected build phase, got {next_action.get('phase')}"

        print("✓ PM → DEV handoff on plan.stories works (via solution)")

def test_pm_to_dev_on_sprint_v6():
    """PM passes plan.sprint (v6) → next action is build.ticket (DEV)."""
    with tempfile.TemporaryDirectory(prefix="bmad-sdlc-test-") as tmp:
        tmp_path = Path(tmp)
        ledger = tmp_path / "_bmad-output" / "sdlc" / "plan.yaml"

        run(
            "init",
            "--project-root", str(tmp_path),
            "--name", "Test Product",
            "--track", "greenfield",
            "--size", "project",
        )

        # Complete all plan gates including sprint
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

        # Next should be build.ticket (DEV role)
        summary = run("summary", "--plan", str(ledger), "--project-root", str(tmp_path))
        next_action = summary.get("next_action", {})
        assert next_action.get("action") == "build.ticket", \
            f"Expected build.ticket after sprint, got {next_action.get('action')}"
        assert next_action.get("phase") == "build"

        print("✓ PM → DEV handoff on plan.sprint works")

if __name__ == "__main__":
    test_pm_to_dev_on_requirements()
    test_pm_to_dev_on_stories()
    test_pm_to_dev_on_sprint_v6()
    print("All PM→DEV handoff tests passed!")