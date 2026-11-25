#!/usr/bin/env python3
"""End-to-end tests for the bmad-sdlc ledger helper.

Run:
  uv run --no-cache python -m unittest discover \
    -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "sdlc_plan.py"
REPO_ROOT = Path(__file__).resolve().parents[5]


def load_module():
    """Import the helper so the suite resolves ownership, never a copy."""
    spec = importlib.util.spec_from_file_location("sdlc_plan_suite", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SDLC = load_module()


def _gate_owner(args: tuple[str, ...]) -> str | None:
    """The role that owns the gate a test command writes.

    The suite sets many gates directly; the actor guard added in round 11 would
    otherwise need `--reason` on every one. This derives the owner from the
    imported resolver — the same table `summary` uses — so a regression in
    ownership resolution fails here too, not just in the role suite.
    """
    parts = list(args)
    if not parts:
        return None
    action = None
    if parts[0] == "ticket" and "--gate" in parts:
        try:
            action = f"build.{parts[parts.index('--gate') + 1]}"
        except IndexError:
            return None
    elif parts[0] == "set" and "--path" in parts:
        try:
            path = parts[parts.index("--path") + 1]
        except IndexError:
            return None
        phase_gate = re.match(r"gates\.(\w+)\.(\w+)(?:\.|$)", path)
        ticket_gate = re.match(r"tickets\..+?\.gates\.(\w+)(?:\.|$)", path)
        if phase_gate:
            action = f"{phase_gate.group(1)}.{phase_gate.group(2)}"
        elif ticket_gate:
            action = f"build.{ticket_gate.group(1)}"
    if not action or SDLC.role_is_free(action):
        return None
    return SDLC.role_for_action(action, None)


def run_full(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    args = tuple(args)
    owner = _gate_owner(args)
    if owner and "--as" not in args:
        args = (*args, "--as", owner)
        if "--reason" not in args:
            args = (*args, "--reason", "test actor attestation")
    return subprocess.run(
        ["uv", "run", "--no-cache", str(SCRIPT), *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def run_raw(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run without the suite's automatic --as, to test a missing argument."""
    return subprocess.run(
        ["uv", "run", "--no-cache", str(SCRIPT), *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def run(*args: str, cwd: Path | None = None) -> dict:
    result = run_full(*args, cwd=cwd)
    if not result.stdout.strip():
        raise AssertionError(f"no JSON output; stderr={result.stderr}")
    return json.loads(result.stdout)


def digests(ledger: Path, memlog: Path | None = None) -> tuple[str, str]:
    """The pre-handoff SHA-256 pair verify-return now requires for acceptance."""
    memlog = memlog or (ledger.parent / ".memlog.md")
    return (
        hashlib.sha256(ledger.read_bytes()).hexdigest(),
        hashlib.sha256(memlog.read_bytes()).hexdigest(),
    )


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="bmad-sdlc-test-"))
        self.ledger = self.tmp / "_bmad-output" / "sdlc" / "plan.yaml"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def init(self) -> dict:
        return run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Test Product",
            "--track",
            "feature",
            "--size",
            "epic",
        )

    def edit_ledger(self, mutation: str) -> None:
        """Simulate a hand edit, which bypasses the script's write guards."""
        code = (
            "import sys\n"
            "from ruamel.yaml import YAML\n"
            "yaml = YAML()\n"
            "data = yaml.load(open(sys.argv[1], encoding='utf-8'))\n"
            f"{mutation}\n"
            "with open(sys.argv[1], 'w', encoding='utf-8') as handle:\n"
            "    yaml.dump(data, handle)\n"
        )
        result = subprocess.run(
            [
                "uv",
                "run",
                "--no-cache",
                "--with",
                "ruamel.yaml",
                "python",
                "-c",
                code,
                str(self.ledger),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)

    def read_ledger(self) -> dict:
        code = (
            "import json, sys\n"
            "from ruamel.yaml import YAML\n"
            "yaml = YAML()\n"
            "data = yaml.load(open(sys.argv[1], encoding='utf-8'))\n"
            "print(json.dumps(data, default=str))\n"
        )
        result = subprocess.run(
            [
                "uv",
                "run",
                "--no-cache",
                "--with",
                "ruamel.yaml",
                "python",
                "-c",
                code,
                str(self.ledger),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)

    def test_detect_reports_v6_for_this_repo(self) -> None:
        if not (
            REPO_ROOT / ".agents" / "skills" / "bmad-create-epics-and-stories"
        ).is_dir():
            self.skipTest("authoring-repo-only assertion")
        payload = run("detect", "--project-root", str(REPO_ROOT))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["model"], "v6")
        self.assertEqual(payload["hub"], "bmad-help")
        self.assertIn("bmad-build", payload["skills"])

    def test_init_creates_valid_ledger_and_memlog(self) -> None:
        payload = self.init()
        self.assertTrue(payload["ok"])
        self.assertTrue(self.ledger.is_file())
        memlog = self.ledger.parent / ".memlog.md"
        self.assertTrue(memlog.is_file())
        text = memlog.read_text()
        self.assertIn("- (event) ", text)
        self.assertIn("workstream ws-001 created", text)
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated["errors"])

    def test_set_closes_nested_gate_and_advances_summary(self) -> None:
        self.init()
        for gate in ("requirements", "stories", "sprint"):
            payload = run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.plan.{gate}.status",
                "--value",
                "passed",
            )
            self.assertTrue(payload["ok"])
        for gate in ("ux", "architecture"):
            run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.plan.{gate}.status",
                "--value",
                "overridden",
                "--reason",
                "not applicable",
            )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.status",
            "--value",
            "done",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_phase"], "solution")
        self.assertNotIn("plan.requirements", summary["open_gates"])

    def test_append_evidence_and_log(self) -> None:
        self.init()
        (self.tmp / "spec.md").write_text("# spec\n", encoding="utf-8")
        run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--value",
            "spec.md",
        )
        run("log", "--plan", str(self.ledger), "--text", "plan.requirements passed")
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["phases"][0]["evidence"], ["spec.md"])
        memlog = (self.ledger.parent / ".memlog.md").read_text()
        self.assertIn("plan.requirements passed", memlog)
        self.assertIn("updated:", memlog.split("---")[1])

    def test_validate_rejects_bad_schema(self) -> None:
        self.init()
        refused = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "schema",
            "--value",
            "wrong/0",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.edit_ledger('data["schema"] = "wrong/0"')
        validated = run("validate", "--plan", str(self.ledger))
        self.assertFalse(validated["ok"])
        self.assertTrue(any("schema" in error for error in validated["errors"]))

    def test_init_honors_custom_plan_and_memlog_paths(self) -> None:
        ledger = self.tmp / "custom" / "ledger.yaml"
        memlog = self.tmp / "audit" / "trail.md"
        payload = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Custom Paths",
            "--track",
            "feature",
            "--size",
            "epic",
            "--plan",
            str(ledger),
            "--memlog",
            str(memlog),
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(Path(payload["ledger"]).resolve(), ledger.resolve())
        self.assertEqual(Path(payload["memlog"]).resolve(), memlog.resolve())
        self.assertTrue(ledger.is_file())
        self.assertTrue(memlog.is_file())
        run("log", "--plan", str(ledger), "--memlog", str(memlog), "--text", "custom")
        self.assertIn("custom", memlog.read_text())

    def test_trivial_fix_starts_at_build_and_skips_plan(self) -> None:
        payload = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Trivial Fix",
            "--track",
            "fix",
            "--size",
            "trivial",
        )
        self.assertTrue(payload["ok"])
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_action"]["action"], "build.ticket")
        self.assertEqual(summary["phases"][0]["status"], "skipped")
        self.assertNotIn("verify.trace", summary["required_open"])

    def test_ticket_gates_advance_build(self) -> None:
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Trivial Fix",
            "--track",
            "fix",
            "--size",
            "trivial",
        )
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "1.3",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_action"]["action"], "build.review")
        self.assertEqual(summary["tickets"]["count"], 1)
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "1.3",
            "--gate",
            "review",
            "--status",
            "passed",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_action"]["action"], "build.done")

    def test_migrate_materializes_levels_and_tickets(self) -> None:
        self.init()

        self.edit_ledger(
            'data["workstreams"]["ws-001"]["gates"]["plan"]["requirements"]'
            '["level"] = None'
        )
        self.edit_ledger(
            'del data["workstreams"]["ws-001"]["tickets"]'
        )
        migrated = run("migrate", "--plan", str(self.ledger))
        self.assertTrue(migrated["ok"])
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)
        self.assertEqual(validated["warnings"], [])
        workstream = self.read_ledger()["workstreams"]["ws-001"]
        self.assertIn("tickets", workstream)

    def test_detect_reports_inventory(self) -> None:
        payload = run("detect", "--project-root", str(REPO_ROOT))
        self.assertTrue(payload["ok"])
        self.assertIn("inventory", payload)
        for key in (
            "has_planning_artifacts",
            "has_epics_tickets",
            "has_application_code",
            "artifact_paths",
        ):
            self.assertIn(key, payload["inventory"])

    def test_summary_flags_stale_cached_next(self) -> None:
        self.init()
        # `next` is derived, so a hand edit is the only way to create a stale
        # cache; `set` refuses it.
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["next"] = '
            '{"phase": "plan", "action": "plan.stories"}'
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertTrue(summary["next_action_stale"])
        self.assertEqual(summary["next_action"]["action"], "frame.spec")

    def test_reconcile_reports_missing_and_orphan_pointers(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.spec",
            "--value",
            "_bmad-output/specs/missing/SPEC.md",
        )
        prd = self.tmp / "_bmad-output" / "planning-artifacts" / "prd-checkout" / "prd.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text("# PRD\n", encoding="utf-8")
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        self.assertFalse(payload["ok"])
        workstream = payload["workstreams"][0]
        self.assertEqual(workstream["missing_pointers"][0]["artifact"], "spec")
        self.assertEqual(workstream["orphan_pointers"][0]["artifact"], "prd")
        self.assertEqual(workstream["gates_to_block"], ["plan.requirements"])

    def test_verify_return_checks_status_artifacts_and_ledger(self) -> None:
        self.init()
        artifact = self.tmp / "artifact.md"
        artifact.write_text("# Artifact\n", encoding="utf-8")
        ledger_sha, memlog_sha = digests(self.ledger)
        good = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"artifact.md"}],"evidence":["artifact.md"]}',
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertTrue(good["ok"], good)
        missing = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"missing.md"}]}',
        )
        self.assertFalse(missing["ok"])
        blocked = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"blocked","artifacts":[]}',
        )
        self.assertFalse(blocked["ok"])

    def test_validate_rejects_bad_ticket_gate(self) -> None:
        self.init()
        run(
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
            "open",
        )

        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"]["T1"]["gates"]["review"]'
            '["status"] = "bogus"'
        )
        validated = run("validate", "--plan", str(self.ledger))
        self.assertFalse(validated["ok"])
        self.assertTrue(any("tickets.T1" in error for error in validated["errors"]))

    def init_track(self, track: str, size: str | None = None, name: str = "Test Product") -> dict:
        args = [
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            name,
            "--track",
            track,
        ]
        if size:
            args.extend(["--size", size])
        return run(*args)

    def close_fix_trivial(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-tickets",
            "--reason",
            "fixture",
        )

    def test_audit_starts_at_review_without_plan_gates(self) -> None:
        self.init_track("audit")
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_action"]["action"], "build.review")
        self.assertEqual(summary["next_action"]["ticket"], "audit")
        self.assertEqual(summary["phases"][0]["status"], "skipped")
        self.assertNotIn("plan.requirements", summary["required_open"])
        self.assertNotIn("plan.stories", summary["required_open"])
        self.assertIn("build.audit.review", summary["required_open"])
        self.assertEqual(summary["workstream"]["size"], "one-session")
        missing = [item["missing_gate"] for item in summary["locked_phases"]]
        self.assertNotIn("plan.requirements", missing)

    def test_audit_advances_after_review(self) -> None:
        self.init_track("audit")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "audit",
            "--gate",
            "review",
            "--status",
            "passed",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertNotEqual(summary["next_action"]["action"], "build.review")
        self.assertEqual(summary["next_action"]["phase"], "verify")
        for gate in ("test_review", "nfr"):
            run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.verify.{gate}.status",
                "--value",
                "overridden",
                "--reason",
                "not applicable to this audit",
            )
        run(
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
        trace = self.tmp / "_bmad-output" / "test-artifacts" / "trace.md"
        trace.parent.mkdir(parents=True, exist_ok=True)
        trace.write_text("# trace\n", encoding="utf-8")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.trace",
            "--value",
            "_bmad-output/test-artifacts/trace.md",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_action"]["action"], "close.mark_done")
        done = run("done", "--plan", str(self.ledger))
        self.assertTrue(done["ok"], done)
        summary = run("summary", "--plan", str(self.ledger), "--workstream", "ws-001")
        self.assertEqual(summary["workstream"]["status"], "done")

    def test_done_command_blocks_and_then_marks_done(self) -> None:
        self.init_track("audit")
        blocked = run("done", "--plan", str(self.ledger))
        self.assertFalse(blocked["ok"])
        self.assertIn("build.audit.review", blocked["error"])
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "audit",
            "--gate",
            "review",
            "--status",
            "passed",
        )
        for gate in ("test_review", "nfr", "trace"):
            extra = [] if gate == "trace" else ["--reason", "not applicable"]
            run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.verify.{gate}.status",
                "--value",
                "overridden" if gate != "trace" else "passed",
                *extra,
            )
        trace = self.tmp / "_bmad-output" / "test-artifacts" / "trace.md"
        trace.parent.mkdir(parents=True, exist_ok=True)
        trace.write_text("# trace\n", encoding="utf-8")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.trace",
            "--value",
            "_bmad-output/test-artifacts/trace.md",
        )
        done = run("done", "--plan", str(self.ledger))
        self.assertTrue(done["ok"], done)

    def test_trivial_completion_recommends_mark_done(self) -> None:
        self.init_track("fix", "trivial")
        self.assertEqual(
            run("summary", "--plan", str(self.ledger))["next_action"]["action"],
            "build.ticket",
        )
        for gate in ("ticket", "review", "done"):
            payload = run(
                "ticket",
                "--plan",
                str(self.ledger),
                "--id",
                "T1",
                "--gate",
                gate,
                "--status",
                "passed",
            )
            self.assertTrue(payload["ok"], payload)
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_action"]["action"], "close.mark_done")
        self.assertTrue(summary["phases"][2]["complete"])
        optional = [action["action"] for action in summary["optional_actions"]]
        self.assertIn("close.retro", optional)
        self.assertIn("close.walkthrough", optional)

    def test_optional_actions_skip_locked_phases(self) -> None:
        self.init_track("fix", "trivial")
        summary = run("summary", "--plan", str(self.ledger))
        locked = {item["phase"] for item in summary["locked_phases"]}
        offered = {item["phase"] for item in summary["optional_actions"]}
        self.assertFalse(offered & locked, (offered, locked))
        self.assertEqual(summary["optional_actions"], [])

        for gate in ("ticket", "review", "done"):
            payload = run(
                "ticket",
                "--plan",
                str(self.ledger),
                "--id",
                "T1",
                "--gate",
                gate,
                "--status",
                "passed",
            )
            self.assertTrue(payload["ok"], payload)
        summary = run("summary", "--plan", str(self.ledger))
        locked = {item["phase"] for item in summary["locked_phases"]}
        offered = {item["phase"] for item in summary["optional_actions"]}
        self.assertFalse(offered & locked, (offered, locked))
        self.assertIn(
            "close.retro",
            [action["action"] for action in summary["optional_actions"]],
        )

    def test_override_requires_reason(self) -> None:
        self.init()
        refused_result = run_raw(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "overridden",
        )
        self.assertNotEqual(refused_result.returncode, 0)
        self.assertIn("needs --reason", json.loads(refused_result.stdout)["error"])
        allowed = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "overridden",
            "--reason",
            "design doc accepted",
        )
        self.assertTrue(allowed["ok"])
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)
        summary = run("summary", "--plan", str(self.ledger))
        requirement = next(
            gate for gate in summary["phases"][0]["gates"] if gate["id"] == "plan.requirements"
        )
        self.assertEqual(requirement["override_reason"], "design doc accepted")

    def test_ticket_gate_order_and_override_reason_enforced(self) -> None:
        self.init_track("fix", "one-session")
        early_done = run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "done",
            "--status",
            "passed",
        )
        self.assertFalse(early_done["ok"])
        early_review = run(
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
        self.assertFalse(early_review["ok"])
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        no_reason = run_raw(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "review",
            "--status",
            "overridden",
        )
        self.assertNotEqual(no_reason.returncode, 0)
        self.assertIn("needs --reason", json.loads(no_reason.stdout)["error"])
        with_reason = run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "review",
            "--status",
            "overridden",
            "--reason",
            "accepted risk",
        )
        self.assertTrue(with_reason["ok"])
        done_after_override = run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "done",
            "--status",
            "passed",
        )
        self.assertFalse(done_after_override["ok"])

    def test_blocked_gate_is_valid_and_blocks_the_next_action(self) -> None:
        self.init()
        blocked = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "blocked",
        )
        self.assertTrue(blocked["ok"])
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIn("plan.requirements", summary["blocked_gates"])
        self.assertEqual(summary["next_action"]["action"], "frame.spec")
        self.assertEqual(summary["next_action"]["gate"], "plan.requirements")

    def test_second_init_pauses_first_workstream(self) -> None:
        self.init()
        second = self.init_track("fix", name="Second")
        self.assertTrue(second["ok"])
        self.assertEqual(second["paused"], ["ws-001"])
        self.assertEqual(second["workstream"], "ws-002")
        summary = run("summary", "--plan", str(self.ledger), "--workstream", "ws-001")
        self.assertEqual(summary["workstream"]["status"], "paused")
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)

    def test_validate_accepts_one_active_workstream_after_a_switch(self) -> None:
        self.init()
        self.init_track("fix", name="Second")
        switched = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "active",
        )
        self.assertTrue(switched["ok"], switched)
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)
        self.assertEqual(self.read_ledger()["workstreams"]["ws-002"]["status"], "paused")

    def test_summary_counts_include_ticket_gates(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "open",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIn("build.T1.ticket", summary["required_open"])
        self.assertIn("build.T1.ticket", summary["phases"][2]["blocking"])

    def test_fix_track_defaults_to_lean_gate_levels(self) -> None:
        self.init_track("fix")
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["workstream"]["size"], "one-session")
        self.assertNotIn("plan.requirements", summary["required_open"])
        self.assertNotIn("plan.sprint", summary["required_open"])
        self.assertNotIn("verify.trace", summary["required_open"])
        second = self.init_track("fix", "epic", name="Big Fix")
        self.assertTrue(second["ok"])
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["workstream"]["size"], "epic")
        self.assertNotIn("plan.requirements", summary["required_open"])
        self.assertNotIn("plan.sprint", summary["required_open"])
        self.assertNotIn("verify.trace", summary["required_open"])
        self.assertIn("plan.stories", summary["conditional_open"])

    def test_detect_missing_core_excludes_optional_code_review(self) -> None:
        for name in (
            "bmad-prd",
            "bmad-create-epics-and-stories",
            "bmad-sprint-planning",
            "bmad-build",
        ):
            skill = self.tmp / ".agents" / "skills" / name
            skill.mkdir(parents=True, exist_ok=True)
            (skill / "SKILL.md").write_text("---\nname: test\n---\n", encoding="utf-8")
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(payload["model"], "v6")
        self.assertEqual(payload["missing_core"], [])
        self.assertIn("bmad-code-review", payload["missing_optional"])

    def test_verify_return_rejects_outside_artifacts(self) -> None:
        self.init()
        outside = REPO_ROOT / "README.md"
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            f'{{"status":"done","role":"dev","action":"build.ticket","artifacts":[{{"path":"{outside}"}}]}}',
        )
        self.assertFalse(payload["ok"])
        self.assertIn(str(outside), payload["outside_artifacts"])

    def test_required_gate_uses_overridden_not_skipped(self) -> None:
        self.init()
        refused = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "skipped",
            "--reason",
            "requirements are covered by the incident ticket",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("use `overridden`", json.loads(refused.stdout)["error"])
        allowed = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "overridden",
            "--reason",
            "requirements are covered by the incident ticket",
        )
        self.assertTrue(allowed["ok"])
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)

    def test_done_refuses_unbuilt_build_phase(self) -> None:
        self.init_track("fix", "trivial")
        blocked = run("done", "--plan", str(self.ledger))
        self.assertFalse(blocked["ok"])
        self.assertIn("no ticket built", blocked["error"])

    # -- gate integrity -----------------------------------------------------

    def test_phase_done_with_open_gates_is_refused(self) -> None:
        self.init()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.status",
            "--value",
            "done",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("plan.requirements", refused["error"])
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIn("plan.requirements", summary["required_open"])

    def test_build_phase_done_with_open_ticket_gates_is_refused(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        refused = run(
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
        self.assertFalse(refused["ok"])
        self.assertIn("build.T1.review", refused["error"])

    def test_audit_without_ticket_cannot_close(self) -> None:
        self.init_track("audit")
        self.edit_ledger(
            "del data['workstreams']['ws-001']['tickets']['audit']"
        )
        for gate, status in (
            ("trace", "passed"),
            ("nfr", "overridden"),
            ("test_review", "overridden"),
        ):
            extra = [] if status == "passed" else ["--reason", "not applicable"]
            run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.verify.{gate}.status",
                "--value",
                status,
                *extra,
            )
        done = run("done", "--plan", str(self.ledger))
        self.assertFalse(done["ok"])
        self.assertIn("build.audit.review", done["error"])

    def test_gate_level_tamper_does_not_unlock_close(self) -> None:
        self.init()

        self.edit_ledger(
            'data["workstreams"]["ws-001"]["gates"]["verify"]["trace"]'
            '["level"] = "optional"'
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIn("verify.trace", summary["required_open"])
        validated = run("validate", "--plan", str(self.ledger))
        self.assertFalse(validated["ok"])
        self.assertTrue(any("resolved" in error for error in validated["errors"]))

    def test_invalid_gate_status_is_rejected(self) -> None:
        self.init()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "passsed",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("unknown gate status", refused["error"])

    def test_set_cannot_bypass_ticket_order(self) -> None:
        self.init_track("fix", "one-session")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "open",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.review.status",
            "--value",
            "passed",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("before build.ticket", refused["error"])

    def test_ticket_status_is_required(self) -> None:
        self.init_track("fix", "trivial")
        result = subprocess.run(
            [
                "uv",
                "run",
                "--no-cache",
                str(SCRIPT),
                "ticket",
                "--plan",
                str(self.ledger),
                "--id",
                "T1",
                "--gate",
                "ticket",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--status", result.stderr)

    # -- write safety -------------------------------------------------------

    def test_set_without_workstream_uses_active(self) -> None:
        self.init()
        payload = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "phases.plan.note",
            "--value",
            "active note",
        )
        self.assertTrue(payload["ok"])
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["phases"][0]["note"], "active note")
        self.assertFalse(
            any(line.startswith("phases:") for line in self.ledger.read_text().splitlines())
        )

    def test_unknown_gate_path_is_rejected(self) -> None:
        self.init()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirement.status",
            "--value",
            "passed",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("unknown gate", refused["error"])

    def test_decisions_are_append_only(self) -> None:
        self.init()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "decisions",
            "--value",
            "[]",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("append-only", refused["error"])
        appended = run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "decisions",
            "--value",
            '{"decision":"keep this"}',
        )
        self.assertTrue(appended["ok"])
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["decisions"][0]["decision"], "keep this")
        self.assertIn("at", summary["decisions"][0])

    def test_init_force_requires_reason_and_backs_up(self) -> None:
        self.init()
        run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "decisions",
            "--value",
            '{"decision":"keep me"}',
        )
        refused = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Reset",
            "--track",
            "feature",
            "--size",
            "epic",
            "--force",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("--reason", refused["error"])
        forced = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Reset",
            "--track",
            "feature",
            "--size",
            "epic",
            "--force",
            "--reason",
            "test reset",
        )
        self.assertTrue(forced["ok"])
        self.assertTrue((self.ledger.parent / "plan.yaml.bak").is_file())
        self.assertIn(
            "ledger reset from",
            (self.ledger.parent / ".memlog.md").read_text(),
        )

    def test_init_preserves_confirmed_model(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad.model",
            "--value",
            "current",
        )
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Second",
            "--track",
            "fix",
        )
        summary = run("summary", "--plan", str(self.ledger), "--workstream", "ws-002")
        self.assertEqual(summary["model"], "current")

    def test_missing_template_fails(self) -> None:
        refused = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "X",
            "--track",
            "feature",
            "--size",
            "epic",
            "--template",
            "missing-template.yaml",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("template not found", refused["error"])

    # -- handoff validation -------------------------------------------------

    def test_verify_return_requires_artifacts_and_rejects_ledger(self) -> None:
        self.init()
        empty = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[]}',
        )
        self.assertFalse(empty["ok"])
        self.assertIn("no artifacts", " ".join(empty["reasons"]))
        ledger_artifact = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"_bmad-output/sdlc/plan.yaml"}]}',
        )
        self.assertFalse(ledger_artifact["ok"])
        self.assertIn("ledger", " ".join(ledger_artifact["reasons"]))
        artifact = self.tmp / "artifact.md"
        artifact.write_text("# Artifact\n", encoding="utf-8")
        questions = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"artifact.md"}],"evidence":["artifact.md"],"open_questions":["q"]}',
        )
        self.assertFalse(questions["ok"])
        ledger_sha, memlog_sha = digests(self.ledger)
        accepted = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"artifact.md"}],"evidence":["artifact.md"],"open_questions":["q"]}',
            "--accept-questions",
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertTrue(accepted["ok"], accepted)

    # -- detection and routing ---------------------------------------------

    def test_detect_alias_aware_missing_core(self) -> None:
        for name in (
            "bmad-create-epics-and-stories",
            "bmad-sprint-planning",
            "bmad-build",
            "bmad-agent-pm",
        ):
            skill = self.tmp / ".agents" / "skills" / name
            skill.mkdir(parents=True, exist_ok=True)
            (skill / "SKILL.md").write_text("---\nname: test\n---\n", encoding="utf-8")
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(payload["model"], "v6")
        self.assertEqual(payload["missing_core"], [])

    def test_detect_reads_nested_sprint_status(self) -> None:
        sprint = (
            self.tmp
            / "_bmad-output"
            / "implementation-artifacts"
            / "sprint-status.yaml"
        )
        sprint.parent.mkdir(parents=True, exist_ok=True)
        sprint.write_text(
            "development_status:\n"
            "  epic-1: in-progress\n"
            "  1-1-story: ready-for-dev\n"
            "  1-2-story: review\n",
            encoding="utf-8",
        )
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(payload["inventory"]["epic_count"], 1)
        self.assertEqual(payload["inventory"]["open_story_count"], 2)
        self.assertTrue(payload["inventory"]["has_epics_tickets"])

    def test_fix_one_session_starts_at_build(self) -> None:
        self.init_track("fix")
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["workstream"]["size"], "one-session")
        self.assertEqual(summary["next_action"]["action"], "build.ticket")
        self.assertNotIn("plan.stories", summary["required_open"])

    # -- reconcile and dashboard -------------------------------------------

    def test_reconcile_reports_missing_evidence_and_applies_orphans(self) -> None:
        self.init()
        missing = self.tmp / "docs" / "missing.md"
        missing.parent.mkdir(parents=True, exist_ok=True)
        missing.write_text("# evidence\n", encoding="utf-8")
        run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--value",
            "docs/missing.md",
        )
        # The pointer is accepted only while the file exists; deleting it after
        # the write is what a later session sees.
        missing.unlink()
        prd = self.tmp / "_bmad-output" / "planning-artifacts" / "prd" / "prd.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text("# PRD\n", encoding="utf-8")
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["missing_evidence_count"], 1)
        self.assertEqual(payload["workstreams"][0]["phases_to_block"], ["plan"])
        applied = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--write",
        )
        self.assertTrue(any("artifacts.prd" in item for item in applied["applied"]))
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIn("prd", summary["workstream"]["artifacts"])

    def test_summary_after_done_keeps_full_shape(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review", "done"):
            run(
                "ticket",
                "--plan",
                str(self.ledger),
                "--id",
                "T1",
                "--gate",
                gate,
                "--status",
                "passed",
            )
        run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-tickets",
            "--reason",
            "summary shape fixture",
        )
        summary = run("summary", "--plan", str(self.ledger))
        for key in (
            "phases",
            "tickets",
            "open_gates",
            "blocked_gates",
            "required_open",
            "conditional_open",
            "optional_actions",
            "locked_phases",
            "memlog",
            "phase",
        ):
            self.assertIn(key, summary)
        self.assertIsNone(summary["next_action"])
        self.assertIsNone(summary["active_workstream"])
        self.assertEqual(summary["track"], "fix")
        self.assertEqual(summary["size"], "trivial")
        self.assertEqual(summary["phase"], "close")

    def test_current_phase_and_next_cache_refresh(self) -> None:
        self.init()
        for gate in ("requirements", "stories", "sprint"):
            run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.plan.{gate}.status",
                "--value",
                "passed",
            )
        for gate in ("ux", "architecture"):
            run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.plan.{gate}.status",
                "--value",
                "overridden",
                "--reason",
                "not applicable",
            )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.status",
            "--value",
            "done",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["workstream"]["current_phase"], "solution")
        self.assertEqual(summary["next_action"]["action"], "solution.test_design")
        self.assertEqual(
            summary["cached_next_action"]["action"], "solution.test_design"
        )
        self.assertFalse(summary["next_action_stale"])

    def test_resize_recomputes_levels_and_set_size_is_refused(self) -> None:
        self.init()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "size",
            "--value",
            "one-session",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("resize", refused["error"])
        resized = run(
            "resize",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--size",
            "one-session",
        )
        self.assertTrue(resized["ok"])
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["workstream"]["size"], "one-session")
        self.assertIn("plan.requirements", summary["conditional_open"])

    def test_custom_ledger_requires_project_root(self) -> None:
        ledger = self.tmp / "custom" / "ledger.yaml"
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Custom",
            "--track",
            "feature",
            "--size",
            "epic",
            "--plan",
            str(ledger),
            "--memlog",
            str(self.tmp / "custom" / "memlog.md"),
        )
        refused = run("reconcile", "--plan", str(ledger))
        self.assertFalse(refused["ok"])
        self.assertIn("--project-root", refused["error"])

    def test_paused_workstream_has_no_next_and_done_refuses(self) -> None:
        self.init()
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
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIsNone(summary["next_action"])
        done = run("done", "--plan", str(self.ledger), "--workstream", "ws-001")
        self.assertFalse(done["ok"])
        self.assertIn("paused", done["error"])

    def test_switching_active_workstream_pauses_previous(self) -> None:
        self.init()
        self.init_track("fix", name="Second")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "active_workstream",
            "--value",
            "ws-001",
        )
        first = run("summary", "--plan", str(self.ledger), "--workstream", "ws-001")
        second = run("summary", "--plan", str(self.ledger), "--workstream", "ws-002")
        self.assertEqual(first["workstream"]["status"], "active")
        self.assertEqual(second["workstream"]["status"], "paused")
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])

    def test_memlog_lines_have_timestamps(self) -> None:
        self.init()
        text = (self.ledger.parent / ".memlog.md").read_text()
        self.assertRegex(text, r"- \(event\) \d{4}-\d{2}-\d{2}T")

    def test_verify_return_rejects_custom_memlog_and_directories(self) -> None:
        trail = self.tmp / "audit" / "trail.md"
        trail.parent.mkdir(parents=True)
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--memlog",
            str(trail),
            "--name",
            "Test Product",
            "--track",
            "feature",
            "--size",
            "epic",
        )
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--memlog",
            str(trail),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"audit/trail.md"}]}',
        )
        self.assertFalse(payload["ok"])
        self.assertIn(
            "ledger, audit trail, or return file used as artifact",
            " ".join(payload["reasons"]),
        )
        (self.tmp / "dir").mkdir()
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"dir"}]}',
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["missing_artifacts"], ["dir"])

    def test_resize_audit_to_fix_removes_synthetic_ticket(self) -> None:
        self.init_track("audit", "one-session")
        payload = run(
            "resize",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--track",
            "fix",
        )
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])
        summary = run("summary", "--plan", str(self.ledger))
        self.assertNotIn("audit", summary["tickets"]["items"])

    def test_resize_larger_reopens_a_skipped_phase(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.status",
            "--value",
            "skipped",
            "--reason",
            "not needed at trivial",
        )
        payload = run(
            "resize",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--size",
            "epic",
            "--reason",
            "larger scope",
        )
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("reopened: plan", trail)
        self.assertIn("reason: larger scope", trail)

    def test_resize_reopening_a_phase_needs_a_reason(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.status",
            "--value",
            "skipped",
            "--reason",
            "not needed at trivial",
        )
        refused = run(
            "resize",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--size",
            "epic",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("pass --reason", refused["error"])

    def test_model_switch_recomputes_levels(self) -> None:
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Test Product",
            "--track",
            "feature",
            "--size",
            "epic",
            "--model",
            "unknown",
        )
        payload = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad.model",
            "--value",
            "v6",
        )
        self.assertTrue(payload["ok"], payload)
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)
        summary = run("summary", "--plan", str(self.ledger))
        sprint = next(
            gate for gate in summary["phases"][0]["gates"] if gate["id"] == "plan.sprint"
        )
        self.assertEqual(sprint["level"], "required")

    def test_fix_ignores_the_configured_default_size(self) -> None:
        payload = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Fix",
            "--track",
            "fix",
            "--default-size",
            "epic",
        )
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(run("summary", "--plan", str(self.ledger))["workstream"]["size"], "one-session")

    def test_locked_phases_cover_later_phases_and_close_is_not_complete(self) -> None:
        self.init()
        summary = run("summary", "--plan", str(self.ledger))
        phases = {item["phase"] for item in summary["locked_phases"]}
        self.assertTrue({"solution", "build", "verify", "close"} <= phases, phases)
        close = next(item for item in summary["phases"] if item["phase"] == "close")
        self.assertFalse(close["complete"])

    def test_set_rejects_derived_and_mis_scoped_writes(self) -> None:
        self.init()
        cases = [
            ["--root", "--path", "gates.plan.requirements.status", "--value", "passed"],
            ["--workstream", "ws-001", "--path", "bmad.model", "--value", "v6"],
            ["--path", "phases.plan.gate", "--value", "optional"],
            ["--path", "gates.plan.requirements.level", "--value", "optional"],
        ]
        for extra in cases:
            payload = run("set", "--plan", str(self.ledger), *extra)
            self.assertFalse(payload["ok"], (extra, payload))

    def test_set_node_write_requires_replace_and_respects_phase_guard(self) -> None:
        self.init()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "phases.close",
            "--value",
            '{"status":"done","role":"dev","action":"build.ticket"}',
        )
        self.assertFalse(refused["ok"])
        guarded = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "phases.close",
            "--value",
            '{"status":"done","role":"dev","action":"build.ticket"}',
            "--replace",
            "--reason",
            "tidy",
        )
        self.assertFalse(guarded["ok"])

    def test_reconcile_blocks_a_passed_gate_without_evidence(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "passed",
        )
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        self.assertEqual(
            payload["workstreams"][0]["gates_to_block"], ["plan.requirements"]
        )

    def test_done_refuses_missing_evidence_and_a_blocked_phase(self) -> None:
        self.init_track("fix", "one-session")
        trace = self.tmp / "trace.md"
        trace.write_text("# trace\n", encoding="utf-8")
        run(
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
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.trace",
            "--value",
            "trace.md",
        )
        for gate in ("ticket", "tests", "review", "done"):
            run(
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
                "passed",
            )
        trace.unlink()
        refused = run("done", "--plan", str(self.ledger), "--workstream", "ws-001")
        self.assertFalse(refused["ok"])
        self.assertIn("missing evidence", refused["error"])
        trace.write_text("# trace\n", encoding="utf-8")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.build.status",
            "--value",
            "blocked",
        )
        refused = run("done", "--plan", str(self.ledger), "--workstream", "ws-001")
        self.assertFalse(refused["ok"])
        self.assertIn("blocked", refused["error"])

    def test_done_refuses_tickets_without_a_ticket_artifact(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        refused = run("done", "--plan", str(self.ledger))
        self.assertFalse(refused["ok"])
        self.assertIn("no readable ticket artifact", refused["error"])
        accepted = run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-tickets",
            "--reason",
            "ledger-only fixture",
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_ticket_refuses_a_blocked_gate_passed(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.review.status",
            "--value",
            "blocked",
        )
        refused = run(
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
        )
        self.assertFalse(refused["ok"])
        self.assertIn("blocked gate cannot be passed", refused["error"])

    def test_reopening_a_decided_gate_needs_a_reason_and_order(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review"):
            run(
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
                "passed",
            )
        refused_result = run_raw(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "open",
        )
        self.assertNotEqual(refused_result.returncode, 0)
        self.assertIn("needs --reason", json.loads(refused_result.stdout)["error"])
        refused = run_raw(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "open",
            "--reason",
            "retry",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn(
            "later gates are decided: review", json.loads(refused.stdout)["error"]
        )
        reopened = run(
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
            "open",
            "--reason",
            "rework the review",
        )
        self.assertTrue(reopened["ok"], reopened)
        summary = run("summary", "--plan", str(self.ledger))
        review = summary["tickets"]["items"]["T1"]["gates"]["review"]
        self.assertEqual(review["status"], "open")
        self.assertIsNone(review["override_reason"])

    def test_set_reopening_a_decided_gate_needs_a_reason(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        refused_result = run_raw(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.ticket.status",
            "--value",
            "open",
        )
        self.assertNotEqual(refused_result.returncode, 0)
        self.assertIn("needs --reason", json.loads(refused_result.stdout)["error"])
        accepted = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.ticket.status",
            "--value",
            "open",
            "--reason",
            "reopen for rework",
        )
        self.assertTrue(accepted["ok"], accepted)
        summary = run("summary", "--plan", str(self.ledger))
        ticket = summary["tickets"]["items"]["T1"]["gates"]["ticket"]
        self.assertEqual(ticket["status"], "open")
        self.assertIsNone(ticket["override_reason"])

    def test_set_edits_a_dotted_ticket_id(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "1.3",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        written = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.1.3.note",
            "--value",
            "phantom",
            "--replace",
            "--reason",
            "dotted id fixture",
        )
        self.assertTrue(written["ok"], written)
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(list(summary["tickets"]["items"]), ["1.3"])

    def test_set_refuses_to_create_an_unknown_dotted_ticket(self) -> None:
        self.init_track("fix", "trivial")
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.1.3.note",
            "--value",
            "phantom",
            "--replace",
            "--reason",
            "probe",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("unknown ticket id", refused["error"])

    def test_node_replacement_cannot_pass_a_blocked_gate(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.review.status",
            "--value",
            "blocked",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.review",
            "--value",
            '{"status":"passed"}',
            "--replace",
            "--reason",
            "probe",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("blocked gate cannot be passed", refused["error"])
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.verify.trace.status",
            "--value",
            "blocked",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.verify.trace",
            "--value",
            '{"status":"passed"}',
            "--replace",
            "--reason",
            "probe",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("blocked gate cannot be passed", refused["error"])

    def test_gate_node_replacement_needs_a_status(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "open",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.ticket",
            "--value",
            '{"decided_at":null}',
            "--replace",
            "--reason",
            "compact",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("needs a status", refused["error"])

    def test_reopening_a_gate_on_a_done_workstream_is_refused(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-tickets",
            "--reason",
            "fixture",
        )
        refused = run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "done",
            "--status",
            "open",
            "--reason",
            "rework",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("workstream is done", refused["error"])
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)

    def test_reopening_a_done_workstream_needs_a_reason(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-tickets",
            "--reason",
            "fixture",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "active",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("reopening a done workstream needs --reason", refused["error"])
        accepted = run(
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
            "reopen for rework",
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_blocking_a_decided_gate_needs_a_reason(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        run(
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
            "overridden",
            "--reason",
            "review waived",
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
            "QA takes over the review",
        )
        refused_result = run_raw(
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
            "blocked",
        )
        self.assertNotEqual(refused_result.returncode, 0)
        self.assertIn("needs --reason", json.loads(refused_result.stdout)["error"])
        accepted = run(
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
            "blocked",
            "--reason",
            "reopen for rework",
        )
        self.assertTrue(accepted["ok"], accepted)
        summary = run("summary", "--plan", str(self.ledger))
        review = summary["tickets"]["items"]["T1"]["gates"]["review"]
        self.assertEqual(review["status"], "blocked")
        self.assertIsNone(review["override_reason"])
        self.assertIsNone(review["decided_at"])

    def test_reopening_a_skipped_phase_needs_a_reason(self) -> None:
        self.init_track("fix", "trivial")
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.status",
            "--value",
            "active",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("needs --reason", refused["error"])
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.build.status",
            "--value",
            "pending",
        )
        accepted = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.status",
            "--value",
            "active",
            "--reason",
            "rework the plan",
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_reopening_a_gate_under_a_done_phase_needs_the_phase_first(self) -> None:
        self.init_track("feature", "epic")
        for gate in ("requirements", "stories", "ux", "architecture"):
            run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.plan.{gate}.status",
                "--value",
                "passed",
            )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.status",
            "--value",
            "done",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "open",
            "--reason",
            "rework",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("reopen the phase first", refused["error"])

    def test_set_delete_removes_a_ticket(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "open",
        )
        deleted = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1",
            "--delete",
            "--reason",
            "withdrawn",
        )
        self.assertTrue(deleted["ok"], deleted)
        summary = run("summary", "--plan", str(self.ledger))
        self.assertNotIn("T1", summary["tickets"]["items"])
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)

    def test_delete_refuses_a_ticket_with_a_decided_gate(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        run(
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
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1",
            "--delete",
            "--reason",
            "withdrawn",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("decided gates", refused["error"])

    def test_done_accepts_missing_tickets_on_a_custom_ledger(self) -> None:
        custom = self.tmp / "custom-plan.yaml"
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--plan",
            str(custom),
            "--name",
            "Custom",
            "--track",
            "fix",
            "--size",
            "trivial",
        )
        for gate in ("ticket", "review", "done"):
            run(
                "ticket",
                "--plan",
                str(custom),
                "--id",
                "T1",
                "--gate",
                gate,
                "--status",
                "passed",
            )
        accepted = run(
            "done",
            "--plan",
            str(custom),
            "--project-root",
            str(self.tmp),
            "--accept-missing-tickets",
            "--reason",
            "ledger-only",
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_done_names_the_accepted_gap(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        accepted = run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-tickets",
            "--reason",
            "ledger-only",
        )
        self.assertTrue(accepted["ok"], accepted)
        trail = (self.tmp / "_bmad-output" / "sdlc" / ".memlog.md").read_text()
        self.assertIn("accepted missing ticket artifact for: T1", trail)
        self.assertIn("reason: ledger-only", trail)

    def test_done_expands_the_project_root_token(self) -> None:
        self.init_track("fix", "trivial")
        implementation = (
            self.tmp / "_bmad-output" / "implementation-artifacts" / "tickets"
        )
        implementation.mkdir(parents=True)
        (implementation / "tickets.toml").write_text(
            '[tickets.T1]\ntitle = "T1"\n', encoding="utf-8"
        )
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        accepted = run(
            "done",
            "--plan",
            str(self.ledger),
            "--project-root",
            "{project-root}",
            cwd=self.tmp,
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_done_normalizes_mixed_ticket_id_types(self) -> None:
        self.init_track("fix", "trivial")
        implementation = (
            self.tmp / "_bmad-output" / "implementation-artifacts" / "tickets"
        )
        implementation.mkdir(parents=True)
        (implementation / "tickets.toml").write_text(
            '[tickets.T1]\ntitle = "T1"\n', encoding="utf-8"
        )
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"][1] = '
            '{"title": "legacy", "gates": {"ticket": {"status": "passed"}, '
            '"review": {"status": "passed"}, "done": {"status": "passed"}}}'
        )
        accepted = run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-tickets",
            "--reason",
            "legacy id",
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_done_writes_to_the_memlog_recorded_at_init(self) -> None:
        trail = self.tmp / "audit" / "trail.md"
        trail.parent.mkdir(parents=True)
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--memlog",
            str(trail),
            "--name",
            "Fix",
            "--track",
            "fix",
            "--size",
            "trivial",
        )
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        payload = run(
            "done",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--accept-missing-tickets",
            "--reason",
            "memlog path fixture",
        )
        self.assertTrue(payload["ok"], payload)
        trail_text = trail.read_text()
        self.assertIn("marked done (", trail_text)
        self.assertIn("reason: memlog path fixture", trail_text)
        self.assertFalse((self.ledger.parent / ".memlog.md").exists())

    def test_pause_and_resume_track_the_active_workstream(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "status",
            "--value",
            "paused",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIsNone(summary["active_workstream"])
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])
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
        )
        self.assertEqual(
            run("summary", "--plan", str(self.ledger))["active_workstream"], "ws-001"
        )

    def test_artifact_pointer_must_be_a_string(self) -> None:
        self.init()
        payload = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.prd",
            "--value",
            "1.3",
        )
        self.assertFalse(payload["ok"])

    def test_init_rejects_an_empty_name(self) -> None:
        payload = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "   ",
            "--track",
            "feature",
            "--size",
            "epic",
        )
        self.assertFalse(payload["ok"])

    def test_current_model_detection_and_aliases(self) -> None:
        for skill in ("bmad-agent-po", "bmad-build"):
            directory = self.tmp / ".agents" / "skills" / skill
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(payload["model"], "current")
        self.assertNotIn("bmad-build", payload["missing_core"])
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Current",
            "--track",
            "feature",
            "--size",
            "epic",
            "--model",
            "current",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_action"]["skill"], "bmad-agent-po")

    def test_conditional_gate_uses_overridden_not_skipped(self) -> None:
        self.init()
        refused_skip = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.ux.status",
            "--value",
            "skipped",
            "--reason",
            "CLI only",
        )
        self.assertNotEqual(refused_skip.returncode, 0)
        self.assertIn("use `overridden`", json.loads(refused_skip.stdout)["error"])
        refused_result = run_raw(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.ux.status",
            "--value",
            "overridden",
        )
        self.assertNotEqual(refused_result.returncode, 0)
        self.assertIn("needs --reason", json.loads(refused_result.stdout)["error"])
        allowed = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.ux.status",
            "--value",
            "overridden",
            "--reason",
            "CLI only",
        )
        self.assertTrue(allowed["ok"], allowed)
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])

    def test_init_expands_the_project_root_token(self) -> None:
        payload = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Token",
            "--track",
            "feature",
            "--size",
            "epic",
            "--plan",
            "{project-root}/_bmad-output/sdlc/plan.yaml",
        )
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(self.ledger.is_file())
        self.assertFalse((self.tmp / "{project-root}").exists())

    def test_second_init_without_memlog_uses_the_recorded_path(self) -> None:
        trail = self.tmp / "audit" / "trail.md"
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "First",
            "--track",
            "feature",
            "--size",
            "epic",
            "--memlog",
            str(trail),
        )
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Second",
            "--track",
            "fix",
        )
        text = trail.read_text(encoding="utf-8")
        self.assertIn("workstream ws-002 created", text)
        self.assertFalse((self.ledger.parent / ".memlog.md").exists())

    def test_init_merges_template_bmad_keys(self) -> None:
        template = self.tmp / "template.yaml"
        template.write_text(
            "schema: bmad-sdlc/1\n"
            "project: null\ncreated: null\nupdated: null\n"
            "bmad:\n  model: unknown\n  custom_key: keep-me\n"
            "active_workstream: null\nworkstreams: {}\n",
            encoding="utf-8",
        )
        payload = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Custom",
            "--track",
            "feature",
            "--size",
            "epic",
            "--template",
            str(template),
        )
        self.assertTrue(payload["ok"], payload)
        self.assertIn("custom_key: keep-me", self.ledger.read_text(encoding="utf-8"))

    def test_init_rejects_a_non_mapping_template(self) -> None:
        template = self.tmp / "template.yaml"
        template.write_text("- one\n- two\n", encoding="utf-8")
        payload = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Bad",
            "--track",
            "feature",
            "--template",
            str(template),
        )
        self.assertFalse(payload["ok"])
        self.assertIn("root must be a mapping", payload["error"])

    def test_init_refuses_to_downgrade_a_confirmed_model(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad.model",
            "--value",
            "current",
        )
        refused = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Other",
            "--track",
            "feature",
            "--model",
            "unknown",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("downgrade", refused["error"])

    def test_init_rejects_a_duplicate_explicit_workstream_id(self) -> None:
        self.init()
        refused = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Other",
            "--track",
            "feature",
            "--workstream",
            "ws-001",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("already exists", refused["error"])
        summary = run("summary", "--plan", str(self.ledger), "--workstream", "ws-001")
        self.assertEqual(summary["workstream"]["name"], "Test Product")

    def test_detect_excludes_the_conductor_from_the_skill_inventory(self) -> None:
        if not (
            REPO_ROOT / ".agents" / "skills" / "bmad-create-epics-and-stories"
        ).is_dir():
            self.skipTest("authoring-repo-only assertion")
        payload = run("detect", "--project-root", str(REPO_ROOT))
        self.assertEqual(payload["model"], "v6")
        self.assertNotIn("bmad-sdlc", payload["skills"])

    def test_auto_skipped_phases_record_a_reason(self) -> None:
        self.init_track("fix", "trivial")
        summary = run("summary", "--plan", str(self.ledger))
        plan = next(item for item in summary["phases"] if item["phase"] == "plan")
        self.assertEqual(plan["status"], "skipped")
        self.assertIn("auto-skipped", plan["note"])

    def test_set_rejects_a_direct_workstreams_path(self) -> None:
        self.init()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "workstreams.ws-001.status",
            "--value",
            "paused",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("--workstream", refused["error"])

    def test_set_refuses_to_clear_a_decided_override_reason(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.ux.status",
            "--value",
            "overridden",
            "--reason",
            "CLI only",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.ux.override_reason",
            "--null",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("cannot clear decided gate metadata", refused["error"])

    def test_set_refuses_to_pass_a_blocked_gate(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "blocked",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "passed",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("blocked gate cannot be passed", refused["error"])

    def test_set_refuses_a_second_active_phase(self) -> None:
        self.init()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.solution.status",
            "--value",
            "active",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("only one phase may be active", refused["error"])

    def test_append_rejects_empty_evidence(self) -> None:
        self.init()
        refused = run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--null",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("non-empty", refused["error"])

    def test_append_rejects_a_pointer_to_a_missing_file(self) -> None:
        """An append-only pointer to a typo would block reconcile forever."""
        self.init()
        refused = run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--value",
            "docs/typo.md",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("existing non-empty file", refused["error"])
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["phases"][0]["evidence"], [])

    def test_resize_refuses_a_done_workstream(self) -> None:
        self.init()
        self.edit_ledger("data['workstreams']['ws-001']['status'] = 'done'")
        refused = run(
            "resize",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--size",
            "project",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("done", refused["error"])

    def test_done_refuses_a_skipped_build_with_no_ticket(self) -> None:
        self.init_track("fix", "trivial")
        self.edit_ledger(
            "data['workstreams']['ws-001']['phases']['build']['status'] = 'skipped'"
        )
        payload = run("done", "--plan", str(self.ledger))
        self.assertFalse(payload["ok"])
        self.assertIn("no ticket built", payload["error"])

    def test_audit_ticket_is_exempt_from_the_overlay_check(self) -> None:
        self.init_track("audit", "one-session")
        implementation = (
            self.tmp / "_bmad-output" / "implementation-artifacts" / "tickets"
        )
        implementation.mkdir(parents=True)
        (implementation / "tickets.toml").write_text(
            "[tickets.T1]\ntitle = \"T1\"\n", encoding="utf-8"
        )
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--id",
            "audit",
            "--gate",
            "review",
            "--status",
            "passed",
        )
        for gate in ("test_review", "nfr", "trace"):
            extra = [] if gate == "trace" else ["--reason", "not applicable"]
            run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.verify.{gate}.status",
                "--value",
                "passed" if gate == "trace" else "overridden",
                *extra,
            )
        trace = self.tmp / "_bmad-output" / "test-artifacts" / "trace.md"
        trace.parent.mkdir(parents=True, exist_ok=True)
        trace.write_text("# trace\n", encoding="utf-8")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.trace",
            "--value",
            "_bmad-output/test-artifacts/trace.md",
        )
        payload = run("done", "--plan", str(self.ledger))
        self.assertTrue(payload["ok"], payload)

    def test_done_requires_evidence_and_its_accept_flag_needs_a_reason(self) -> None:
        self.init_track("fix", "one-session")
        implementation = (
            self.tmp / "_bmad-output" / "implementation-artifacts" / "tickets"
        )
        implementation.mkdir(parents=True)
        (implementation / "tickets.toml").write_text(
            "[tickets.T1]\ntitle = \"T1\"\n", encoding="utf-8"
        )
        for gate in ("ticket", "tests", "review", "done"):
            run(
                "ticket",
                "--plan",
                str(self.ledger),
                "--id",
                "T1",
                "--gate",
                gate,
                "--status",
                "passed",
            )
        run(
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
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.trace",
            "--value",
            "missing-trace.md",
        )
        refused = run("done", "--plan", str(self.ledger))
        self.assertFalse(refused["ok"])
        self.assertIn("missing evidence", refused["error"])
        refused = run(
            "done", "--plan", str(self.ledger), "--accept-missing-evidence"
        )
        self.assertFalse(refused["ok"])
        self.assertIn("--accept-missing-evidence needs --reason", refused["error"])
        accepted = run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-evidence",
            "--reason",
            "accepted for the test",
        )
        self.assertTrue(accepted["ok"], accepted)
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("accepted missing evidence: trace=missing-trace.md", trail)

    def test_reconcile_and_done_report_ticket_overlay_drift(self) -> None:
        self.init_track("fix", "trivial")
        implementation = (
            self.tmp / "_bmad-output" / "implementation-artifacts" / "tickets"
        )
        implementation.mkdir(parents=True)
        (implementation / "tickets.toml").write_text(
            "[tickets.T1]\ntitle = \"T1\"\n", encoding="utf-8"
        )
        for gate in ("ticket", "tests", "review", "done"):
            run(
                "ticket",
                "--plan",
                str(self.ledger),
                "--id",
                "T2",
                "--gate",
                gate,
                "--status",
                "passed",
            )
        reconciled = run(
            "reconcile", "--plan", str(self.ledger), "--project-root", str(self.tmp)
        )
        self.assertEqual(
            reconciled["workstreams"][0]["tickets_missing_in_ledger"], ["T1"]
        )
        self.assertEqual(
            reconciled["workstreams"][0]["tickets_missing_in_artifacts"], ["T2"]
        )
        refused = run("done", "--plan", str(self.ledger))
        self.assertFalse(refused["ok"])
        self.assertIn("ledger tickets not found", refused["error"])
        accepted = run(
            "done",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--accept-missing-evidence",
            "--accept-missing-tickets",
            "--reason",
            "accepted for the test",
        )
        self.assertTrue(accepted["ok"], accepted)
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("accepted tickets absent from BMAD artifacts: T2", trail)

    def test_reconcile_reports_ambiguous_artifact_matches(self) -> None:
        self.init()
        planning = self.tmp / "_bmad-output" / "planning-artifacts"
        for name in ("one", "two"):
            target = planning / name
            target.mkdir(parents=True)
            (target / "SPEC.md").write_text("# spec\n", encoding="utf-8")
        payload = run(
            "reconcile", "--plan", str(self.ledger), "--project-root", str(self.tmp)
        )
        ambiguous = payload["workstreams"][0]["ambiguous_pointers"]
        self.assertTrue(any(item.startswith("spec:") for item in ambiguous), ambiguous)

    def test_verify_return_file_and_empty_artifact_flag(self) -> None:
        self.init()
        artifact = self.tmp / "artifact.md"
        artifact.write_text("# artifact\n", encoding="utf-8")
        return_file = self.tmp / "return.json"
        return_file.write_text(
            json.dumps(
                {
                    "status": "done",
                    "role": "dev",
                    "action": "build.ticket",
                    "artifacts": [{"path": "artifact.md"}],
                    "evidence": ["artifact.md"],
                }
            ),
            encoding="utf-8",
        )
        ledger_sha, memlog_sha = digests(self.ledger)
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return-file",
            str(return_file),
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertTrue(payload["ok"], payload)
        refused = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket"}',
        )
        self.assertFalse(refused["ok"])
        self.assertIn("no artifacts returned", " ".join(refused["reasons"]))
        no_evidence = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":["artifact.md"]}',
        )
        self.assertFalse(no_evidence["ok"])
        self.assertIn("no evidence returned", " ".join(no_evidence["reasons"]))
        unreasoned = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","evidence":["artifact.md"]}',
            "--allow-empty-artifacts",
        )
        self.assertFalse(unreasoned["ok"])
        self.assertIn("--allow-empty-artifacts needs --reason", unreasoned["error"])
        ledger_sha, memlog_sha = digests(self.ledger)
        allowed = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","evidence":["artifact.md"]}',
            "--allow-empty-artifacts",
            "--reason",
            "the brief produces no file",
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertTrue(allowed["ok"], allowed)

    def test_verify_return_rejects_zero_byte_artifacts(self) -> None:
        self.init()
        empty = self.tmp / "empty.md"
        empty.write_text("", encoding="utf-8")
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"empty.md"}]}',
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["missing_artifacts"], ["empty.md"])

    def test_verify_return_logs_accepted_open_questions(self) -> None:
        self.init()
        artifact = self.tmp / "artifact.md"
        artifact.write_text("# artifact\n", encoding="utf-8")
        ledger_sha, memlog_sha = digests(self.ledger)
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"artifact.md"}],'
            '"evidence":["artifact.md"],"open_questions":["which region?"]}',
            "--accept-questions",
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertTrue(payload["ok"], payload)
        memlog = run("summary", "--plan", str(self.ledger))["memlog"]
        self.assertIn(
            "accepted open questions: which region?",
            Path(memlog).read_text(encoding="utf-8"),
        )

    def test_config_precedence_and_token_substitution(self) -> None:
        self.init()
        bmad = self.tmp / "_bmad"
        bmad.mkdir(parents=True)
        (bmad / "config.toml").write_text(
            "[core]\noutput_folder = \"{project-root}/base-out\"\n"
            "[modules.tea]\ntest_artifacts = \"{project-root}/base-tests\"\n",
            encoding="utf-8",
        )
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(
            payload["paths"]["output_folder"], str((self.tmp / "base-out").resolve())
        )
        self.assertEqual(
            payload["paths"]["test_artifacts"],
            str((self.tmp / "base-tests").resolve()),
        )
        (bmad / "config.user.toml").write_text(
            "[core]\noutput_folder = \"{project-root}/user-out\"\n",
            encoding="utf-8",
        )
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(
            payload["paths"]["output_folder"], str((self.tmp / "user-out").resolve())
        )
        custom = bmad / "custom"
        custom.mkdir()
        (custom / "config.toml").write_text(
            "[core]\noutput_folder = \"{project-root}/custom-out\"\n",
            encoding="utf-8",
        )
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(
            payload["paths"]["output_folder"], str((self.tmp / "custom-out").resolve())
        )
        (custom / "config.user.toml").write_text(
            "[core]\noutput_folder = \"{project-root}/personal-out\"\n",
            encoding="utf-8",
        )
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(
            payload["paths"]["output_folder"],
            str((self.tmp / "personal-out").resolve()),
        )

    def test_workstreams_map_cannot_be_replaced(self) -> None:
        self.init_track("fix", "trivial")
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "workstreams",
            "--replace",
            "--reason",
            "replace everything",
            "--value",
            '{"ws-001": {}}',
        )
        self.assertFalse(refused["ok"])
        self.assertIn("not workstreams", refused["error"])

    def test_bmad_block_requires_replace_and_keeps_the_audit_path(self) -> None:
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--plan",
            str(self.ledger),
            "--memlog",
            str(self.tmp / "audit.md"),
            "--name",
            "Test Product",
            "--track",
            "fix",
            "--size",
            "trivial",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad",
            "--value",
            '{"model": "current"}',
        )
        self.assertFalse(refused["ok"])
        self.assertIn("needs --replace", refused["error"])
        dropped = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad",
            "--replace",
            "--reason",
            "refresh the detected model",
            "--value",
            '{"model": "current"}',
        )
        self.assertFalse(dropped["ok"])
        self.assertIn("must keep the recorded memlog", dropped["error"])
        replaced = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad",
            "--replace",
            "--reason",
            "refresh the detected model",
            "--value",
            '{"model": "current", "memlog": "audit.md"}',
        )
        self.assertTrue(replaced["ok"], replaced)
        self.assertEqual(self.read_ledger()["bmad"]["memlog"], "audit.md")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "phases.plan.note",
            "--value",
            "after replacement",
        )
        trail = self.tmp / "audit.md"
        self.assertIn("phases.plan.note updated", trail.read_text(encoding="utf-8"))

    def test_active_workstream_cannot_reopen_a_done_workstream_without_reason(self) -> None:
        self.close_fix_trivial()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "active_workstream",
            "--value",
            "ws-001",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("reopening a done workstream needs --reason", refused["error"])
        accepted = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "active_workstream",
            "--value",
            "ws-001",
            "--reason",
            "reopen for rework",
        )
        self.assertTrue(accepted["ok"], accepted)
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("reopen for rework", trail)

    def test_done_workstream_cannot_be_paused(self) -> None:
        self.close_fix_trivial()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "status",
            "--value",
            "paused",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("workstream is done", refused["error"])

    def test_phase_reopen_on_a_done_workstream_is_refused(self) -> None:
        self.close_fix_trivial()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.build.status",
            "--value",
            "active",
            "--reason",
            "rework",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("workstream is done", refused["error"])

    def test_set_cannot_change_a_gate_on_a_done_workstream(self) -> None:
        self.close_fix_trivial()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.close.retro.status",
            "--value",
            "passed",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("workstream is done", refused["error"])

    def test_decided_gate_can_move_to_passed_with_a_reason(self) -> None:
        self.init_track("feature", "epic")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "gates.plan.ux.status",
            "--value",
            "overridden",
            "--reason",
            "no user interface",
        )
        moved = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "gates.plan.ux.status",
            "--value",
            "passed",
            "--reason",
            "a UI was added",
        )
        self.assertTrue(moved["ok"], moved)
        gate = self.read_ledger()["workstreams"]["ws-001"]["gates"]["plan"]["ux"]
        self.assertEqual(gate["status"], "passed")
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("a UI was added", trail)

    def test_ticket_gate_reopen_under_a_done_build_phase_is_refused(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        run(
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
            "built",
        )
        refused = run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "done",
            "--status",
            "open",
            "--reason",
            "rework",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("reopen the phase first", refused["error"])

    def test_dotted_ticket_metadata_cannot_be_cleared(self) -> None:
        self.init_track("audit", "one-session")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "1.3",
            "--gate",
            "review",
            "--status",
            "overridden",
            "--reason",
            "accepted risk",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.1.3.gates.review.override_reason",
            "--null",
        )
        self.assertFalse(refused["ok"], refused)
        self.assertIn("cannot clear decided gate metadata", refused["error"])
        # `decided_at` is rejected earlier as derived, which is the stronger
        # rule: it cannot be backdated or cleared at all.
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.1.3.gates.review.decided_at",
            "--null",
        )
        self.assertFalse(refused["ok"], refused)
        self.assertIn("decided_at is derived", refused["error"])

    def test_build_phase_without_a_ticket_is_refused(self) -> None:
        self.init_track("fix", "one-session")
        refused = run(
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
            "built",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("no ticket built", refused["error"])

    def test_whole_ticket_replacement_runs_the_gate_guards(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1.gates.ticket.status",
            "--value",
            "blocked",
            "--reason",
            "evidence lost",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1",
            "--replace",
            "--reason",
            "compact",
            "--value",
            '{"title": "T1", "gates": {"ticket": {"status": "passed"}, '
            '"review": {"status": "open"}, "done": {"status": "open"}}}',
        )
        self.assertFalse(refused["ok"])
        self.assertIn("blocked gate cannot be passed", refused["error"])

    def test_done_rechecks_ticket_order(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"]["T1"]["gates"] = {'
            '"ticket": {"status": "passed"}, '
            '"review": {"status": "skipped", "override_reason": "waived"}, '
            '"done": {"status": "passed"}}'
        )
        refused = run(
            "done",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--accept-missing-evidence",
            "--accept-missing-tickets",
            "--reason",
            "seed",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("review not passed", refused["error"])

    def test_unknown_dotted_ticket_prefix_is_refused(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.1.3",
            "--replace",
            "--reason",
            "probe",
            "--value",
            '{"title": "phantom"}',
        )
        self.assertFalse(refused["ok"])
        self.assertIn("unknown ticket", refused["error"])

    def test_phase_node_cannot_write_a_derived_gate(self) -> None:
        self.init_track("feature", "epic")
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan",
            "--replace",
            "--reason",
            "reshape",
            "--value",
            '{"status": "active", "gate": "optional", "evidence": [], "note": ""}',
        )
        self.assertFalse(refused["ok"])
        self.assertIn("derived", refused["error"])

    def test_delete_refuses_a_done_workstream_and_the_audit_ticket(self) -> None:
        self.close_fix_trivial()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1",
            "--delete",
            "--reason",
            "cleanup",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("workstream is done", refused["error"])
        self.init_track("audit", "one-session")
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-002",
            "--path",
            "tickets.audit",
            "--delete",
            "--reason",
            "cleanup",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("synthetic audit ticket", refused["error"])

    def test_delete_accepts_an_integer_keyed_ticket(self) -> None:
        self.init_track("audit", "one-session")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"] = '
            '{7: {"title": "seven", "gates": {"review": {"status": "open"}}}}'
        )
        deleted = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.7",
            "--delete",
            "--reason",
            "cleanup",
        )
        self.assertTrue(deleted["ok"], deleted)
        self.assertEqual(self.read_ledger()["workstreams"]["ws-001"]["tickets"], {})

    def test_memlog_expands_the_project_root_token(self) -> None:
        self.init_track("fix", "trivial")
        written = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.note",
            "--value",
            "token",
            "--memlog",
            "{project-root}/audit2.md",
            cwd=self.tmp,
        )
        self.assertTrue(written["ok"], written)
        self.assertTrue((self.tmp / "audit2.md").exists())
        self.assertFalse((self.tmp / "{project-root}").exists())

    def test_project_root_token_expands_in_read_commands(self) -> None:
        self.init_track("fix", "trivial")
        detected = run("detect", "--project-root", "{project-root}", cwd=self.tmp)
        self.assertTrue(detected["ok"], detected)
        reconciled = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            "{project-root}",
            cwd=self.tmp,
        )
        self.assertTrue(reconciled["ok"], reconciled)
        verified = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            "{project-root}",
            "--return",
            '{"status": "blocked"}',
            cwd=self.tmp,
        )
        self.assertNotIn("project root not found", verified.get("error", ""))
        bad = run("detect", "--project-root", str(self.tmp / "missing"), cwd=self.tmp)
        self.assertFalse(bad["ok"])
        self.assertIn("project root not found", bad["error"])

    def test_workstream_status_reopen_records_its_reason(self) -> None:
        self.close_fix_trivial()
        accepted = run(
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
            "reopen for rework",
        )
        self.assertTrue(accepted["ok"], accepted)
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("ws-001 status=active (reason: reopen for rework)", trail)

    def test_package_check_reports_no_drift(self) -> None:
        script = REPO_ROOT / "skills" / "bmad-sdlc-module" / "scripts" / "package.sh"
        if not script.is_file():
            self.skipTest("packaging is authoring-repo-only")
        result = subprocess.run(
            ["bash", str(script), "--check"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_packaged_skill_contains_every_runtime_file(self) -> None:
        """Sync is not enough: the packaged tree must carry what SKILL.md names."""
        packaged = (
            REPO_ROOT / "skills" / "bmad-sdlc-module" / "skills" / "bmad-sdlc"
        )
        if not packaged.is_dir():
            self.skipTest("packaging is authoring-repo-only")
        required = [
            "SKILL.md",
            "VERSION",
            "customize.toml",
            "assets/plan-template.yaml",
            "references/role-config.toml",
            "references/phase-map.md",
            "references/gate-matrix.md",
            "references/ledger-schema.md",
            "references/version-adapters.md",
            "references/handoff-protocol.md",
            "references/menu.md",
            "references/headless.md",
        ]
        for role in ("pm", "dev", "qa"):
            required.append(f"references/{role}/phase-map.md")
            required.append(f"references/{role}/gate-matrix.md")
        required.append("references/qa/solution-phase.md")
        for relative in required:
            self.assertTrue(
                (packaged / relative).is_file(), f"missing {relative}"
            )
        self.assertTrue(list((packaged / "scripts").glob("sdlc_plan.py")))
        self.assertTrue(list((packaged / "scripts" / "tests").glob("test_*.py")))
        self.assertFalse((packaged / "evals").exists())


    # --- round-5 regressions -------------------------------------------------

    def test_verify_return_allow_empty_does_not_waive_evidence(self) -> None:
        self.init_track("fix", "trivial")
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[],"evidence":[],"open_questions":[]}',
            "--allow-empty-artifacts",
            "--reason",
            "the brief produces no file",
        )
        self.assertFalse(payload["ok"])
        self.assertIn("no evidence returned", payload["reasons"])

    def test_validate_and_verify_return_exit_nonzero_when_not_ok(self) -> None:
        self.init()
        refused = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "schema",
            "--value",
            "wrong/0",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.edit_ledger('data["schema"] = "wrong/0"')
        validated = run_full("validate", "--plan", str(self.ledger))
        self.assertEqual(validated.returncode, 1)
        self.assertFalse(json.loads(validated.stdout)["ok"])
        rejected = run_full(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"blocked"}',
        )
        self.assertEqual(rejected.returncode, 1)

    def test_memlog_token_expands_against_the_project_root(self) -> None:
        self.init_track("fix", "trivial")
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--memlog",
            "{project-root}/audit/trail.md",
            "--return",
            '{"status":"blocked"}',
            cwd=elsewhere,
        )
        self.assertEqual(
            Path(payload["memlog"]).resolve(),
            (self.tmp / "audit" / "trail.md").resolve(),
        )
        self.assertFalse((elsewhere / "audit").exists())

    def test_init_resolves_a_relative_plan_against_the_project_root(self) -> None:
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        payload = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--plan",
            "_bmad-output/sdlc/plan.yaml",
            "--name",
            "Relative Plan",
            "--track",
            "fix",
            "--size",
            "trivial",
            "--model",
            "v6",
            cwd=elsewhere,
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(Path(payload["ledger"]).resolve(), self.ledger.resolve())
        self.assertTrue(self.ledger.is_file())
        self.assertFalse((elsewhere / "_bmad-output").exists())

    def test_memlog_must_differ_from_the_ledger(self) -> None:
        self.init_track("fix", "trivial")
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.note",
            "--value",
            "x",
            "--memlog",
            str(self.ledger),
        )
        self.assertFalse(refused["ok"])
        self.assertIn("must differ from the ledger", refused["error"])

    def test_active_workstream_cannot_be_cleared_while_one_is_active(self) -> None:
        self.init_track("fix", "trivial")
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "active_workstream",
            "--null",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("pause the active workstream", refused["error"])
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated["errors"])

    def test_phase_replacement_needs_a_complete_node(self) -> None:
        self.init_track("feature", "epic")
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan",
            "--replace",
            "--reason",
            "reshape",
            "--value",
            '{"note": "half"}',
        )
        self.assertFalse(refused["ok"])
        self.assertIn("needs a status", refused["error"])
        accepted = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan",
            "--replace",
            "--reason",
            "reshape",
            "--value",
            '{"status": "active", "evidence": [], "note": ""}',
        )
        self.assertTrue(accepted["ok"], accepted)
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated["errors"])

    def test_phase_evidence_can_be_pruned_with_a_reason(self) -> None:
        self.init_track("feature", "epic")
        refused = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--replace",
            "--value",
            "[]",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn(
            "--replace needs --reason", json.loads(refused.stdout)["error"]
        )
        accepted = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--replace",
            "--reason",
            "drop it",
            "--value",
            "[]",
        )
        self.assertTrue(accepted["ok"], accepted)
        node = self.read_ledger()["workstreams"]["ws-001"]["phases"]["plan"]
        self.assertEqual(node["evidence"], [])

    def test_done_requires_both_ux_artifacts_even_with_phase_evidence(self) -> None:
        self.init_track("feature", "one-session")
        planning = self.tmp / "_bmad-output" / "planning-artifacts"
        planning.mkdir(parents=True, exist_ok=True)
        (planning / "DESIGN.md").write_text("# design\n", encoding="utf-8")
        notes = self.tmp / "notes.md"
        notes.write_text("evidence\n", encoding="utf-8")
        for gate in ("requirements", "stories", "ux"):
            run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"gates.plan.{gate}.status",
                "--value",
                "passed",
            )
        run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--value",
            "notes.md",
        )
        for gate in ("ticket", "tests", "review", "done"):
            run(
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
                "passed",
            )
        run(
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
        run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.verify.evidence",
            "--value",
            "notes.md",
        )
        refused = run(
            "done",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--accept-missing-tickets",
            "--reason",
            "fixture",
        )
        self.assertFalse(refused["ok"])
        self.assertIn(
            "plan.ux (needs DESIGN.md and EXPERIENCE.md)", refused["error"]
        )

    def test_done_names_overridden_gates_in_the_close_note(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review"):
            run(
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
                "passed",
            )
        (self.tmp / "review.md").write_text("review\n", encoding="utf-8")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "done",
            "--status",
            "overridden",
            "--reason",
            "accepted by the user",
            "--evidence",
            "review.md",
        )
        closed = run(
            "done",
            "--plan",
            str(self.ledger),
            "--accept-missing-tickets",
            "--reason",
            "fixture",
        )
        self.assertTrue(closed["ok"], closed)
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("overrides: build.T1.done", trail)

    def test_reconcile_reports_but_done_ignores_an_optional_outside_pointer(self) -> None:
        self.init_track("fix", "trivial")
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        outside = REPO_ROOT / "README.md"
        refused_set = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.spec",
            "--value",
            str(outside),
        )
        self.assertFalse(refused_set["ok"])
        self.assertIn("inside the project root", refused_set["error"])
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["artifacts"]["spec"] = '
            + json.dumps(str(outside))
        )
        accepted = run(
            "done",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--accept-missing-tickets",
            "--reason",
            "fixture",
        )
        # plan.requirements is optional and undecided for a fix/trivial, so the
        # stale pointer is not part of the close contract.
        self.assertTrue(accepted["ok"], accepted)
        reconciled = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        self.assertFalse(reconciled["ok"])
        self.assertEqual(reconciled["missing_count"], 1)
        self.assertEqual(
            reconciled["workstreams"][0]["missing_pointers"][0]["artifact"],
            "spec",
        )

    def test_migrate_writes_a_correction_line(self) -> None:
        self.init_track("fix", "trivial")
        self.edit_ledger('del data["workstreams"]["ws-001"]["tickets"]')
        migrated = run("migrate", "--plan", str(self.ledger))
        self.assertTrue(migrated["ok"], migrated)
        self.assertIn("ws-001.tickets", migrated["changed"])
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("(correction)", trail)
        self.assertIn("migrate applied:", trail)

    def test_resize_refuses_to_drop_a_decided_audit_track(self) -> None:
        self.init_track("audit")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "audit",
            "--gate",
            "review",
            "--status",
            "passed",
        )
        refused = run(
            "resize",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--track",
            "fix",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("audit gates are already decided", refused["error"])

    def test_detect_reads_the_installer_manifest(self) -> None:
        config = self.tmp / "_bmad" / "_config"
        config.mkdir(parents=True)
        (config / "skill-manifest.csv").write_text(
            "skill,name,canonicalId\n"
            "bmad-agent-po,PO,bmad-agent-po\n"
            "bmad-sdlc,Conductor,bmad-sdlc\n",
            encoding="utf-8",
        )
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(payload["model"], "current")
        self.assertIn("bmad-agent-po", payload["skills"])
        self.assertNotIn("bmad-sdlc", payload["skills"])

    def test_detect_finds_skills_in_a_claude_install(self) -> None:
        for name in ("bmad-agent-po", "bmad-build"):
            directory = self.tmp / ".claude" / "skills" / name
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(payload["model"], "current")
        self.assertEqual(payload["skills_dir"], ".claude/skills")

    def test_detect_reports_test_style_and_hub(self) -> None:
        for name in ("bmad", "bmad-tea"):
            directory = self.tmp / ".agents" / "skills" / name
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(payload["hub"], "bmad")
        self.assertEqual(payload["test_style"], "bmad-tea")
        fabricated = self.tmp / ".agents" / "skills" / "bmad-tea-trace"
        fabricated.mkdir()
        (fabricated / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        (self.tmp / ".agents" / "skills" / "bmad-tea" / "SKILL.md").unlink()
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(payload["test_style"], "unknown")

    def test_summary_reports_optional_open_and_workstream_briefs(self) -> None:
        self.init_track("feature", "epic")
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIn("optional_open", summary)
        self.assertEqual(
            {
                "id",
                "name",
                "track",
                "size",
                "status",
                "current_phase",
                "role",
                "role_source",
                "role_override",
                "next_action",
            },
            set(summary["workstreams_detail"][0]),
        )

    def test_init_uses_the_configured_default_track(self) -> None:
        payload = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Default Track",
            "--default-track",
            "fix",
        )
        self.assertTrue(payload["ok"], payload)
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["workstream"]["track"], "fix")

    def test_failed_memlog_append_rolls_back_the_ledger(self) -> None:
        self.init_track("fix", "trivial")
        before = self.ledger.read_text(encoding="utf-8")
        memlog = self.ledger.parent / ".memlog.md"
        memlog.unlink()
        memlog.mkdir()
        failed = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.note",
            "--value",
            "x",
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), before)

    def test_ledger_touched_ignores_lock_files(self) -> None:
        self.init_track("fix", "trivial")
        for lock in (
            self.ledger.with_name(self.ledger.name + ".lock"),
            self.ledger.parent / ".memlog.md.lock",
        ):
            lock.unlink(missing_ok=True)
        out = self.tmp / "out.md"
        out.write_text("artifact\n", encoding="utf-8")
        for command in (
            ["git", "init", "-q", str(self.tmp)],
            ["git", "-C", str(self.tmp), "config", "user.email", "t@example.com"],
            ["git", "-C", str(self.tmp), "config", "user.name", "T"],
            ["git", "-C", str(self.tmp), "add", "-A"],
            [
                "git",
                "-C",
                str(self.tmp),
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "init",
            ],
        ):
            subprocess.run(command, capture_output=True, check=False)
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.note",
            "--value",
            "after the commit",
        )
        subprocess.run(
            ["git", "-C", str(self.tmp), "add", "-u"],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.tmp),
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "ledger write",
            ],
            capture_output=True,
            check=False,
        )
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":["out.md"],"evidence":["out.md"]}',
        )
        self.assertFalse(payload["ledger_touched"], payload)


    # -- round-6 regressions ----------------------------------------------

    def test_memlog_equal_to_the_ledger_is_refused(self) -> None:
        self.init()
        payload = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad",
            "--replace",
            "--reason",
            "test",
            "--value",
            json.dumps({"model": "v6", "memlog": str(self.ledger)}),
        )
        self.assertFalse(payload["ok"])
        self.assertIn("must differ", payload["error"])

    def test_paused_workstream_refuses_writes_until_resumed(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "status",
            "--value",
            "paused",
            "--reason",
            "pause",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "overridden",
            "--reason",
            "covered",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("paused", refused["error"])
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
            "resume",
        )
        allowed = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "overridden",
            "--reason",
            "covered",
        )
        self.assertTrue(allowed["ok"], allowed)

    def test_model_downgrade_needs_a_reason(self) -> None:
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Test Product",
            "--track",
            "feature",
            "--size",
            "epic",
            "--model",
            "v6",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad.model",
            "--value",
            "unknown",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("downgrade", refused["error"])
        allowed = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad.model",
            "--value",
            "unknown",
            "--reason",
            "installer was removed",
        )
        self.assertTrue(allowed["ok"], allowed)

    def test_model_change_that_reopens_a_phase_needs_a_reason(self) -> None:
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Test Product",
            "--track",
            "feature",
            "--size",
            "epic",
            "--model",
            "current",
        )
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["phases"]["plan"]["status"] = "done"'
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad.model",
            "--value",
            "v6",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("reopens", refused["error"])
        allowed = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "bmad.model",
            "--value",
            "v6",
            "--reason",
            "upgraded BMAD",
        )
        self.assertTrue(allowed["ok"], allowed)
        workstream = self.read_ledger()["workstreams"]["ws-001"]
        self.assertEqual(workstream["phases"]["plan"]["status"], "pending")

    def test_done_rejects_a_directory_as_artifact_evidence(self) -> None:
        self.init_track("fix", "trivial")
        (self.tmp / "artifact-dir").mkdir()
        for gate in ("ticket", "review", "done"):
            run(
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
                "passed",
            )
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"]["T1"]["gates"]["ticket"]'
            '["evidence"] = "artifact-dir"'
        )
        payload = run(
            "done",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--accept-missing-tickets",
            "--reason",
            "fixture",
        )
        self.assertFalse(payload["ok"])
        self.assertIn("build.T1.ticket=artifact-dir", payload["error"])

    def test_phase_evidence_does_not_replace_a_gate_artifact(self) -> None:
        self.init_track("feature", "epic")
        artifact = self.tmp / "artifact.md"
        artifact.write_text("# evidence\n", encoding="utf-8")
        run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--value",
            "artifact.md",
        )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "passed",
        )
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        self.assertIn(
            "plan.requirements", payload["workstreams"][0]["gates_to_block"]
        )

    def test_ux_pair_resolves_from_the_recorded_pointer(self) -> None:
        self.init_track("feature", "epic")
        ux = self.tmp / "ux-docs"
        ux.mkdir()
        (ux / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
        (ux / "EXPERIENCE.md").write_text("# Experience\n", encoding="utf-8")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.ux",
            "--value",
            "ux-docs/DESIGN.md",
        )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.ux.status",
            "--value",
            "passed",
        )
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        self.assertNotIn(
            "plan.ux", payload["workstreams"][0]["gates_to_block"]
        )

    def test_reconcile_write_blocks_an_open_gate(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.spec",
            "--value",
            "missing/SPEC.md",
        )
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--write",
        )
        self.assertIn(
            "ws-001.gates.plan.requirements=blocked", payload["applied"]
        )
        workstream = self.read_ledger()["workstreams"]["ws-001"]
        self.assertEqual(
            workstream["gates"]["plan"]["requirements"]["status"], "blocked"
        )

    def test_reconcile_reports_a_decided_gate_instead_of_reopening_it(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.spec",
            "--value",
            "missing/SPEC.md",
        )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "passed",
        )
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--write",
        )
        self.assertIn(
            "gates.plan.requirements",
            payload["workstreams"][0]["requires_reason"],
        )
        workstream = self.read_ledger()["workstreams"]["ws-001"]
        self.assertEqual(
            workstream["gates"]["plan"]["requirements"]["status"], "passed"
        )

    def test_gate_node_replacement_keeps_derived_level_and_reason(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements.status",
            "--value",
            "overridden",
            "--reason",
            "accepted risk",
        )
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.requirements",
            "--replace",
            "--reason",
            "replace the node",
            "--value",
            '{"status":"overridden"}',
        )
        gate = self.read_ledger()["workstreams"]["ws-001"]["gates"]["plan"][
            "requirements"
        ]
        self.assertEqual(gate["level"], "required")
        self.assertEqual(gate["override_reason"], "accepted risk")

    def test_set_cannot_create_a_ticket(self) -> None:
        self.init_track("fix", "trivial")
        payload = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1",
            "--replace",
            "--reason",
            "create",
            "--value",
            '{"title":"T1","gates":{"ticket":{"status":"passed"}}}',
        )
        self.assertFalse(payload["ok"])
        self.assertIn("ticket command", payload["error"])

    def test_ticket_argument_errors_are_json(self) -> None:
        self.init()
        result = run(
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
        self.assertFalse(result["ok"])
        self.assertIn("unknown ticket gate", result["error"])

    def test_append_refuses_artifact_pointers_and_closed_workstreams(self) -> None:
        self.close_fix_trivial()
        closed = run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--value",
            "artifact.md",
        )
        self.assertFalse(closed["ok"])
        self.assertIn("done", closed["error"])
        self.ledger.unlink()
        self.init()
        refused = run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.spec",
            "--value",
            "SPEC.md",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("take set", refused["error"])

    def test_project_size_routes_plan_requirements_to_the_prd(self) -> None:
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Test Product",
            "--track",
            "greenfield",
            "--size",
            "project",
            "--model",
            "v6",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_action"]["action"], "plan.prd")
        self.assertEqual(summary["next_action"]["skill"], "bmad-prd")

    def test_sprint_status_supplies_the_ticket_overlay(self) -> None:
        run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Test Product",
            "--track",
            "feature",
            "--size",
            "epic",
            "--model",
            "v6",
        )
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "1-1-story",
            "--gate",
            "ticket",
            "--status",
            "open",
        )
        implementation = (
            self.tmp / "_bmad-output" / "implementation-artifacts"
        )
        implementation.mkdir(parents=True)
        (implementation / "sprint-status.yaml").write_text(
            "development_status:\n"
            "  epic-1: in-progress\n"
            "  1-1-story: done\n",
            encoding="utf-8",
        )
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        workstream = payload["workstreams"][0]
        self.assertEqual(workstream["tickets_missing_in_artifacts"], [])
        self.assertEqual(workstream["tickets_missing_in_ledger"], [])

    def test_migrate_reopens_a_done_phase_it_invalidates(self) -> None:
        self.init()
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["gates"]["plan"].pop("requirements")'
        )
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["phases"]["plan"]["status"] = "done"'
        )
        migrated = run(
            "migrate", "--plan", str(self.ledger), "--reason", "rebuild levels"
        )
        self.assertTrue(migrated["ok"], migrated)
        workstream = self.read_ledger()["workstreams"]["ws-001"]
        self.assertEqual(workstream["phases"]["plan"]["status"], "pending")
        self.assertIn("requirements", workstream["gates"]["plan"])

    def test_resize_to_audit_adds_the_synthetic_ticket(self) -> None:
        self.init_track("feature", "one-session")
        payload = run(
            "resize",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--track",
            "audit",
        )
        self.assertTrue(payload["ok"], payload)
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIn("audit", summary["tickets"]["items"])
        self.assertTrue(
            run("validate", "--plan", str(self.ledger))["ok"]
        )

    def test_detect_reports_the_testarch_family(self) -> None:
        skill = self.tmp / ".agents" / "skills" / "bmad-testarch-trace"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# trace\n", encoding="utf-8")
        payload = run("detect", "--project-root", str(self.tmp))
        self.assertEqual(payload["test_style"], "bmad-testarch")

    def test_reconcile_discovers_a_framework_scaffold(self) -> None:
        self.init()
        (self.tmp / "playwright.config.ts").write_text(
            "export default {}\n", encoding="utf-8"
        )
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        orphans = payload["workstreams"][0]["orphan_pointers"]
        self.assertIn("test_framework", [item["artifact"] for item in orphans])

    def test_summary_reports_whether_the_next_skill_is_installed(self) -> None:
        self.init()
        before = run(
            "summary",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        self.assertFalse(before["next_action"]["skill_installed"])
        skill = self.tmp / ".agents" / "skills" / "bmad-spec"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# spec\n", encoding="utf-8")
        after = run(
            "summary",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        self.assertTrue(after["next_action"]["skill_installed"])

    def test_malformed_config_is_reported_and_blocks_init(self) -> None:
        bmad = self.tmp / "_bmad"
        bmad.mkdir()
        (bmad / "config.toml").write_text("this is not toml\n", encoding="utf-8")
        detected = run("detect", "--project-root", str(self.tmp))
        self.assertTrue(detected["config_errors"])
        refused = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Test Product",
            "--track",
            "feature",
            "--size",
            "epic",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("malformed BMAD config", refused["error"])

    def test_read_only_reconcile_does_not_create_a_lock(self) -> None:
        self.init()
        lock = self.ledger.with_name(self.ledger.name + ".lock")
        if lock.exists():
            lock.unlink()
        payload = run(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
        )
        self.assertTrue(payload["ok"], payload)
        self.assertFalse(lock.exists())

    def test_verify_return_rejects_missing_and_outside_evidence(self) -> None:
        self.init()
        artifact = self.tmp / "artifact.md"
        artifact.write_text("# artifact\n", encoding="utf-8")
        missing = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":["artifact.md"],'
            '"evidence":["missing.log"]}',
        )
        self.assertFalse(missing["ok"])
        self.assertIn("missing.log", missing["missing_evidence"])
        outside = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            json.dumps(
                {
                    "status": "done",
                    "artifacts": ["artifact.md"],
                    "evidence": [str(REPO_ROOT / "README.md")],
                }
            ),
        )
        self.assertFalse(outside["ok"])
        self.assertTrue(outside["outside_evidence"])

    def test_done_reports_a_decided_gate_with_no_artifact(self) -> None:
        self.init_track("fix", "one-session")
        for gate in ("ticket", "tests", "review", "done"):
            run(
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
                "passed",
            )
        run(
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
        payload = run(
            "done",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--accept-missing-tickets",
            "--reason",
            "fixture",
        )
        self.assertFalse(payload["ok"])
        self.assertIn("verify.trace (no artifact)", payload["error"])

    def test_skipping_a_phase_without_a_reason_is_refused(self) -> None:
        self.init_track("fix", "trivial")
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.close.status",
            "--value",
            "skipped",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("skipping phase close needs --reason", refused["error"])

    def test_whole_ticket_replacement_cannot_drop_a_decided_gate(self) -> None:
        self.init_track("fix", "trivial")
        run(
            "ticket",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--id",
            "T1",
            "--gate",
            "ticket",
            "--status",
            "passed",
        )
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets.T1",
            "--replace",
            "--reason",
            "rewrite",
            "--value",
            '{"title":"T1","gates":{"review":{"status":"open"}}}',
        )
        self.assertFalse(refused["ok"])
        self.assertIn("cannot drop decided gate", refused["error"])

    def test_first_init_removes_the_ledger_when_the_audit_append_fails(self) -> None:
        logdir = self.tmp / "logdir"
        logdir.mkdir()
        payload = run_full(
            "init",
            "--project-root",
            str(self.tmp),
            "--memlog",
            str(logdir),
            "--name",
            "Test Product",
            "--track",
            "feature",
            "--size",
            "epic",
        )
        self.assertNotEqual(payload.returncode, 0)
        self.assertFalse(self.ledger.exists())

    def test_reconcile_write_exits_nonzero_on_drift(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.spec",
            "--value",
            "missing/SPEC.md",
        )
        result = run_full(
            "reconcile",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--write",
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()


class RegressionTests(unittest.TestCase):
    """Regressions for the review findings: each test names the contract."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="bmad-sdlc-regress-"))
        self.ledger = self.tmp / "_bmad-output" / "sdlc" / "plan.yaml"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def init(self, **kwargs) -> dict:
        args = {
            "cwd": None,
            "root": str(self.tmp),
            "name": "Test Product",
            "track": "feature",
            "size": "epic",
            "model": "v6",
            "plan": None,
        }
        args.update(kwargs)
        command = [
            "init",
            "--project-root", args["root"],
            "--name", args["name"],
            "--track", args["track"],
            "--size", args["size"],
            "--model", args["model"],
        ]
        if args["plan"]:
            command += ["--plan", args["plan"]]
        return run(*command, cwd=args["cwd"])

    def ticket_all(self, ticket_id: str = "1") -> None:
        for gate in ("ticket", "review", "done"):
            run(
                "ticket", "--plan", str(self.ledger),
                "--id", ticket_id, "--gate", gate, "--status", "passed",
            )

    def edit_ledger(self, mutation: str) -> None:
        code = (
            "import sys\n"
            "from ruamel.yaml import YAML\n"
            "yaml = YAML()\n"
            "data = yaml.load(open(sys.argv[1], encoding='utf-8'))\n"
            f"{mutation}\n"
            "with open(sys.argv[1], 'w', encoding='utf-8') as handle:\n"
            "    yaml.dump(data, handle)\n"
        )
        result = subprocess.run(
            [
                "uv", "run", "--no-cache", "--with", "ruamel.yaml",
                "python", "-c", code, str(self.ledger),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)

    def read_ledger(self) -> dict:
        code = (
            "import json, sys\n"
            "from ruamel.yaml import YAML\n"
            "yaml = YAML()\n"
            "data = yaml.load(open(sys.argv[1], encoding='utf-8'))\n"
            "print(json.dumps(data, default=str))\n"
        )
        result = subprocess.run(
            [
                "uv", "run", "--no-cache", "--with", "ruamel.yaml",
                "python", "-c", code, str(self.ledger),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)

    def test_resize_refuses_a_paused_workstream(self) -> None:
        self.init()
        run("set", "--plan", str(self.ledger), "--path", "status", "--value", "paused")
        result = run_full(
            "resize", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--size", "one-session",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("paused", json.loads(result.stdout)["error"])

    def test_done_refuses_a_second_close(self) -> None:
        self.init(track="fix", size="trivial")
        self.ticket_all()
        run(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "no tracker",
        )
        result = run_full(
            "done", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "again",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already done", json.loads(result.stdout)["error"])

    def test_done_requires_a_project_root_for_a_custom_ledger(self) -> None:
        self.init(track="audit", size="one-session", plan="docs/sdlc/plan.yaml")
        custom = self.tmp / "docs" / "sdlc" / "plan.yaml"
        run(
            "ticket", "--plan", str(custom), "--id", "audit",
            "--gate", "review", "--status", "passed",
        )
        for gate in ("trace", "nfr", "test_review"):
            run(
                "set", "--plan", str(custom), "--path", f"gates.verify.{gate}.status",
                "--value", "overridden", "--reason", "accepted",
            )
        result = run_full("done", "--plan", str(custom))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--project-root", json.loads(result.stdout)["error"])

    def test_done_requires_evidence_for_a_gate_with_no_artifact_key(self) -> None:
        self.init(track="audit", size="one-session")
        (self.tmp / "trace.md").write_text("trace\n", encoding="utf-8")
        run(
            "ticket", "--plan", str(self.ledger), "--id", "audit",
            "--gate", "review", "--status", "passed",
        )
        run("set", "--plan", str(self.ledger), "--path", "artifacts.trace",
            "--value", "trace.md")
        for gate in ("trace", "nfr", "test_review"):
            run("set", "--plan", str(self.ledger), "--path",
                f"gates.verify.{gate}.status", "--value", "passed")
        result = run_full(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no artifact key and no phase evidence",
                      json.loads(result.stdout)["error"])

    def test_ticket_done_requires_a_passed_review(self) -> None:
        self.init(track="fix", size="trivial")
        run("ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed")
        run("ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "review", "--status", "overridden", "--reason", "risk")
        result = run_full(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "done", "--status", "passed",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("passed build.review", json.loads(result.stdout)["error"])

    def test_overridden_ticket_gate_needs_evidence_at_close(self) -> None:
        self.init(track="fix", size="trivial")
        run("ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed")
        run("ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "review", "--status", "passed")
        run("ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "done", "--status", "overridden", "--reason", "accepted")
        result = run_full(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "no tracker",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overridden without evidence",
                      json.loads(result.stdout)["error"])
        (self.tmp / "review.md").write_text("review\n", encoding="utf-8")
        run("ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "done", "--status", "overridden", "--reason", "accepted",
            "--evidence", "review.md")
        accepted = run(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "no tracker",
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_set_rejects_an_invalid_schema(self) -> None:
        self.init()
        before = self.ledger.read_text(encoding="utf-8")
        result = run_full(
            "set", "--plan", str(self.ledger), "--path", "schema",
            "--value", "not-a-schema",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, self.ledger.read_text(encoding="utf-8"))

    def test_migrate_requires_a_reason_when_it_reopens_a_phase(self) -> None:
        self.init()
        self.edit_ledger(
            "ws = data['workstreams']['ws-001']\n"
            "ws['phases']['plan']['status'] = 'done'\n"
            "del ws['gates']['plan']['stories']"
        )
        result = run_full("migrate", "--plan", str(self.ledger))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--reason", json.loads(result.stdout)["error"])
        accepted = run(
            "migrate", "--plan", str(self.ledger), "--reason", "rebuild levels",
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_phase_replace_cannot_drop_evidence(self) -> None:
        self.init()
        (self.tmp / "a.md").write_text("a\n", encoding="utf-8")
        (self.tmp / "b.md").write_text("b\n", encoding="utf-8")
        for name in ("a.md", "b.md"):
            run("append", "--plan", str(self.ledger), "--path",
                "phases.plan.evidence", "--value", name)
        result = run_full(
            "set", "--plan", str(self.ledger), "--path", "phases.plan",
            "--value", '{"status":"active","evidence":["a.md"],"note":""}',
            "--replace", "--reason", "trim",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("append-only", json.loads(result.stdout)["error"])

    def test_resize_to_audit_refuses_existing_tickets(self) -> None:
        self.init()
        run("ticket", "--plan", str(self.ledger), "--id", "2-1",
            "--gate", "ticket", "--status", "passed")
        result = run_full(
            "resize", "--plan", str(self.ledger), "--track", "audit",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tickets exist", json.loads(result.stdout)["error"])

    def test_init_refuses_paths_outside_the_project_root(self) -> None:
        outside = self.tmp.parent / f"{self.tmp.name}-outside-plan.yaml"
        result = run_full(
            "init", "--project-root", str(self.tmp), "--plan", str(outside),
            "--name", "T", "--track", "fix", "--size", "trivial",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the project root", json.loads(result.stdout)["error"])
        self.assertFalse(outside.exists())

    def test_init_records_a_relative_memlog_for_a_custom_ledger(self) -> None:
        self.init(plan="docs/sdlc/plan.yaml")
        text = (self.tmp / "docs" / "sdlc" / "plan.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("memlog: docs/sdlc/.memlog.md", text)
        self.assertNotIn(str(self.tmp), text)

    def test_summary_reports_an_installed_alternative_skill(self) -> None:
        skill = self.tmp / ".agents" / "skills" / "bmad-agent-pm"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# pm\n", encoding="utf-8")
        self.init(track="greenfield", size="project")
        summary = run(
            "summary", "--plan", str(self.ledger), "--project-root", str(self.tmp),
        )
        self.assertEqual(summary["next_action"]["action"], "plan.prd")
        self.assertEqual(summary["next_action"]["skill"], "bmad-agent-pm")
        self.assertTrue(summary["next_action"]["skill_installed"])

    def test_build_review_accepts_bmad_build(self) -> None:
        skill = self.tmp / ".agents" / "skills" / "bmad-build"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# build\n", encoding="utf-8")
        self.init(track="fix", size="trivial")
        run("ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed")
        summary = run(
            "summary", "--plan", str(self.ledger), "--project-root", str(self.tmp),
        )
        self.assertEqual(summary["next_action"]["action"], "build.review")
        self.assertEqual(summary["next_action"]["skill"], "bmad-build")
        self.assertTrue(summary["next_action"]["skill_installed"])

    def test_next_action_stale_detects_a_gate_change(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            "ws = data['workstreams']['ws-001']\n"
            "ws['next'] = {'phase': 'build', 'gate': 'build.1.done', "
            "'action': 'build.ticket', 'skill': 'bmad-build'}"
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertTrue(summary["next_action_stale"], summary["next_action"])

    def test_manifest_only_skill_is_reported(self) -> None:
        config = self.tmp / "_bmad" / "_config"
        config.mkdir(parents=True)
        (config / "skill-manifest.csv").write_text(
            "skill,name\nbmad-build,bmad-build\n", encoding="utf-8"
        )
        detect = run("detect", "--project-root", str(self.tmp))
        self.assertIn("bmad-build", detect["skills"])
        self.assertIn("bmad-build", detect["manifest_only"])
        self.assertNotIn("bmad-build", detect["missing_core"])

    def test_relative_plan_resolves_against_the_project_root(self) -> None:
        self.init()
        sub = self.tmp / "sub"
        sub.mkdir()
        payload = run(
            "set", "--project-root", str(self.tmp),
            "--plan", "_bmad-output/sdlc/plan.yaml",
            "--path", "phases.build.note", "--value", "from-sub",
            cwd=sub,
        )
        self.assertTrue(payload["ok"], payload)

    def test_detect_scans_every_skill_dir(self) -> None:
        for rel in (
            ".agents", ".claude", ".cline", ".bob", ".agent", ".adal",
        ):
            name = "bmad-probe-" + rel.strip(".").replace(".", "-")
            skill = self.tmp / rel / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# probe\n", encoding="utf-8")
        detect = run("detect", "--project-root", str(self.tmp))
        for rel in (
            ".agents", ".claude", ".cline", ".bob", ".agent", ".adal",
        ):
            name = "bmad-probe-" + rel.strip(".").replace(".", "-")
            self.assertIn(name, detect["skills"])

    def test_package_check_detects_drift(self) -> None:
        repo = self.tmp / "repo"
        source = repo / ".agents" / "skills" / "bmad-sdlc"
        package_script = repo / "skills" / "bmad-sdlc-module" / "scripts" / "package.sh"
        packaged = repo / "skills" / "bmad-sdlc-module" / "skills" / "bmad-sdlc"
        shutil.copytree(
            REPO_ROOT / ".agents" / "skills" / "bmad-sdlc",
            source,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "evals"),
        )
        package_script.parent.mkdir(parents=True)
        shutil.copy2(
            REPO_ROOT / "skills" / "bmad-sdlc-module" / "scripts" / "package.sh",
            package_script,
        )
        shutil.copytree(source, packaged)
        clean = subprocess.run(
            ["bash", str(package_script), "--check"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(clean.returncode, 0, clean.stderr)
        with (packaged / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("\ndrift\n")
        drifted = subprocess.run(
            ["bash", str(package_script), "--check"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(drifted.returncode, 1)
        self.assertIn("drifted", drifted.stderr)

    def test_concurrent_appends_preserve_every_write(self) -> None:
        self.init()
        processes = [
            subprocess.Popen(
                [
                    "uv", "run", "--no-cache", str(SCRIPT),
                    "append", "--plan", str(self.ledger),
                    "--path", "decisions",
                    "--value", json.dumps({"decision": f"d{index}", "reason": "r"}),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for index in range(6)
        ]
        for process in processes:
            _stdout, stderr = process.communicate(timeout=120)
            self.assertEqual(process.returncode, 0, stderr)
        text = self.ledger.read_text(encoding="utf-8")
        for index in range(6):
            self.assertIn(f"d{index}", text)

    def test_recorded_memlog_resolves_against_the_project_root(self) -> None:
        self.init(plan="docs/sdlc/plan.yaml")
        custom = self.tmp / "docs" / "sdlc" / "plan.yaml"
        payload = run(
            "log", "--project-root", str(self.tmp), "--plan", str(custom),
            "--text", "custom trail",
        )
        self.assertTrue(payload["ok"], payload)
        memlog = custom.parent / ".memlog.md"
        self.assertTrue(memlog.is_file())
        self.assertIn("custom trail", memlog.read_text())
        self.assertFalse((custom.parent / "docs").exists())

    def test_recorded_memlog_outside_the_root_is_refused(self) -> None:
        self.init()
        self.edit_ledger('data["bmad"]["memlog"] = "../outside.md"')
        result = run_full(
            "log", "--project-root", str(self.tmp), "--plan", str(self.ledger),
            "--text", "escape",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the project root", json.loads(result.stdout)["error"])

    def test_append_cannot_seed_gate_metadata(self) -> None:
        self.init()
        for field in ("override_reason", "decided_at"):
            result = run_full(
                "append", "--plan", str(self.ledger),
                "--path", f"gates.plan.requirements.{field}",
                "--value", "planted",
            )
            self.assertNotEqual(result.returncode, 0)
            message = json.loads(result.stdout)["error"]
            if field == "decided_at":
                self.assertIn("decided_at is derived", message)
            else:
                self.assertIn("gate metadata", message)

    def test_ticket_evidence_must_stay_inside_the_project_root(self) -> None:
        self.init(track="fix", size="trivial")
        result = run_full(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed",
            "--evidence", "/etc/hosts",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the project root", json.loads(result.stdout)["error"])

    def test_done_rejects_missing_ticket_evidence(self) -> None:
        self.init(track="fix", size="trivial")
        # The write path refuses a missing pointer; plant one by hand to prove
        # `done` still rejects an older ledger that carries it.
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"] = {"1": {"gates": {'
            '"ticket": {"status": "passed", "decided_at": "2026-01-01T00:00:00Z", '
            '"evidence": "missing-ticket.md"}, '
            '"review": {"status": "passed", "decided_at": "2026-01-01T00:00:00Z"}, '
            '"done": {"status": "passed", "decided_at": "2026-01-01T00:00:00Z"}}}}'
        )
        (self.tmp / "trace.md").write_text("trace\n", encoding="utf-8")
        run(
            "set", "--plan", str(self.ledger), "--path",
            "gates.verify.trace.status", "--value", "passed",
        )
        run(
            "append", "--plan", str(self.ledger), "--path",
            "phases.verify.evidence", "--value", "trace.md",
        )
        result = run_full(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "build.1.ticket=missing-ticket.md",
            json.loads(result.stdout)["error"],
        )

    def test_set_ticket_done_requires_a_passed_review(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed",
        )
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "review", "--status", "overridden", "--reason", "risk",
        )
        leaf = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "tickets.1.gates.done.status", "--value", "passed",
        )
        self.assertNotEqual(leaf.returncode, 0)
        self.assertIn("passed build.review", json.loads(leaf.stdout)["error"])
        replacement = {
            "title": "",
            "gates": {
                "ticket": {"status": "passed"},
                "review": {"status": "overridden", "override_reason": "risk"},
                "done": {"status": "passed"},
            },
        }
        node = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "tickets.1", "--replace",
            "--value", json.dumps(replacement), "--reason", "replace",
            "--as", "qa",
        )
        self.assertNotEqual(node.returncode, 0)
        self.assertIn("passed build.review", json.loads(node.stdout)["error"])

    def test_gate_node_replacement_cannot_forge_decided_at(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed",
        )
        before = self.read_ledger()["workstreams"]["ws-001"]["tickets"]["1"][
            "gates"
        ]["ticket"]["decided_at"]
        payload = json.dumps(
            {"status": "passed", "decided_at": "2000-01-01T00:00:00Z"}
        )
        result = run(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "tickets.1.gates.ticket", "--replace",
            "--value", payload, "--reason", "reapply",
        )
        self.assertTrue(result["ok"], result)
        after = self.read_ledger()["workstreams"]["ws-001"]["tickets"]["1"][
            "gates"
        ]["ticket"]["decided_at"]
        self.assertEqual(after, before)

    def test_set_reopen_clears_ticket_evidence(self) -> None:
        self.init(track="fix", size="trivial")
        (self.tmp / "ticket.md").write_text("ticket\n", encoding="utf-8")
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed",
            "--evidence", "ticket.md",
        )
        run(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "tickets.1.gates.ticket.status", "--value", "open",
            "--reason", "rework",
        )
        gate = self.read_ledger()["workstreams"]["ws-001"]["tickets"]["1"][
            "gates"
        ]["ticket"]
        self.assertNotIn("evidence", gate)

    def test_set_root_fields_are_type_checked(self) -> None:
        self.init()
        result = run_full(
            "set", "--plan", str(self.ledger), "--root",
            "--path", "project", "--value", "42",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "project must be a non-empty string",
            json.loads(result.stdout)["error"],
        )

    def test_gate_node_evidence_type_is_checked(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed",
        )
        payload = json.dumps({"status": "passed", "evidence": 123})
        result = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "tickets.1.gates.ticket", "--replace",
            "--value", payload, "--reason", "replace",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "non-empty path string", json.loads(result.stdout)["error"]
        )

    def test_migrate_repairs_a_done_workstream(self) -> None:
        self.init(track="fix", size="trivial")
        self.ticket_all()
        run(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "no tracker",
        )
        result = run("migrate", "--plan", str(self.ledger),
                     "--project-root", str(self.tmp))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["skipped_workstreams"], [])
        self.assertEqual(result["changed"], [])
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])

    def test_reconcile_write_skips_a_paused_workstream(self) -> None:
        self.init(track="fix", size="trivial")
        run("set", "--plan", str(self.ledger), "--path", "status",
            "--value", "paused")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["phases"]["verify"]["evidence"]'
            ' = ["missing.md"]'
        )
        result = run(
            "reconcile", "--plan", str(self.ledger),
            "--project-root", str(self.tmp), "--write",
        )
        self.assertIn("ws-001", result["skipped_workstreams"])
        ledger = self.read_ledger()
        self.assertNotEqual(
            ledger["workstreams"]["ws-001"]["phases"]["verify"]["status"],
            "blocked",
        )

    def test_done_marks_phases_terminal(self) -> None:
        self.init(track="fix", size="trivial")
        self.ticket_all()
        run(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "no tracker",
        )
        phases = self.read_ledger()["workstreams"]["ws-001"]["phases"]
        for phase in ("plan", "solution", "build", "verify", "close"):
            self.assertNotIn(phases[phase]["status"], ("active", "pending"))

    def test_verify_return_hash_flags_reject_a_changed_ledger(self) -> None:
        self.init(track="fix", size="trivial")
        (self.tmp / "artifact.md").write_text("x\n", encoding="utf-8")
        memlog = self.ledger.parent / ".memlog.md"
        ledger_sha = hashlib.sha256(self.ledger.read_bytes()).hexdigest()
        memlog_sha = hashlib.sha256(memlog.read_bytes()).hexdigest()
        self.edit_ledger('data["updated"] = "2099-01-01T00:00:00Z"')
        returned = json.dumps(
            {
                "status": "done",
                "role": "dev",
                "action": "build.ticket",
                "artifacts": [{"path": "artifact.md"}],
                "evidence": [{"path": "artifact.md"}],
            }
        )
        stale = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp), "--return", returned,
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertFalse(stale["ok"])
        self.assertTrue(
            any("ledger changed during the handoff" in item
                for item in stale["reasons"])
        )
        current = hashlib.sha256(self.ledger.read_bytes()).hexdigest()
        fresh = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp), "--return", returned,
            "--expect-ledger-sha", current,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertTrue(fresh["ok"], fresh)

    def test_verify_return_reports_post_write_digests(self) -> None:
        self.init(track="fix", size="trivial")
        (self.tmp / "artifact.md").write_text("x\n", encoding="utf-8")
        returned = json.dumps(
            {
                "status": "done",
                "role": "dev",
                "action": "build.ticket",
                "artifacts": [{"path": "artifact.md"}],
                "evidence": [{"path": "artifact.md"}],
                "open_questions": ["q"],
            }
        )
        payload = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp), "--return", returned,
            "--accept-questions",
            "--expect-ledger-sha", hashlib.sha256(self.ledger.read_bytes()).hexdigest(),
            "--expect-memlog-sha", hashlib.sha256(
                (self.ledger.parent / ".memlog.md").read_bytes()
            ).hexdigest(),
        )
        self.assertTrue(payload["ok"], payload)
        memlog = self.ledger.parent / ".memlog.md"
        self.assertEqual(
            payload["memlog_sha256"],
            hashlib.sha256(memlog.read_bytes()).hexdigest(),
        )

    def test_summary_prefers_the_latest_updated_workstream(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "init", "--project-root", str(self.tmp), "--name", "Second",
            "--track", "feature", "--size", "epic",
        )
        run("set", "--plan", str(self.ledger), "--path",
            "active_workstream", "--value", "ws-001")
        self.ticket_all()
        run(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "no tracker",
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["track"], "fix")
        self.assertEqual(summary["size"], "trivial")
        self.assertEqual(summary["phase"], "close")

    def test_plan_stories_resolves_to_the_stories_skill(self) -> None:
        self.init(model="current", track="feature", size="epic")
        for name in ("bmad-spec", "bmad-create-epics-and-stories"):
            skill = self.tmp / ".agents" / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
        run(
            "set", "--plan", str(self.ledger), "--path",
            "gates.plan.requirements.status", "--value", "passed",
        )
        summary = run(
            "summary", "--plan", str(self.ledger),
            "--project-root", str(self.tmp),
        )
        action = summary["next_action"]
        self.assertEqual(action["gate"], "plan.stories")
        self.assertEqual(action["skill"], "bmad-create-epics-and-stories")
        self.assertTrue(action["skill_installed"])

    def test_verify_trace_resolves_to_the_installed_testarch_skill(self) -> None:
        self.init(model="current", track="fix", size="one-session")
        skill = self.tmp / ".agents" / "skills" / "bmad-testarch-trace"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# trace\n", encoding="utf-8")
        self.ticket_all()
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "tests", "--status", "passed",
        )
        summary = run(
            "summary", "--plan", str(self.ledger),
            "--project-root", str(self.tmp),
        )
        action = summary["next_action"]
        self.assertEqual(action["gate"], "verify.trace")
        self.assertEqual(action["skill"], "bmad-testarch-trace")
        self.assertTrue(action["skill_installed"])

    def test_bmad_model_change_refuses_a_done_workstream(self) -> None:
        self.init(track="fix", size="trivial")
        self.ticket_all()
        run(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "no tracker",
        )
        result = run_full(
            "set", "--plan", str(self.ledger), "--path", "bmad.model",
            "--value", "current", "--reason", "upgrade",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reopen", json.loads(result.stdout)["error"])

    def test_set_project_root_checks_artifact_pointers(self) -> None:
        self.init(plan="docs/sdlc/plan.yaml", track="fix", size="trivial")
        custom = self.tmp / "docs" / "sdlc" / "plan.yaml"
        result = run_full(
            "set", "--project-root", str(self.tmp), "--plan", str(custom),
            "--path", "artifacts.spec", "--value", "/etc/hosts",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the project root", json.loads(result.stdout)["error"])

    def test_set_ticket_evidence_needs_an_existing_decided_gate(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "open",
        )
        missing = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "tickets.1.gates.review.evidence",
            "--value", "review.md",
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn(
            "create the gate with the ticket command first",
            json.loads(missing.stdout)["error"],
        )
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "review", "--status", "open",
        )
        open_gate = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "tickets.1.gates.review.evidence",
            "--value", "review.md",
        )
        self.assertNotEqual(open_gate.returncode, 0)
        self.assertIn(
            "decided gate", json.loads(open_gate.stdout)["error"]
        )

    def test_validate_rejects_ticket_evidence_type(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed",
        )
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"]["1"]["gates"]'
            '["ticket"]["evidence"] = 7'
        )
        validated = run("validate", "--plan", str(self.ledger))
        self.assertFalse(validated["ok"])
        self.assertTrue(any("evidence" in error for error in validated["errors"]))

    # -- round 10 regressions ------------------------------------------------

    def test_init_resolves_the_default_template_from_the_skill_root(self) -> None:
        result = run_full(
            "init", "--project-root", str(self.tmp), "--name", "T",
            "--track", "fix", "--size", "trivial",
            "--template", "assets/plan-template.yaml",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.tmp / "assets").exists())

    def test_default_size_applies_to_a_feature(self) -> None:
        result = run(
            "init", "--project-root", str(self.tmp), "--name", "T",
            "--track", "feature", "--model", "v6", "--default-size", "epic",
        )
        self.assertTrue(result["ok"], result)
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["workstream"]["size"], "epic")

    def test_set_rejects_derived_and_unknown_paths(self) -> None:
        self.init(track="fix", size="trivial")
        for path, value in (
            ("current_phase", "close"),
            ("gats.plan.requirements.status", "passed"),
            ("gates.build.ticket.decided_at", "12345"),
        ):
            result = run_full(
                "set", "--plan", str(self.ledger), "--path", path,
                "--value", value,
            )
            self.assertNotEqual(result.returncode, 0, (path, result.stdout))
            self.assertTrue(result.stdout.strip().startswith("{"), result.stdout)

    def test_failed_write_leaves_no_lock_or_directory(self) -> None:
        target = self.tmp / "missing" / "plan.yaml"
        result = run_full(
            "set", "--plan", str(target), "--path", "phases.plan.note",
            "--value", "x",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.parent.exists())

    def test_memlog_must_stay_inside_the_project_root(self) -> None:
        ledger = self.tmp / "plan" / "plan.yaml"
        run(
            "init", "--project-root", str(self.tmp), "--plan", str(ledger),
            "--memlog", str(self.tmp / "plan" / "audit.md"),
            "--name", "T", "--track", "fix", "--size", "trivial",
        )
        result = run_full(
            "set", "--plan", str(ledger), "--memlog", "/etc/hosts",
            "--path", "phases.build.note", "--value", "x",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the project root", json.loads(result.stdout)["error"])

    def test_optional_blocked_gate_blocks_its_phase(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "set", "--plan", str(self.ledger), "--path",
            "gates.close.retro.status", "--value", "blocked", "--reason", "x",
        )
        summary = run("summary", "--plan", str(self.ledger))
        close = [p for p in summary["phases"] if p["phase"] == "close"][0]
        self.assertIn("close.retro", close["blocking"])

    def test_skipped_build_without_a_ticket_does_not_recommend_close(self) -> None:
        self.init(track="fix", size="trivial")
        for phase in ("build", "verify", "close"):
            run(
                "set", "--plan", str(self.ledger), "--path",
                f"phases.{phase}.status", "--value", "skipped",
                "--reason", "nothing to do",
            )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(summary["next_action"]["action"], "build.ticket")
        result = run_full("done", "--plan", str(self.ledger))
        self.assertNotEqual(result.returncode, 0)

    def test_blocking_a_decided_gate_on_a_done_phase_is_refused(self) -> None:
        self.init(track="feature", size="one-session")
        for path, value in (
            ("gates.plan.requirements.status", "passed"),
            ("gates.plan.stories.status", "overridden"),
            ("gates.plan.ux.status", "overridden"),
        ):
            command = [
                "set", "--plan", str(self.ledger), "--path", path,
                "--value", value,
            ]
            if value != "passed":
                command += ["--reason", "for the test"]
            run(*command)
        run(
            "set", "--plan", str(self.ledger), "--path",
            "phases.plan.status", "--value", "done", "--reason", "done",
        )
        result = run_full(
            "set", "--plan", str(self.ledger), "--path",
            "gates.plan.requirements.status", "--value", "blocked",
            "--reason", "late",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reopen the phase first", json.loads(result.stdout)["error"])

    def test_validate_rejects_an_overridden_review_for_a_done_ticket(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"] = {"1": {"gates": {'
            '"ticket": {"status": "passed", "decided_at": "2026-01-01T00:00:00Z"},'
            '"review": {"status": "overridden", "decided_at": "2026-01-01T00:00:00Z", "override_reason": "r"},'
            '"done": {"status": "overridden", "decided_at": "2026-01-01T00:00:00Z", "override_reason": "r"}'
            '}}}'
        )
        validated = run("validate", "--plan", str(self.ledger))
        self.assertFalse(validated["ok"])
        self.assertTrue(any("review" in error for error in validated["errors"]))
        result = run_full("done", "--plan", str(self.ledger), "--project-root", str(self.tmp))
        self.assertNotEqual(result.returncode, 0)

    def test_verify_return_requires_handoff_digests(self) -> None:
        self.init()
        (self.tmp / "artifact.md").write_text("x\n", encoding="utf-8")
        payload = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket","artifacts":[{"path":"artifact.md"}],"evidence":["artifact.md"]}',
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["digest_check"], "not_run")
        self.assertTrue(any("digests not supplied" in reason for reason in payload["reasons"]))

    def test_bad_track_and_model_emit_json(self) -> None:
        self.init(track="fix", size="trivial")
        resized = run_full(
            "resize", "--plan", str(self.ledger), "--track", "bogus",
        )
        self.assertNotEqual(resized.returncode, 0)
        self.assertTrue(resized.stdout.strip().startswith("{"), resized.stdout)
        self.assertIn("unknown track", json.loads(resized.stdout)["error"])
        initial = run_full(
            "init", "--project-root", str(self.tmp), "--name", "T",
            "--track", "fix", "--size", "trivial", "--model", "nope",
        )
        self.assertNotEqual(initial.returncode, 0)
        self.assertTrue(initial.stdout.strip().startswith("{"), initial.stdout)
        self.assertIn("unknown model", json.loads(initial.stdout)["error"])

    def test_init_force_keeps_the_recorded_audit_path(self) -> None:
        memlog = self.tmp / "custom" / "audit.md"
        run(
            "init", "--project-root", str(self.tmp), "--name", "T",
            "--track", "fix", "--size", "trivial", "--memlog", str(memlog),
        )
        run(
            "init", "--project-root", str(self.tmp), "--name", "T",
            "--track", "fix", "--size", "trivial", "--force",
            "--reason", "reset for the test",
        )
        recorded = self.read_ledger()["bmad"]["memlog"]
        self.assertEqual(recorded, "custom/audit.md")
        self.assertIn("ledger reset", memlog.read_text(encoding="utf-8"))

    def test_reconcile_reports_ticket_evidence_outside_the_root(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"] = {"1": {"gates": {'
            '"ticket": {"status": "passed", "decided_at": "2026-01-01T00:00:00Z", "evidence": "/etc/hosts"}'
            '}}}'
        )
        payload = run("reconcile", "--plan", str(self.ledger), "--project-root", str(self.tmp))
        self.assertFalse(payload["ok"])
        evidence = payload["workstreams"][0]["missing_evidence"]
        self.assertTrue(any(item.get("ticket") == "1" for item in evidence), evidence)

    def test_reconcile_applies_a_phase_block(self) -> None:
        self.init(track="fix", size="trivial")
        missing = self.tmp / "verify-notes.md"
        missing.write_text("# notes\n", encoding="utf-8")
        run(
            "append", "--plan", str(self.ledger), "--path",
            "phases.verify.evidence", "--value", "verify-notes.md",
        )
        # The pointer is valid when written; deleting the file is what a later
        # session sees when the artifact was never produced.
        missing.unlink()
        payload = run(
            "reconcile", "--plan", str(self.ledger), "--project-root",
            str(self.tmp), "--write",
        )
        self.assertIn(
            "ws-001.phases.verify.status=blocked",
            payload["workstreams"][0]["applied"],
        )
        self.assertEqual(
            self.read_ledger()["workstreams"]["ws-001"]["phases"]["verify"]["status"],
            "blocked",
        )

    def test_reconcile_blocks_a_gate_with_no_artifact_key_and_no_evidence(self) -> None:
        self.init()
        run(
            "set", "--plan", str(self.ledger), "--path",
            "gates.verify.nfr.status", "--value", "passed",
        )
        payload = run("reconcile", "--plan", str(self.ledger), "--project-root", str(self.tmp))
        self.assertIn("verify.nfr", payload["workstreams"][0]["gates_to_block"])

    def test_gate_replacement_cannot_drop_evidence(self) -> None:
        self.init(track="fix", size="trivial")
        (self.tmp / "review.md").write_text("review\n", encoding="utf-8")
        run(
            "ticket", "--plan", str(self.ledger), "--id", "1",
            "--gate", "ticket", "--status", "passed", "--evidence", "review.md",
        )
        result = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "tickets.1.gates.ticket", "--replace",
            "--value", '{"status":"passed"}', "--reason", "replace",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence", json.loads(result.stdout)["error"])

    def test_init_force_recovers_an_unparseable_ledger(self) -> None:
        self.ledger.parent.mkdir(parents=True)
        self.ledger.write_text("schema: bmad-sdlc/1\ngates: [oops\n", encoding="utf-8")
        payload = run(
            "init", "--project-root", str(self.tmp), "--name", "T",
            "--track", "fix", "--size", "trivial", "--model", "unknown",
            "--force", "--reason", "recover a corrupt ledger",
        )
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])
        self.assertTrue(self.ledger.with_name("plan.yaml.bak").is_file())

    def test_build_cannot_be_skipped_with_no_ticket(self) -> None:
        self.init(track="fix", size="trivial")
        result = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "phases.build.status", "--value", "skipped",
            "--reason", "not needed",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no ticket built", json.loads(result.stdout)["error"])

    def test_reopening_a_done_phase_to_blocked_needs_a_reason(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["phases"]["plan"]["status"] = "done"'
        )
        result = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "phases.plan.status", "--value", "blocked",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needs --reason", json.loads(result.stdout)["error"])

    def test_verify_return_digest_check_fails_on_a_stale_memlog(self) -> None:
        self.init(track="fix", size="trivial")
        (self.tmp / "artifact.md").write_text("x\n", encoding="utf-8")
        memlog = self.ledger.parent / ".memlog.md"
        ledger_sha = hashlib.sha256(self.ledger.read_bytes()).hexdigest()
        stale_memlog_sha = hashlib.sha256(memlog.read_bytes()).hexdigest()
        with memlog.open("a", encoding="utf-8") as handle:
            handle.write("hand edit\n")
        returned = json.dumps(
            {
                "status": "done",
                "role": "dev",
                "action": "build.ticket",
                "artifacts": [{"path": "artifact.md"}],
                "evidence": [{"path": "artifact.md"}],
            }
        )
        payload = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp), "--return", returned,
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", stale_memlog_sha,
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["digest_check"], "failed")
        self.assertTrue(
            any("audit trail changed during the handoff" in item
                for item in payload["reasons"])
        )

    def test_reconcile_rejects_phase_evidence_outside_the_root(self) -> None:
        self.init(track="fix", size="trivial")
        # The write path refuses an outside pointer; plant one by hand to
        # prove reconcile still catches an older ledger that carries it.
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["phases"]["verify"]["evidence"] = '
            '["/etc/hosts"]'
        )
        payload = run(
            "reconcile", "--plan", str(self.ledger), "--project-root",
            str(self.tmp),
        )
        missing = payload["workstreams"][0]["missing_evidence"]
        self.assertTrue(any(item.get("phase") == "verify" for item in missing), missing)

    def test_summary_reports_a_manifest_only_skill(self) -> None:
        self.init(track="fix", size="trivial")
        config = self.tmp / "_bmad" / "_config"
        config.mkdir(parents=True)
        (config / "skill-manifest.csv").write_text(
            "skill,name\nbmad-build,bmad-build\n", encoding="utf-8"
        )
        summary = run(
            "summary", "--plan", str(self.ledger), "--project-root", str(self.tmp)
        )
        self.assertTrue(summary["next_action"]["skill_installed"])
        self.assertTrue(summary["next_action"]["skill_manifest_only"])

    def test_project_root_token_is_stored_project_relative(self) -> None:
        self.init()
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "prd.md").write_text("# PRD\n", encoding="utf-8")
        payload = run(
            "set", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--path", "artifacts.prd", "--value", "{project-root}/docs/prd.md",
        )
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(
            self.read_ledger()["workstreams"]["ws-001"]["artifacts"]["prd"],
            "docs/prd.md",
        )

    def test_ux_pointer_may_name_the_folder_that_holds_the_pair(self) -> None:
        self.init()
        ux = self.tmp / "_bmad-output" / "planning-artifacts" / "ux"
        ux.mkdir(parents=True)
        (ux / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
        (ux / "EXPERIENCE.md").write_text("# Experience\n", encoding="utf-8")
        run(
            "set", "--plan", str(self.ledger), "--path", "artifacts.ux",
            "--value", "_bmad-output/planning-artifacts/ux",
        )
        payload = run(
            "reconcile", "--plan", str(self.ledger), "--project-root",
            str(self.tmp),
        )
        missing = payload["workstreams"][0]["missing_pointers"]
        self.assertFalse(any(item.get("artifact") == "ux" for item in missing), missing)

    def test_append_refuses_phase_evidence_outside_the_root(self) -> None:
        self.init(track="fix", size="trivial")
        result = run_full(
            "append", "--plan", str(self.ledger), "--path",
            "phases.verify.evidence", "--value", "/etc/hosts",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the project root", json.loads(result.stdout)["error"])

    def test_init_refuses_a_missing_project_root(self) -> None:
        missing = self.tmp / "ghost"
        result = run_full(
            "init", "--project-root", str(missing), "--name", "T",
            "--track", "fix", "--size", "trivial",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project root not found", json.loads(result.stdout)["error"])
        self.assertFalse(missing.exists())

    def test_validate_rejects_an_unknown_workstream_field(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["gats"] = {"plan": {}}'
        )
        payload = run("validate", "--plan", str(self.ledger))
        self.assertFalse(payload["ok"])
        self.assertTrue(
            any("unknown fields" in error for error in payload["errors"]),
            payload["errors"],
        )

    def test_done_rejects_a_ticket_closed_on_an_overridden_review(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["tickets"] = {"1": {"gates": {'
            '"ticket": {"status": "passed", "decided_at": "2026-01-01T00:00:00Z"}, '
            '"review": {"status": "overridden", "decided_at": "2026-01-01T00:00:00Z", '
            '"override_reason": "accepted risk"}, '
            '"done": {"status": "passed", "decided_at": "2026-01-01T00:00:00Z"}}}}'
        )
        result = run_full(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "build.1.done (review not passed)",
            json.loads(result.stdout)["error"],
        )

    def test_reconcile_reports_a_decided_phase_instead_of_blocking_it(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            'node = data["workstreams"]["ws-001"]["phases"]["verify"]\n'
            'node["status"] = "done"\n'
            'node["evidence"] = ["missing.md"]'
        )
        payload = run(
            "reconcile", "--plan", str(self.ledger), "--project-root",
            str(self.tmp), "--write",
        )
        self.assertIn("phases.verify", payload["workstreams"][0]["requires_reason"])
        self.assertEqual(
            self.read_ledger()["workstreams"]["ws-001"]["phases"]["verify"]["status"],
            "done",
        )

    # -- round-13 regressions ----------------------------------------------

    def test_done_accept_missing_tickets_leaves_a_valid_ledger(self) -> None:
        self.init(track="fix", size="trivial")
        closed = run(
            "done",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--accept-missing-tickets",
            "--reason",
            "ledger-only fixture",
        )
        self.assertTrue(closed["ok"], closed)
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("accepted build with no ticket", trail)
        self.assertIn("auto-advanced phases:", trail)
        build = self.read_ledger()["workstreams"]["ws-001"]["phases"]["build"]
        self.assertNotEqual(build["status"], "done")

    def test_verify_return_one_digest_is_not_an_acceptance(self) -> None:
        self.init(track="fix", size="trivial")
        artifact = self.tmp / "change.md"
        artifact.write_text("# change\n", encoding="utf-8")
        ledger_sha, _ = digests(self.ledger)
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket",'
            '"artifacts":["change.md"],"evidence":["change.md"]}',
            "--expect-ledger-sha",
            ledger_sha,
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["digest_check"], "not_run")
        self.assertTrue(
            any("digests not supplied" in reason for reason in payload["reasons"]),
            payload["reasons"],
        )

    def test_allow_empty_artifacts_logs_its_decision(self) -> None:
        self.init(track="fix", size="trivial")
        artifact = self.tmp / "change.md"
        artifact.write_text("# change\n", encoding="utf-8")
        ledger_sha, memlog_sha = digests(self.ledger)
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket",'
            '"artifacts":[],"evidence":["change.md"]}',
            "--expect-ledger-sha",
            ledger_sha,
            "--expect-memlog-sha",
            memlog_sha,
            "--allow-empty-artifacts",
            "--reason",
            "brief produces no file",
        )
        self.assertTrue(payload["ok"], payload)
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn(
            "accepted an empty artifact list (reason: brief produces no file)",
            trail,
        )

    def test_manual_phase_skip_writes_its_reason_to_the_note(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.verify.status",
            "--value",
            "skipped",
            "--reason",
            "no verification needed for this fixture",
        )
        node = self.read_ledger()["workstreams"]["ws-001"]["phases"]["verify"]
        self.assertEqual(node["status"], "skipped")
        self.assertEqual(node["note"], "no verification needed for this fixture")

    def test_pausing_stamps_the_workstream_not_a_sibling(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["updated"] = "2000-01-01T00:00:00+00:00"'
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
            "paused",
            "--reason",
            "pause",
        )
        node = self.read_ledger()["workstreams"]["ws-001"]
        self.assertEqual(node["status"], "paused")
        self.assertNotEqual(node["updated"], "2000-01-01T00:00:00+00:00")
        payload = run("summary", "--plan", str(self.ledger))
        self.assertIsNone(payload["active_workstream"])
        self.assertEqual(payload["workstream"], None)
        self.assertEqual(payload["track"], "fix")

    def test_init_appends_after_a_paused_sibling(self) -> None:
        self.init(track="fix", size="trivial")
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
            "pause before the next workstream",
        )
        appended = run(
            "init",
            "--project-root",
            str(self.tmp),
            "--name",
            "Second",
            "--track",
            "feature",
            "--size",
            "one-session",
        )
        self.assertTrue(appended["ok"], appended)
        self.assertEqual(appended["workstream"], "ws-002")
        self.assertEqual(appended["model"], "v6")
        self.assertEqual(appended["paused"], [])

    def test_migrate_drops_an_unknown_gate(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["gates"]["verify"]["bogus"] = '
            '{"status": "open", "level": "required", "decided_at": None, '
            '"override_reason": None}'
        )
        summary = run("summary", "--plan", str(self.ledger))
        self.assertIn("verify.bogus", summary["open_gates"])
        refused = run_full(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.verify.bogus.status",
            "--value",
            "passed",
        )
        self.assertNotEqual(refused.returncode, 0)
        migrated = run("migrate", "--plan", str(self.ledger))
        self.assertTrue(migrated["ok"], migrated)
        self.assertTrue(
            any("verify.bogus removed" in entry for entry in migrated["changed"]),
            migrated["changed"],
        )
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])

    def test_migrate_repairs_a_closed_workstream(self) -> None:
        self.init(track="fix", size="trivial")
        self.edit_ledger(
            'data["workstreams"]["ws-001"]["status"] = "done"\n'
            'data["active_workstream"] = None\n'
            'del data["workstreams"]["ws-001"]["gates"]["verify"]["trace"]'
        )
        migrated = run("migrate", "--plan", str(self.ledger))
        self.assertTrue(migrated["ok"], migrated)
        self.assertEqual(migrated["skipped_workstreams"], [])
        self.assertTrue(
            any("gates.verify.trace" in entry for entry in migrated["changed"]),
            migrated["changed"],
        )
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])

    def test_reconcile_returns_a_gate_to_open_once_the_artifact_resolves(self) -> None:
        self.init(track="feature", size="one-session")
        trace = self.tmp / "trace.md"
        trace.write_text("# trace\n", encoding="utf-8")
        run(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "artifacts.trace", "--value", "trace.md",
        )
        trace.unlink()
        blocked = run(
            "reconcile", "--plan", str(self.ledger), "--project-root",
            str(self.tmp), "--write",
        )
        self.assertIn("verify.trace", blocked["workstreams"][0]["gates_to_block"])
        trace.write_text("# trace\n", encoding="utf-8")
        recovered = run(
            "reconcile", "--plan", str(self.ledger), "--project-root",
            str(self.tmp), "--write",
        )
        self.assertTrue(
            any("verify.trace=open" in entry for entry in recovered["applied"]),
            recovered["applied"],
        )
        summary = run("summary", "--plan", str(self.ledger))
        trace_gate = next(
            gate for gate in summary["phases"][3]["gates"] if gate["id"] == "verify.trace"
        )
        self.assertEqual(trace_gate["status"], "open")

    def test_init_force_rotates_its_backup(self) -> None:
        self.init(track="fix", size="trivial")
        first = run(
            "init", "--project-root", str(self.tmp), "--name", "Reset",
            "--track", "fix", "--size", "trivial",
            "--force", "--reason", "first reset",
        )
        self.assertTrue(first["ok"], first)
        backups = sorted((self.ledger.parent).glob("plan.yaml*.bak"))
        self.assertEqual(len(backups), 1)
        base_backup = self.ledger.with_name("plan.yaml.bak")
        first_bytes = base_backup.read_bytes()
        second = run(
            "init", "--project-root", str(self.tmp), "--name", "Reset Again",
            "--track", "fix", "--size", "trivial",
            "--force", "--reason", "second reset",
        )
        self.assertTrue(second["ok"], second)
        self.assertEqual(base_backup.read_bytes(), first_bytes)
        self.assertGreater(
            len(list(self.ledger.parent.glob("plan.yaml*.bak"))), 1
        )

    def test_init_force_needs_a_reason_even_without_a_ledger(self) -> None:
        result = run_full(
            "init", "--project-root", str(self.tmp), "--name", "Fresh",
            "--track", "fix", "--size", "trivial", "--force",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--force requires --reason", json.loads(result.stdout)["error"])
        self.assertFalse(self.ledger.exists())

    def test_resize_needs_a_flag(self) -> None:
        self.init(track="fix", size="trivial")
        result = run_full(
            "resize", "--plan", str(self.ledger), "--workstream", "ws-001",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--track or --size", json.loads(result.stdout)["error"])

    def test_resize_noop_keeps_the_role_override(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "role", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--role", "qa", "--reason", "take over",
        )
        run(
            "resize", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--size", "trivial",
        )
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn("role_override: qa", text)

    def test_done_and_reconcile_refuse_a_malformed_config(self) -> None:
        self.init(track="fix", size="trivial")
        config = self.tmp / "_bmad" / "config.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text("not = [valid", encoding="utf-8")
        done = run_full(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "no tracker",
        )
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("malformed BMAD config", json.loads(done.stdout)["error"])
        reconcile = run_full(
            "reconcile", "--plan", str(self.ledger), "--project-root", str(self.tmp),
        )
        self.assertNotEqual(reconcile.returncode, 0)
        self.assertIn("malformed BMAD config", json.loads(reconcile.stdout)["error"])

    def test_verify_return_rejects_scratch_files(self) -> None:
        self.init(track="fix", size="trivial")
        scratch = self.ledger.parent / ".tmp" / "scratch.md"
        scratch.parent.mkdir(parents=True, exist_ok=True)
        scratch.write_text("# scratch\n", encoding="utf-8")
        ledger_sha, memlog_sha = digests(self.ledger)
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","role":"dev","action":"build.ticket",'
            '"artifacts":["_bmad-output/sdlc/.tmp/scratch.md"],'
            '"evidence":["_bmad-output/sdlc/.tmp/scratch.md"]}',
            "--expect-ledger-sha",
            ledger_sha,
            "--expect-memlog-sha",
            memlog_sha,
        )
        self.assertFalse(payload["ok"])
        self.assertTrue(
            any("scratch file used as an artifact" in reason for reason in payload["reasons"]),
            payload["reasons"],
        )
        self.assertTrue(
            any("scratch file used as evidence" in reason for reason in payload["reasons"]),
            payload["reasons"],
        )

    def test_verify_return_takes_a_workstream(self) -> None:
        self.init(track="fix", size="trivial")
        artifact = self.tmp / "change.md"
        artifact.write_text("# change\n", encoding="utf-8")
        ledger_sha, memlog_sha = digests(self.ledger)
        unknown = run_full(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp), "--workstream", "ws-999",
            "--return", '{"status":"done","role":"dev","action":"build.ticket",'
            '"artifacts":["change.md"],"evidence":["change.md"]}',
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertNotEqual(unknown.returncode, 0)
        self.assertIn("workstream not found", json.loads(unknown.stdout)["error"])
        accepted = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp), "--workstream", "ws-001",
            "--return", '{"status":"done","role":"dev","action":"build.ticket",'
            '"artifacts":["change.md"],"evidence":["change.md"]}',
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_verify_return_requires_a_changed_artifact(self) -> None:
        self.init(track="fix", size="trivial")
        artifact = self.tmp / "change.md"
        artifact.write_text("# change\n", encoding="utf-8")
        for command in (
            ["git", "init", "-q"],
            ["git", "config", "user.email", "test@example.com"],
            ["git", "config", "user.name", "Test"],
            ["git", "config", "commit.gpgsign", "false"],
            ["git", "add", "change.md"],
            ["git", "commit", "-qm", "seed"],
        ):
            result = subprocess.run(
                command, cwd=self.tmp, capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        ledger_sha, memlog_sha = digests(self.ledger)
        unchanged = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp),
            "--return", '{"status":"done","role":"dev","action":"build.ticket",'
            '"artifacts":["change.md"],"evidence":["change.md"]}',
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertFalse(unchanged["ok"])
        self.assertTrue(
            any("appears in git status" in reason for reason in unchanged["reasons"]),
            unchanged["reasons"],
        )
        allowed = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp),
            "--return", '{"status":"done","role":"dev","action":"build.ticket",'
            '"artifacts":["change.md"],"evidence":["change.md"]}',
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
            "--allow-unchanged-artifact", "--reason", "artifact is already committed",
        )
        self.assertTrue(allowed["ok"], allowed)

    def test_verify_return_rejects_an_unattributed_done(self) -> None:
        self.init(track="fix", size="trivial")
        artifact = self.tmp / "change.md"
        artifact.write_text("# change\n", encoding="utf-8")
        ledger_sha, memlog_sha = digests(self.ledger)
        payload = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp),
            "--return", '{"status":"done","artifacts":["change.md"],'
            '"evidence":["change.md"]}',
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertFalse(payload["ok"])
        self.assertTrue(
            any("must name its role and action" in reason for reason in payload["reasons"]),
            payload["reasons"],
        )
        allowed = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp),
            "--return", '{"status":"done","artifacts":["change.md"],'
            '"evidence":["change.md"]}',
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
            "--allow-unattributed", "--reason", "legacy return",
        )
        self.assertTrue(allowed["ok"], allowed)
        trail = (self.ledger.parent / ".memlog.md").read_text(encoding="utf-8")
        self.assertIn("accepted an unattributed return", trail)

    def test_append_rejects_a_numeric_evidence_entry(self) -> None:
        self.init(track="fix", size="trivial")
        result = run_full(
            "append", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "phases.verify.evidence", "--value", "7",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "non-empty path strings", json.loads(result.stdout)["error"]
        )

    def test_phase_evidence_can_be_pruned_with_a_reason(self) -> None:
        self.init(track="fix", size="trivial")
        kept = self.tmp / "kept.md"
        dropped = self.tmp / "dropped.md"
        kept.write_text("kept\n", encoding="utf-8")
        dropped.write_text("dropped\n", encoding="utf-8")
        for path in ("kept.md", "dropped.md"):
            run(
                "append", "--plan", str(self.ledger), "--workstream", "ws-001",
                "--path", "phases.verify.evidence", "--value", path,
            )
        dropped.unlink()
        refused = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "phases.verify.evidence", "--value", '["kept.md"]',
            "--replace",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("--replace needs --reason", json.loads(refused.stdout)["error"])
        pruned = run(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "phases.verify.evidence", "--value", '["kept.md"]',
            "--replace", "--reason", "removed a deleted file",
        )
        self.assertTrue(pruned["ok"], pruned)
        node = self.read_ledger()["workstreams"]["ws-001"]["phases"]["verify"]
        self.assertEqual([entry for entry in node["evidence"]], ["kept.md"])

    def test_phase_replacement_rejects_missing_evidence(self) -> None:
        self.init(track="fix", size="trivial")
        result = run_full(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "phases.verify", "--replace",
            "--value", '{"status": "pending", "evidence": ["missing.md"], "note": ""}',
            "--reason", "replace the phase",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "existing non-empty file", json.loads(result.stdout)["error"]
        )

    def test_stale_optional_pointer_does_not_block_close(self) -> None:
        self.init(track="fix", size="trivial")
        self.ticket_all()
        run(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "artifacts.trace", "--value", "missing-trace.md",
        )
        closed = run(
            "done", "--plan", str(self.ledger), "--project-root", str(self.tmp),
            "--accept-missing-tickets", "--reason", "no tracker",
        )
        self.assertTrue(closed["ok"], closed)

    def test_ticket_add_refused_while_a_later_phase_is_done(self) -> None:
        self.init(track="fix", size="trivial")
        for phase in ("verify", "close"):
            run(
                "set", "--plan", str(self.ledger), "--workstream", "ws-001",
                "--path", f"phases.{phase}.status", "--value", "done",
                "--reason", "done out of order",
            )
        refused = run_raw(
            "ticket", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--id", "T1", "--gate", "ticket", "--status", "open",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn(
            "cannot add a ticket while a later phase is done",
            json.loads(refused.stdout)["error"],
        )

    def test_verify_return_rejects_its_own_return_file(self) -> None:
        self.init(track="fix", size="trivial")
        return_file = self.tmp / "return.json"
        return_file.write_text(
            json.dumps(
                {
                    "status": "done",
                    "role": "dev",
                    "action": "build.ticket",
                    "artifacts": [{"path": "return.json"}],
                    "evidence": ["return.json"],
                }
            ),
            encoding="utf-8",
        )
        ledger_sha, memlog_sha = digests(self.ledger)
        payload = run(
            "verify-return", "--plan", str(self.ledger),
            "--project-root", str(self.tmp), "--return-file", str(return_file),
            "--expect-ledger-sha", ledger_sha,
            "--expect-memlog-sha", memlog_sha,
        )
        self.assertFalse(payload["ok"])
        self.assertTrue(
            any("return file used as artifact" in reason for reason in payload["reasons"]),
            payload["reasons"],
        )

    def test_phase_evidence_can_be_cleared_after_a_deleted_file(self) -> None:
        self.init(track="fix", size="trivial")
        gone = self.tmp / "gone.md"
        gone.write_text("gone\n", encoding="utf-8")
        run(
            "append", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "phases.verify.evidence", "--value", "gone.md",
        )
        gone.unlink()
        cleared = run(
            "set", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--path", "phases.verify.evidence", "--value", "[]",
            "--replace", "--reason", "the evidence file was removed",
        )
        self.assertTrue(cleared["ok"], cleared)
        node = self.read_ledger()["workstreams"]["ws-001"]["phases"]["verify"]
        self.assertEqual(node["evidence"], [])

    def test_as_switch_needs_a_reason(self) -> None:
        self.init(track="fix", size="trivial")
        run(
            "ticket", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--id", "T1", "--gate", "ticket", "--status", "passed",
        )
        refused = run_raw(
            "ticket", "--plan", str(self.ledger), "--workstream", "ws-001",
            "--id", "T1", "--gate", "review", "--status", "passed",
            "--as", "qa",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn(
            "--as qa needs --reason", json.loads(refused.stdout)["error"]
        )
