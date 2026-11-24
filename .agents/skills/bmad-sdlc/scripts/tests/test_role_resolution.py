#!/usr/bin/env python3
"""Role resolution and ownership tests for the bmad-sdlc helper.

Role ownership is defined once in `references/role-config.toml`. These tests
pin the deterministic surface the conductor reads: `summary.current_role`,
`role_source`, per-action `role` / `role_allowed`, the persisted `role`
override, and the role config loader. They import the script's resolver rather
than re-implementing it, and derive the action set from the script's gate,
ticket, and skill-action tables so a new action with no owner fails the suite.

Run:
  uv run --no-cache python -m unittest discover \
    -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
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


def load_module():
    """Import the helper so tests call the real resolver, not a copy."""
    spec = importlib.util.spec_from_file_location("sdlc_plan_roles", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sdlc = load_module()


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

    def test_config_validates(self) -> None:
        self.assertIs(sdlc.validate_role_config(self.config), self.config)

    def test_missing_config_fails_instead_of_defaulting(self) -> None:
        """role-config.toml is the only source; there is no built-in copy."""
        missing = Path(tempfile.mkdtemp(prefix="bmad-sdlc-rolecfg-"))
        self.addCleanup(shutil.rmtree, missing, True)
        with ConsoleEscape() as escaped, self.assertRaises(SystemExit):
            sdlc.role_config.cache_clear()
            original = sdlc.ROLE_CONFIG_PATH
            try:
                sdlc.ROLE_CONFIG_PATH = missing / "role-config.toml"
                sdlc.role_names()
            finally:
                sdlc.ROLE_CONFIG_PATH = original
                sdlc.role_config.cache_clear()
        self.assertIn("role config not found", escaped.payload()["error"])

    def test_every_action_has_one_owner_or_is_role_free(self) -> None:
        for action in sdlc.ALL_ACTION_IDS:
            if sdlc.role_is_free(action, self.config):
                self.assertIsNone(sdlc.role_for_action(action, "feature"), action)
                continue
            for track in sdlc.TRACKS:
                self.assertIsNotNone(
                    sdlc.role_for_action(action, track),
                    f"{action} on track {track}",
                )

    def test_review_and_done_are_qa_on_every_track(self) -> None:
        for track in sdlc.TRACKS:
            self.assertEqual(sdlc.role_for_action("build.review", track), "qa")
            self.assertEqual(sdlc.role_for_action("build.done", track), "qa")
            self.assertEqual(sdlc.role_for_action("build.ticket", track), "dev")

    def test_track_action_override_wins_over_the_prefix(self) -> None:
        """The advertised first-precedence rule is exercised, not just parsed."""
        custom = Path(tempfile.mkdtemp(prefix="bmad-sdlc-roleoverride-"))
        self.addCleanup(shutil.rmtree, custom, True)
        config = custom / "role-config.toml"
        text = ROLE_CONFIG.read_text(encoding="utf-8").replace(
            "[track_action_overrides]\n",
            '[track_action_overrides]\n"fix.verify.trace" = "dev"\n',
            1,
        )
        config.write_text(text, encoding="utf-8")
        original = sdlc.ROLE_CONFIG_PATH
        try:
            sdlc.ROLE_CONFIG_PATH = config
            sdlc.role_config.cache_clear()
            self.assertEqual(sdlc.role_for_action("verify.trace", "fix"), "dev")
            self.assertTrue(sdlc.role_allows("verify.trace", "dev", "fix"))
            self.assertFalse(sdlc.role_allows("verify.trace", "qa", "fix"))
            # A different track keeps the prefix owner.
            self.assertEqual(sdlc.role_for_action("verify.trace", "feature"), "qa")
        finally:
            sdlc.ROLE_CONFIG_PATH = original
            sdlc.role_config.cache_clear()

    def test_phase_roles_cover_the_lifecycle(self) -> None:
        phase_roles = self.config["phase_roles"]
        for phase in PHASES:
            self.assertIn(phase, phase_roles)
            self.assertIn(phase_roles[phase], self.config["roles"])
        self.assertEqual(phase_roles["build"], "dev")
        self.assertEqual(self.config["track_roles"]["audit"], "qa")

    def test_conductor_actions_are_role_free(self) -> None:
        for action in (*sdlc.CONDUCTOR_ACTIONS, *sdlc.PHASE_UNBLOCK_ACTIONS):
            self.assertTrue(sdlc.role_is_free(action, self.config), action)
            self.assertTrue(sdlc.role_allows(action, "dev", "feature"), action)

    def test_invalid_configs_are_rejected(self) -> None:
        cases = {
            "string prefixes": {
                **self.config,
                "roles": {
                    **self.config["roles"],
                    "dev": {**self.config["roles"]["dev"], "action_prefixes": "build."},
                },
            },
            "phase_roles unknown role": {
                **self.config,
                "phase_roles": {**self.config["phase_roles"], "build": "nobody"},
            },
            "track_roles unknown role": {
                **self.config,
                "track_roles": {"audit": "nobody"},
            },
            "track_roles unknown track": {
                **self.config,
                "track_roles": {"audti": "qa"},
            },
            "track_action_overrides unknown track": {
                **self.config,
                "track_action_overrides": {"audti.verify.trace": "qa"},
            },
            "roles.phases is gone": {
                **self.config,
                "roles": {
                    **self.config["roles"],
                    "qa": {**self.config["roles"]["qa"], "phases": ["verify"]},
                },
            },
        }
        for label, config in cases.items():
            with self.assertRaises(sdlc.RoleConfigError, msg=label):
                sdlc.validate_role_config(config)


class ConsoleEscape:
    """Capture the JSON a fail() writes before it exits."""

    def __init__(self) -> None:
        self.buffer = io.StringIO()

    def __enter__(self) -> "ConsoleEscape":
        self.redirect = contextlib.redirect_stdout(self.buffer)
        self.redirect.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        self.redirect.__exit__(*exc)

    def payload(self) -> dict:
        return json.loads(self.buffer.getvalue())


class ConfigFailureTests(unittest.TestCase):
    """A broken role config fails summary, not detect/init/validate/--help."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="bmad-sdlc-rolecfg-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "project"
        self.root.mkdir()
        self.skill = self.tmp / "skill"
        (self.skill / "scripts").mkdir(parents=True)
        (self.skill / "references").mkdir()
        shutil.copy2(SCRIPT, self.skill / "scripts" / "sdlc_plan.py")
        self.copied_script = self.skill / "scripts" / "sdlc_plan.py"
        self.ledger = self.root / "_bmad-output" / "sdlc" / "plan.yaml"

    def write_config(self, text: str) -> None:
        shutil.copy2(ROLE_CONFIG, self.skill / "references" / "role-config.toml")
        (self.skill / "references" / "role-config.toml").write_text(
            text, encoding="utf-8"
        )

    def copied(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["uv", "run", "--no-cache", str(self.copied_script), *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_malformed_toml_breaks_only_summary(self) -> None:
        run(
            "init",
            "--project-root",
            str(self.root),
            "--name",
            "Config Fixture",
            "--track",
            "fix",
            "--size",
            "trivial",
            "--model",
            "v6",
        )
        self.write_config("this is not toml [[[")
        detect = self.copied("detect", "--project-root", str(self.root))
        self.assertEqual(detect.returncode, 0, detect.stderr)
        self.assertTrue(json.loads(detect.stdout)["ok"])
        helped = self.copied("--help")
        self.assertEqual(helped.returncode, 0, helped.stderr)
        validated = self.copied("validate", "--plan", str(self.ledger))
        self.assertEqual(validated.returncode, 0, validated.stdout)
        summary = self.copied("summary", "--plan", str(self.ledger))
        self.assertNotEqual(summary.returncode, 0)
        payload = json.loads(summary.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("invalid role config", payload["error"])

    def test_unmapped_phase_fails_naming_the_phase(self) -> None:
        config = tomllib.loads(ROLE_CONFIG.read_text())
        del config["phase_roles"]["verify"]
        self.write_config(
            "\n".join(
                [
                    "[roles.pm]",
                    'action_prefixes = ["frame.", "plan."]',
                    "[roles.dev]",
                    'action_prefixes = ["build."]',
                    "[roles.qa]",
                    'action_prefixes = ["solution.", "verify.", "close."]',
                    "[phase_roles]",
                    *[
                        f'{phase} = "{role}"'
                        for phase, role in config["phase_roles"].items()
                    ],
                    "[track_roles]",
                    'audit = "qa"',
                    "[track_action_overrides]",
                    "[advisory]",
                    'prefix = "advisory."',
                ]
            )
            + "\n"
        )
        with ConsoleEscape() as escaped, self.assertRaises(SystemExit):
            sdlc.role_config.cache_clear()
            original = sdlc.ROLE_CONFIG_PATH
            try:
                sdlc.ROLE_CONFIG_PATH = self.skill / "references" / "role-config.toml"
                sdlc.assert_phase_mapped("verify", "feature", sdlc.role_config())
            finally:
                sdlc.ROLE_CONFIG_PATH = original
                sdlc.role_config.cache_clear()
        self.assertIn("phase 'verify' has no [phase_roles] entry", escaped.payload()["error"])


class RoleResolverTests(unittest.TestCase):
    def test_unowned_action_fails_naming_the_action(self) -> None:
        with ConsoleEscape() as escaped, self.assertRaises(SystemExit):
            sdlc.role_config.cache_clear()
            original = sdlc.ROLE_CONFIG_PATH
            temp = Path(tempfile.mkdtemp(prefix="bmad-sdlc-rolecfg-"))
            self.addCleanup(shutil.rmtree, temp, True)
            config = tomllib.loads(ROLE_CONFIG.read_text())
            config["roles"]["qa"]["action_prefixes"] = ["solution.", "close."]
            (temp / "role-config.toml").write_text(
                "\n".join(
                    [
                        "[roles.pm]",
                        'action_prefixes = ["frame.", "plan."]',
                        "[roles.dev]",
                        'action_prefixes = ["build."]',
                        "[roles.qa]",
                        'action_prefixes = ["solution.", "close."]',
                        "[phase_roles]",
                        *[
                            f'{phase} = "{role}"'
                            for phase, role in config["phase_roles"].items()
                        ],
                        "[track_roles]",
                        'audit = "qa"',
                        "[track_action_overrides]",
                        "[advisory]",
                        'prefix = "advisory."',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            try:
                sdlc.ROLE_CONFIG_PATH = temp / "role-config.toml"
                sdlc.annotate_role(
                    {"action": "verify.trace"}, "feature", "dev", sdlc.role_config()
                )
            finally:
                sdlc.ROLE_CONFIG_PATH = original
                sdlc.role_config.cache_clear()
        self.assertIn("no role owns action 'verify.trace'", escaped.payload()["error"])

    def test_annotation_marks_conductor_actions_role_free(self) -> None:
        entry = {"action": "close.mark_done"}
        sdlc.annotate_role(entry, "feature", "dev", tomllib.loads(ROLE_CONFIG.read_text()))
        self.assertIsNone(entry["role"])
        self.assertTrue(entry["role_free"])
        self.assertTrue(entry["role_allowed"])


class SummaryRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="bmad-sdlc-roles-")
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "_bmad-output" / "sdlc" / "plan.yaml"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def init(
        self,
        track: str,
        size: str | None = None,
        root: Path | None = None,
        model: str = "v6",
    ):
        root = root or self.root
        args = [
            "init",
            "--project-root",
            str(root),
            "--name",
            "Role Fixture",
            "--track",
            track,
            "--model",
            model,
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

    def mark(self, phase: str, status: str) -> None:
        args = [
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            f"phases.{phase}.status",
            "--value",
            status,
        ]
        if status in ("done", "skipped"):
            args += ["--reason", "role fixture"]
        run(*args)

    def ticket(self, gate: str, status: str = "passed") -> None:
        args = [
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            gate,
            "--status",
            status,
        ]
        if gate in ("review", "done"):
            args += ["--as", "qa"]
        if "--as" in args and "--reason" not in args:
            args += ["--reason", "role fixture"]
        run(*args)

    def plan_done(self) -> None:
        self.decide("plan", ("requirements", "stories", "sprint"), "passed")
        self.decide("plan", ("ux", "architecture"), "overridden")
        self.mark("plan", "done")

    def test_plan_phase_owns_pm_actions(self) -> None:
        self.init("greenfield", "epic")
        summary = self.summary()
        self.assertEqual(summary["current_role"], "pm")
        self.assertEqual(summary["role_source"], "phase")
        self.assertEqual(summary["workstream"]["current_phase"], "plan")
        self.assertEqual(summary["next_action"]["action"], "frame.spec")
        self.assertEqual(summary["next_action"]["role"], "pm")
        self.assertTrue(summary["next_action"]["role_allowed"])
        self.assertEqual(
            [phase["role"] for phase in summary["phases"]],
            ["pm", "qa", "dev", "qa", "qa"],
        )
        self.assertEqual(summary["workstreams_detail"][0]["role"], "pm")

    def test_stored_phase_advances_only_when_marked_done(self) -> None:
        self.init("greenfield", "epic")
        self.decide("plan", ("requirements", "stories", "sprint"), "passed")
        self.decide("plan", ("ux", "architecture"), "overridden")
        # Every plan gate is decided, but the phase is not done: the role stays
        # PM and the stored phase is not rewritten to the recommended phase.
        undecided = self.summary()
        self.assertEqual(undecided["workstream"]["current_phase"], "plan")
        self.assertEqual(undecided["current_role"], "pm")
        self.assertEqual(undecided["phase"], "solution")

        self.mark("plan", "done")
        advanced = self.summary()
        self.assertEqual(advanced["workstream"]["current_phase"], "solution")
        self.assertEqual(advanced["current_role"], "qa")
        self.assertEqual(advanced["next_action"]["action"], "solution.test_design")
        self.assertEqual(advanced["next_action"]["role"], "qa")
        self.assertTrue(advanced["next_action"]["role_allowed"])

    def test_explicit_role_blocks_foreign_action(self) -> None:
        self.init("greenfield", "epic")
        self.plan_done()
        summary = self.summary("--role", "QA")
        self.assertEqual(summary["current_role"], "qa")
        self.assertEqual(summary["role_source"], "explicit")
        self.assertTrue(summary["next_action"]["role_allowed"])

        blocked = self.summary("--role", "pm")
        self.assertEqual(blocked["role_source"], "explicit")
        self.assertFalse(blocked["next_action"]["role_allowed"])
        self.assertEqual(blocked["next_action"]["role"], "qa")

    def test_invalid_role_returns_json(self) -> None:
        self.init("fix", "trivial")
        result = run_full("summary", "--plan", str(self.ledger), "--role", "bogus")
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("unknown role", payload["error"])

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

    def test_completed_workstream_reports_role_free_close(self) -> None:
        self.init("fix", "trivial")
        self.ticket("ticket")
        self.ticket("review")
        self.ticket("done")
        summary = self.summary()
        self.assertEqual(summary["next_action"]["action"], "close.mark_done")
        self.assertIsNone(summary["next_action"]["role"])
        self.assertTrue(summary["next_action"]["role_free"])
        self.assertTrue(summary["next_action"]["role_allowed"])
        for entry in summary["optional_actions"]:
            self.assertIn("role", entry)
            self.assertIn("role_allowed", entry)

        done = run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-tickets",
            "--reason",
            "role fixture",
        )
        self.assertTrue(done["ok"], done)
        closed = self.summary()
        self.assertIsNone(closed["active_workstream"])
        self.assertIn("current_role", closed)
        self.assertIn("role_source", closed)
        self.assertEqual(closed["role_source"], "phase")

    def test_paused_workstream_keeps_the_role_fields(self) -> None:
        self.init("fix", "trivial")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "paused",
            "--reason",
            "role fixture",
        )
        summary = self.summary()
        self.assertIsNone(summary["active_workstream"])
        self.assertEqual(summary["current_role"], "dev")
        self.assertEqual(summary["role_source"], "phase")

    def test_default_role_source_is_reachable(self) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(
            "\n".join(
                [
                    "schema: bmad-sdlc/1",
                    "project: Empty",
                    "created: '2026-01-01T00:00:00+00:00'",
                    "updated: '2026-01-01T00:00:00+00:00'",
                    "bmad:",
                    "  model: unknown",
                    "active_workstream: null",
                    "workstreams: {}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        summary = self.summary()
        self.assertEqual(summary["current_role"], "pm")
        self.assertEqual(summary["role_source"], "default")

    def test_role_override_persists_and_clears(self) -> None:
        self.init("fix", "trivial")
        chosen = run(
            "role",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--role",
            "QA",
            "--reason",
            "review pass",
        )
        self.assertEqual(chosen["current_role"], "qa")
        summary = self.summary()
        self.assertEqual(summary["current_role"], "qa")
        self.assertEqual(summary["role_source"], "override")
        self.assertFalse(summary["next_action"]["role_allowed"])

        # A resume clears the per-run override and re-resolves from the phase.
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "paused",
            "--reason",
            "role fixture",
        )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "active",
            "--reason",
            "role fixture",
        )
        resumed = self.summary()
        self.assertEqual(resumed["role_source"], "phase")
        self.assertEqual(resumed["current_role"], "dev")
        memlog = (self.root / "_bmad-output" / "sdlc" / ".memlog.md").read_text()
        self.assertIn("role set to qa", memlog)

    def test_unknown_gate_names_the_valid_ids(self) -> None:
        self.init("fix", "trivial")
        self.ticket("ticket")
        bad = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.bogus.status",
            "--value",
            "passed",
        )
        self.assertNotEqual(bad.returncode, 0)
        error = json.loads(bad.stdout)["error"]
        for gate in sdlc.TICKET_GATES:
            self.assertIn(gate, error)
        bad_gate = run_full(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "bogus",
            "--status",
            "passed",
        )
        self.assertNotEqual(bad_gate.returncode, 0)
        self.assertIn("choose one of", json.loads(bad_gate.stdout)["error"])

    def test_foreign_gate_decision_needs_a_reason(self) -> None:
        self.init("fix", "trivial")
        self.ticket("ticket")
        refused = run_full(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "review",
            "--status",
            "passed",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("belongs to qa", json.loads(refused.stdout)["error"])
        allowed = run_full(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "review",
            "--status",
            "passed",
            "--as",
            "qa",
            "--reason",
            "QA recorded its review",
        )
        self.assertEqual(allowed.returncode, 0, allowed.stdout)
        memlog = (self.root / "_bmad-output" / "sdlc" / ".memlog.md").read_text()
        self.assertIn("by qa", memlog)

    def test_verify_return_checks_role_and_action(self) -> None:
        self.init("fix", "trivial")
        artifact = self.root / "change.md"
        artifact.write_text("# change\n", encoding="utf-8")
        memlog = self.root / "_bmad-output" / "sdlc" / ".memlog.md"
        ledger_sha = hashlib.sha256(self.ledger.read_bytes()).hexdigest()
        memlog_sha = hashlib.sha256(memlog.read_bytes()).hexdigest()

        def verify(
            role: str | None,
            action: str = "build.ticket",
            expect_action: str = "build.ticket",
            expect_role: str = "qa",
        ) -> dict:
            returned = {
                "status": "done",
                "artifacts": [{"path": "change.md"}],
                "evidence": ["change.md"],
            }
            if role is not None:
                returned["role"] = role
                returned["action"] = action
            return json.loads(
                run_full(
                    "verify-return",
                    "--plan",
                    str(self.ledger),
                    "--project-root",
                    str(self.root),
                    "--return",
                    json.dumps(returned),
                    "--expect-ledger-sha",
                    ledger_sha,
                    "--expect-memlog-sha",
                    memlog_sha,
                    "--expect-role",
                    expect_role,
                    "--expect-action",
                    expect_action,
                ).stdout
            )

        mismatch = verify("dev")
        self.assertFalse(mismatch["ok"])
        self.assertTrue(
            any("does not match expected 'qa'" in reason for reason in mismatch["reasons"])
        )

        missing = verify(None)
        self.assertFalse(missing["ok"])
        self.assertTrue(any("does not name a role" in reason for reason in missing["reasons"]))

        # The returned role must own the returned action; a QA label on a DEV
        # action is exactly what verify-return exists to refuse.
        wrong_owner = verify("qa", expect_role="qa")
        self.assertFalse(wrong_owner["ok"])
        self.assertTrue(
            any(
                "belongs to dev" in reason and "cannot return it" in reason
                for reason in wrong_owner["reasons"]
            )
        )

        # A return produced for a different action than the handoff is refused.
        wrong_action = verify("qa", "build.review", expect_action="build.ticket")
        self.assertFalse(wrong_action["ok"])
        self.assertTrue(
            any(
                "does not match expected 'build.ticket'" in reason
                for reason in wrong_action["reasons"]
            )
        )

        accepted = verify("dev", expect_role="dev")
        self.assertTrue(accepted["ok"], accepted["reasons"])
        self.assertEqual(accepted["role"], "dev")
        self.assertEqual(accepted["action"], "build.ticket")

    def test_phase_gate_foreign_role_needs_a_reason(self) -> None:
        """A phase gate is guarded like a ticket gate, not just the ticket one."""
        self.init("fix", "trivial")
        refused = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.verify.trace.status",
            "--value",
            "passed",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("belongs to qa", json.loads(refused.stdout)["error"])

        allowed = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.verify.trace.status",
            "--value",
            "passed",
            "--as",
            "qa",
            "--reason",
            "QA recorded the trace gate",
        )
        self.assertEqual(allowed.returncode, 0, allowed.stdout)
        memlog = (self.root / "_bmad-output" / "sdlc" / ".memlog.md").read_text()
        self.assertIn("by qa", memlog)

    def test_blocked_phase_recommends_unblock(self) -> None:
        self.init("greenfield", "epic")
        self.decide("plan", ("requirements", "stories", "sprint"), "passed")
        self.decide("plan", ("ux", "architecture"), "overridden")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.status",
            "--value",
            "blocked",
        )
        summary = self.summary()
        self.assertEqual(summary["next_action"]["action"], "plan.unblock")
        self.assertIsNone(summary["next_action"]["gate"])
        self.assertIsNone(summary["next_action"]["role"])
        self.assertTrue(summary["next_action"]["role_free"])
        self.assertTrue(summary["next_action"]["role_allowed"])
        self.assertNotEqual(summary["next_action"]["action"], "close.mark_done")

    def test_phase_gate_lists_are_scoped_to_their_phase(self) -> None:
        self.init("greenfield", "epic")
        summary = self.summary()
        self.assertTrue(summary["phases"])
        for phase in summary["phases"]:
            name = phase["phase"]
            for key in (
                "required_open",
                "conditional_open",
                "optional_open",
                "open_gates",
                "blocked_gates",
            ):
                for gate_id in phase[key]:
                    self.assertTrue(
                        gate_id.startswith(f"{name}."),
                        f"{name}.{key} leaks {gate_id}",
                    )
            self.assertEqual(
                phase["required_open"],
                [
                    entry["id"]
                    for entry in phase["gates"]
                    if entry["level"] == "required"
                    and entry["status"] in ("open", "blocked")
                ],
            )

    def test_workstream_detail_next_action_carries_role_fields(self) -> None:
        self.init("fix", "trivial")
        brief = self.summary()["workstreams_detail"][0]
        self.assertEqual(brief["role"], "dev")
        self.assertEqual(brief["role_source"], "phase")
        self.assertEqual(brief["next_action"]["action"], "build.ticket")
        self.assertEqual(brief["next_action"]["role"], "dev")
        self.assertTrue(brief["next_action"]["role_allowed"])

    def test_action_catalog_covers_gateless_actions(self) -> None:
        self.init("greenfield", "epic")
        catalog = self.summary()["actions"]
        seen = {(entry["action"], entry.get("ticket")) for entry in catalog}
        expected = (
            {action for action, _ in sdlc.GATE_ACTIONS.values()}
            | {action for action, _ in sdlc.TICKET_ACTIONS.values()}
            | set(sdlc.SKILL_ACTION_IDS)
            | set(sdlc.ADVISORY_ACTION_IDS)
            | set(sdlc.ROLE_FREE_ACTIONS)
        )
        for action in sorted(expected):
            self.assertIn((action, None), seen, action)
        for entry in catalog:
            self.assertIn("role", entry)
            self.assertIn("role_allowed", entry)
            if sdlc.role_is_free(entry["action"]):
                self.assertTrue(entry["role_free"], entry)
                self.assertIsNone(entry["role"], entry)
            else:
                self.assertEqual(
                    entry["role"],
                    sdlc.role_for_action(entry["action"], "greenfield"),
                    entry,
                )

    def test_self_approval_is_refused(self) -> None:
        self.init("fix", "trivial")
        self.ticket("ticket")
        refused = run_full(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "review",
            "--status",
            "passed",
            "--reason",
            "reviewing my own change",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("decided by dev", json.loads(refused.stdout)["error"])

        # QA did not build it, so QA may review and approve it.
        self.ticket("review")
        self.ticket("done")
        trail = (self.root / "_bmad-output" / "sdlc" / ".memlog.md").read_text()
        self.assertIn("T1 review=passed by qa", trail)
        self.assertIn("T1 done=passed by qa", trail)

    def test_self_approval_is_refused_through_the_set_route(self) -> None:
        """The set editor must apply the same guard as the ticket command."""
        self.init("fix", "trivial")
        self.ticket("ticket")
        refused = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.review.status",
            "--value",
            "passed",
            "--reason",
            "reviewing my own change",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("decided by dev", json.loads(refused.stdout)["error"])
        allowed = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.review.status",
            "--value",
            "passed",
            "--as",
            "qa",
            "--reason",
            "QA reviewed the change",
        )
        self.assertEqual(allowed.returncode, 0, allowed.stdout)

    def test_phase_advance_by_foreign_role_needs_a_reason(self) -> None:
        self.init("fix", "trivial")
        self.ticket("ticket")
        self.ticket("tests", "skipped")
        self.ticket("review")
        self.ticket("done")
        # Persist the foreign role without --as; the phase owner is still DEV.
        run(
            "role",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--role",
            "qa",
            "--reason",
            "handoff to QA",
        )
        refused = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.build.status",
            "--value",
            "done",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("belongs to dev", json.loads(refused.stdout)["error"])

        allowed = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.build.status",
            "--value",
            "done",
            "--reason",
            "ticket closed by QA",
        )
        self.assertEqual(allowed.returncode, 0, allowed.stdout)
        trail = (self.root / "_bmad-output" / "sdlc" / ".memlog.md").read_text()
        self.assertIn("phases.build.status=done by qa", trail)

    def test_unknown_role_override_is_rejected(self) -> None:
        self.init("fix", "trivial")
        run(
            "role",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--role",
            "qa",
            "--reason",
            "role fixture",
        )
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn("role_override: qa", text)
        self.ledger.write_text(
            text.replace("role_override: qa", "role_override: bogus"),
            encoding="utf-8",
        )
        validated = run_full("validate", "--plan", str(self.ledger))
        self.assertNotEqual(validated.returncode, 0)
        self.assertIn("role_override", json.loads(validated.stdout)["errors"][0])
        summary = run_full("summary", "--plan", str(self.ledger))
        self.assertNotEqual(summary.returncode, 0)
        self.assertIn("unknown role", json.loads(summary.stdout)["error"])

    def test_role_clear_and_paused_refusal(self) -> None:
        self.init("fix", "trivial")
        run(
            "role",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--role",
            "qa",
            "--reason",
            "role fixture",
        )
        self.assertEqual(self.summary()["role_source"], "override")

        # A paused workstream refuses the write; resume first.
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "paused",
            "--reason",
            "role fixture",
        )
        paused_clear = run_full(
            "role",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--clear",
        )
        self.assertNotEqual(paused_clear.returncode, 0)
        self.assertIn("paused", json.loads(paused_clear.stdout)["error"])

        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "active",
            "--reason",
            "role fixture",
        )
        run(
            "role",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--role",
            "qa",
            "--reason",
            "role fixture",
        )
        cleared = run(
            "role",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--clear",
            "--reason",
            "handoff complete",
        )
        self.assertIsNone(cleared["role"])
        self.assertEqual(cleared["role_source"], "phase")
        trail = (self.root / "_bmad-output" / "sdlc" / ".memlog.md").read_text()
        self.assertIn("role cleared (reason: handoff complete)", trail)

    def test_init_refuses_a_model_change_on_an_existing_ledger(self) -> None:
        """Appending a workstream must not migrate the whole document."""
        self.init("fix", "trivial", model="v6")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "paused",
            "--reason",
            "role fixture",
        )
        refused = run_full(
            "init",
            "--project-root",
            str(self.root),
            "--name",
            "Role Fixture",
            "--track",
            "fix",
            "--size",
            "trivial",
            "--model",
            "current",
            "--reason",
            "model upgraded",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn(
            "change the model first with", json.loads(refused.stdout)["error"]
        )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "active",
            "--reason",
            "role fixture",
        )
        changed = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad.model",
            "--value",
            "current",
            "--reason",
            "model upgraded",
        )
        self.assertTrue(changed["ok"], changed)
        self.assertIn("model: current", self.ledger.read_text(encoding="utf-8"))

    def test_gate_nodes_record_the_deciding_actor(self) -> None:
        self.init("fix", "trivial")
        self.ticket("ticket")
        self.ticket("review")
        ledger = self.ledger.read_text(encoding="utf-8")
        self.assertIn("actor: dev", ledger)
        self.assertIn("actor: qa", ledger)

    def test_validate_reports_self_approval(self) -> None:
        self.init("fix", "trivial")
        self.ticket("ticket")
        self.ticket("review")
        text = self.ledger.read_text(encoding="utf-8")
        # Forge the review so the builder also decided it, as a hand edit could.
        head, _, tail = text.rpartition("actor: qa")
        self.ledger.write_text(head + "actor: dev" + tail, encoding="utf-8")
        validated = run_full("validate", "--plan", str(self.ledger))
        self.assertNotEqual(validated.returncode, 0)
        errors = json.loads(validated.stdout)["errors"]
        self.assertTrue(
            any(
                "another role must review and approve it" in error
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
