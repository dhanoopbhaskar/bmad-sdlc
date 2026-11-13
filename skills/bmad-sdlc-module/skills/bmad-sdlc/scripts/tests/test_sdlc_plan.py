#!/usr/bin/env python3
"""End-to-end tests for the bmad-sdlc ledger helper.

Run:
  uv run --no-cache python -m unittest discover \
    -s .agents/skills/bmad-sdlc/scripts/tests -p 'test_*.py'
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "sdlc_plan.py"
REPO_ROOT = Path(__file__).resolve().parents[5]


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
                "skipped",
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
        run(
            "append",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "phases.plan.evidence",
            "--value",
            "/tmp/spec.md",
        )
        run("log", "--plan", str(self.ledger), "--text", "plan.requirements passed")
        summary = run("summary", "--plan", str(self.ledger))
        self.assertEqual(
            summary["phases"][0]["evidence"], ["/tmp/spec.md"]
        )
        memlog = (self.ledger.parent / ".memlog.md").read_text()
        self.assertIn("plan.requirements passed", memlog)
        self.assertIn("updated:", memlog.split("---")[1])

    def test_validate_rejects_bad_schema(self) -> None:
        self.init()
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "schema",
            "--value",
            "wrong/0",
        )
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
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets",
            "--null",
            "--replace",
            "--reason",
            "simulate an older ledger",
        )
        migrated = run("migrate", "--plan", str(self.ledger))
        self.assertTrue(migrated["ok"])
        validated = run("validate", "--plan", str(self.ledger))
        self.assertTrue(validated["ok"], validated)
        self.assertEqual(validated["warnings"], [])

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
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "next",
            "--value",
            '{"phase":"plan","action":"plan.stories"}',
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
        good = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","artifacts":[{"path":"artifact.md"}]}',
        )
        self.assertTrue(good["ok"], good)
        missing = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","artifacts":[{"path":"missing.md"}]}',
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
                "skipped",
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
                "skipped" if gate != "trace" else "passed",
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

    def test_override_requires_reason(self) -> None:
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
            "overridden",
        )
        self.assertFalse(refused["ok"])
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
        no_reason = run(
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
        self.assertFalse(no_reason["ok"])
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

    def test_validate_rejects_two_active_workstreams(self) -> None:
        self.init()
        self.init_track("fix", name="Second")
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
        validated = run("validate", "--plan", str(self.ledger))
        self.assertFalse(validated["ok"])
        self.assertTrue(any("only one workstream" in error for error in validated["errors"]))

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
            f'{{"status":"done","artifacts":[{{"path":"{outside}"}}]}}',
        )
        self.assertFalse(payload["ok"])
        self.assertIn(str(outside), payload["outside_artifacts"])

    def test_required_skip_requires_reason(self) -> None:
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
            "skipped",
        )
        self.assertFalse(refused["ok"])
        allowed = run(
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
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "tickets",
            "--null",
            "--replace",
            "--reason",
            "simulate a lost audit ticket",
        )
        for gate, status in (
            ("trace", "passed"),
            ("nfr", "skipped"),
            ("test_review", "skipped"),
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
            '{"status":"done","artifacts":[]}',
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
            '{"status":"done","artifacts":[{"path":"_bmad-output/sdlc/plan.yaml"}]}',
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
            '{"status":"done","artifacts":[{"path":"artifact.md"}],"open_questions":["q"]}',
        )
        self.assertFalse(questions["ok"])
        accepted = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","artifacts":[{"path":"artifact.md"}],"open_questions":["q"]}',
            "--accept-questions",
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
        run("done", "--plan", str(self.ledger))
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
                "skipped",
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
            '{"status":"done","artifacts":[{"path":"audit/trail.md"}]}',
        )
        self.assertFalse(payload["ok"])
        self.assertIn("ledger/memlog used as artifact", " ".join(payload["reasons"]))
        (self.tmp / "dir").mkdir()
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","artifacts":[{"path":"dir"}]}',
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
        )
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(run("validate", "--plan", str(self.ledger))["ok"])

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
            '{"status":"done"}',
        )
        self.assertFalse(refused["ok"])
        guarded = run(
            "set",
            "--plan",
            str(self.ledger),
            "--path",
            "phases.close",
            "--value",
            '{"status":"done"}',
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
        self.init_track("fix", "trivial")
        (self.tmp / "spec").mkdir()
        spec = self.tmp / "spec" / "SPEC.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.spec",
            "--value",
            "spec/SPEC.md",
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
        spec.unlink()
        refused = run("done", "--plan", str(self.ledger), "--workstream", "ws-001")
        self.assertFalse(refused["ok"])
        self.assertIn("missing evidence", refused["error"])
        spec.write_text("# Spec\n", encoding="utf-8")
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
        payload = run("done", "--plan", str(self.ledger), "--workstream", "ws-001")
        self.assertTrue(payload["ok"], payload)
        self.assertIn("marked done", trail.read_text())
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

    def test_conditional_skip_needs_a_reason(self) -> None:
        self.init()
        refused = run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "gates.plan.ux.status",
            "--value",
            "skipped",
        )
        self.assertFalse(refused["ok"])
        allowed = run(
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
                "passed" if gate == "trace" else "skipped",
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
                {"status": "done", "artifacts": [{"path": "artifact.md"}]}
            ),
            encoding="utf-8",
        )
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return-file",
            str(return_file),
        )
        self.assertTrue(payload["ok"], payload)
        refused = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done"}',
        )
        self.assertFalse(refused["ok"])
        self.assertIn("no artifacts returned", " ".join(refused["reasons"]))
        allowed = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done"}',
            "--allow-empty-artifacts",
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
            '{"status":"done","artifacts":[{"path":"empty.md"}]}',
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["missing_artifacts"], ["empty.md"])

    def test_verify_return_logs_accepted_open_questions(self) -> None:
        self.init()
        artifact = self.tmp / "artifact.md"
        artifact.write_text("# artifact\n", encoding="utf-8")
        payload = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","artifacts":[{"path":"artifact.md"}],'
            '"open_questions":["which region?"]}',
            "--accept-questions",
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


if __name__ == "__main__":
    unittest.main()
