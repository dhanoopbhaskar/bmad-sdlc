#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml>=0.18"]
# ///
"""Deterministic state helper for the bmad-sdlc conductor.

Prints JSON to stdout. Errors are emitted as JSON with a non-zero exit code.
Every write is atomic (temp file, fsync, os.replace).

Subcommands:
  detect    Identify the installed BMAD model, hub, test skill family, paths,
            and a compact artifact/code inventory.
  init      Create the ledger and the audit trail at the resolved paths.
  validate  Check the ledger's structure. No writes.
  summary   Report workstream position, per-gate level/status, locked phases,
            ticket gates, and the recomputed next action.
  set       Set a scalar/object at a dotted path (optionally under a workstream).
  append    Append a value to a list at a dotted path.
  ticket    Set one per-ticket gate (ticket|tests|review|done).
  done      Mark the workstream done once all required gates are decided.
  migrate   Add gate levels and a tickets map to a pre-v2 ledger.
  reconcile Report missing artifact pointers and discoverable orphan artifacts.
  verify-return  Check a handoff return's artifacts and status; report ledger
                 edits as advisory.
  log       Append one line to the audit trail.

The ledger is an overlay. BMAD artifacts (sprint-status.yaml, tickets.toml,
build plans) remain the source of truth for ticket status; the ledger stores
position, gate outcomes, per-ticket gate state, decisions, and pointers only.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import fnmatch
import functools
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]

from ruamel.yaml import YAML

SCHEMA = "bmad-sdlc/1"
PHASES = ("plan", "solution", "build", "verify", "close")
PHASE_DEFAULT_GATE = {
    "plan": "required",
    "solution": "conditional",
    "build": "required",
    "verify": "required",
    "close": "optional",
}
PHASE_STATUSES = ("pending", "active", "done", "skipped", "blocked")
GATE_LEVELS = ("required", "conditional", "optional")
GATE_STATUSES = ("open", "passed", "overridden", "skipped", "blocked")
TICKET_GATES = ("ticket", "tests", "review", "done")
DOC_ROOTS = {"schema", "project", "created", "updated", "bmad", "active_workstream", "workstreams"}
WORKSTREAM_ROOTS = {
    "name",
    "track",
    "size",
    "status",
    "started",
    "current_phase",
    "artifacts",
    "phases",
    "gates",
    "tickets",
    "decisions",
    "next",
}
TRACKS = ("greenfield", "feature", "fix", "audit")
SIZES = ("trivial", "one-session", "epic", "project")
WS_STATUSES = ("active", "paused", "done")
ARTIFACTS = (
    "spec",
    "prd",
    "ux",
    "architecture",
    "stories",
    "tickets",
    "sprint_plan",
    "test_design",
    "test_framework",
    "ci",
    "trace",
)
GATE_NAMES = {
    "plan": ("requirements", "stories", "sprint", "ux", "architecture"),
    "solution": ("test_design", "framework", "ci"),
    "build": (),
    "verify": ("trace", "nfr", "test_review"),
    "close": ("retro", "walkthrough"),
}
GATES = tuple(
    f"{phase}.{name}" for phase, names in GATE_NAMES.items() for name in names
)
SKILL_DIRS = (
    ".agents/skills",
    ".claude/skills",
    ".cline/skills",
    ".bob/skills",
    ".agent/skills",
    ".adal/skills",
)
CODE_SUFFIXES = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".vue",
    ".svelte",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".rb",
    ".php",
    ".cs",
    ".swift",
    ".dart",
    ".ex",
    ".exs",
    ".lua",
    ".r",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".m",
    ".mm",
    ".sql",
    ".sh",
}
INVENTORY_SKIP = {
    ".git",
    ".hg",
    ".svn",
    ".agents",
    ".claude",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    "vendor",
    "Pods",
    ".gradle",
    ".next",
    ".nuxt",
    ".cache",
    ".tox",
    ".mypy_cache",
    ".terraform",
    "coverage",
    "_bmad",
    "_bmad-output",
    "__pycache__",
}

# Gate -> (action id, v6 skill). The current-model alias is resolved later.
GATE_ACTIONS = {
    "plan.stories": ("plan.stories", "bmad-create-epics-and-stories"),
    "plan.sprint": ("plan.sprint", "bmad-sprint-planning"),
    "plan.ux": ("plan.ux", "bmad-ux"),
    "plan.architecture": ("plan.architecture", "bmad-architecture"),
    "solution.test_design": ("solution.test_design", "bmad-testarch-test-design"),
    "solution.framework": ("solution.framework", "bmad-testarch-framework"),
    "solution.ci": ("solution.ci", "bmad-testarch-ci"),
    "verify.trace": ("verify.trace", "bmad-testarch-trace"),
    "verify.nfr": ("verify.nfr", "bmad-testarch-nfr"),
    "verify.test_review": ("verify.test_review", "bmad-testarch-test-review"),
    "close.retro": ("close.retro", "bmad-retrospective"),
    "close.walkthrough": ("close.walkthrough", "bmad-walkthrough"),
}
TICKET_ACTIONS = {
    "ticket": ("build.ticket", "bmad-build"),
    "tests": ("build.tests", "bmad-build"),
    "review": ("build.review", "bmad-code-review"),
    "done": ("build.done", "bmad-sprint-planning"),
}
CURRENT_ALIASES = {
    "bmad-spec": "bmad-agent-po",
    "bmad-prd": "bmad-agent-pm",
    "bmad-create-epics-and-stories": "bmad-agent-po",
    "bmad-sprint-planning": "bmad-agent-po",
    "bmad-product-brief": "bmad-agent-analyst",
    "bmad-prfaq": "bmad-agent-analyst",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def emit(payload: dict, code: int = 0) -> None:
    sys.stdout.write(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n"
    )
    sys.exit(code)


_COMMAND_FAILED = False


def fail(message: str, code: int = 1) -> None:
    global _COMMAND_FAILED
    _COMMAND_FAILED = True
    emit({"ok": False, "error": message}, code)


@contextlib.contextmanager
def file_lock(path: Path):
    """Serialize read-modify-write cycles for a ledger or audit trail.

    A sibling ``.lock`` file is used because atomic replaces change the ledger
    inode. POSIX uses ``flock``; Windows uses ``msvcrt.locking``.
    """
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is not None:
        with lock_path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return
    if msvcrt is not None:  # pragma: no cover - Windows only
        with lock_path.open("a+", encoding="utf-8") as handle:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    yield


def expand_project_root(
    value: str | Path, project_root: Path | None = None
) -> Path:
    """Substitute the {project-root} token in a caller-supplied path.

    Resolved customization values (for example ``ledger_path``) still carry
    the token, so every path that reaches the script must expand it. The
    working directory is the project root when no explicit root is given.
    """
    root = project_root if project_root is not None else Path.cwd()
    return Path(str(value).replace("{project-root}", str(root)))


def _plan_path(args: argparse.Namespace) -> Path:
    root = _resolve_root(args)
    if getattr(args, "plan", None):
        value = expand_project_root(args.plan, root)
        # A relative --plan is relative to the project root the command was
        # given, not to whatever directory the shell happens to be in.
        return (value if value.is_absolute() else root / value).resolve()
    return root / "_bmad-output" / "sdlc" / "plan.yaml"


def plan_locked(func):
    """Lock the ledger for the whole command and roll back a failed write.

    A command may save the ledger and then fail while appending the audit
    line. Restoring the pre-command bytes keeps the ledger and the audit
    trail from disagreeing.
    """

    @functools.wraps(func)
    def wrapper(args: argparse.Namespace):
        global _COMMAND_FAILED
        _COMMAND_FAILED = False
        if func.__name__ == "cmd_reconcile" and not getattr(args, "write", False):
            # Read-only reconcile must not need a lock file, so activation
            # works in a read-only checkout.
            return func(args)
        plan = _plan_path(args)
        with file_lock(plan):
            before = None
            if plan.is_file():
                before = plan.read_text(encoding="utf-8")
            try:
                return func(args)
            except SystemExit as exc:
                # `fail()` means the command did not complete. A negative
                # verdict (validate/reconcile exiting 1 with ok:false) is not
                # a failed write and must not undo what it just saved.
                if exc.code not in (0, None) and _COMMAND_FAILED:
                    try:
                        if before is not None:
                            atomic_write_text(plan, before)
                        elif plan.is_file():
                            plan.unlink()
                    except OSError:
                        pass
                raise
            except BaseException:
                try:
                    if before is not None:
                        atomic_write_text(plan, before)
                    elif plan.is_file():
                        plan.unlink()
                except OSError:
                    pass
                raise

    return wrapper


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


_CONFIG_ERRORS: list[str] = []


def _load_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        # A malformed config is not the same as an absent one: resolving the
        # default folders would silently point every evidence check at the
        # wrong directory, so record the failure for detect/init to surface.
        _CONFIG_ERRORS.append(f"{path}: {exc}")
        return {}
    except OSError:
        return {}


def _parts(path: str) -> list[str]:
    return [part for part in path.split(".") if part]


def _first_root(path: str) -> str:
    parts = _parts(path)
    return parts[0] if parts else ""


def _is_doc_path(path: str) -> bool:
    return _first_root(path) in DOC_ROOTS


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    yaml.encoding = "utf-8"
    return yaml


def atomic_write_text(path: Path, text: str) -> None:
    """Write text through a fsync'd temp file and an atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, encoding="utf-8"
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_name = handle.name
        # NamedTemporaryFile creates 0600; keep an existing file's mode and
        # create a new ledger/audit trail readable by the project.
        os.chmod(
            tmp_name,
            (path.stat().st_mode & 0o777) if path.exists() else 0o644,
        )
        os.replace(tmp_name, path)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_plan(path: Path) -> dict:
    if not path.is_file():
        fail(f"ledger not found: {path}")
    try:
        data = _yaml().load(path.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001 - surface the parser message
        fail(f"cannot parse ledger {path}: {error}")
    if not isinstance(data, dict):
        fail(f"ledger root must be a mapping: {path}")
    return data


def save_plan(path: Path, data: dict) -> None:
    buffer = io.StringIO()
    _yaml().dump(data, buffer)
    atomic_write_text(path, buffer.getvalue())


def read_skills(project_root: Path) -> tuple[set[str], str | None]:
    found: set[str] = set()
    used_dir: str | None = None
    for rel in SKILL_DIRS:
        directory = project_root / rel
        if not directory.is_dir():
            continue
        for item in directory.iterdir():
            if not (item.is_dir() and (item / "SKILL.md").is_file()):
                continue
            # The conductor is not a BMAD model skill. Counting it would make
            # an otherwise bare project look like a BMAD install.
            if item.name == "bmad-sdlc":
                continue
            found.add(item.name)
            used_dir = used_dir or rel
    manifest = project_root / "_bmad" / "_config" / "skill-manifest.csv"
    if manifest.is_file():
        try:
            with manifest.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    for key in ("skill", "name", "canonicalId"):
                        value = (row.get(key) or "").strip()
                        if value == "bmad-sdlc":
                            continue
                        if value.startswith("bmad-"):
                            found.add(value)
                            break
        except OSError:
            pass
    return found, used_dir


def resolve_paths(project_root: Path) -> dict[str, str]:
    _CONFIG_ERRORS.clear()
    paths = {
        "output_folder": "{project-root}/_bmad-output",
        "planning_artifacts": "{project-root}/_bmad-output/planning-artifacts",
        "implementation_artifacts": "{project-root}/_bmad-output/implementation-artifacts",
        "test_artifacts": "{project-root}/_bmad-output/test-artifacts",
    }
    config: dict = {}
    # Same precedence as _bmad/scripts/config_utils.py: the installer-owned
    # baseline, the personal layer, then the team and personal custom layers.
    for rel in (
        "_bmad/config.toml",
        "_bmad/config.user.toml",
        "_bmad/custom/config.toml",
        "_bmad/custom/config.user.toml",
    ):
        candidate = project_root / rel
        if candidate.is_file():
            _deep_merge(config, _load_toml(candidate))
    core = config.get("core") or {}
    modules = config.get("modules") or {}
    bmm = modules.get("bmm") or {}
    tea = modules.get("tea") or {}
    paths["output_folder"] = core.get("output_folder", paths["output_folder"])
    paths["planning_artifacts"] = bmm.get(
        "planning_artifacts", paths["planning_artifacts"]
    )
    paths["implementation_artifacts"] = bmm.get(
        "implementation_artifacts", paths["implementation_artifacts"]
    )
    paths["test_artifacts"] = tea.get("test_artifacts", paths["test_artifacts"])
    resolved: dict[str, str] = {}
    for key, value in paths.items():
        candidate = Path(str(value).replace("{project-root}", str(project_root)))
        if not candidate.is_absolute():
            candidate = project_root / candidate
        resolved[key] = str(candidate)
    return resolved


def project_relative(value: str, project_root: Path) -> str:
    try:
        return str(Path(value).resolve().relative_to(project_root))
    except ValueError:
        return value


def _default_project_root(ledger: Path) -> Path | None:
    """The project root for the default <project>/_bmad-output/sdlc layout."""
    resolved = ledger.resolve()
    if (
        resolved.parent.name == "sdlc"
        and resolved.parent.parent.name == "_bmad-output"
    ):
        return resolved.parent.parent.parent
    return None


def _resolve_root(args: argparse.Namespace) -> Path:
    """Resolve a command's project root, expanding the token once."""
    return Path(
        expand_project_root(
            getattr(args, "project_root", None) or ".", Path.cwd()
        )
    ).resolve()


def resolve_memlog(data: dict, args: argparse.Namespace, ledger: Path) -> Path:
    """Resolve the audit trail: explicit flag, then the path recorded at init."""
    if getattr(args, "memlog", None):
        root = _resolve_root(args)
        value = expand_project_root(args.memlog, root)
        resolved = (value if value.is_absolute() else root / value).resolve()
        if resolved == ledger.resolve():
            fail("the audit trail must differ from the ledger")
        return resolved
    recorded = (data.get("bmad") or {}).get("memlog")
    if recorded:
        candidate = Path(str(recorded))
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            root = _default_project_root(ledger)
            if root is not None:
                resolved = (root / candidate).resolve()
            else:
                resolved = (ledger.parent / candidate).resolve()
        if resolved == ledger.resolve():
            # A recorded audit path equal to the ledger would make every write
            # lock the ledger a second time and hang. Treat it as corruption.
            fail("the audit trail must differ from the ledger")
        return resolved
    return ledger.parent / ".memlog.md"


def apply_levels(workstream: dict, model: str) -> list[str]:
    """Recompute derived levels and repair phase states they invalidate."""
    track = workstream.get("track", "feature")
    size = workstream.get("size", "epic")
    levels = resolve_gate_levels(track, size, model)
    phase_levels = resolve_phase_levels(track, size, model)
    changed: list[str] = []
    gates = workstream.get("gates")
    if isinstance(gates, dict):
        for phase in PHASES:
            phase_gates = gates.get(phase)
            if not isinstance(phase_gates, dict):
                continue
            for name in GATE_NAMES[phase]:
                node = phase_gates.get(name)
                if not isinstance(node, dict):
                    continue
                resolved = levels.get(f"{phase}.{name}", "optional")
                if node.get("level") != resolved:
                    node["level"] = resolved
                    changed.append(f"gates.{phase}.{name}.level")
    phases = workstream.get("phases")
    if isinstance(phases, dict):
        for phase in PHASES:
            node = phases.get(phase)
            if not isinstance(node, dict):
                continue
            if node.get("gate") != phase_levels[phase]:
                node["gate"] = phase_levels[phase]
                changed.append(f"phases.{phase}.gate")
            # A phase status is a cache. A size/track change can demand gates
            # the old status skipped; reopen the phase instead of leaving a
            # ledger that validate rejects.
            if node.get("status") in ("done", "skipped"):
                entries = phase_gate_entries(workstream, phase, track, size, model)
                if phase_blocking(entries):
                    node["status"] = "pending"
                    changed.append(f"phases.{phase}.status->pending")
    return changed


def artifact_ticket_ids(project_root: Path, paths: dict[str, str]) -> set[str] | None:
    """Ticket ids named by BMAD artifacts, or None when no artifact is readable."""
    found: set[str] = set()
    seen = False
    tickets_file = discover_artifact("tickets", project_root, paths)
    if tickets_file is not None:
        try:
            parsed = tomllib.loads(tickets_file.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            seen = True
            tickets = parsed.get("tickets")
            if isinstance(tickets, dict):
                found.update(str(key) for key in tickets)
            elif isinstance(tickets, list):
                for item in tickets:
                    if isinstance(item, dict) and item.get("id"):
                        found.add(str(item["id"]))
        elif isinstance(parsed, list):
            seen = True
            for item in parsed:
                if isinstance(item, dict) and item.get("id"):
                    found.add(str(item["id"]))
    sprint = discover_artifact("sprint_plan", project_root, paths)
    if sprint is not None:
        try:
            parsed = _yaml().load(sprint.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a malformed sprint file is reported elsewhere
            parsed = None
        if isinstance(parsed, dict):
            seen = True
            for key in ("tickets", "stories"):
                items = parsed.get(key)
                if isinstance(items, dict):
                    found.update(str(item) for item in items)
                elif isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get("id"):
                            found.add(str(item["id"]))
            development = parsed.get("development_status")
            if isinstance(development, dict):
                # v6 lists epic-level rows beside story rows; only the story
                # keys are ticket ids.
                found.update(
                    str(item)
                    for item in development
                    if not str(item).startswith("epic")
                )
    return found if seen else None


def inventory(project_root: Path, paths: dict[str, str]) -> dict:
    """Return compact structural facts for track and size detection."""
    planning = Path(paths["planning_artifacts"])
    implementation = Path(paths["implementation_artifacts"])

    artifacts: list[str] = []
    for root in (planning, implementation):
        if not root.is_dir():
            continue
        for item in sorted(root.rglob("*")):
            if item.is_file() and item.suffix in (".md", ".yaml", ".yml", ".toml"):
                artifacts.append(project_relative(str(item), project_root))
                if len(artifacts) >= 40:
                    break
        if len(artifacts) >= 40:
            break

    sprint = implementation / "sprint-status.yaml"
    counts = {"epic": 0, "open": 0}

    def count_status(node: dict) -> None:
        for key, value in node.items():
            text = str(key)
            is_epic = text.startswith("epic")
            if is_epic:
                counts["epic"] += 1
            if (
                not is_epic
                and isinstance(value, str)
                and value in ("ready-for-dev", "in-progress", "review")
            ):
                counts["open"] += 1
            elif isinstance(value, dict):
                count_status(value)

    if sprint.is_file():
        try:
            sprint_data = _yaml().load(sprint.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - best-effort inventory
            sprint_data = None
        if isinstance(sprint_data, dict):
            count_status(sprint_data)
    epic_count = counts["epic"]
    open_story_count = counts["open"]

    ticket_files = []
    for candidate in (
        planning / "tickets" / "tickets.toml",
        implementation / "tickets" / "tickets.toml",
        project_root / "tickets.toml",
    ):
        if candidate.is_file():
            ticket_files.append(project_relative(str(candidate), project_root))

    has_epics_tickets = bool(
        epic_count
        or open_story_count
        or ticket_files
        or any("epic" in name.lower() for name in artifacts)
    )

    has_code = False
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(project_root):
        rel_parts = Path(dirpath).relative_to(project_root).parts
        if any(part in INVENTORY_SKIP for part in rel_parts):
            dirnames[:] = []
            continue
        for name in filenames:
            scanned += 1
            if Path(name).suffix in CODE_SUFFIXES:
                has_code = True
                break
        if has_code or scanned >= 5000:
            break

    return {
        "has_planning_artifacts": bool(artifacts),
        "has_epics_tickets": has_epics_tickets,
        "has_application_code": has_code,
        "epic_count": epic_count,
        "open_story_count": open_story_count,
        "ticket_files": ticket_files,
        "artifact_paths": artifacts,
    }


def detect_document(project_root: Path) -> dict:
    skills, skills_dir = read_skills(project_root)
    if "bmad-agent-po" in skills:
        model = "current"
        evidence = "bmad-agent-po is installed"
    elif "bmad-create-epics-and-stories" in skills or "bmad-sprint-planning" in skills:
        model = "v6"
        evidence = "bmad-create-epics-and-stories/bmad-sprint-planning are installed"
    elif any(name.startswith("bmad-") for name in skills):
        model = "unknown"
        evidence = "BMAD skills exist but the model-specific skills do not match"
    else:
        model = "unknown"
        evidence = "no BMAD skills found under the project root"
    if "bmad" in skills:
        hub = "bmad"
    elif "bmad-help" in skills:
        hub = "bmad-help"
    else:
        hub = None
    if "bmad-tea" in skills:
        # A fabricated bmad-tea-<capability> name is a missing-skill error in
        # version-adapters, so it must not make the detector look ready.
        test_style = "bmad-tea"
    elif any(name.startswith("bmad-testarch-") for name in skills):
        test_style = "bmad-testarch"
    else:
        test_style = "unknown"
    required_groups = {
        "v6": [
            ("bmad-prd", "bmad-agent-pm"),
            ("bmad-create-epics-and-stories", "bmad-agent-po"),
            ("bmad-sprint-planning", "bmad-agent-po"),
            ("bmad-build",),
        ],
        "current": [("bmad-agent-po",), ("bmad-build",)],
        "unknown": [("bmad-build",)],
    }[model]
    missing_core = [
        group[0]
        for group in required_groups
        if not any(name in skills for name in group)
    ]
    optional = ["bmad-code-review"] if "bmad-code-review" not in skills else []
    resolved = resolve_paths(project_root)
    return {
        "ok": True,
        "project_root": str(project_root),
        "search_roots": [str(project_root)],
        "skills_dir": skills_dir,
        "model": model,
        "hub": hub,
        "test_style": test_style,
        "evidence": evidence,
        "skills": sorted(skills),
        "missing_core": missing_core,
        "missing_optional": optional,
        "paths": resolved,
        "config_errors": list(_CONFIG_ERRORS),
        "inventory": inventory(project_root, resolved),
    }


def resolve_phase_levels(track: str, size: str, model: str) -> dict[str, str]:
    if track in ("audit", "fix"):
        return {
            "plan": (
                "optional"
                if track == "audit" or size in ("trivial", "one-session")
                else "conditional"
            ),
            "solution": "optional",
            "build": "required",
            "verify": "required" if track == "audit" else "conditional",
            "close": "optional",
        }
    if size == "trivial":
        return {
            "plan": "optional",
            "solution": "optional",
            "build": "required",
            "verify": "optional",
            "close": "optional",
        }
    if size in ("epic", "project"):
        return {
            "plan": "required",
            "solution": "conditional",
            "build": "required",
            "verify": "required",
            "close": "optional",
        }
    return {
        "plan": "conditional",
        "solution": "optional",
        "build": "required",
        "verify": "conditional",
        "close": "optional",
    }


def resolve_gate_levels(track: str, size: str, model: str) -> dict[str, str]:
    """Resolve one level per phase gate from track, size, and model."""
    big = size in ("epic", "project")
    trivial = size == "trivial"
    audit = track == "audit"
    fix = track == "fix"
    levels: dict[str, str] = {}

    if audit:
        return {
            "plan.requirements": "optional",
            "plan.stories": "optional",
            "plan.sprint": "optional",
            "plan.ux": "optional",
            "plan.architecture": "optional",
            "solution.test_design": "optional",
            "solution.framework": "optional",
            "solution.ci": "optional",
            "verify.trace": "required",
            "verify.nfr": "conditional",
            "verify.test_review": "conditional",
            "close.retro": "optional",
            "close.walkthrough": "optional",
        }

    if fix:
        levels["plan.requirements"] = "optional"
    elif big:
        levels["plan.requirements"] = "required"
    elif size == "one-session":
        levels["plan.requirements"] = "conditional"
    else:
        levels["plan.requirements"] = "optional"

    if fix and size in ("trivial", "one-session"):
        # A fix starts from a direct build intent; a separate ticket tree is
        # optional and is recorded as the build action itself.
        levels["plan.stories"] = "optional"
    elif fix:
        levels["plan.stories"] = "conditional"
    elif big:
        levels["plan.stories"] = "required"
    elif size == "one-session":
        levels["plan.stories"] = "conditional"
    else:
        levels["plan.stories"] = "optional"

    levels["plan.sprint"] = (
        "required" if (big and model == "v6" and not fix) else "optional"
    )
    levels["plan.ux"] = "optional" if (trivial or fix) else "conditional"
    levels["plan.architecture"] = (
        "conditional" if (big and not fix) else "optional"
    )

    for gate in ("test_design", "framework", "ci"):
        levels[f"solution.{gate}"] = (
            "conditional" if (big and not fix) else "optional"
        )

    if big and not fix:
        levels["verify.trace"] = "required"
    elif trivial or fix:
        levels["verify.trace"] = "optional" if trivial else "conditional"
    else:
        levels["verify.trace"] = "conditional"
    levels["verify.nfr"] = (
        "conditional" if (big and not fix) else "optional"
    )
    levels["verify.test_review"] = (
        "conditional" if (big and not fix) else "optional"
    )

    levels["close.retro"] = "optional"
    levels["close.walkthrough"] = "optional"
    return levels


def resolve_skill(skill: str | None, model: str) -> str | None:
    if not skill:
        return None
    if model == "current":
        if skill in CURRENT_ALIASES:
            return CURRENT_ALIASES[skill]
        if skill.startswith("bmad-testarch-"):
            # Current BMAD ships one test-architecture agent, not fabricated
            # per-capability names. Blocking on a missing bmad-tea is honest;
            # recommending bmad-tea-trace is not.
            return "bmad-tea"
    return skill


def action_for_gate(
    gate_id: str, track: str, size: str, model: str
) -> dict:
    parts = gate_id.split(".")
    ticket = None
    ticket_gate = None
    if parts[0] == "build" and len(parts) >= 3:
        # build.<ticket>.<gate>: the ticket is the middle, the action key is
        # the last segment. Keeping the full id avoids two names for one gate.
        ticket = ".".join(parts[1:-1])
        ticket_gate = parts[-1]
    elif parts[0] == "build" and len(parts) == 2:
        ticket_gate = parts[1]
    if gate_id == "plan.requirements":
        if size == "project":
            action, skill = "plan.prd", "bmad-prd"
        else:
            action, skill = "frame.spec", "bmad-spec"
    elif gate_id in GATE_ACTIONS:
        action, skill = GATE_ACTIONS[gate_id]
    elif ticket_gate in TICKET_ACTIONS:
        action, skill = TICKET_ACTIONS[ticket_gate]
    else:
        action, skill = gate_id, None
    result = {
        "phase": parts[0],
        "gate": gate_id,
        "action": action,
        "skill": resolve_skill(skill, model),
    }
    if ticket is not None:
        result["ticket"] = ticket
    return result


def default_workstream(name: str, track: str, size: str, stamp: str, model: str) -> dict:
    levels = resolve_gate_levels(track, size, model)
    phase_levels = resolve_phase_levels(track, size, model)
    current = (
        "build"
        if track == "audit"
        or size == "trivial"
        or (track == "fix" and size == "one-session")
        else "plan"
    )
    phases: dict[str, dict] = {}
    for phase in PHASES:
        if phase == current:
            status = "active"
        elif phase in ("plan", "solution") and phase_levels[phase] == "optional":
            status = "skipped"
        else:
            status = "pending"
        phases[phase] = {
            "status": status,
            "gate": phase_levels[phase],
            "evidence": [],
            # `set` refuses a skip without a reason; auto-skipped phases must
            # carry an equivalent recorded reason or the default ledger would
            # violate its own rule.
            "note": (
                f"auto-skipped: not required for track={track}, size={size}"
                if status == "skipped"
                else ""
            ),
        }
    gates: dict[str, dict] = {}
    for phase in PHASES:
        gates[phase] = {}
        for gate_name in GATE_NAMES[phase]:
            gate_id = f"{phase}.{gate_name}"
            gates[phase][gate_name] = {
                "status": "open",
                "level": levels.get(gate_id, "optional"),
                "decided_at": None,
                "override_reason": None,
            }
    tickets: dict[str, dict] = {}
    if track == "audit":
        # An audit has no build tickets. The synthetic `audit` ticket carries
        # the required code-review gate so the conductor can track it exactly
        # like a per-ticket review.
        tickets["audit"] = {
            "title": "Audit",
            "gates": {
                "ticket": {
                    "status": "skipped",
                    "decided_at": None,
                    "override_reason": None,
                },
                "tests": {
                    "status": "skipped",
                    "decided_at": None,
                    "override_reason": None,
                },
                "review": {
                    "status": "open",
                    "decided_at": None,
                    "override_reason": None,
                },
                "done": {
                    "status": "skipped",
                    "decided_at": None,
                    "override_reason": None,
                },
            },
        }
    return {
        "name": name,
        "track": track,
        "size": size,
        "status": "active",
        "started": stamp,
        "updated": stamp,
        "current_phase": current,
        "artifacts": {key: None for key in ARTIFACTS},
        "phases": phases,
        "gates": gates,
        "tickets": tickets,
        "decisions": [],
        "next": None,
    }


def template_document(script_dir: Path, template_path: Path | None = None) -> dict:
    candidates = [template_path] if template_path is not None else []
    candidates.append(script_dir.parent / "assets" / "plan-template.yaml")
    for template in candidates:
        if template is None:
            continue
        if not template.is_file():
            if template_path is not None and template == template_path:
                fail(f"ledger template not found: {template}")
            continue
        try:
            data = _yaml().load(template.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            if template_path is not None and template == template_path:
                fail(f"ledger template root must be a mapping: {template}")
        except Exception as error:  # noqa: BLE001 - surface a bad explicit template
            if template_path is not None and template == template_path:
                fail(f"cannot parse ledger template {template}: {error}")
    return {
        "schema": SCHEMA,
        "project": None,
        "created": None,
        "updated": None,
        "bmad": {
            "model": "unknown",
            "hub": None,
            "output_folder": "_bmad-output",
            "planning_artifacts": "_bmad-output/planning-artifacts",
            "implementation_artifacts": "_bmad-output/implementation-artifacts",
            "test_artifacts": "_bmad-output/test-artifacts",
        },
        "active_workstream": None,
        "workstreams": {},
    }


def next_workstream_id(workstreams: dict) -> str:
    index = 1
    while f"ws-{index:03d}" in workstreams:
        index += 1
    return f"ws-{index:03d}"


def append_memlog(path: Path, type_: str, text: str) -> Path:
    with file_lock(path):
        return _append_memlog(path, type_, text)


def _append_memlog(path: Path, type_: str, text: str) -> Path:
    stamp = now_iso()
    clean = " ".join(text.split())
    line = f"- ({type_}) {stamp} — {clean}"
    if path.is_file():
        content = path.read_text(encoding="utf-8")
    else:
        content = f"---\ntopic: bmad-sdlc\ngoal: conduct the BMAD SDLC with a durable plan\nupdated: {stamp}\n---\n\n"
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) == 3:
            front = parts[1]
            if not front.startswith("\n"):
                front = "\n" + front
            lines = front.splitlines()
            updated = False
            for index, row in enumerate(lines):
                if row.strip().startswith("updated:"):
                    lines[index] = f"updated: {stamp}"
                    updated = True
            if not updated:
                lines.append(f"updated: {stamp}")
            content = "---" + "\n".join(lines) + "\n---" + parts[2]
    if not content.endswith("\n"):
        content += "\n"
    atomic_write_text(path, content + line + "\n")
    return path


def get_parent(document: dict, path: str) -> tuple[dict, str]:
    parts = [part for part in path.split(".") if part]
    if not parts:
        fail("empty --path")
    current: dict = document
    start = 0
    # Ticket ids are arbitrary strings, dots included, so a dotted path cannot
    # be split blindly. Match the whole remainder first (a whole-node write),
    # then the longest existing ticket id.
    if (
        parts[0] == "tickets"
        and len(parts) > 1
        and isinstance(document.get("tickets"), dict)
    ):
        tickets = document["tickets"]
        whole = ".".join(parts[1:])
        if whole in tickets:
            return tickets, whole
        if len(parts) > 2:
            for cut in range(len(parts) - 1, 1, -1):
                candidate = ".".join(parts[1:cut])
                if candidate not in tickets:
                    continue
                node = tickets[candidate]
                if not isinstance(node, dict):
                    fail(f"ticket {candidate!r} is not a mapping")
                current = node
                start = cut
                break
    for part in parts[start:-1]:
        node = current.get(part)
        if node is None:
            node = {}
            current[part] = node
        if not isinstance(node, dict):
            fail(f"path segment is not a mapping: {part}")
        current = node
    return current, parts[-1]


def parse_value(raw: str | None, null: bool):
    if null:
        return None
    if raw is None:
        fail("provide --value or --null")
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def workstream_root(data: dict, workstream_id: str | None) -> tuple[str, dict]:
    workstreams = data.get("workstreams") or {}
    target = workstream_id or data.get("active_workstream")
    if not target:
        fail("no workstream selected; pass --workstream")
    if target not in workstreams:
        fail(f"workstream not found: {target}")
    return target, workstreams[target]


def gate_level(gate_id: str, gate_node: dict, levels: dict[str, str]) -> str:
    """Levels are derived state. The stored copy is informational only.

    ``validate`` reports drift from the resolver; ``summary``, ``done`` and
    ``computed_next`` must never be unlocked by editing the stored value.
    """
    del gate_node
    return levels.get(gate_id, "optional")


def ticket_levels(track: str, size: str) -> dict[str, str]:
    """A ticket always needs a build, a review, and an explicit done approval."""
    if track == "audit":
        return {
            "ticket": "optional",
            "tests": "optional",
            "review": "required",
            "done": "optional",
        }
    if size == "trivial":
        return {
            "ticket": "required",
            "tests": "optional",
            "review": "required",
            "done": "required",
        }
    return {
        "ticket": "required",
        "tests": "conditional",
        "review": "required",
        "done": "required",
    }


def ticket_summary(workstream: dict) -> dict:
    track = workstream.get("track", "feature")
    size = workstream.get("size", "epic")
    levels = ticket_levels(track, size)
    tickets = workstream.get("tickets")
    if not isinstance(tickets, dict):
        return {
            "count": 0,
            "open": [],
            "blocked": [],
            "required_open": [],
            "conditional_open": [],
            "items": {},
        }
    items: dict[str, dict] = {}
    open_gates: list[str] = []
    blocked_gates: list[str] = []
    required_open: list[str] = []
    conditional_open: list[str] = []
    for ticket_id, ticket in tickets.items():
        gates = (ticket or {}).get("gates") or {}
        item_gates = {}
        for gate_name in TICKET_GATES:
            node = gates.get(gate_name) or {}
            status = node.get("status", "open")
            level = levels.get(gate_name, "optional")
            item_gates[gate_name] = {
                "level": level,
                "status": status,
                "decided_at": node.get("decided_at"),
                "override_reason": node.get("override_reason"),
            }
            if status in ("open", "blocked"):
                gate_id = f"build.{ticket_id}.{gate_name}"
                if status == "blocked":
                    blocked_gates.append(gate_id)
                else:
                    open_gates.append(gate_id)
                if level == "required":
                    required_open.append(gate_id)
                elif level == "conditional":
                    conditional_open.append(gate_id)
        items[str(ticket_id)] = {
            "title": (ticket or {}).get("title"),
            "gates": item_gates,
        }
    return {
        "count": len(tickets),
        "open": open_gates,
        "blocked": blocked_gates,
        "required_open": required_open,
        "conditional_open": conditional_open,
        "items": items,
    }


def phase_gate_entries(
    workstream: dict, phase: str, track: str, size: str, model: str
) -> list[dict]:
    """Every gate that can block or advance a phase.

    Phase gates come first. The build phase contributes per-ticket gates
    instead; an audit's synthetic `audit` ticket is handled the same way.
    """
    levels = resolve_gate_levels(track, size, model)
    gate_nodes = (workstream.get("gates") or {}).get(phase) or {}
    entries: list[dict] = []
    for name in GATE_NAMES[phase]:
        gate_id = f"{phase}.{name}"
        node = gate_nodes.get(name) or {}
        entries.append(
            {
                "id": gate_id,
                "phase": phase,
                "name": name,
                "ticket": None,
                "level": gate_level(gate_id, node, levels),
                "status": node.get("status", "open"),
                "decided_at": node.get("decided_at"),
                "override_reason": node.get("override_reason"),
            }
        )
    if phase == "build":
        tlevels = ticket_levels(track, size)
        tickets = workstream.get("tickets")
        if not isinstance(tickets, dict):
            tickets = {}
        if track == "audit" and "audit" not in tickets:
            # An audit always has one required code review, even if the
            # synthetic ticket was removed from the ledger.
            entries.append(
                {
                    "id": "build.audit.review",
                    "phase": "build",
                    "name": "review",
                    "ticket": "audit",
                    "level": "required",
                    "status": "open",
                    "decided_at": None,
                    "override_reason": None,
                }
            )
        for ticket_id, ticket in tickets.items():
            gates = (ticket or {}).get("gates") or {}
            for gate_name in TICKET_GATES:
                node = gates.get(gate_name) or {}
                entries.append(
                    {
                        "id": f"build.{ticket_id}.{gate_name}",
                        "phase": "build",
                        "name": gate_name,
                        "ticket": str(ticket_id),
                        "level": tlevels.get(gate_name, "optional"),
                        "status": node.get("status", "open"),
                        "decided_at": node.get("decided_at"),
                        "override_reason": node.get("override_reason"),
                    }
                )
    # Preserve any extra gates an older ledger added under this phase.
    for name, node in gate_nodes.items():
        if name in GATE_NAMES[phase]:
            continue
        gate_id = f"{phase}.{name}"
        entries.append(
            {
                "id": gate_id,
                "phase": phase,
                "name": name,
                "ticket": None,
                "level": (node or {}).get("level", "optional"),
                "status": (node or {}).get("status", "open"),
                "decided_at": (node or {}).get("decided_at"),
                "override_reason": (node or {}).get("override_reason"),
            }
        )
    return entries


def first_blocking(entries: list[dict]) -> dict | None:
    """The next gate that must be decided, required before conditional."""
    for level in ("required", "conditional"):
        for entry in entries:
            if entry["level"] != level:
                continue
            if entry["status"] in ("open", "blocked"):
                return entry
            if (
                level in ("required", "conditional")
                and entry["status"] == "skipped"
                and not entry["override_reason"]
            ):
                return entry
    return None


def phase_blocking(entries: list[dict]) -> list[dict]:
    """Every gate that prevents a phase from being complete."""
    blocking: list[dict] = []
    for entry in entries:
        if entry["level"] in ("required", "conditional") and entry["status"] in (
            "open",
            "blocked",
        ):
            blocking.append(entry)
        elif (
            entry["level"] in ("required", "conditional")
            and entry["status"] == "skipped"
            and not entry["override_reason"]
        ):
            blocking.append(entry)
    return blocking


def optional_actions(
    workstream: dict, track: str, size: str, model: str
) -> list[dict]:
    """Open optional gates, offered but never required to advance."""
    phases = workstream.get("phases") or {}
    actions: list[dict] = []
    seen: set[tuple[str, str | None]] = set()
    for phase in PHASES:
        node = phases.get(phase) or {}
        if node.get("status") in ("done", "skipped"):
            continue
        for entry in phase_gate_entries(workstream, phase, track, size, model):
            if entry["status"] != "open" or entry["level"] != "optional":
                continue
            action = action_for_gate(entry["id"], track, size, model)
            key = (action["action"], action.get("ticket"))
            if key in seen:
                continue
            seen.add(key)
            action["reason"] = f"{entry['id']} is optional."
            actions.append(action)
    return actions


def computed_next(
    workstream: dict,
    track: str,
    size: str,
    model: str,
) -> dict | None:
    if workstream.get("status") in ("done", "paused"):
        return None
    phases = workstream.get("phases") or {}
    tickets = workstream.get("tickets")
    if not isinstance(tickets, dict):
        tickets = {}
    for phase in PHASES:
        node = phases.get(phase) or {}
        entries = phase_gate_entries(workstream, phase, track, size, model)
        blocking = phase_blocking(entries)
        # A phase status is a cache. It may only suppress gates when the
        # phase actually has no blocking gate left.
        if node.get("status") in ("done", "skipped") and not blocking:
            continue
        next_gate = first_blocking(entries)
        if next_gate:
            result = action_for_gate(next_gate["id"], track, size, model)
            state = "blocked" if next_gate["status"] == "blocked" else "open"
            if next_gate["status"] == "skipped":
                state = "skipped without a reason"
            result["reason"] = (
                f"{next_gate['id']} is a {next_gate['level']} {state} gate."
            )
            return result
        if node.get("status") == "blocked":
            return {
                "phase": phase,
                "gate": None,
                "action": f"{phase}.unblock",
                "skill": None,
                "reason": f"{phase} is blocked; resolve the blocker.",
            }
        if phase == "build" and not tickets:
            if track == "audit":
                result = action_for_gate("build.audit.review", track, size, model)
                result["reason"] = "An audit starts with an independent code review."
            else:
                result = action_for_gate("build.ticket", track, size, model)
                result["reason"] = "Build the next ready ticket."
            # The ticket id is supplied by the user or the BMAD artifact.
            result.setdefault("ticket", None)
            result["ticket_required"] = True
            return result
        # No blocking gates: the phase is complete for recommendation
        # purposes. Optional gates stay available through optional_actions.
    return {
        "phase": "close",
        "gate": None,
        "action": "close.mark_done",
        "skill": None,
        "reason": "All required gates are passed; mark the workstream done.",
    }


def refresh_workstream(workstream: dict, model: str) -> None:
    """Recompute the current phase and the next-action cache from gate state."""
    track = workstream.get("track", "feature")
    size = workstream.get("size", "epic")
    phases = workstream.get("phases") or {}
    if workstream.get("status") == "done":
        workstream["current_phase"] = "close"
        workstream["next"] = None
        return
    current = None
    for phase in PHASES:
        node = phases.get(phase) or {}
        entries = phase_gate_entries(workstream, phase, track, size, model)
        blocking = phase_blocking(entries)
        if node.get("status") in ("done", "skipped") and not blocking:
            continue
        if (
            phase == "build"
            and not (workstream.get("tickets") or {})
            and track != "audit"
        ):
            current = phase
            break
        if blocking or node.get("status") in ("active", "blocked"):
            current = phase
            break
    workstream["current_phase"] = current or "close"
    workstream["next"] = computed_next(workstream, track, size, model)


def cmd_detect(args: argparse.Namespace) -> None:
    project_root = Path(
        expand_project_root(args.project_root, Path.cwd())
    ).resolve()
    if not project_root.is_dir():
        fail(f"project root not found: {project_root}")
    emit(detect_document(project_root))


@plan_locked
def cmd_init(args: argparse.Namespace) -> None:
    project_root = Path(
        expand_project_root(args.project_root, Path.cwd())
    ).resolve()
    if not project_root.is_dir():
        fail(f"project root not found: {project_root}")

    def under_root(value: str) -> Path:
        path = expand_project_root(value, project_root)
        return (path if path.is_absolute() else project_root / path).resolve()

    ledger_path = (
        under_root(args.plan)
        if args.plan
        else project_root / "_bmad-output" / "sdlc" / "plan.yaml"
    )
    memlog_path = (
        under_root(args.memlog)
        if args.memlog
        else ledger_path.parent / ".memlog.md"
    )
    if memlog_path == ledger_path.resolve():
        fail("the audit trail must differ from the ledger")
    template_path = None
    if args.template:
        candidate = expand_project_root(args.template, project_root)
        if not candidate.is_absolute():
            # A project-relative template wins; the skill's own assets are the
            # fallback. Keep this order documented in SKILL.md.
            project_candidate = project_root / candidate
            skill_candidate = Path(__file__).resolve().parent.parent / candidate
            candidate = (
                project_candidate
                if project_candidate.is_file()
                else skill_candidate
            )
        template_path = candidate.resolve()
        if not template_path.is_file():
            fail(f"ledger template not found: {template_path}")
    if not str(args.name or "").strip():
        fail("--name must be non-empty")
    track = args.track or args.default_track or "feature"
    if track not in TRACKS:
        fail(f"unknown track {track!r}; choose one of {', '.join(TRACKS)}")
    if args.size is not None and args.size not in SIZES:
        fail(f"unknown size {args.size!r}; choose one of {', '.join(SIZES)}")
    if args.default_size is not None and args.default_size not in SIZES:
        fail(
            f"unknown default size {args.default_size!r}; "
            f"choose one of {', '.join(SIZES)}"
        )
    # A fix or audit without an explicit size starts small, regardless of the
    # configured default; a greenfield or feature starts at that default.
    if args.size is not None:
        size = args.size
    elif track in ("fix", "audit"):
        size = "one-session"
    else:
        size = args.default_size or "epic"
    detection = detect_document(project_root)
    if detection.get("config_errors"):
        fail(
            "malformed BMAD config; fix it before init: "
            + "; ".join(detection["config_errors"])
        )
    stamp = now_iso()
    reset_from = None
    if args.force and ledger_path.exists():
        if not str(args.reason or "").strip():
            fail("--force requires --reason")
        backup = ledger_path.with_name(ledger_path.name + ".bak")
        atomic_write_text(backup, ledger_path.read_text(encoding="utf-8"))
        reset_from = backup
    existing = ledger_path.exists() and not args.force
    if existing:
        data = load_plan(ledger_path)
    else:
        data = template_document(Path(__file__).resolve().parent, template_path)
    # A second init without --memlog must keep appending to the audit trail
    # recorded at init, not start a second one beside the ledger.
    if not args.memlog:
        memlog_path = resolve_memlog(data, args, ledger_path)
    current_model = (data.get("bmad") or {}).get("model")
    if (
        args.model == "unknown"
        and existing
        and current_model in ("v6", "current")
        and not args.force
    ):
        fail(
            "refusing to downgrade the confirmed BMAD model to unknown; "
            "pass --force --reason to reset it"
        )
    if args.model:
        model = args.model
    elif existing and detection["model"] == "unknown" and current_model in (
        "v6",
        "current",
    ):
        # Never downgrade a user-confirmed model because detection is silent.
        model = current_model
    else:
        model = detection["model"]
    model_drift = bool(
        existing
        and current_model in ("v6", "current")
        and model != current_model
    )
    data["schema"] = SCHEMA
    if args.force or not data.get("project"):
        data["project"] = args.name
    data["created"] = stamp if args.force else (data.get("created") or stamp)
    data["updated"] = stamp
    if args.memlog or not (data.get("bmad") or {}).get("memlog"):
        recorded_memlog = (
            str(memlog_path)
            if _default_project_root(ledger_path) is None
            else project_relative(str(memlog_path), project_root)
        )
    else:
        recorded_memlog = (data.get("bmad") or {}).get("memlog")
    # Merge, do not replace: a custom template may add organization-specific
    # keys under bmad and they must survive init.
    bmad = data.get("bmad")
    if not isinstance(bmad, dict):
        bmad = {}
    bmad.update(
        {
            "model": model,
            "memlog": recorded_memlog,
            "hub": detection["hub"],
            "output_folder": project_relative(
                detection["paths"]["output_folder"], project_root
            ),
            "planning_artifacts": project_relative(
                detection["paths"]["planning_artifacts"], project_root
            ),
            "implementation_artifacts": project_relative(
                detection["paths"]["implementation_artifacts"], project_root
            ),
            "test_artifacts": project_relative(
                detection["paths"]["test_artifacts"], project_root
            ),
        }
    )
    data["bmad"] = bmad
    workstreams = data.get("workstreams")
    if not isinstance(workstreams, dict):
        workstreams = {}
    if existing and model != current_model:
        # Derived levels must follow the recorded model, including when an
        # older workstream was created under the previous model. A phase the
        # new model reopens is a lifecycle change and needs a reason.
        reopened: list[str] = []
        for other_id, other in workstreams.items():
            if not isinstance(other, dict):
                continue
            for entry in apply_levels(other, model):
                if entry.startswith("phases.") and entry.endswith(
                    ".status->pending"
                ):
                    reopened.append(f"{other_id}.{entry}")
            refresh_workstream(other, model)
        if reopened and not str(getattr(args, "reason", "") or "").strip():
            fail(
                "changing the model reopens "
                + ", ".join(reopened)
                + "; pass --reason to record why"
            )
    workstream_id = args.workstream or next_workstream_id(workstreams)
    if workstream_id in workstreams:
        fail(f"workstream already exists: {workstream_id}")
    paused: list[str] = []
    for other_id, other in workstreams.items():
        if isinstance(other, dict) and other.get("status") == "active":
            other["status"] = "paused"
            paused.append(other_id)
    workstream = default_workstream(args.name, track, size, stamp, model)
    refresh_workstream(workstream, model)
    workstreams[workstream_id] = workstream
    data["workstreams"] = workstreams
    data["active_workstream"] = workstream_id
    save_plan(ledger_path, data)
    memlog = append_memlog(
        memlog_path,
        "event",
        f"workstream {workstream_id} created: {args.name} "
        f"(track={track}, size={size}, model={model})",
    )
    if model_drift:
        append_memlog(
            memlog_path,
            "event",
            f"BMAD model changed from {current_model} to {model}",
        )
    if reset_from is not None:
        append_memlog(
            memlog_path,
            "event",
            f"ledger reset from {reset_from}: {args.reason}",
        )
    if paused:
        append_memlog(
            memlog_path,
            "event",
            f"workstream(s) paused for new active workstream: {', '.join(paused)}",
        )
    emit(
        {
            "ok": True,
            "ledger": str(ledger_path),
            "memlog": str(memlog),
            "workstream": workstream_id,
            "model": model,
            "model_drift": model_drift,
            "paused": paused,
            "reset_from": str(reset_from) if reset_from else None,
            "detection": detection,
        }
    )


def cmd_validate(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    errors: list[str] = []
    warnings: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")
    if not isinstance(data.get("project"), str) or not data.get("project"):
        errors.append("project must be a non-empty string")
    if not isinstance(data.get("created"), str):
        errors.append("created must be a string")
    if not isinstance(data.get("updated"), str):
        errors.append("updated must be a string")
    workstreams = data.get("workstreams")
    if not isinstance(workstreams, dict):
        errors.append("workstreams must be a mapping")
        workstreams = {}
    active = data.get("active_workstream")
    if active is not None and active not in workstreams:
        errors.append(f"active_workstream {active!r} is not in workstreams")
    elif (
        active is not None
        and isinstance(workstreams.get(active), dict)
        and workstreams[active].get("status") != "active"
    ):
        errors.append(
            f"active_workstream {active!r} must have status 'active'"
        )
    model = (data.get("bmad") or {}).get("model")
    if model not in ("v6", "current", "unknown"):
        errors.append("bmad.model must be one of v6, current, unknown")
    active_count = sum(
        1
        for workstream in workstreams.values()
        if isinstance(workstream, dict) and workstream.get("status") == "active"
    )
    if active_count > 1:
        errors.append(
            "only one workstream may be active at a time; "
            "set the others to paused or done"
        )
    if active is None and active_count:
        errors.append(
            "active_workstream is null while a workstream is active; "
            "name the active workstream or pause it"
        )
    for workstream_id, workstream in workstreams.items():
        label = f"workstreams.{workstream_id}"
        if not isinstance(workstream, dict):
            errors.append(f"{label} must be a mapping")
            continue
        track = workstream.get("track")
        size = workstream.get("size")
        if track not in TRACKS:
            errors.append(f"{label}.track must be one of {', '.join(TRACKS)}")
        if size not in SIZES:
            errors.append(f"{label}.size must be one of {', '.join(SIZES)}")
        levels = resolve_gate_levels(
            track if track in TRACKS else "feature",
            size if size in SIZES else "epic",
            model if model in ("v6", "current", "unknown") else "unknown",
        )
        ticket_level_map = ticket_levels(
            track if track in TRACKS else "feature",
            size if size in SIZES else "epic",
        )
        if not isinstance(workstream.get("name"), str) or not str(
            workstream.get("name") or ""
        ).strip():
            errors.append(f"{label}.name must be a non-empty string")
        if not isinstance(workstream.get("started"), str) or not str(
            workstream.get("started") or ""
        ).strip():
            errors.append(f"{label}.started must be a timestamp string")
        if workstream.get("status") not in WS_STATUSES:
            errors.append(f"{label}.status must be one of {', '.join(WS_STATUSES)}")
        if workstream.get("current_phase") not in PHASES:
            errors.append(f"{label}.current_phase must be one of {', '.join(PHASES)}")
        if not isinstance(workstream.get("artifacts"), dict):
            errors.append(f"{label}.artifacts must be a mapping")
        else:
            missing = [key for key in ARTIFACTS if key not in workstream["artifacts"]]
            if missing:
                errors.append(f"{label}.artifacts missing keys: {', '.join(missing)}")
        phases = workstream.get("phases")
        if not isinstance(phases, dict):
            errors.append(f"{label}.phases must be a mapping")
        else:
            active_phases = [
                phase
                for phase in PHASES
                if isinstance(phases.get(phase), dict)
                and phases[phase].get("status") == "active"
            ]
            if len(active_phases) > 1:
                errors.append(
                    f"{label} has more than one active phase: "
                    + ", ".join(active_phases)
                )
            for phase in PHASES:
                node = phases.get(phase)
                if not isinstance(node, dict):
                    errors.append(f"{label}.phases.{phase} must be a mapping")
                    continue
                if node.get("status") not in PHASE_STATUSES:
                    errors.append(
                        f"{label}.phases.{phase}.status must be one of "
                        f"{', '.join(PHASE_STATUSES)}"
                    )
                if node.get("gate") not in GATE_LEVELS:
                    errors.append(
                        f"{label}.phases.{phase}.gate must be one of "
                        f"{', '.join(GATE_LEVELS)}"
                    )
                if not isinstance(node.get("evidence"), list):
                    errors.append(f"{label}.phases.{phase}.evidence must be a list")
                phase_levels = resolve_phase_levels(
                    track if track in TRACKS else "feature",
                    size if size in SIZES else "epic",
                    model if model in ("v6", "current", "unknown") else "unknown",
                )
                if (
                    node.get("gate") in GATE_LEVELS
                    and node.get("gate") != phase_levels[phase]
                ):
                    errors.append(
                        f"{label}.phases.{phase}.gate is {node.get('gate')}, "
                        f"resolved {phase_levels[phase]}"
                    )
                if node.get("status") in ("done", "skipped"):
                    entries = phase_gate_entries(
                        workstream,
                        phase,
                        track if track in TRACKS else "feature",
                        size if size in SIZES else "epic",
                        model if model in ("v6", "current", "unknown") else "unknown",
                    )
                    blocking = phase_blocking(entries)
                    if blocking:
                        errors.append(
                            f"{label}.phases.{phase} is {node.get('status')} with "
                            f"undecided gates: "
                            + ", ".join(entry["id"] for entry in blocking)
                        )
                    if node.get("status") == "done":
                        for earlier in PHASES[: PHASES.index(phase)]:
                            earlier_entries = phase_gate_entries(
                                workstream,
                                earlier,
                                track if track in TRACKS else "feature",
                                size if size in SIZES else "epic",
                                model
                                if model in ("v6", "current", "unknown")
                                else "unknown",
                            )
                            if phase_blocking(earlier_entries):
                                errors.append(
                                    f"{label}.phases.{phase} is done while "
                                    f"{earlier} has undecided gates"
                                )
                                break
                    if (
                        phase == "build"
                        and node.get("status") == "done"
                        and not (workstream.get("tickets") or {})
                        and track != "audit"
                    ):
                        errors.append(
                            f"{label}.phases.build is done with no ticket built"
                        )
        gates = workstream.get("gates")
        if not isinstance(gates, dict):
            errors.append(f"{label}.gates must be a mapping")
        else:
            for phase in PHASES:
                phase_gates = gates.get(phase)
                if not isinstance(phase_gates, dict):
                    errors.append(f"{label}.gates.{phase} must be a mapping")
                    continue
                for name in GATE_NAMES[phase]:
                    node = phase_gates.get(name)
                    if not isinstance(node, dict):
                        errors.append(f"{label}.gates.{phase}.{name} must be a mapping")
                        continue
                    if node.get("status") not in GATE_STATUSES:
                        errors.append(
                            f"{label}.gates.{phase}.{name}.status must be one of "
                            f"{', '.join(GATE_STATUSES)}"
                        )
                    level = node.get("level")
                    if level is None:
                        warnings.append(
                            f"{label}.gates.{phase}.{name}.level missing; "
                            "run migrate to materialize it"
                        )
                        level = levels.get(f"{phase}.{name}", "optional")
                    elif level not in GATE_LEVELS:
                        errors.append(
                            f"{label}.gates.{phase}.{name}.level must be one of "
                            f"{', '.join(GATE_LEVELS)}"
                        )
                    elif level != levels.get(f"{phase}.{name}", "optional"):
                        errors.append(
                            f"{label}.gates.{phase}.{name}.level is {level}, "
                            f"resolved {levels.get(f'{phase}.{name}', 'optional')}; "
                            "run resize or migrate"
                        )
                    if (
                        node.get("status") == "overridden"
                        and level in ("required", "conditional")
                        and not str(node.get("override_reason") or "").strip()
                    ) or (
                        node.get("status") == "skipped"
                        and level in ("required", "conditional")
                        and not str(node.get("override_reason") or "").strip()
                    ):
                        errors.append(
                            f"{label}.gates.{phase}.{name} is "
                            f"{node.get('status')} without an override_reason"
                        )
                for name in phase_gates:
                    if name not in GATE_NAMES[phase]:
                        warnings.append(
                            f"{label}.gates.{phase}.{name} is not a known gate; "
                            "remove it or migrate the ledger"
                        )
        tickets = workstream.get("tickets")
        if tickets is None:
            warnings.append(f"{label}.tickets missing; run migrate to add it")
        elif not isinstance(tickets, dict):
            errors.append(f"{label}.tickets must be a mapping")
        else:
            seen_ticket_ids: dict[str, object] = {}
            for ticket_id in tickets:
                normalized = str(ticket_id)
                if normalized in seen_ticket_ids:
                    errors.append(
                        f"{label}.tickets has two ids that normalize to "
                        f"{normalized!r} ({seen_ticket_ids[normalized]!r} and "
                        f"{ticket_id!r}); merge them"
                    )
                seen_ticket_ids[normalized] = ticket_id
            for ticket_id, ticket in tickets.items():
                tlabel = f"{label}.tickets.{ticket_id}"
                if not isinstance(ticket, dict):
                    errors.append(f"{tlabel} must be a mapping")
                    continue
                ticket_gates = ticket.get("gates")
                if not isinstance(ticket_gates, dict):
                    errors.append(f"{tlabel}.gates must be a mapping")
                    continue
                statuses = {
                    gate_name: str(
                        (
                            (ticket_gates.get(gate_name) or {}).get("status")
                            if isinstance(ticket_gates.get(gate_name), dict)
                            else None
                        )
                        or "open"
                    )
                    for gate_name in TICKET_GATES
                }
                for gate_name, node in ticket_gates.items():
                    if gate_name not in TICKET_GATES:
                        errors.append(
                            f"{tlabel}.gates.{gate_name} is not a ticket gate"
                        )
                        continue
                    if not isinstance(node, dict):
                        errors.append(f"{tlabel}.gates.{gate_name} must be a mapping")
                        continue
                    if node.get("status") not in GATE_STATUSES:
                        errors.append(
                            f"{tlabel}.gates.{gate_name}.status must be one of "
                            f"{', '.join(GATE_STATUSES)}"
                        )
                    if (
                        node.get("status") == "overridden"
                        and ticket_level_map.get(gate_name, "optional")
                        in ("required", "conditional")
                        and not str(node.get("override_reason") or "").strip()
                    ) or (
                        node.get("status") == "skipped"
                        and ticket_level_map.get(gate_name, "optional")
                        in ("required", "conditional")
                        and not str(node.get("override_reason") or "").strip()
                    ):
                        errors.append(
                            f"{tlabel}.gates.{gate_name} is "
                            f"{node.get('status')} without an override_reason"
                        )
                if statuses["done"] == "passed" and statuses["review"] != "passed":
                    errors.append(
                        f"{tlabel}.gates.done is passed before build.review "
                        "is passed"
                    )
                elif (
                    statuses["done"] == "overridden"
                    and statuses["review"] not in ("passed", "overridden")
                ):
                    errors.append(
                        f"{tlabel}.gates.done is overridden before build.review "
                        "is decided"
                    )
                if (
                    track != "audit"
                    and statuses["review"] in ("passed", "overridden")
                    and statuses["ticket"] not in ("passed", "overridden")
                ):
                    errors.append(
                        f"{tlabel}.gates.review is decided before build.ticket "
                        "is passed"
                    )
            if track == "audit":
                audit_ticket = tickets.get("audit")
                if not isinstance(audit_ticket, dict):
                    errors.append(
                        f"{label}.tickets.audit is required for an audit"
                    )
                else:
                    review = (audit_ticket.get("gates") or {}).get("review")
                    if not isinstance(review, dict) or review.get(
                        "status"
                    ) not in GATE_STATUSES:
                        errors.append(
                            f"{label}.tickets.audit.gates.review is required "
                            "for an audit"
                        )
        if workstream.get("status") == "done":
            left = []
            for phase in PHASES:
                entries = phase_gate_entries(
                    workstream,
                    phase,
                    track if track in TRACKS else "feature",
                    size if size in SIZES else "epic",
                    model if model in ("v6", "current", "unknown") else "unknown",
                )
                left.extend(entry["id"] for entry in phase_blocking(entries))
            if left:
                errors.append(
                    f"{label} is done with undecided gates: " + ", ".join(left)
                )
        if not isinstance(workstream.get("decisions"), list):
            errors.append(f"{label}.decisions must be a list")
        next_action = workstream.get("next")
        if next_action is not None and not isinstance(next_action, dict):
            warnings.append(f"{label}.next is not a mapping; summary will recompute")
    emit(
        {
            "ok": not errors,
            "ledger": str(path),
            "errors": errors,
            "warnings": warnings,
        },
        0 if not errors else 1,
    )


def workstream_briefs(workstreams: dict, model: str) -> list[dict]:
    briefs = []
    for workstream_id, workstream in workstreams.items():
        if not isinstance(workstream, dict):
            continue
        track = workstream.get("track", "feature")
        size = workstream.get("size", "epic")
        briefs.append(
            {
                "id": workstream_id,
                "name": workstream.get("name"),
                "track": track,
                "size": size,
                "status": workstream.get("status"),
                "current_phase": workstream.get("current_phase"),
                "next_action": computed_next(workstream, track, size, model),
            }
        )
    return briefs


def empty_ticket_summary() -> dict:
    return {
        "count": 0,
        "open": [],
        "blocked": [],
        "required_open": [],
        "conditional_open": [],
        "items": {},
    }


def cmd_summary(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    model = (data.get("bmad") or {}).get("model") or "unknown"
    workstreams = data.get("workstreams") or {}
    memlog = resolve_memlog(data, args, path)
    workstream_id = args.workstream or data.get("active_workstream")
    if not workstream_id:
        briefs = workstream_briefs(workstreams, model)
        last = briefs[-1] if briefs else None
        emit(
            {
                "ok": True,
                "ledger": str(path),
                "memlog": str(memlog),
                "project": data.get("project"),
                "model": model,
                "active_workstream": None,
                "workstream": None,
                # A closed workstream clears active_workstream; keep the last
                # recorded track/size/phase so the headless block stays full.
                "track": last.get("track") if last else None,
                "size": last.get("size") if last else None,
                "phases": [],
                "tickets": empty_ticket_summary(),
                "open_gates": [],
                "blocked_gates": [],
                "required_open": [],
                "conditional_open": [],
                "optional_open": [],
                "locked_phases": [],
                "optional_actions": [],
                "next_phase": None,
                "phase": last.get("current_phase") if last else None,
                "next_action": None,
                "cached_next_action": None,
                "next_action_stale": False,
                "workstreams": list(workstreams),
                "workstreams_detail": briefs,
                "decisions": [],
            }
        )
        return
    if workstream_id not in workstreams:
        fail(f"workstream not found: {workstream_id}")
    workstream = workstreams[workstream_id]
    track = workstream.get("track", "feature")
    size = workstream.get("size", "epic")

    phases: list[dict] = []
    open_gates: list[str] = []
    blocked_gates: list[str] = []
    required_open: list[str] = []
    conditional_open: list[str] = []
    optional_open: list[str] = []
    prior_complete = True
    for phase in PHASES:
        node = (workstream.get("phases") or {}).get(phase) or {}
        status = node.get("status", "pending")
        entries = phase_gate_entries(workstream, phase, track, size, model)
        gates_out = [
            {
                "id": entry["id"],
                "level": entry["level"],
                "status": entry["status"],
                "decided_at": entry["decided_at"],
                "override_reason": entry["override_reason"],
            }
            for entry in entries
            if entry["ticket"] is None
        ]
        blocking_entries = phase_blocking(entries)
        blocking = [entry["id"] for entry in blocking_entries]
        inactive = status in ("done", "skipped")
        inconsistent = inactive and bool(blocking_entries)
        blocking_ids = {entry["id"] for entry in blocking_entries}
        for entry in entries:
            # A skipped/done phase contributes only the gates that prove the
            # status is inconsistent. Its other open gates are not live work.
            if inactive and not inconsistent:
                continue
            if inactive and entry["id"] not in blocking_ids:
                continue
            if entry["status"] == "open":
                open_gates.append(entry["id"])
            elif entry["status"] == "blocked":
                blocked_gates.append(entry["id"])
            if entry["status"] in ("open", "blocked"):
                if entry["level"] == "required":
                    required_open.append(entry["id"])
                elif entry["level"] == "conditional":
                    conditional_open.append(entry["id"])
                elif entry["status"] == "open" and not inactive:
                    optional_open.append(entry["id"])
        has_tickets = bool(workstream.get("tickets") or {})
        active = status not in ("done", "skipped") or bool(blocking_entries)
        # A phase is complete only after every earlier phase is complete, so
        # close cannot look done before any work exists.
        complete = (
            prior_complete
            and status != "blocked"
            and not blocking_entries
            and (phase != "build" or has_tickets or status in ("done", "skipped"))
        )
        prior_complete = prior_complete and complete
        phases.append(
            {
                "phase": phase,
                "status": status,
                "gate": node.get("gate") or PHASE_DEFAULT_GATE[phase],
                "evidence": node.get("evidence") or [],
                "note": node.get("note") or "",
                "gates": gates_out,
                "blocking": blocking,
                "complete": complete,
                "open_gates": [
                    entry["id"] for entry in entries if entry["status"] == "open"
                ],
                "blocked_gates": [
                    entry["id"] for entry in entries if entry["status"] == "blocked"
                ],
                "required_open": [
                    entry["id"]
                    for entry in entries
                    if entry["status"] in ("open", "blocked")
                    and entry["level"] == "required"
                ],
                "conditional_open": [
                    entry["id"]
                    for entry in entries
                    if entry["status"] in ("open", "blocked")
                    and entry["level"] == "conditional"
                ],
                "optional_open": [
                    entry["id"]
                    for entry in entries
                    if entry["status"] == "open" and entry["level"] == "optional"
                ],
                "active": active,
            }
        )

    tickets = ticket_summary(workstream)
    locked_phases: list[dict] = []
    prior_blocking: list[str] = []
    for phase in phases:
        # A phase is locked by any earlier undecided gate, whether or not the
        # phase has open gates of its own.
        if phase["status"] == "pending" and prior_blocking:
            locked_phases.append(
                {"phase": phase["phase"], "missing_gate": prior_blocking[0]}
            )
        if phase["status"] not in ("done", "skipped") or phase["blocking"]:
            if phase["blocking"]:
                prior_blocking.extend(phase["blocking"])
            elif phase["phase"] == "build" and not tickets["count"]:
                # The only real blocker with no gate id is an unbuilt build
                # phase. Never synthesize `<phase>.status`, which no command
                # can set.
                prior_blocking.append("build.ticket")

    computed = computed_next(workstream, track, size, model)
    optional = optional_actions(workstream, track, size, model)
    cached = workstream.get("next")
    cached_action = cached.get("action") if isinstance(cached, dict) else None
    computed_action = computed.get("action") if computed else None
    stale = bool(cached_action and computed_action and cached_action != computed_action)
    next_action = computed or (cached if isinstance(cached, dict) else None)
    if workstream.get("status") in ("done", "paused"):
        next_action = None
    elif next_action is not None:
        next_action = dict(next_action)
        next_action["source"] = "cache" if computed is None else "computed"
        if getattr(args, "project_root", None):
            project_root = Path(
                expand_project_root(args.project_root, Path.cwd())
            ).resolve()
            installed, _ = read_skills(project_root)
            next_action["skill_installed"] = (
                next_action.get("skill") is None
                or next_action.get("skill") in installed
            )

    artifacts = {
        key: value
        for key, value in (workstream.get("artifacts") or {}).items()
        if value
    }
    next_phase = next_action.get("phase") if next_action else None
    if next_phase is None:
        for phase in phases:
            if phase["status"] not in ("done", "skipped") or phase["blocking"]:
                next_phase = phase["phase"]
                break
    display_phase = next_phase or workstream.get("current_phase")
    emit(
        {
            "ok": True,
            "ledger": str(path),
            "memlog": str(memlog),
            "project": data.get("project"),
            "model": model,
            "active_workstream": data.get("active_workstream"),
            "workstream": {
                "id": workstream_id,
                "name": workstream.get("name"),
                "track": track,
                "size": size,
                "status": workstream.get("status"),
                "current_phase": display_phase,
                "artifacts": artifacts,
            },
            "phases": phases,
            "tickets": tickets,
            "open_gates": open_gates,
            "blocked_gates": blocked_gates,
            "required_open": required_open,
            "conditional_open": conditional_open,
            "optional_open": optional_open,
            "locked_phases": locked_phases,
            "optional_actions": optional,
            "next_phase": next_phase,
            "phase": display_phase,
            "next_action": next_action,
            "cached_next_action": cached if isinstance(cached, dict) else None,
            "next_action_stale": stale,
            "workstreams": list(workstreams),
            "workstreams_detail": workstream_briefs(workstreams, model),
            "decisions": workstream.get("decisions") or [],
        }
    )


def _resolve_ticket_path(
    parts: list[str], ticket_map: dict | None
) -> tuple[str, list[str]] | None:
    """Match a tickets.* path to an existing ticket id, dots included."""
    if not parts or parts[0] != "tickets" or not isinstance(ticket_map, dict):
        return None
    whole = ".".join(parts[1:])
    if whole in ticket_map:
        return whole, []
    for cut in range(len(parts) - 1, 1, -1):
        candidate = ".".join(parts[1:cut])
        if candidate in ticket_map:
            return candidate, parts[cut:]
    return None


def _gate_node_target(path: str) -> tuple[str, str, str] | None:
    """Parse a whole gate node: gates.<phase>.<name> or tickets.<id>.gates.<name>."""
    parts = _parts(path)
    if len(parts) == 3 and parts[0] == "gates":
        return ("phase", parts[1], parts[2])
    if len(parts) >= 4 and parts[0] == "tickets" and parts[-2] == "gates":
        return ("ticket", ".".join(parts[1:-2]), parts[-1])
    return None


def _gate_status_target(path: str) -> tuple[str, str, str] | None:
    """Parse gates.<phase>.<name>.status or tickets.<id>.gates.<name>.status."""
    parts = _parts(path)
    if len(parts) == 4 and parts[0] == "gates" and parts[3] == "status":
        return ("phase", parts[1], parts[2])
    if (
        len(parts) >= 5
        and parts[0] == "tickets"
        and parts[-3] == "gates"
        and parts[-1] == "status"
    ):
        return ("ticket", ".".join(parts[1:-3]), parts[-2])
    return None


def _scope(
    args: argparse.Namespace, data: dict, path: str
) -> tuple[dict, str | None]:
    """Resolve a dotted path to the document or one workstream."""
    root_name = _first_root(path)
    workstreams = data.get("workstreams") or {}
    if getattr(args, "root", False):
        if root_name not in DOC_ROOTS:
            fail(
                "--root is only for document paths; omit it to target "
                "the workstream"
            )
        return data, None
    if args.workstream:
        if root_name == "workstreams":
            fail("use --path name with --workstream, not workstreams.<id>")
        if _is_doc_path(path):
            fail(
                "--workstream targets workstream fields; omit it for "
                "document paths"
            )
        if args.workstream not in workstreams:
            fail(f"workstream not found: {args.workstream}")
        return workstreams[args.workstream], args.workstream
    if _is_doc_path(path):
        return data, None
    active = data.get("active_workstream")
    if active and active in workstreams:
        return workstreams[active], active
    if root_name in WORKSTREAM_ROOTS:
        fail("no active workstream; pass --workstream or --root")
    fail(f"unknown path root {root_name!r}; pass --workstream or --root")


def _validate_path(path: str, ticket_map: dict | None = None) -> None:
    """Reject typos inside the known ledger shapes; allow custom roots."""
    parts = _parts(path)
    if not parts:
        fail("empty --path")
    root = parts[0]
    if root == "phases":
        if len(parts) < 2 or parts[1] not in PHASES:
            fail(f"unknown phase in path: {path}")
        if len(parts) == 2:
            return
        field = parts[2]
        if field == "gate":
            fail("phases.<phase>.gate is derived; use resize or migrate")
        if field not in (
            "status",
            "evidence",
            "note",
        ):
            fail(f"unknown phase field {field!r}")
        if len(parts) > 3:
            fail(f"path is too deep: {path}")
    elif root == "gates":
        if len(parts) < 3 or parts[1] not in PHASES:
            fail(f"unknown gate path: {path}")
        if parts[2] not in GATE_NAMES[parts[1]]:
            fail(
                f"unknown gate {parts[1]}.{parts[2]}; choose one of "
                + ", ".join(GATE_NAMES[parts[1]])
            )
        if len(parts) > 4 or (
            len(parts) == 4
            and parts[3] not in ("status", "decided_at", "override_reason")
        ):
            fail(f"unknown gate field in path: {path}")
    elif root == "tickets":
        if len(parts) < 2:
            fail(f"unknown ticket path: {path}")
        if len(parts) == 2:
            return
        resolved = _resolve_ticket_path(parts, ticket_map)
        if resolved is None:
            fail(
                "unknown ticket id; create it with the ticket command "
                f"first: set --path {path}"
            )
        ticket_id, rest = resolved
        if not rest:
            # A dotted id addressed as a whole node.
            return
        if rest[0] in ("title", "note"):
            if len(rest) > 1:
                fail(f"path is too deep: {path}")
            return
        if rest[0] != "gates":
            fail(
                f"unknown ticket field {rest[0]!r}; use title, note, or gates "
                f"on ticket {ticket_id}"
            )
        if len(rest) < 2 or rest[1] not in TICKET_GATES:
            fail(f"unknown ticket gate in path: {path}")
        if len(rest) > 3 or (
            len(rest) == 3
            and rest[2] not in ("status", "decided_at", "override_reason")
        ):
            fail(f"unknown ticket gate field in path: {path}")
    elif root == "artifacts":
        if len(parts) != 2 or parts[1] not in ARTIFACTS:
            fail(
                f"unknown artifact {parts[1] if len(parts) > 1 else ''!r}; "
                "choose one of " + ", ".join(ARTIFACTS)
            )
    elif root == "workstreams":
        # Route edits through the guarded workstream form: a direct
        # workstreams.* write would replace or edit a workstream wholesale
        # and bypass the enum, lifecycle, and single-active checks.
        fail(
            "edit a workstream with --workstream <id> --path <field>, "
            "not workstreams.*"
        )
    elif root == "bmad":
        if len(parts) == 1:
            return
        if parts[1] != "model" or len(parts) > 2:
            fail(f"unknown bmad field in path: {path}")
    elif root in ("name", "track", "size", "status", "started", "current_phase", "next"):
        if len(parts) != 1:
            fail(f"path is too deep: {path}")


def _validate_value(path: str, value, ticket_map: dict | None = None) -> None:
    target = _gate_status_target(path)
    if target:
        if value not in GATE_STATUSES:
            fail(
                f"unknown gate status {value!r}; choose one of "
                + ", ".join(GATE_STATUSES)
            )
        return
    gate_node = _gate_node_target(path)
    if gate_node:
        if not isinstance(value, dict):
            fail("a gate node must be a JSON object")
        status = value.get("status")
        if status not in GATE_STATUSES:
            fail(
                "a gate node needs a status; choose one of "
                + ", ".join(GATE_STATUSES)
            )
        if "level" in value:
            fail("gate levels are derived; use resize or migrate")
        return
    parts = _parts(path)
    if parts and parts[0] == "phases" and len(parts) == 2:
        if not isinstance(value, dict):
            fail("a phase node must be a JSON object")
        if "gate" in value:
            fail("phases.<phase>.gate is derived; use resize or migrate")
        # A replacement must be a complete phase node. Accepting a partial
        # node wrote a ledger that validate then rejected.
        if value.get("status") not in PHASE_STATUSES:
            fail(
                "a phase replacement needs a status; choose one of "
                + ", ".join(PHASE_STATUSES)
            )
        if not isinstance(value.get("evidence", []), list):
            fail("phases.<phase>.evidence must be a list")
        value.setdefault("evidence", [])
        value.setdefault("note", "")
        for extra in value:
            if extra not in ("status", "evidence", "note"):
                fail(f"unknown phase field {extra!r}")
    if (
        parts
        and parts[0] == "phases"
        and len(parts) >= 3
        and parts[2] == "status"
    ):
        if value not in PHASE_STATUSES:
            fail(
                f"unknown phase status {value!r}; choose one of "
                + ", ".join(PHASE_STATUSES)
            )
    elif parts and parts[0] == "phases" and len(parts) == 2:
        status = value.get("status")
        if status is not None and status not in PHASE_STATUSES:
            fail(
                f"unknown phase status {status!r}; choose one of "
                + ", ".join(PHASE_STATUSES)
            )
        evidence = value.get("evidence")
        if evidence is not None and not isinstance(evidence, list):
            fail("phases.<phase>.evidence must be a list")
        note = value.get("note")
        if note is not None and not isinstance(note, str):
            fail("phases.<phase>.note must be a string")
    elif parts and parts[0] == "tickets":
        resolved = _resolve_ticket_path(parts, ticket_map)
        is_node = len(parts) == 2 or (resolved is not None and not resolved[1])
        if is_node:
            if not isinstance(value, dict):
                fail("a ticket node must be a JSON object")
            gates = value.get("gates")
            if gates is not None:
                if not isinstance(gates, dict):
                    fail("tickets.<id>.gates must be a JSON object")
                for name, gate in gates.items():
                    if name not in TICKET_GATES:
                        fail(
                            f"unknown ticket gate {name!r}; choose one of "
                            + ", ".join(TICKET_GATES)
                        )
                    status = gate.get("status") if isinstance(gate, dict) else None
                    if status not in GATE_STATUSES:
                        fail(
                            f"ticket gate {name} needs a status; choose one of "
                            + ", ".join(GATE_STATUSES)
                        )
            title = value.get("title")
            if title is not None and not isinstance(title, str):
                fail("tickets.<id>.title must be a string")
            note = value.get("note")
            if note is not None and not isinstance(note, str):
                fail("tickets.<id>.note must be a string")
    elif parts and parts[0] == "bmad":
        if path == "bmad.model":
            if value not in ("v6", "current", "unknown"):
                fail("bmad.model must be one of v6, current, unknown")
            return
        if not isinstance(value, dict):
            fail("the bmad block must be a JSON object")
        model = value.get("model")
        if model not in ("v6", "current", "unknown"):
            fail("the bmad block needs a model: v6, current, or unknown")
        for key in (
            "memlog",
            "hub",
            "output_folder",
            "planning_artifacts",
            "implementation_artifacts",
            "test_artifacts",
        ):
            if key in value and value[key] is not None and not isinstance(
                value[key], str
            ):
                fail(f"bmad.{key} must be a string or null")
    elif parts and parts[0] == "artifacts":
        if value is not None and not isinstance(value, str):
            fail("an artifact pointer must be a string")
    elif path == "name":
        if not isinstance(value, str) or not value.strip():
            fail("name must be a non-empty string")
    elif path == "started":
        if not isinstance(value, str) or not value.strip():
            fail("started must be an ISO-8601 timestamp")
    elif path == "status":
        if value not in WS_STATUSES:
            fail(
                f"unknown workstream status {value!r}; choose one of "
                + ", ".join(WS_STATUSES)
            )
        if value == "done":
            fail("use the done command to close a workstream")
    elif path == "size":
        if value not in SIZES:
            fail(f"unknown size {value!r}; choose one of {', '.join(SIZES)}")
        fail("use the resize command to change size")
    elif path == "track":
        if value not in TRACKS:
            fail(f"unknown track {value!r}; choose one of {', '.join(TRACKS)}")
        fail("use the resize command to change track")
    elif path == "bmad.model":
        if value not in ("v6", "current", "unknown"):
            fail("bmad.model must be one of v6, current, unknown")


def _written_gate(
    path: str, value
) -> tuple[str, str, str, str | None] | None:
    """Read a gate status from a scalar write or a whole-node write."""
    target = _gate_status_target(path)
    if target:
        return (target[0], target[1], target[2], value)
    parts = _parts(path)
    if len(parts) == 3 and parts[0] == "gates" and isinstance(value, dict):
        return ("phase", parts[1], parts[2], value.get("status"))
    if (
        len(parts) >= 4
        and parts[0] == "tickets"
        and parts[-2] == "gates"
        and isinstance(value, dict)
    ):
        return (
            "ticket",
            ".".join(parts[1:-2]),
            parts[-1],
            value.get("status"),
        )
    return None


def _guard_ticket_order(workstream: dict, path: str, value) -> None:
    written = _written_gate(path, value)
    if not written:
        return
    kind, ticket_id, gate_name, status = written
    if kind != "ticket" or status not in ("passed", "overridden"):
        return
    value = status
    tickets = workstream.get("tickets")
    if not isinstance(tickets, dict):
        tickets = {}
    ticket = tickets.get(ticket_id)
    if not isinstance(ticket, dict):
        ticket = {}
    gates = ticket.get("gates")
    if not isinstance(gates, dict):
        gates = {}

    def status(name: str) -> str:
        node = gates.get(name)
        return str((node or {}).get("status") or "open") if isinstance(node, dict) else "open"

    if gate_name == "done":
        if status("review") not in ("passed", "overridden"):
            fail("build.done cannot be decided before build.review")
        if value == "passed" and status("review") != "passed":
            fail("build.done requires a passed build.review")
    if (
        gate_name == "review"
        and workstream.get("track") != "audit"
        and status("ticket") not in ("passed", "overridden")
    ):
        fail("build.review cannot be decided before build.ticket")


def _guard_ticket_node(
    root: dict, path: str, value, reason: str | None
) -> None:
    """Apply the gate guards to every gate inside a whole-ticket replacement."""
    parts = _parts(path)
    tickets = root.get("tickets")
    if not isinstance(tickets, dict):
        return
    resolved = _resolve_ticket_path(parts, tickets)
    if resolved is None or resolved[1]:
        return
    ticket_id = resolved[0]
    ticket = tickets.get(ticket_id)
    existing = (ticket.get("gates") if isinstance(ticket, dict) else None) or {}
    new_gates = value.get("gates") if isinstance(value, dict) else None
    if not isinstance(new_gates, dict):
        if existing:
            fail(
                "a whole-ticket replacement must include the existing gates map"
            )
        return
    for gate_name, old_node in existing.items():
        if gate_name in new_gates or not isinstance(old_node, dict):
            continue
        if old_node.get("status") in ("passed", "overridden", "skipped"):
            fail(
                f"cannot drop decided gate {ticket_id}.{gate_name} by replacing "
                "the ticket; reopen it with --reason first"
            )
    for gate_name, new_node in new_gates.items():
        if not isinstance(new_node, dict):
            continue
        old_node = existing.get(gate_name)
        synthetic = f"tickets.{ticket_id}.gates.{gate_name}"
        _guard_blocked_gate(root, synthetic, new_node)
        _guard_reopen(root, synthetic, new_node, reason)
        new_status = new_node.get("status")
        if new_status in ("passed", "overridden"):
            new_statuses = {}
            for name in TICKET_GATES:
                node = new_gates.get(name, existing.get(name))
                new_statuses[name] = (
                    str((node or {}).get("status") or "open")
                    if isinstance(node, dict)
                    else "open"
                )
            if gate_name == "done":
                if new_statuses["review"] not in ("passed", "overridden"):
                    fail("build.done cannot be decided before build.review")
                if new_status == "passed" and new_statuses["review"] != "passed":
                    fail("build.done requires a passed build.review")
            if (
                gate_name == "review"
                and str(root.get("track") or "") != "audit"
                and new_statuses["ticket"] not in ("passed", "overridden")
            ):
                fail("build.review cannot be decided before build.ticket")
        if (
            isinstance(old_node, dict)
            and old_node.get("status") in ("passed", "overridden", "skipped")
            and new_node.get("status") in ("passed", "overridden", "skipped")
            and old_node.get("override_reason")
            and not new_node.get("override_reason")
        ):
            fail(
                "cannot clear a decided gate's override_reason by replacing "
                f"{synthetic}; reopen it with --reason first"
            )


def _guard_reopen(root: dict, path: str, value, reason: str | None) -> None:
    """A decided gate may reopen, but only explicitly and never out of order."""
    written = _written_gate(path, value)
    if not written:
        return
    kind, reference, gate_name, status = written
    if kind == "phase":
        node = ((root.get("gates") or {}).get(reference) or {}).get(gate_name)
    else:
        ticket = (root.get("tickets") or {}).get(reference) or {}
        node = (ticket.get("gates") or {}).get(gate_name)
    current = (
        str(node.get("status") or "open") if isinstance(node, dict) else "open"
    )
    if current not in ("passed", "overridden", "skipped"):
        return
    if status == current:
        return
    # Every move out of a decided state is a reopen: open, blocked, skipped,
    # or a different decision. It needs an explicit reason either way.
    if not str(reason or "").strip():
        fail("reopening a decided gate needs --reason")
    if str(root.get("status") or "active") == "done":
        fail(
            "cannot reopen a gate on a done workstream; reopen the "
            "workstream first"
        )
    if status != "open":
        return
    if kind == "phase":
        phase = (root.get("phases") or {}).get(reference) or {}
        if isinstance(phase, dict) and phase.get("status") in ("done", "skipped"):
            fail(
                f"cannot reopen {reference}.{gate_name} while phase "
                f"{reference} is {phase.get('status')}; reopen the phase first"
            )
        return
    build = (root.get("phases") or {}).get("build") or {}
    if isinstance(build, dict) and build.get("status") in ("done", "skipped"):
        fail(
            f"cannot reopen build.{gate_name} while phase build is "
            f"{build.get('status')}; reopen the phase first"
        )
    order = list(TICKET_GATES)
    later = order[order.index(gate_name) + 1 :]
    ticket = (root.get("tickets") or {}).get(reference) or {}
    gates = ticket.get("gates") or {}
    decided = [
        name
        for name in later
        if isinstance(gates.get(name), dict)
        and gates[name].get("status") in ("passed", "overridden", "skipped")
    ]
    if decided:
        fail(
            f"cannot reopen build.{gate_name} while later gates are decided: "
            + ", ".join(decided)
        )


def _node_at(root: dict, path: str) -> dict | None:
    """The gate mapping that holds an override_reason/decided_at field."""
    parts = _parts(path)
    if not parts or parts[-1] not in ("override_reason", "decided_at"):
        return None
    if len(parts) == 4 and parts[0] == "gates":
        node = ((root.get("gates") or {}).get(parts[1]) or {}).get(parts[2])
        return node if isinstance(node, dict) else None
    if (
        len(parts) >= 5
        and parts[0] == "tickets"
        and parts[-3] == "gates"
    ):
        ticket = (root.get("tickets") or {}).get(".".join(parts[1:-3])) or {}
        node = (ticket.get("gates") or {}).get(parts[-2])
        return node if isinstance(node, dict) else None
    return None


def _guard_decided_metadata(root: dict, path: str, value) -> None:
    if value is not None:
        return
    parts = _parts(path)
    if not parts or parts[-1] not in ("override_reason", "decided_at"):
        return
    node = _node_at(root, path)
    if isinstance(node, dict) and node.get("status") in (
        "passed",
        "overridden",
        "skipped",
    ):
        fail(
            "cannot clear decided gate metadata; set the gate to open or "
            "blocked first"
        )


def _guard_blocked_gate(root: dict, path: str, value) -> None:
    written = _written_gate(path, value)
    if written is None or written[3] != "passed":
        return
    kind, reference, gate_name, _ = written
    if kind == "phase":
        node = ((root.get("gates") or {}).get(reference) or {}).get(gate_name)
    else:
        ticket = (root.get("tickets") or {}).get(reference) or {}
        node = (ticket.get("gates") or {}).get(gate_name)
    if isinstance(node, dict) and node.get("status") == "blocked":
        fail(
            "a blocked gate cannot be passed; resolve its evidence or "
            "override it with --reason"
        )


def _guard_active_phase(root: dict, path: str, value) -> None:
    parts = _parts(path)
    if not (parts and parts[0] == "phases" and parts[1] in PHASES):
        return
    if len(parts) >= 3 and parts[2] == "status":
        status = value
    elif len(parts) == 2 and isinstance(value, dict):
        status = value.get("status")
    else:
        return
    if status != "active":
        return
    phases = root.get("phases") or {}
    others = [
        phase
        for phase in PHASES
        if phase != parts[1]
        and isinstance(phases.get(phase), dict)
        and phases[phase].get("status") == "active"
    ]
    if others:
        fail(
            "only one phase may be active; finish or block "
            + ", ".join(others)
            + " first"
        )


def _guard_phase_status(
    workstream: dict, path: str, value, reason: str | None, model: str
) -> None:
    parts = _parts(path)
    if not (parts and parts[0] == "phases"):
        return
    if len(parts) >= 3 and parts[2] == "status":
        status = value
    elif len(parts) == 2 and isinstance(value, dict):
        status = value.get("status")
    else:
        return
    phase_node = (workstream.get("phases") or {}).get(parts[1]) or {}
    current = phase_node.get("status") if isinstance(phase_node, dict) else None
    if status in ("active", "pending") and current in ("done", "skipped"):
        if not str(reason or "").strip():
            fail(f"reopening phase {parts[1]} needs --reason")
        return
    if status not in ("done", "skipped"):
        return
    phase = parts[1]
    if (
        status == "done"
        and phase == "build"
        and workstream.get("track") != "audit"
        and not (workstream.get("tickets") or {})
    ):
        fail("build cannot be done with no ticket built")
    entries = phase_gate_entries(
        workstream,
        phase,
        workstream.get("track", "feature"),
        workstream.get("size", "epic"),
        model,
    )
    blocking = phase_blocking(entries)
    earlier: list[dict] = []
    for name in PHASES[: PHASES.index(phase)]:
        earlier_entries = phase_gate_entries(
            workstream,
            name,
            workstream.get("track", "feature"),
            workstream.get("size", "epic"),
            model,
        )
        earlier.extend(phase_blocking(earlier_entries))
    if blocking or earlier:
        fail(
            f"phase {phase} cannot be {status} while earlier or own gates "
            "are undecided: "
            + ", ".join(entry["id"] for entry in earlier + blocking)
        )
    if status == "skipped" and not str(reason or "").strip():
        fail(f"skipping phase {phase} needs --reason")


@plan_locked
def cmd_set(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    previous_model = (data.get("bmad") or {}).get("model")
    root, scope_id = _scope(args, data, args.path)
    ticket_map = root.get("tickets") if isinstance(root, dict) else None
    if not isinstance(ticket_map, dict):
        ticket_map = None
    _validate_path(args.path, ticket_map)
    parts = _parts(args.path)
    model = (data.get("bmad") or {}).get("model") or "unknown"
    if getattr(args, "delete", False):
        if args.value is not None or args.null:
            fail("--delete cannot be combined with --value or --null")
        if not str(args.reason or "").strip():
            fail("--delete needs --reason")
        ticket_id = ".".join(parts[1:]) if parts and parts[0] == "tickets" else ""
        keys = {str(key): key for key in (ticket_map or {})}
        if not (parts and parts[0] == "tickets" and ticket_id in keys):
            fail("--delete is only for an existing whole ticket node: tickets.<id>")
        if scope_id is None:
            fail("deleting a ticket needs a workstream; omit --root")
        if str(root.get("status") or "active") == "done":
            fail(
                "workstream is done; reopen it with set --path status "
                "--value active --reason <why>"
            )
        if str(root.get("status") or "") == "paused":
            fail(
                "workstream is paused; resume it with set --path status "
                "--value active --reason <why>"
            )
        if str(root.get("track") or "") == "audit" and ticket_id == "audit":
            fail("the synthetic audit ticket is required; it cannot be deleted")
        ticket = (ticket_map or {}).get(keys[ticket_id]) or {}
        decided = sorted(
            name
            for name, node in ((ticket.get("gates") or {}) or {}).items()
            if isinstance(node, dict)
            and node.get("status") in ("passed", "overridden", "skipped")
        )
        if decided:
            fail(
                f"cannot delete a ticket with decided gates ({', '.join(decided)}); "
                "reopen them with --reason first"
            )
        if (
            len(ticket_map or {}) <= 1
            and ((root.get("phases") or {}).get("build") or {}).get("status")
            in ("done", "skipped")
        ):
            fail(
                "cannot delete the only ticket of a done build phase; "
                "reopen phase build first"
            )
        parent, key = get_parent(root, args.path)
        real_key = keys[ticket_id]
        if real_key not in parent:
            fail(f"ticket not found: {ticket_id}")
        del parent[real_key]
        refresh_workstream(root, model)
        data["updated"] = now_iso()
        save_plan(path, data)
        append_memlog(
            resolve_memlog(data, args, path),
            "correction",
            f"{scope_id}: deleted {args.path} (reason: {args.reason})",
        )
        emit(
            {
                "ok": True,
                "ledger": str(path),
                "workstream": scope_id,
                "path": args.path,
                "deleted": True,
            }
        )
        return
    value = parse_value(args.value, args.null)
    _validate_value(args.path, value, ticket_map)
    if parts and parts[0] == "artifacts" and isinstance(value, str) and value:
        project_root = _default_project_root(path)
        if project_root is not None:
            candidate = Path(expand_project_root(value, project_root))
            if not candidate.is_absolute():
                candidate = project_root / candidate
            try:
                candidate.resolve().relative_to(project_root.resolve())
            except ValueError:
                fail("artifact pointers must stay inside the project root")
    if scope_id is not None and str(root.get("status") or "active") == "done":
        if not (
            args.path == "status"
            and value == "active"
            and str(args.reason or "").strip()
        ):
            if args.path == "status" and value == "active":
                fail("reopening a done workstream needs --reason")
            fail(
                "workstream is done; reopen it with set --path status "
                "--value active --reason <why>"
            )
    if (
        scope_id is not None
        and str(root.get("status") or "") == "paused"
        and args.path != "status"
    ):
        fail(
            "workstream is paused; resume it with set --path status "
            "--value active --reason <why>"
        )
    written = _written_gate(args.path, value)
    resolved_ticket = (
        _resolve_ticket_path(parts, ticket_map)
        if parts and parts[0] == "tickets"
        else None
    )
    if (
        parts
        and parts[0] == "tickets"
        and len(parts) == 2
        and resolved_ticket is None
    ):
        fail("create the ticket with the ticket command first")
    ticket_node = bool(parts) and parts[0] == "tickets" and (
        len(parts) == 2
        or (resolved_ticket is not None and not resolved_ticket[1])
    )
    ticket_gate_node = (
        resolved_ticket is not None
        and len(resolved_ticket[1]) == 2
        and resolved_ticket[1][0] == "gates"
    )
    replace_required = (
        args.path == "bmad"
        or ticket_node
        or ticket_gate_node
        or (parts and parts[0] in ("gates", "phases", "artifacts") and len(parts) == 1)
        or (parts and parts[0] == "phases" and len(parts) == 2)
        or (parts and parts[0] == "gates" and len(parts) == 3)
    )
    if replace_required and not args.replace:
        fail(f"replacing {args.path} needs --replace and --reason")
    if args.replace and not str(args.reason or "").strip():
        fail("--replace needs --reason")
    if args.path == "bmad":
        previous = data.get("bmad") or {}
        if previous.get("memlog") and not (
            isinstance(value, dict) and value.get("memlog")
        ):
            fail(
                "a bmad replacement must keep the recorded memlog in the "
                "block; dropping it would split the audit trail"
            )
        if isinstance(value, dict) and value.get("memlog"):
            recorded = Path(str(value["memlog"]))
            if not recorded.is_absolute():
                recorded = (_default_project_root(path) or path.parent) / recorded
            if recorded.resolve() == path.resolve():
                fail("the audit trail must differ from the ledger")
    if args.path == "decisions":
        fail("decisions are append-only; use append")
    if (
        parts
        and parts[0] == "phases"
        and len(parts) >= 3
        and parts[2] == "evidence"
    ):
        # --replace must not clear the list either: the audit trail then says
        # only "replaced" and the evidence a gate closed on is gone.
        fail("phase evidence is append-only; use append")
    if written is not None and scope_id is None:
        fail("gate writes need a workstream; omit --root")
    current_status = None
    if written is not None:
        kind, reference, gate_name, _ = written
        if kind == "phase":
            node = ((root.get("gates") or {}).get(reference) or {}).get(gate_name)
        else:
            ticket = (root.get("tickets") or {}).get(reference) or {}
            node = (ticket.get("gates") or {}).get(gate_name)
        if isinstance(node, dict):
            current_status = node.get("status")
    if (
        written is not None
        and written[3] not in ("overridden", "skipped", "open", "blocked")
        and args.reason
        and not args.replace
        and not (
            written[3] == "passed"
            and current_status in ("passed", "overridden", "skipped")
        )
    ):
        fail(
            "--reason applies to an override, a skip, or a reopen, "
            "not a passed gate"
        )
    if scope_id is not None:
        _guard_phase_status(root, args.path, value, args.reason, model)
        _guard_active_phase(root, args.path, value)
        _guard_decided_metadata(root, args.path, value)
        _guard_blocked_gate(root, args.path, value)
        _guard_reopen(root, args.path, value, args.reason)
        _guard_ticket_order(root, args.path, value)
        _guard_ticket_node(root, args.path, value, args.reason)
    parent, key = get_parent(root, args.path)
    node_write = written is not None and _gate_status_target(args.path) is None
    previous = parent.get(key)
    if isinstance(value, dict):
        if (
            parts
            and parts[0] == "phases"
            and len(parts) == 2
        ):
            # `gate` is derived and cannot travel in the replacement payload,
            # so carry the existing value forward instead of writing a node
            # that validate then rejects.
            if isinstance(previous, dict) and previous.get("gate"):
                value.setdefault("gate", previous["gate"])
        if (
            node_write
            and parts
            and parts[0] == "gates"
            and len(parts) == 3
            and isinstance(previous, dict)
        ):
            # `level` is derived and is rejected in a payload, so a node
            # replacement must inherit it. A decided node also keeps its
            # decision metadata unless the write reopens it.
            if previous.get("level"):
                value.setdefault("level", previous["level"])
            if (
                value.get("status") == previous.get("status")
                and previous.get("decided_at")
            ):
                value.setdefault("decided_at", previous["decided_at"])
            if (
                previous.get("override_reason")
                and value.get("status") in ("passed", "overridden", "skipped")
                and not value.get("override_reason")
            ):
                value.setdefault("override_reason", previous["override_reason"])
    parent[key] = value
    if written is not None and scope_id is not None:
        kind, reference, gate_name, status = written
        track = root.get("track", "feature")
        size = root.get("size", "epic")
        if kind == "phase":
            level = resolve_gate_levels(track, size, model).get(
                f"{reference}.{gate_name}", "optional"
            )
        else:
            level = ticket_levels(track, size).get(gate_name, "optional")
        needs_reason = status in ("overridden", "skipped") and level in (
            "required",
            "conditional",
        )
        stored = value if node_write else parent
        if needs_reason:
            if node_write and str(stored.get("override_reason") or "").strip():
                # A node replacement carries the decision's original reason;
                # the --reason on the command explains the replacement.
                reason = str(stored["override_reason"]).strip()
            else:
                reason = str(
                    args.reason or stored.get("override_reason") or ""
                ).strip()
            if not reason:
                fail(
                    f"{kind} gate {reference}.{gate_name} is {level}; "
                    f"a {status} needs --reason"
                )
            stored["override_reason"] = reason
        elif node_write:
            # A --reason on a node replacement belongs to --replace, not to
            # the gate. Keep a reason already present on the new node.
            stored.setdefault("override_reason", None)
        elif args.reason and status not in ("open", "blocked"):
            stored["override_reason"] = args.reason
        else:
            # An open or blocked gate has no decision, so it carries no
            # override reason. A reopen reason lives in the audit trail.
            stored["override_reason"] = None
        if status is not None:
            stored["decided_at"] = (
                None if status in ("open", "blocked") else now_iso()
            )
    if (
        scope_id is not None
        and parts
        and parts[0] == "phases"
        and len(parts) >= 3
        and parts[2] == "status"
        and value == "skipped"
        and str(args.reason or "").strip()
    ):
        root.setdefault("phases", {}).setdefault(parts[1], {})["note"] = args.reason
    if args.path == "active_workstream":
        workstreams = data.get("workstreams") or {}
        if value is None:
            still_active = [
                workstream_id
                for workstream_id, workstream in workstreams.items()
                if isinstance(workstream, dict)
                and workstream.get("status") == "active"
            ]
            if still_active:
                fail(
                    "pause the active workstream before clearing "
                    "active_workstream: " + ", ".join(still_active)
                )
            data["active_workstream"] = None
        else:
            if value not in workstreams:
                fail(f"workstream not found: {value}")
            target = workstreams[value]
            if isinstance(target, dict) and target.get("status") == "done":
                if not str(args.reason or "").strip():
                    fail("reopening a done workstream needs --reason")
            for workstream_id, workstream in workstreams.items():
                if not isinstance(workstream, dict):
                    continue
                if workstream_id == value:
                    workstream["status"] = "active"
                    refresh_workstream(workstream, model)
                elif workstream.get("status") == "active":
                    workstream["status"] = "paused"
                    refresh_workstream(workstream, model)
    if args.path == "status" and scope_id is not None:
        if value == "active":
            for other_id, other in (data.get("workstreams") or {}).items():
                if other_id == scope_id or not isinstance(other, dict):
                    continue
                if other.get("status") == "active":
                    other["status"] = "paused"
                    refresh_workstream(other, model)
            data["active_workstream"] = scope_id
        elif data.get("active_workstream") == scope_id:
            data["active_workstream"] = None
    if args.path == "bmad.model":
        current_model = previous_model or "unknown"
        if (
            value == "unknown"
            and current_model in ("v6", "current")
            and not str(args.reason or "").strip()
        ):
            fail(
                "refusing to downgrade the confirmed BMAD model to unknown "
                "without --reason"
            )
        reopened: list[str] = []
        for workstream_id, workstream in (data.get("workstreams") or {}).items():
            if not isinstance(workstream, dict):
                continue
            for entry in apply_levels(workstream, value):
                if entry.startswith("phases.") and entry.endswith(
                    ".status->pending"
                ):
                    reopened.append(f"{workstream_id}.{entry}")
            refresh_workstream(workstream, value)
        if reopened and not str(args.reason or "").strip():
            fail(
                "changing the model reopens "
                + ", ".join(reopened)
                + "; pass --reason to record why"
            )
    elif scope_id is not None and args.path != "next":
        refresh_workstream(root, model)
    data["updated"] = now_iso()
    save_plan(path, data)
    memlog_path = resolve_memlog(data, args, path)
    if written is not None:
        append_memlog(
            memlog_path,
            "gate",
            f"{scope_id or 'root'} {args.path}={value}"
            + (f" (reason: {args.reason})" if args.reason else ""),
        )
    elif parts and parts[0] == "phases" and parts[-1] == "status":
        append_memlog(
            memlog_path,
            "event",
            f"{scope_id or 'root'} {args.path}={value}"
            + (f" (reason: {args.reason})" if args.reason else ""),
        )
    elif args.path == "bmad.model":
        line = f"BMAD model set to {value}"
        if reopened:
            line += " (reopened: " + ", ".join(reopened) + ")"
        if str(args.reason or "").strip():
            line += f" (reason: {args.reason})"
        append_memlog(memlog_path, "event", line)
    elif args.path == "status" and scope_id is not None:
        append_memlog(
            memlog_path,
            "event",
            f"{scope_id} status={value}"
            + (f" (reason: {args.reason})" if args.reason else ""),
        )
    elif args.path == "active_workstream":
        append_memlog(
            memlog_path,
            "event",
            f"active workstream set to {value}"
            + (f" (reason: {args.reason})" if args.reason else ""),
        )
    elif args.replace:
        append_memlog(
            memlog_path,
            "correction",
            f"{scope_id or 'root'}: replaced {args.path} "
            f"(reason: {args.reason})",
        )
    else:
        append_memlog(
            memlog_path,
            "event",
            f"{scope_id or 'root'} {args.path} updated",
        )
    emit(
        {
            "ok": True,
            "ledger": str(path),
            "workstream": scope_id,
            "path": args.path,
            "value": value,
        }
    )


@plan_locked
def cmd_append(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    root, scope_id = _scope(args, data, args.path)
    ticket_map = root.get("tickets") if isinstance(root, dict) else None
    _validate_path(args.path, ticket_map if isinstance(ticket_map, dict) else None)
    parts = _parts(args.path)
    if parts and parts[0] == "artifacts":
        fail("artifact pointers take set, not append")
    if scope_id is not None:
        status = str(root.get("status") or "active")
        if status == "done":
            fail("workstream is done; reopen it before appending")
        if status == "paused":
            fail("workstream is paused; resume it before appending")
    parent, key = get_parent(root, args.path)
    node = parent.get(key)
    if node is None:
        node = []
        parent[key] = node
    if not isinstance(node, list):
        fail(f"path is not a list: {args.path}")
    value = parse_value(args.value, args.null)
    if args.path.endswith(".evidence") and (
        value is None or (isinstance(value, str) and not value.strip())
    ):
        fail("evidence entries must be non-empty paths")
    if args.path == "decisions":
        if not isinstance(value, dict):
            fail("a decision must be a JSON object")
        if not str(value.get("decision") or "").strip():
            fail("a decision needs a 'decision' field")
        value.setdefault("at", now_iso())
        value.setdefault("reason", "")
    node.append(value)
    if scope_id is not None and args.path != "next":
        refresh_workstream(root, (data.get("bmad") or {}).get("model") or "unknown")
    data["updated"] = now_iso()
    save_plan(path, data)
    append_memlog(
        resolve_memlog(data, args, path),
        "event",
        f"{scope_id or 'root'}: appended {args.path}",
    )
    emit(
        {
            "ok": True,
            "ledger": str(path),
            "workstream": scope_id,
            "path": args.path,
            "length": len(node),
        }
    )


@plan_locked
def cmd_ticket(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    workstream_id, workstream = workstream_root(data, args.workstream)
    if str(workstream.get("status") or "active") == "done":
        fail("workstream is done; reopen it before changing ticket gates")
    if str(workstream.get("status") or "") == "paused":
        fail("workstream is paused; resume it before changing ticket gates")
    if ((workstream.get("phases") or {}).get("build") or {}).get("status") in (
        "done",
        "skipped",
    ):
        fail("phase build is done; reopen the phase first before changing ticket gates")
    if args.gate not in TICKET_GATES:
        fail(f"unknown ticket gate {args.gate!r}; choose one of {', '.join(TICKET_GATES)}")
    if args.status not in GATE_STATUSES:
        fail(f"unknown status {args.status!r}; choose one of {', '.join(GATE_STATUSES)}")
    tickets = workstream.get("tickets")
    if tickets is None:
        tickets = {}
        workstream["tickets"] = tickets
    if not isinstance(tickets, dict):
        fail("workstream.tickets must be a mapping")
    ticket = tickets.get(args.id)
    if ticket is None:
        ticket = {"title": args.title or "", "gates": {}}
        tickets[args.id] = ticket
    if not isinstance(ticket, dict):
        fail(f"ticket {args.id!r} must be a mapping")
    if args.title:
        ticket["title"] = args.title
    gates = ticket.get("gates")
    if gates is None:
        gates = {}
        ticket["gates"] = gates
    if not isinstance(gates, dict):
        fail(f"ticket {args.id!r}.gates must be a mapping")
    node = gates.get(args.gate)
    if node is None:
        node = {"status": "open", "decided_at": None, "override_reason": None}
        gates[args.gate] = node
    if not isinstance(node, dict):
        fail(f"ticket {args.id!r}.gates.{args.gate} must be a mapping")
    level_map = ticket_levels(
        workstream.get("track", "feature"), workstream.get("size", "epic")
    )
    statuses = {
        gate_name: (
            str((gates.get(gate_name) or {}).get("status") or "open")
            if isinstance(gates.get(gate_name), dict)
            else "open"
        )
        for gate_name in TICKET_GATES
    }
    level = level_map.get(args.gate, "optional")
    current = str(node.get("status") or "open")
    if (
        args.status not in ("overridden", "skipped", "open", "blocked")
        and args.reason
        and not (args.status == "passed" and current in ("passed", "overridden", "skipped"))
    ):
        fail(
            "--reason applies to an override, a skip, or a reopen, "
            "not a passed gate"
        )
    needs_reason = args.status in ("overridden", "skipped") and level in (
        "required",
        "conditional",
    )
    if needs_reason:
        reason = str(args.reason or node.get("override_reason") or "").strip()
        if not reason:
            fail(
                f"ticket gate {args.gate} is {level}; "
                f"a {args.status} needs --reason"
            )
    if args.status in ("passed", "overridden"):
        if args.gate == "done" and statuses["review"] not in ("passed", "overridden"):
            fail("build.done cannot be decided before build.review")
        if (
            args.status == "passed"
            and args.gate == "done"
            and statuses["review"] != "passed"
        ):
            fail(
                "build.done requires a passed build.review; "
                "an overridden review is not enough"
            )
        if (
            args.gate == "review"
            and workstream.get("track") != "audit"
            and statuses["ticket"] not in ("passed", "overridden")
        ):
            fail("build.review cannot be decided before build.ticket")
    if args.status == "passed" and str(node.get("status") or "open") == "blocked":
        fail(
            "a blocked gate cannot be passed; resolve its evidence or "
            "override it with --reason"
        )
    _guard_reopen(
        workstream,
        f"tickets.{args.id}.gates.{args.gate}.status",
        args.status,
        args.reason,
    )
    node["status"] = args.status
    node["decided_at"] = (
        None if args.status in ("open", "blocked") else now_iso()
    )
    if args.status in ("open", "blocked"):
        node["override_reason"] = None
    elif args.reason:
        node["override_reason"] = args.reason
    elif args.status != "overridden":
        node["override_reason"] = None
    refresh_workstream(
        workstream, (data.get("bmad") or {}).get("model") or "unknown"
    )
    data["updated"] = now_iso()
    save_plan(path, data)
    append_memlog(
        resolve_memlog(data, args, path),
        "gate",
        f"{workstream_id} ticket {args.id} {args.gate}={args.status}"
        + (f" (reason: {args.reason})" if args.reason else ""),
    )
    emit(
        {
            "ok": True,
            "ledger": str(path),
            "workstream": workstream_id,
            "ticket": args.id,
            "gate": args.gate,
            "status": args.status,
            "next_action": workstream.get("next"),
        }
    )


def ux_pair_ready(
    workstream: dict, project_root: Path, planning: Path | None = None
) -> bool:
    """True when DESIGN.md and EXPERIENCE.md are discoverable for plan.ux.

    The recorded `artifacts.ux` pointer wins over the planning-artifacts glob,
    so a ledger that already points at the pair does not need the files copied
    into the default folder.
    """
    pointer = (workstream.get("artifacts") or {}).get("ux")
    if pointer:
        candidate = Path(str(pointer))
        if not candidate.is_absolute():
            candidate = project_root / candidate
        folder = candidate if candidate.is_dir() else candidate.parent
        names = {
            item.name for item in folder.glob("*") if item.is_file()
        }
        if {"DESIGN.md", "EXPERIENCE.md"} <= names:
            return True
    planning = planning or Path(
        resolve_paths(project_root)["planning_artifacts"]
    )
    return bool(
        list(planning.glob("**/DESIGN.md"))
        and list(planning.glob("**/EXPERIENCE.md"))
    )


@plan_locked
def cmd_done(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    workstream_id, workstream = workstream_root(data, args.workstream)
    if workstream.get("status") == "paused":
        fail("workstream is paused; resume it before closing")
    model = (data.get("bmad") or {}).get("model") or "unknown"
    track = workstream.get("track", "feature")
    size = workstream.get("size", "epic")
    blocking: list[str] = []
    tickets = workstream.get("tickets")
    if not isinstance(tickets, dict):
        tickets = {}
    for phase in PHASES:
        node = (workstream.get("phases") or {}).get(phase) or {}
        entries = phase_gate_entries(workstream, phase, track, size, model)
        phase_block = phase_blocking(entries)
        if node.get("status") == "blocked":
            blocking.append(f"{phase} is blocked")
        # Check build before the done/skipped short-circuit: a skipped build
        # phase with no ticket must not close the workstream.
        if phase == "build" and not tickets and track != "audit":
            blocking.append("build.ticket (no ticket built)")
        if node.get("status") in ("done", "skipped") and not phase_block:
            continue
        for entry in phase_block:
            if entry["status"] == "skipped" and not entry["override_reason"]:
                blocking.append(f"{entry['id']} (skipped without a reason)")
            else:
                blocking.append(entry["id"])
    for ticket_id, ticket in tickets.items():
        if not isinstance(ticket, dict):
            continue
        ticket_gates = ticket.get("gates")
        if not isinstance(ticket_gates, dict):
            continue
        statuses = {
            name: (
                str((ticket_gates.get(name) or {}).get("status") or "open")
                if isinstance(ticket_gates.get(name), dict)
                else "open"
            )
            for name in TICKET_GATES
        }
        if statuses["done"] == "passed" and statuses["review"] != "passed":
            blocking.append(f"build.{ticket_id}.done (review not passed)")
        elif (
            statuses["done"] == "overridden"
            and statuses["review"] not in ("passed", "overridden")
        ):
            blocking.append(f"build.{ticket_id}.done (review not decided)")
        if (
            track != "audit"
            and statuses["review"] in ("passed", "overridden")
            and statuses["ticket"] not in ("passed", "overridden")
        ):
            blocking.append(f"build.{ticket_id}.review (ticket not passed)")
    if blocking:
        fail(
            "cannot mark the workstream done; blocking gates: "
            + ", ".join(blocking)
        )

    project_root = (
        Path(expand_project_root(args.project_root, Path.cwd())).resolve()
        if getattr(args, "project_root", None)
        else _default_project_root(path)
    )
    if project_root is not None and not project_root.is_dir():
        fail(f"project root not found: {project_root}")
    artifacts = workstream.get("artifacts") or {}
    missing_evidence: list[str] = []
    if project_root is not None:
        for key, pointer in artifacts.items():
            if not pointer:
                continue
            candidate = Path(str(pointer))
            if not candidate.is_absolute():
                candidate = project_root / candidate
            try:
                candidate.resolve().relative_to(project_root.resolve())
            except ValueError:
                missing_evidence.append(
                    f"{key}={pointer} (outside project root)"
                )
                continue
            if not candidate.is_file() or candidate.stat().st_size == 0:
                missing_evidence.append(f"{key}={pointer}")
        for phase in PHASES:
            node = (workstream.get("phases") or {}).get(phase) or {}
            for value in node.get("evidence") or []:
                candidate = Path(str(value))
                if not candidate.is_absolute():
                    candidate = project_root / candidate
                try:
                    candidate.resolve().relative_to(project_root.resolve())
                except ValueError:
                    missing_evidence.append(
                        f"{phase}.evidence={value} (outside project root)"
                    )
                    continue
                if not candidate.is_file() or candidate.stat().st_size == 0:
                    missing_evidence.append(f"{phase}.evidence={value}")
        # A decided required/conditional gate must have the artifact it
        # claims. Without this, every gate can be marked passed and the
        # workstream closes with no evidence at all.
        levels = resolve_gate_levels(track, size, model)
        planning = Path(resolve_paths(project_root)["planning_artifacts"])
        for phase in PHASES:
            phase_gates = (workstream.get("gates") or {}).get(phase) or {}
            for name in GATE_NAMES[phase]:
                gate_id = f"{phase}.{name}"
                gate_node = phase_gates.get(name) or {}
                if gate_node.get("status") not in ("passed", "overridden"):
                    continue
                if levels.get(gate_id) not in ("required", "conditional"):
                    continue
                keys = [
                    key
                    for key, gates in ARTIFACT_GATES.items()
                    if gate_id in gates
                ]
                # The UX gate needs both halves; phase evidence must not
                # short-circuit that rule.
                if gate_id == "plan.ux":
                    if not ux_pair_ready(workstream, project_root, planning):
                        missing_evidence.append(
                            "plan.ux (needs DESIGN.md and EXPERIENCE.md)"
                        )
                    continue
                if not keys:
                    continue
                if not any(artifacts.get(key) for key in keys):
                    missing_evidence.append(f"{gate_id} (no artifact)")
    elif any(artifacts.values()):
        fail(
            "pass --project-root to validate artifact evidence for a "
            "custom ledger path"
        )
    if missing_evidence and not getattr(args, "accept_missing_evidence", False):
        fail(
            "cannot mark the workstream done; missing evidence: "
            + ", ".join(missing_evidence)
        )
    if missing_evidence and not str(args.reason or "").strip():
        fail("--accept-missing-evidence needs --reason")

    ledger_tickets = {str(ticket) for ticket in tickets}
    if track == "audit":
        # The synthetic audit ticket is not a BMAD artifact, so it must never
        # count as overlay drift. reconcile already exempts it.
        ledger_tickets.discard("audit")
    artifact_tickets = (
        artifact_ticket_ids(project_root, resolve_paths(project_root))
        if project_root is not None
        else None
    )
    accept_missing_tickets = bool(
        getattr(args, "accept_missing_tickets", False)
    )
    if ledger_tickets and artifact_tickets is None:
        # No readable ticket artifact means the overlay cannot be checked.
        # Treat that as a gap, not as a silent pass.
        if not accept_missing_tickets:
            hint = (
                "pass --project-root to verify ledger tickets"
                if project_root is None
                else "pass --accept-missing-tickets --reason to accept the gap"
            )
            fail(
                "cannot mark the workstream done; no readable ticket artifact "
                "(tickets.toml or sprint-status.yaml) to verify ledger tickets: "
                + ", ".join(sorted(ledger_tickets))
                + "; "
                + hint
            )
        if not str(args.reason or "").strip():
            fail("--accept-missing-tickets needs --reason")
    stale_tickets = (
        sorted(ledger_tickets - artifact_tickets)
        if artifact_tickets is not None
        else []
    )
    if stale_tickets and not accept_missing_tickets:
        fail(
            "cannot mark the workstream done; ledger tickets not found in "
            "BMAD artifacts: " + ", ".join(stale_tickets)
        )
    if stale_tickets and not str(args.reason or "").strip():
        fail("--accept-missing-tickets needs --reason")
    stamp = now_iso()
    workstream["status"] = "done"
    workstream["current_phase"] = "close"
    workstream["next"] = None
    workstream["updated"] = stamp
    close = (workstream.get("phases") or {}).get("close")
    if isinstance(close, dict) and close.get("status") != "skipped":
        close["status"] = "done"
    if data.get("active_workstream") == workstream_id:
        data["active_workstream"] = None
    data["updated"] = stamp
    save_plan(path, data)
    memlog_path = resolve_memlog(data, args, path)
    close_note = f"workstream {workstream_id} marked done"
    close_notes: list[str] = []
    overridden = [
        f"{phase}.{name}"
        for phase, gates in (workstream.get("gates") or {}).items()
        if isinstance(gates, dict)
        for name, node in gates.items()
        if isinstance(node, dict)
        and (
            node.get("status") == "overridden"
            # A reasoned skip of a required/conditional gate is an override
            # too; an optional skip stores no reason and stays out.
            or (
                node.get("status") == "skipped"
                and node.get("override_reason")
            )
        )
    ]
    for ticket_id, ticket in tickets.items():
        if not isinstance(ticket, dict):
            continue
        for name, node in (ticket.get("gates") or {}).items():
            if isinstance(node, dict) and (
                node.get("status") == "overridden"
                or (
                    node.get("status") == "skipped"
                    and node.get("override_reason")
                )
            ):
                overridden.append(f"build.{ticket_id}.{name}")
    if overridden:
        # gate-matrix requires an override to be visible in the close summary,
        # not only in the gate line where it happened.
        close_notes.append("overrides: " + ", ".join(sorted(overridden)))
    if missing_evidence and getattr(args, "accept_missing_evidence", False):
        close_notes.append(
            "accepted missing evidence: " + ", ".join(missing_evidence)
        )
    if accept_missing_tickets and ledger_tickets and artifact_tickets is None:
        close_notes.append(
            "accepted missing ticket artifact for: "
            + ", ".join(sorted(ledger_tickets))
        )
    elif accept_missing_tickets and stale_tickets:
        close_notes.append(
            "accepted tickets absent from BMAD artifacts: "
            + ", ".join(stale_tickets)
        )
    if str(args.reason or "").strip():
        close_notes.append(f"reason: {args.reason}")
    if close_notes:
        close_note += " (" + "; ".join(close_notes) + ")"
    memlog = append_memlog(memlog_path, "event", close_note)
    emit(
        {
            "ok": True,
            "ledger": str(path),
            "workstream": workstream_id,
            "status": "done",
            "memlog": str(memlog),
        }
    )


@plan_locked
def cmd_migrate(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    model = (data.get("bmad") or {}).get("model") or "unknown"
    workstreams = data.get("workstreams") or {}
    changed: list[str] = []
    for workstream_id, workstream in workstreams.items():
        if not isinstance(workstream, dict):
            continue
        track = workstream.get("track", "feature")
        size = workstream.get("size", "epic")
        levels = resolve_gate_levels(track, size, model)
        phase_levels = resolve_phase_levels(track, size, model)
        phases = workstream.get("phases")
        if not isinstance(phases, dict):
            phases = {}
            workstream["phases"] = phases
            changed.append(f"{workstream_id}.phases")
        for phase in PHASES:
            node = phases.get(phase)
            if not isinstance(node, dict):
                node = {
                    "status": "pending",
                    "gate": phase_levels[phase],
                    "evidence": [],
                    "note": "",
                }
                phases[phase] = node
                changed.append(f"{workstream_id}.phases.{phase}")
            elif node.get("gate") != phase_levels[phase]:
                node["gate"] = phase_levels[phase]
                changed.append(f"{workstream_id}.phases.{phase}.gate")
        gates = workstream.get("gates")
        if not isinstance(gates, dict):
            gates = {}
            workstream["gates"] = gates
            changed.append(f"{workstream_id}.gates")
        for phase in PHASES:
            phase_gates = gates.get(phase)
            if not isinstance(phase_gates, dict):
                phase_gates = {}
                gates[phase] = phase_gates
                changed.append(f"{workstream_id}.gates.{phase}")
            for name in GATE_NAMES[phase]:
                node = phase_gates.get(name)
                resolved = levels.get(f"{phase}.{name}", "optional")
                if not isinstance(node, dict):
                    # migrate is the repair path: create a gate a newer schema
                    # added instead of leaving the ledger permanently invalid.
                    phase_gates[name] = {
                        "status": "open",
                        "level": resolved,
                        "decided_at": None,
                        "override_reason": None,
                    }
                    changed.append(f"{workstream_id}.gates.{phase}.{name}")
                elif node.get("level") != resolved:
                    node["level"] = resolved
                    changed.append(f"{workstream_id}.gates.{phase}.{name}.level")
        for phase in PHASES:
            node = phases.get(phase)
            if not isinstance(node, dict):
                continue
            if node.get("status") not in ("done", "skipped"):
                continue
            entries = phase_gate_entries(workstream, phase, track, size, model)
            if phase_blocking(entries):
                # Materializing a gate can invalidate a cached phase status.
                # Reopen it instead of saving a ledger validate still rejects.
                node["status"] = "pending"
                changed.append(
                    f"{workstream_id}.phases.{phase}.status->pending"
                )
        if not isinstance(workstream.get("tickets"), dict):
            workstream["tickets"] = {}
            changed.append(f"{workstream_id}.tickets")
        if track == "audit" and not workstream.get("tickets"):
            workstream["tickets"]["audit"] = {
                "title": "Audit",
                "gates": {
                    "ticket": {
                        "status": "skipped",
                        "decided_at": None,
                        "override_reason": None,
                    },
                    "tests": {
                        "status": "skipped",
                        "decided_at": None,
                        "override_reason": None,
                    },
                    "review": {
                        "status": "open",
                        "decided_at": None,
                        "override_reason": None,
                    },
                    "done": {
                        "status": "skipped",
                        "decided_at": None,
                        "override_reason": None,
                    },
                },
            }
            changed.append(f"{workstream_id}.tickets.audit")
        refresh_workstream(workstream, model)
    data["updated"] = now_iso()
    save_plan(path, data)
    if changed:
        append_memlog(
            resolve_memlog(data, args, path),
            "correction",
            "migrate applied: " + "; ".join(changed),
        )
    emit({"ok": True, "ledger": str(path), "changed": changed})


def _infer_project_root(ledger: Path) -> Path:
    # Default layout: <project>/_bmad-output/sdlc/plan.yaml
    root = _default_project_root(ledger)
    if root is not None:
        return root
    fail(
        "cannot infer the project root for a custom ledger path; "
        "pass --project-root"
    )
    raise AssertionError("unreachable")


def discover_matches(
    key: str, project_root: Path, paths: dict[str, str]
) -> list[Path]:
    """Every artifact path matching a key, sorted and de-duplicated."""
    planning = Path(paths["planning_artifacts"])
    implementation = Path(paths["implementation_artifacts"])
    tests = Path(paths["test_artifacts"])
    if key == "test_framework":
        matches: list[Path] = []
        patterns = (
            "playwright.config.*",
            "cypress.config.*",
            "vitest.config.*",
            "jest.config.*",
        )
        for dirpath, dirnames, filenames in os.walk(project_root):
            dirnames[:] = [
                name for name in dirnames if name not in INVENTORY_SKIP
            ]
            for name in filenames:
                if any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
                    matches.append(Path(dirpath) / name)
        return sorted(set(matches))
    searches: dict[str, list[tuple[Path, str]]] = {
        "spec": [(planning, "**/SPEC.md"), (planning, "**/spec*.md")],
        "prd": [(planning, "**/prd*.md")],
        "ux": [
            (planning, "**/DESIGN.md"),
            (planning, "**/EXPERIENCE.md"),
            (planning, "**/ux-*.md"),
        ],
        "architecture": [(planning, "**/architecture*.md")],
        "stories": [(planning, "**/epic*.md"), (planning, "**/stories*.md")],
        "tickets": [
            (planning, "**/tickets.toml"),
            (implementation, "**/tickets.toml"),
            (project_root, "tickets.toml"),
        ],
        "sprint_plan": [(implementation, "**/sprint-status.yaml")],
        "test_design": [
            (tests, "**/test-design*.md"),
            (tests, "**/test_plan*.md"),
        ],
        "test_framework": [],
        "ci": [
            (project_root, ".github/workflows/*.yml"),
            (project_root, ".github/workflows/*.yaml"),
            (project_root, ".gitlab-ci.yml"),
            (project_root, "azure-pipelines.yml"),
        ],
        "trace": [(tests, "**/*trace*.md")],
    }
    matches = []
    for root, pattern in searches.get(key, []):
        if not root.is_dir():
            continue
        for candidate in sorted(root.glob(pattern)):
            if candidate.is_file():
                matches.append(candidate)
    return sorted(set(matches))


def discover_artifact(
    key: str, project_root: Path, paths: dict[str, str]
) -> Path | None:
    """One unambiguous artifact, or None when absent or ambiguous.

    Several matching files under one key (for example two SPEC.md files) must
    not bind an arbitrary path as gate evidence. CI and test-framework keys
    legitimately have many matches, so their first match is used.
    """
    matches = discover_matches(key, project_root, paths)
    if not matches:
        return None
    if key in ("ci", "test_framework"):
        return matches[0]
    if key == "ux":
        # The UX artifact is deliberately two documents. Point at DESIGN.md
        # only when both halves exist; the gate check verifies the pair.
        names = {item.name for item in matches}
        if {"DESIGN.md", "EXPERIENCE.md"} <= names:
            return next(item for item in matches if item.name == "DESIGN.md")
        return None
    return matches[0] if len(matches) == 1 else None


ARTIFACT_GATES = {
    "spec": ["plan.requirements"],
    "prd": ["plan.requirements"],
    "ux": ["plan.ux"],
    "architecture": ["plan.architecture"],
    "stories": ["plan.stories"],
    "tickets": ["plan.stories"],
    "sprint_plan": ["plan.sprint"],
    "test_design": ["solution.test_design"],
    "test_framework": ["solution.framework"],
    "ci": ["solution.ci"],
    "trace": ["verify.trace"],
}


@plan_locked
def cmd_reconcile(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    project_root = (
        Path(expand_project_root(args.project_root, Path.cwd())).resolve()
        if args.project_root
        else _infer_project_root(path)
    )
    if not project_root.is_dir():
        fail(f"project root not found: {project_root}")
    paths = resolve_paths(project_root)
    write = bool(getattr(args, "write", False))
    memlog = resolve_memlog(data, args, path)
    workstreams = data.get("workstreams") or {}
    results = []
    missing_total = 0
    orphan_total = 0
    missing_evidence_total = 0
    applied: list[str] = []
    for workstream_id, workstream in workstreams.items():
        if not isinstance(workstream, dict):
            continue
        artifacts = workstream.get("artifacts") or {}
        missing = []
        orphans = []
        ambiguous: list[str] = []
        for key in ARTIFACTS:
            pointer = artifacts.get(key)
            if pointer:
                candidate = Path(str(pointer))
                if not candidate.is_absolute():
                    candidate = project_root / candidate
                try:
                    candidate.resolve().relative_to(project_root.resolve())
                    inside = True
                except ValueError:
                    inside = False
                if not inside or not candidate.is_file():
                    missing.append({"artifact": key, "pointer": str(pointer)})
                continue
            matches = discover_matches(key, project_root, paths)
            found = discover_artifact(key, project_root, paths)
            if found is not None:
                orphans.append(
                    {
                        "artifact": key,
                        "path": project_relative(str(found), project_root),
                    }
                )
            elif len(matches) > 1 and key not in ("ci", "test_framework", "ux"):
                ambiguous.append(
                    key
                    + ": "
                    + ", ".join(
                        project_relative(str(item), project_root)
                        for item in matches
                    )
                )
        missing_evidence = []
        phases = workstream.get("phases") or {}
        for phase in PHASES:
            node = phases.get(phase) or {}
            for value in node.get("evidence") or []:
                candidate = Path(str(value))
                if not candidate.is_absolute():
                    candidate = project_root / candidate
                try:
                    relative = project_relative(str(candidate), project_root)
                except ValueError:
                    relative = str(value)
                if not candidate.is_file():
                    missing_evidence.append(
                        {"phase": phase, "path": relative}
                    )
        applied_here: list[str] = []
        if write:
            for orphan in orphans:
                artifacts[orphan["artifact"]] = orphan["path"]
                applied_here.append(
                    f"{workstream_id}.artifacts.{orphan['artifact']}="
                    f"{orphan['path']}"
                )
            if applied_here:
                workstream["artifacts"] = artifacts
        levels = resolve_gate_levels(
            workstream.get("track", "feature"),
            workstream.get("size", "epic"),
            (data.get("bmad") or {}).get("model") or "unknown",
        )
        gates_to_block = [
            gate
            for item in missing
            for gate in ARTIFACT_GATES.get(item["artifact"], [])
            if levels.get(gate) in ("required", "conditional")
        ]
        # A passed/overridden gate whose artifact pointer is unset has no
        # evidence behind it; that gate is blocked, not silently passed.
        for phase in PHASES:
            for name in GATE_NAMES[phase]:
                gate_id = f"{phase}.{name}"
                node = ((workstream.get("gates") or {}).get(phase) or {}).get(name) or {}
                if node.get("status") not in ("passed", "overridden"):
                    continue
                if levels.get(gate_id) not in ("required", "conditional"):
                    continue
                keys = [
                    key
                    for key, gates in ARTIFACT_GATES.items()
                    if gate_id in gates
                ]
                if gate_id == "plan.ux":
                    # The UX gate needs both halves; one DESIGN.md alone is
                    # not the complete artifact, and phase evidence does not
                    # waive the pair.
                    if not ux_pair_ready(
                        workstream,
                        project_root,
                        Path(paths["planning_artifacts"]),
                    ):
                        gates_to_block.append(gate_id)
                    continue
                if keys and not any(artifacts.get(key) for key in keys):
                    gates_to_block.append(gate_id)
        gates_to_block = sorted(set(gates_to_block))
        phases_to_block = sorted(
            {item["phase"] for item in missing_evidence}
        )
        requires_reason: list[str] = []
        if write:
            model = (data.get("bmad") or {}).get("model") or "unknown"
            for gate_id in gates_to_block:
                phase, _, name = gate_id.partition(".")
                node = (
                    ((workstream.get("gates") or {}).get(phase) or {}).get(name)
                )
                if not isinstance(node, dict):
                    continue
                if node.get("status") == "open":
                    node["status"] = "blocked"
                    node["decided_at"] = None
                    node["override_reason"] = None
                    applied_here.append(
                        f"{workstream_id}.gates.{gate_id}=blocked"
                    )
                elif node.get("status") in ("passed", "overridden", "skipped"):
                    # A decided gate reopens only with a reason; report it so
                    # the conductor can ask instead of silently undoing it.
                    requires_reason.append(f"gates.{gate_id}")
            for phase in phases_to_block:
                node = (workstream.get("phases") or {}).get(phase)
                if not isinstance(node, dict):
                    continue
                if node.get("status") in ("pending", "active"):
                    node["status"] = "blocked"
                    applied_here.append(
                        f"{workstream_id}.phases.{phase}.status=blocked"
                    )
                elif node.get("status") in ("done", "skipped"):
                    requires_reason.append(f"phases.{phase}")
            if applied_here:
                refresh_workstream(workstream, model)
            applied.extend(applied_here)
        artifact_ids = artifact_ticket_ids(project_root, paths)
        ledger_ids = set((workstream.get("tickets") or {}).keys())
        if artifact_ids is not None and workstream.get("track") != "audit":
            tickets_missing_in_ledger = sorted(artifact_ids - ledger_ids)
            tickets_missing_in_artifacts = sorted(ledger_ids - artifact_ids)
        else:
            tickets_missing_in_ledger = []
            tickets_missing_in_artifacts = []
        missing_total += len(missing)
        orphan_total += len(orphans)
        missing_evidence_total += len(missing_evidence)
        results.append(
            {
                "workstream": workstream_id,
                "missing_pointers": missing,
                "orphan_pointers": orphans,
                "ambiguous_pointers": ambiguous,
                "missing_evidence": missing_evidence,
                "gates_to_block": gates_to_block,
                "phases_to_block": phases_to_block,
                "requires_reason": requires_reason,
                "applied": applied_here,
                "tickets_missing_in_ledger": tickets_missing_in_ledger,
                "tickets_missing_in_artifacts": tickets_missing_in_artifacts,
            }
        )
    if write and applied:
        data["updated"] = now_iso()
        save_plan(path, data)
        append_memlog(
            memlog,
            "correction",
            "reconcile applied: " + "; ".join(applied),
        )
    ok = missing_total == 0 and missing_evidence_total == 0
    emit(
        {
            "ok": ok,
            "project_root": str(project_root),
            "workstreams": results,
            "missing_count": missing_total,
            "orphan_count": orphan_total,
            "missing_evidence_count": missing_evidence_total,
            "applied": applied,
            "write": write,
            "memlog": str(memlog),
        },
        0 if ok else 1,
    )


def cmd_verify_return(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    project_root = (
        Path(expand_project_root(args.project_root, Path.cwd())).resolve()
        if args.project_root
        else _infer_project_root(path)
    )
    if not project_root.is_dir():
        fail(f"project root not found: {project_root}")
    if args.return_file:
        raw = Path(args.return_file).read_text(encoding="utf-8")
    elif args.return_json:
        raw = args.return_json
    else:
        fail("provide --return or --return-file")
    try:
        returned = json.loads(raw)
    except json.JSONDecodeError as error:
        fail(f"return is not valid JSON: {error}")
    if not isinstance(returned, dict):
        fail("return must be a JSON object")

    status = returned.get("status")
    if status not in ("done", "blocked", "needs_input"):
        fail(f"status must be one of done, blocked, needs_input; got {status!r}")
    raw_artifacts = returned.get("artifacts")
    if raw_artifacts is None:
        raw_artifacts = []
    if not isinstance(raw_artifacts, list):
        fail("artifacts must be a list")
    open_questions = returned.get("open_questions") or []
    if not isinstance(open_questions, list):
        fail("open_questions must be a list")
    raw_evidence = returned.get("evidence")
    if raw_evidence is None:
        evidence: list = []
    elif isinstance(raw_evidence, list):
        evidence = raw_evidence
    else:
        fail("evidence must be a list")
    allow_empty = bool(getattr(args, "allow_empty_artifacts", False))
    if allow_empty and not str(getattr(args, "reason", "") or "").strip():
        fail("--allow-empty-artifacts needs --reason")
    accept_questions = bool(getattr(args, "accept_questions", False))
    memlog_path = resolve_memlog(data, args, path)

    missing: list[str] = []
    outside: list[str] = []
    malformed: list[str] = []
    ledger_artifacts: list[str] = []
    artifacts: list[dict] = []
    for item in raw_artifacts:
        value = item.get("path") if isinstance(item, dict) else item
        if not value:
            malformed.append(str(item))
            continue
        artifacts.append({"path": str(value)})
        candidate = Path(str(value))
        if not candidate.is_absolute():
            candidate = project_root / candidate
        if not candidate.is_file() or candidate.stat().st_size == 0:
            missing.append(str(value))
            continue
        resolved = candidate.resolve()
        try:
            resolved.relative_to(project_root.resolve())
        except ValueError:
            outside.append(str(value))
            continue
        if resolved in (path.resolve(), memlog_path.resolve()):
            ledger_artifacts.append(str(value))

    evidence_missing: list[str] = []
    evidence_outside: list[str] = []
    for item in evidence:
        value = item.get("path") if isinstance(item, dict) else item
        if not value:
            evidence_missing.append(str(item))
            continue
        candidate = Path(str(value))
        if not candidate.is_absolute():
            candidate = project_root / candidate
        if not candidate.is_file() or candidate.stat().st_size == 0:
            evidence_missing.append(str(value))
            continue
        try:
            candidate.resolve().relative_to(project_root.resolve())
        except ValueError:
            evidence_outside.append(str(value))

    changed: list[str] = []
    git_dirty = None
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode == 0:
            changed = [line for line in proc.stdout.splitlines() if line.strip()]
            git_dirty = bool(changed)
    except (OSError, subprocess.SubprocessError):
        git_dirty = None

    ledger_rel = project_relative(str(path), project_root)
    memlog_rel = project_relative(str(memlog_path), project_root)
    touched_paths = set()
    for line in changed:
        # Porcelain lines are "XY path" or "XY old -> new". Compare whole
        # paths: a substring test also matches plan.yaml.lock.
        body = line[3:].strip() if len(line) > 3 else ""
        if " -> " in body:
            body = body.split(" -> ", 1)[1]
        touched_paths.add(body.strip('"'))
    ledger_touched = ledger_rel in touched_paths or memlog_rel in touched_paths
    reasons: list[str] = []
    if status != "done":
        reasons.append(f"status is {status}")
    if not artifacts and not allow_empty:
        reasons.append("no artifacts returned")
    if not evidence:
        # Evidence is part of the return contract, and omitting the key must
        # not be a cheaper way to pass than an explicit empty list.
        reasons.append("no evidence returned")
    if missing:
        reasons.append("missing artifacts: " + ", ".join(missing))
    if outside:
        reasons.append("artifacts outside project root: " + ", ".join(outside))
    if malformed:
        reasons.append("malformed artifacts: " + ", ".join(malformed))
    if evidence_missing:
        reasons.append("missing evidence: " + ", ".join(evidence_missing))
    if evidence_outside:
        reasons.append(
            "evidence outside project root: " + ", ".join(evidence_outside)
        )
    if ledger_artifacts:
        reasons.append("ledger/memlog used as artifact: " + ", ".join(ledger_artifacts))
    if open_questions and not accept_questions:
        reasons.append("open questions remain: " + "; ".join(map(str, open_questions)))
    # Git status cannot distinguish a prior uncommitted ledger edit from a
    # subagent edit, so this is advisory; the hard check is status + artifacts.
    ok = not reasons
    if ok and accept_questions and open_questions:
        append_memlog(
            memlog_path,
            "decision",
            "accepted open questions: "
            + "; ".join(str(question) for question in open_questions),
        )
    if ok and allow_empty:
        append_memlog(
            memlog_path,
            "decision",
            f"accepted an empty artifact list (reason: {args.reason})",
        )
    emit(
        {
            "ok": ok,
            "status": status,
            "reasons": reasons,
            "artifact_count": len(artifacts),
            "missing_artifacts": missing,
            "outside_artifacts": outside,
            "malformed_artifacts": malformed,
            "missing_evidence": evidence_missing,
            "outside_evidence": evidence_outside,
            "ledger_artifacts": ledger_artifacts,
            "open_questions": open_questions,
            "accept_questions": accept_questions,
            "allow_empty_artifacts": allow_empty,
            "decisions": returned.get("decisions") or [],
            "next_recommendation": returned.get("next_recommendation"),
            "git_dirty": git_dirty,
            "changed_files": changed,
            "ledger_touched": ledger_touched,
            "ledger": str(path),
            "memlog": str(memlog_path),
            "project_root": str(project_root),
        },
        0 if ok else 1,
    )


@plan_locked
def cmd_resize(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    data = load_plan(path)
    workstream_id, workstream = workstream_root(data, args.workstream)
    if workstream.get("status") == "done":
        fail("workstream is done; start a new workstream instead of resizing it")
    track = args.track or workstream.get("track", "feature")
    size = args.size or workstream.get("size", "epic")
    if track not in TRACKS:
        fail(f"unknown track {track!r}; choose one of {', '.join(TRACKS)}")
    if size not in SIZES:
        fail(f"unknown size {size!r}; choose one of {', '.join(SIZES)}")
    model = (data.get("bmad") or {}).get("model") or "unknown"
    if track != "audit" and workstream.get("track") == "audit":
        audit_ticket = (workstream.get("tickets") or {}).get("audit")
        decided = [
            name
            for name, node in ((audit_ticket or {}).get("gates") or {}).items()
            if isinstance(node, dict)
            and (
                node.get("status") in ("passed", "overridden")
                or (
                    node.get("status") == "skipped"
                    and node.get("override_reason")
                )
            )
        ]
        if decided:
            fail(
                "audit gates are already decided ("
                + ", ".join(sorted(decided))
                + "); close the audit workstream or keep track=audit"
            )
    workstream["track"] = track
    workstream["size"] = size
    changed = apply_levels(workstream, model)
    reopened = [
        entry.split(".")[1]
        for entry in changed
        if entry.startswith("phases.") and entry.endswith(".status->pending")
    ]
    if reopened and not str(getattr(args, "reason", None) or "").strip():
        fail(
            "resizing reopens "
            + ", ".join(reopened)
            + "; pass --reason to record why"
        )
    tickets = workstream.get("tickets")
    if not isinstance(tickets, dict):
        tickets = {}
        workstream["tickets"] = tickets
    if track != "audit":
        audit_ticket = tickets.get("audit")
        if isinstance(audit_ticket, dict):
            decided = any(
                isinstance(node, dict)
                and (
                    node.get("status") in ("passed", "overridden")
                    or (
                        node.get("status") == "skipped"
                        and node.get("override_reason")
                    )
                )
                for node in (audit_ticket.get("gates") or {}).values()
            )
            if not decided:
                tickets.pop("audit", None)
                changed.append("tickets.audit removed")
    if track == "audit" and "audit" not in tickets:
        tickets["audit"] = {
            "title": "Audit",
            "gates": {
                "ticket": {
                    "status": "skipped",
                    "decided_at": None,
                    "override_reason": None,
                },
                "tests": {
                    "status": "skipped",
                    "decided_at": None,
                    "override_reason": None,
                },
                "review": {
                    "status": "open",
                    "decided_at": None,
                    "override_reason": None,
                },
                "done": {
                    "status": "skipped",
                    "decided_at": None,
                    "override_reason": None,
                },
            },
        }
    refresh_workstream(workstream, model)
    data["updated"] = now_iso()
    save_plan(path, data)
    append_memlog(
        resolve_memlog(data, args, path),
        "event",
        f"{workstream_id} resized to track={track} size={size}"
        + (
            "; reopened: " + ", ".join(reopened)
            + (f" (reason: {args.reason})" if args.reason else "")
            if reopened
            else ""
        ),
    )
    emit(
        {
            "ok": True,
            "ledger": str(path),
            "workstream": workstream_id,
            "track": track,
            "size": size,
            "changed": changed,
            "next_action": workstream.get("next"),
        }
    )


def cmd_log(args: argparse.Namespace) -> None:
    path = _plan_path(args)
    if not path.is_file():
        fail(f"ledger not found: {path}")
    data = load_plan(path)
    memlog = resolve_memlog(data, args, path)
    written = append_memlog(memlog, args.type, args.text)
    emit({"ok": True, "memlog": str(written), "type": args.type})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect = subparsers.add_parser("detect")
    detect.add_argument("--project-root", default=".")
    detect.set_defaults(func=cmd_detect)

    init = subparsers.add_parser("init")
    init.add_argument("--project-root", default=".")
    init.add_argument("--name", required=True)
    init.add_argument("--track", default=None)
    init.add_argument("--size", default=None)
    init.add_argument("--model", choices=("v6", "current", "unknown"))
    init.add_argument("--default-track", default=None)
    init.add_argument("--default-size", default=None)
    init.add_argument("--workstream")
    init.add_argument("--plan")
    init.add_argument("--memlog")
    init.add_argument("--template")
    init.add_argument("--reason")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--plan", required=True)
    validate.set_defaults(func=cmd_validate)

    summary = subparsers.add_parser("summary")
    summary.add_argument("--plan", required=True)
    summary.add_argument("--workstream")
    summary.add_argument("--project-root")
    summary.add_argument("--memlog")
    summary.set_defaults(func=cmd_summary)

    set_cmd = subparsers.add_parser("set")
    set_cmd.add_argument("--plan", required=True)
    set_cmd.add_argument("--workstream")
    set_cmd.add_argument("--path", required=True)
    set_cmd.add_argument("--value")
    set_cmd.add_argument("--null", action="store_true")
    set_cmd.add_argument("--delete", action="store_true")
    set_cmd.add_argument("--reason")
    set_cmd.add_argument("--replace", action="store_true")
    set_cmd.add_argument("--root", action="store_true")
    set_cmd.add_argument("--memlog")
    set_cmd.set_defaults(func=cmd_set)

    append = subparsers.add_parser("append")
    append.add_argument("--plan", required=True)
    append.add_argument("--workstream")
    append.add_argument("--path", required=True)
    append.add_argument("--value")
    append.add_argument("--null", action="store_true")
    append.add_argument("--root", action="store_true")
    append.add_argument("--memlog")
    append.set_defaults(func=cmd_append)

    ticket = subparsers.add_parser("ticket")
    ticket.add_argument("--plan", required=True)
    ticket.add_argument("--workstream")
    ticket.add_argument("--id", required=True)
    ticket.add_argument("--gate", required=True)
    ticket.add_argument("--status", required=True)
    ticket.add_argument("--reason")
    ticket.add_argument("--title")
    ticket.add_argument("--memlog")
    ticket.set_defaults(func=cmd_ticket)

    done = subparsers.add_parser("done")
    done.add_argument("--plan", required=True)
    done.add_argument("--workstream")
    done.add_argument("--project-root")
    done.add_argument("--accept-missing-evidence", action="store_true")
    done.add_argument("--accept-missing-tickets", action="store_true")
    done.add_argument("--reason")
    done.add_argument("--memlog")
    done.set_defaults(func=cmd_done)

    migrate = subparsers.add_parser("migrate")
    migrate.add_argument("--plan", required=True)
    migrate.add_argument("--memlog")
    migrate.set_defaults(func=cmd_migrate)

    resize = subparsers.add_parser("resize")
    resize.add_argument("--plan", required=True)
    resize.add_argument("--workstream")
    resize.add_argument("--track", choices=TRACKS)
    resize.add_argument("--size", choices=SIZES)
    resize.add_argument("--reason")
    resize.add_argument("--memlog")
    resize.set_defaults(func=cmd_resize)

    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--plan", required=True)
    reconcile.add_argument("--project-root")
    reconcile.add_argument("--write", action="store_true")
    reconcile.add_argument("--memlog")
    reconcile.set_defaults(func=cmd_reconcile)

    verify = subparsers.add_parser("verify-return")
    verify.add_argument("--plan", required=True)
    verify.add_argument("--return", dest="return_json")
    verify.add_argument("--return-file")
    verify.add_argument("--project-root")
    verify.add_argument("--memlog")
    verify.add_argument("--accept-questions", action="store_true")
    verify.add_argument("--allow-empty-artifacts", action="store_true")
    verify.add_argument("--reason")
    verify.set_defaults(func=cmd_verify_return)

    log = subparsers.add_parser("log")
    log.add_argument("--plan", required=True)
    log.add_argument("--memlog")
    log.add_argument("--type", default="event")
    log.add_argument("--text", required=True)
    log.set_defaults(func=cmd_log)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - JSON error contract
        fail(str(error))


if __name__ == "__main__":
    main()
