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


def run_full(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
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
            '{"status":"done","artifacts":[{"path":"artifact.md"}],"evidence":["artifact.md"]}',
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
        self.edit_ledger(
            "del data['workstreams']['ws-001']['tickets']['audit']"
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
            '{"status":"done","artifacts":[{"path":"artifact.md"}],"evidence":["artifact.md"],"open_questions":["q"]}',
        )
        self.assertFalse(questions["ok"])
        accepted = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","artifacts":[{"path":"artifact.md"}],"evidence":["artifact.md"],"open_questions":["q"]}',
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
        refused = run(
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
        self.assertFalse(refused["ok"])
        self.assertIn("needs --reason", refused["error"])
        refused = run(
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
        self.assertFalse(refused["ok"])
        self.assertIn("later gates are decided: review", refused["error"])
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
        refused = run(
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
        self.assertFalse(refused["ok"])
        self.assertIn("needs --reason", refused["error"])
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
            "blocked",
        )
        self.assertFalse(refused["ok"])
        self.assertIn("needs --reason", refused["error"])
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
                    "artifacts": [{"path": "artifact.md"}],
                    "evidence": ["artifact.md"],
                }
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
        no_evidence = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","artifacts":["artifact.md"]}',
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
            '{"status":"done","evidence":["artifact.md"]}',
            "--allow-empty-artifacts",
        )
        self.assertFalse(unreasoned["ok"])
        self.assertIn("--allow-empty-artifacts needs --reason", unreasoned["error"])
        allowed = run(
            "verify-return",
            "--plan",
            str(self.ledger),
            "--project-root",
            str(self.tmp),
            "--return",
            '{"status":"done","evidence":["artifact.md"]}',
            "--allow-empty-artifacts",
            "--reason",
            "the brief produces no file",
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
            '"evidence":["artifact.md"],"open_questions":["which region?"]}',
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
            "skipped",
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
        for field in ("override_reason", "decided_at"):
            refused = run(
                "set",
                "--plan",
                str(self.ledger),
                "--workstream",
                "ws-001",
                "--path",
                f"tickets.1.3.gates.review.{field}",
                "--null",
            )
            self.assertFalse(refused["ok"], refused)
            self.assertIn("cannot clear decided gate metadata", refused["error"])

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
            "tickets.T1.gates.review.status",
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
            '"review": {"status": "passed"}, "done": {"status": "open"}}}',
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
            '{"status":"done","artifacts":[],"evidence":[],"open_questions":[]}',
            "--allow-empty-artifacts",
            "--reason",
            "the brief produces no file",
        )
        self.assertFalse(payload["ok"])
        self.assertIn("no evidence returned", payload["reasons"])

    def test_validate_and_verify_return_exit_nonzero_when_not_ok(self) -> None:
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

    def test_phase_evidence_cannot_be_replaced(self) -> None:
        self.init_track("feature", "epic")
        refused = run(
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
        self.assertFalse(refused["ok"])
        self.assertIn("append-only", refused["error"])

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

    def test_done_and_reconcile_reject_an_outside_root_pointer(self) -> None:
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
        self.assertIn("outside project root", refused["error"])
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
            '{"status":"done","artifacts":["out.md"],"evidence":["out.md"]}',
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
            "skipped",
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
            "skipped",
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
        run(
            "set",
            "--plan",
            str(self.ledger),
            "--workstream",
            "ws-001",
            "--path",
            "artifacts.spec",
            "--value",
            "artifact-dir",
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
            "--project-root",
            str(self.tmp),
            "--accept-missing-tickets",
            "--reason",
            "fixture",
        )
        self.assertFalse(payload["ok"])
        self.assertIn("spec=artifact-dir", payload["error"])

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
        migrated = run("migrate", "--plan", str(self.ledger))
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
            '{"status":"done","artifacts":["artifact.md"],'
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
