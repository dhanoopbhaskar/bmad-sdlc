#!/usr/bin/env python3
"""Role resolution and ownership tests for the bmad-sdlc helper.

Role ownership is defined once in `references/role-config.toml`. These tests
pin the deterministic surface the conductor reads: `summary.current_role`,
`role_source`, and per-action `role` / `role_allowed`.

Run:
  uv run --no-cache python -m unittest discover \
    -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "sdlc_plan.py"
REPO_ROOT = Path(__file__).resolve().parents[5]
SKILL_ROOT = SCRIPT.parent.parent
ROLE_CONFIG = SKILL_ROOT / "references" / "role-config.toml"

PHASES = ("plan", "solution", "build", "verify", "close")

# Every action the helper can emit, plus the non-gate actions the menu offers.
ACTIONS = {
    "frame.spec",
    "plan.requirements",
    "plan.stories",
    "plan.sprint",
    "plan.ux",
    "plan.architecture",
    "solution.test_design",
    "solution.framework",
    "solution.ci",
    "solution.unblock",
    "build.ticket",
    "build.tests",
    "build.review",
    "build.done",
    "verify.trace",
    "verify.nfr",
    "verify.test_review",
    "close.retro",
    "close.walkthrough",
    "close.mark_done",
}


def run_full(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--no-cache", str(SCRIPT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def run(*args: str) -> dict:
    result = run_full(*args)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {result.stderr or result.stdout}"
        )
    payload = json.loads(result.stdout)
    if payload.get("ok") is not True:
        raise AssertionError(payload)
    return payload


class RoleConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = tomllib.loads(ROLE_CONFIG.read_text())
        self.roles = self.config["roles"]

    def owner(self, action: str, track: str | None = None) -> set[str]:
        override = (self.config["track_action_overrides"] or {}).get(
            f"{track}.{action}"
        )
        if override:
            return {override}
        return {
            role
            for role, spec in self.roles.items()
            if any(action.startswith(prefix) for prefix in spec["action_prefixes"])
        }

    def test_config_is_complete_and_consistent(self) -> None:
        self.assertEqual(set(self.roles), {"pm", "dev", "qa"})
        self.assertEqual(set(self.config["phase_roles"]), set(PHASES))
        for role, spec in self.roles.items():
            self.assertTrue(spec["action_prefixes"], role)
            self.assertTrue(set(spec["phases"]) <= set(PHASES), role)
            for reference in spec["references"]:
                self.assertTrue((SKILL_ROOT / reference).is_dir(), reference)
        for mapping in ("phase_roles", "track_roles", "track_action_overrides"):
            for owner in self.config[mapping].values():
                self.assertIn(owner, self.roles, mapping)

    def test_every_action_has_exactly_one_owner(self) -> None:
        for action in ACTIONS:
            self.assertEqual(len(self.owner(action)), 1, action)
        self.assertEqual(self.owner("build.review", "audit"), {"qa"})
        self.assertEqual(self.owner("build.review", "feature"), {"dev"})

    def test_phase_roles_cover_the_lifecycle(self) -> None:
        phase_roles = self.config["phase_roles"]
        self.assertEqual(phase_roles["solution"], "qa")
        self.assertEqual(phase_roles["build"], "dev")
        self.assertEqual(self.config["track_roles"]["audit"], "qa")
        self.assertEqual(
            set(self.roles["qa"]["phases"]), {"solution", "verify", "close"}
        )


class SummaryRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="bmad-sdlc-roles-")
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "_bmad-output" / "sdlc" / "plan.yaml"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def init(self, track: str, size: str | None = None, root: Path | None = None):
        root = root or self.root
        args = [
            "init",
            "--project-root",
            str(root),
            "--name",
            "Role Fixture",
            "--track",
            track,
        ]
        if size:
            args += ["--size", size]
        return run(*args)

    def summary(self, *extra: str, root: Path | None = None, ledger: Path | None = None):
        root = root or self.root
        return run(
            "summary",
            "--plan",
            str(ledger or self.ledger),
            "--project-root",
            str(root),
            *extra,
        )

    def decide(self, phase: str, gates: tuple[str, ...], status: str) -> None:
        for gate in gates:
            args = [
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.{phase}.{gate}.status",
                "--value",
                status,
            ]
            if status in ("skipped", "overridden"):
                args += ["--reason", "role fixture"]
            run(*args)

    def test_plan_then_solution_resolves_to_owner(self) -> None:
        self.init("greenfield", "epic")
        summary = self.summary()
        self.assertEqual(summary["current_role"], "pm")
        self.assertEqual(summary["role_source"], "phase")
        self.assertEqual(summary["next_action"]["action"], "frame.spec")
        self.assertEqual(summary["next_action"]["role"], "pm")
        self.assertTrue(summary["next_action"]["role_allowed"])
        self.assertEqual(
            {item["role"] for item in summary["optional_actions"]}, {"pm"}
        )

        self.decide("plan", ("requirements", "stories"), "passed")
        self.decide("plan", ("ux", "architecture", "sprint"), "skipped")
        summary = self.summary()
        self.assertEqual(summary["current_role"], "qa")
        self.assertEqual(summary["next_action"]["action"], "solution.test_design")
        self.assertEqual(summary["next_action"]["role"], "qa")
        self.assertTrue(summary["next_action"]["role_allowed"])

    def test_explicit_role_blocks_foreign_action(self) -> None:
        self.init("greenfield", "epic")
        self.decide("plan", ("requirements", "stories"), "passed")
        self.decide("plan", ("ux", "architecture", "sprint"), "skipped")
        summary = self.summary("--role", "pm")
        self.assertEqual(summary["current_role"], "pm")
        self.assertEqual(summary["role_source"], "explicit")
        self.assertFalse(summary["next_action"]["role_allowed"])
        self.assertEqual(summary["next_action"]["role"], "qa")

    def test_build_and_audit_roles(self) -> None:
        self.init("fix", "trivial")
        summary = self.summary()
        self.assertEqual(summary["current_role"], "dev")
        self.assertEqual(summary["next_action"]["action"], "build.ticket")
        self.assertEqual(summary["next_action"]["role"], "dev")
        self.assertTrue(summary["next_action"]["role_allowed"])

        audit = tempfile.TemporaryDirectory(prefix="bmad-sdlc-audit-")
        self.addCleanup(audit.cleanup)
        audit_root = Path(audit.name)
        audit_ledger = audit_root / "_bmad-output" / "sdlc" / "plan.yaml"
        self.init("audit", root=audit_root)
        payload = self.summary(root=audit_root, ledger=audit_ledger)
        self.assertEqual(payload["current_role"], "qa")
        self.assertEqual(payload["role_source"], "track")
        self.assertEqual(payload["next_action"]["action"], "build.review")
        self.assertEqual(payload["next_action"]["gate"], "build.audit.review")
        self.assertEqual(payload["next_action"]["role"], "qa")
        self.assertTrue(payload["next_action"]["role_allowed"])


if __name__ == "__main__":
    unittest.main()
