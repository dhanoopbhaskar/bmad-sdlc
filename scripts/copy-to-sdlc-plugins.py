#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Bundle the bmad-sdlc skill into the sdlc-plugins Agent Plugins repository.

The target repository uses the Agent Plugins v1 layout::

    plugins/<plugin>/plugin.json
    plugins/<plugin>/skills/<skill>/SKILL.md

This script mirrors the canonical skill into that layout, writes the plugin
manifest, registers the plugin in ``.github/plugin/marketplace.json``, and
keeps the repository-wide lockstep version. BMAD module metadata
(``module.yaml``, ``module-help.csv``, ``VERSION``) is not part of an Agent
Plugins bundle and is removed from the target.

The target repository is a git checkout. Files are synced in place so history
and untracked repository state are preserved; a ``.git`` directory inside the
skill is never touched.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_NAME = "bmad"
SKILL_NAME = "bmad-sdlc"
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN_DESCRIPTION = (
    "BMAD delivery lifecycle conductor: detect the project model, keep a durable "
    "ledger, present a phase/action menu with gates, hand off to the right skill, "
    "and validate artifacts."
)
PLUGIN_KEYWORDS = [
    "bmad",
    "sdlc",
    "skills",
    "planning",
    "lifecycle",
    "conductor",
    "gates",
    "handoff",
]
MARKETPLACE_REL = Path(".github") / "plugin" / "marketplace.json"
SKILL_NAME_RE = re.compile(r"^name:\s*([^\s#]+)\s*$", re.MULTILINE)
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)

# Authoring and BMAD-module files are not runtime content for an Agent Skill.
# ``VERSION`` duplicates the plugin version that now lives in plugin.json.
IGNORE_PATTERNS = (
    ".analysis",
    ".memlog.md",
    "evals",
    "VERSION",
    "__pycache__",
    "*.pyc",
    ".DS_Store",
    ".git",
)

FALLBACK_METADATA = {
    "author": {
        "name": "Dhanoop Bhaskar",
        "email": "dhaskarbhaskar@gmail.com",
        "url": "https://dhanoopbhaskar.com",
    },
    "homepage": "https://github.com/dhanoopbhaskar/sdlc-plugins",
    "repository": "https://github.com/dhanoopbhaskar/sdlc-plugins",
    "license": "MIT",
}


class BundleError(RuntimeError):
    """Raised when the target repository cannot be bundled safely."""


def should_ignore(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in IGNORE_PATTERNS)


def copy_tree_safe(src: Path, dst: Path) -> None:
    """Copy the tree without removing dst first, skipping non-runtime files."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in sorted(src.iterdir(), key=lambda path: path.name):
        if should_ignore(item.name):
            continue
        dst_item = dst / item.name
        if item.is_dir():
            if dst_item.is_file() or dst_item.is_symlink():
                dst_item.unlink()
            copy_tree_safe(item, dst_item)
        else:
            if dst_item.is_dir():
                shutil.rmtree(dst_item)
            shutil.copy2(item, dst_item)


def remove_stale(src: Path, dst: Path, root: Path | None = None) -> list[str]:
    """Remove target entries that are excluded or no longer exist in src."""
    removed: list[str] = []
    if not dst.exists():
        return removed
    if root is None:
        root = dst
    for item in sorted(dst.iterdir(), key=lambda path: path.name):
        if item.name == ".git":
            # Preserve repository state if the target skill is itself a checkout.
            continue
        src_item = src / item.name
        if should_ignore(item.name) or not src_item.exists():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed.append(item.relative_to(root).as_posix())
        elif item.is_dir():
            removed.extend(remove_stale(src_item, item, root))
    return removed


def prune_empty_dirs(root: Path) -> None:
    """Remove empty directories left behind after stale-file cleanup."""
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def read_json_object(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BundleError(f"{label}: cannot read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BundleError(f"{label}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise BundleError(f"{label}: expected a JSON object")
    return data


def write_json_object(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def plugin_manifests(target_repo: Path) -> list[tuple[Path, dict]]:
    plugins_root = target_repo / "plugins"
    manifests: list[tuple[Path, dict]] = []
    for path in sorted(plugins_root.glob("*/plugin.json")):
        manifests.append(
            (path, read_json_object(path, f"{path.relative_to(target_repo)}"))
        )
    return manifests


def resolve_lockstep_version(
    target_repo: Path, marketplace: dict, source_skill: Path
) -> str:
    """Return the repository-wide plugin version and verify it is unambiguous."""
    candidates: dict[str, str] = {}

    for path, manifest in plugin_manifests(target_repo):
        version = manifest.get("version")
        if isinstance(version, str) and version.strip():
            candidates[str(path.relative_to(target_repo))] = version.strip()

    metadata = marketplace.get("metadata")
    if isinstance(metadata, dict):
        version = metadata.get("version")
        if isinstance(version, str) and version.strip():
            candidates[str(MARKETPLACE_REL)] = version.strip()

    plugins = marketplace.get("plugins")
    if isinstance(plugins, list):
        for entry in plugins:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            version = entry.get("version")
            if isinstance(name, str) and isinstance(version, str) and version.strip():
                candidates[f"{MARKETPLACE_REL}:{name}"] = version.strip()

    unique = sorted(set(candidates.values()))
    if len(unique) > 1:
        details = ", ".join(f"{label}={version}" for label, version in candidates.items())
        raise BundleError(
            "target repository versions are not in lockstep "
            f"({details}); fix them before bundling"
        )
    if len(unique) == 1:
        version = unique[0]
    else:
        version_file = source_skill / "VERSION"
        try:
            version = version_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise BundleError(
                "cannot determine a plugin version; add a version to an existing "
                "plugin.json, the marketplace metadata, or the skill VERSION file"
            ) from exc
        if not version:
            raise BundleError("skill VERSION file is empty")

    if not SEMVER_RE.fullmatch(version):
        raise BundleError(f"plugin version {version!r} is not semantic versioning")
    return version


def shared_metadata(target_repo: Path, plugin_dir: Path) -> dict:
    """Reuse author/homepage/repository/license from the target's other plugins."""
    metadata = {
        "author": dict(FALLBACK_METADATA["author"]),
        "homepage": FALLBACK_METADATA["homepage"],
        "repository": FALLBACK_METADATA["repository"],
        "license": FALLBACK_METADATA["license"],
    }
    for path, manifest in plugin_manifests(target_repo):
        if path.parent == plugin_dir:
            continue
        author = manifest.get("author")
        if isinstance(author, dict) and author.get("name"):
            metadata["author"] = dict(author)
        for key in ("homepage", "repository", "license"):
            value = manifest.get(key)
            if isinstance(value, str) and value.strip():
                metadata[key] = value
        break
    return metadata


def build_manifest(version: str, metadata: dict) -> dict:
    return {
        "$schema": PLUGIN_SCHEMA,
        "name": PLUGIN_NAME,
        "version": version,
        "description": PLUGIN_DESCRIPTION,
        "author": metadata["author"],
        "homepage": metadata["homepage"],
        "repository": metadata["repository"],
        "license": metadata["license"],
        "keywords": list(PLUGIN_KEYWORDS),
    }


def build_marketplace_entry(version: str, metadata: dict) -> dict:
    return {
        "name": PLUGIN_NAME,
        "description": PLUGIN_DESCRIPTION,
        "version": version,
        "source": f"./plugins/{PLUGIN_NAME}",
        "author": metadata["author"],
        "homepage": metadata["homepage"],
        "repository": metadata["repository"],
        "license": metadata["license"],
        "keywords": list(PLUGIN_KEYWORDS),
    }


def update_marketplace(
    marketplace: dict, version: str, metadata: dict
) -> str:
    """Add or replace the plugin entry, keeping lockstep marketplace metadata."""
    market_metadata = marketplace.get("metadata")
    if not isinstance(market_metadata, dict):
        raise BundleError(f"{MARKETPLACE_REL}: 'metadata' must be an object")
    market_metadata["version"] = version

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        raise BundleError(f"{MARKETPLACE_REL}: 'plugins' must be an array")

    entry = build_marketplace_entry(version, metadata)
    matches = [
        index
        for index, item in enumerate(plugins)
        if isinstance(item, dict) and item.get("name") == PLUGIN_NAME
    ]
    if len(matches) > 1:
        raise BundleError(f"{MARKETPLACE_REL}: duplicate plugin entry {PLUGIN_NAME!r}")
    if matches:
        plugins[matches[0]] = entry
        return "updated"
    plugins.append(entry)
    return "added"


def verify_skill_frontmatter(skill_md: Path) -> None:
    try:
        text = skill_md.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise BundleError(f"cannot read {skill_md}: {exc}") from exc
    if not text.startswith("---\n"):
        raise BundleError(f"{skill_md}: missing YAML frontmatter")
    frontmatter = text.split("\n---", 1)[0]
    match = SKILL_NAME_RE.search(frontmatter)
    if match is None:
        raise BundleError(f"{skill_md}: frontmatter is missing 'name'")
    if match.group(1).strip("'\"") != skill_md.parent.name:
        raise BundleError(
            f"{skill_md}: frontmatter name {match.group(1)!r} does not match "
            f"directory {skill_md.parent.name!r}"
        )


def run_target_validator(target_repo: Path) -> None:
    validator = target_repo / "scripts" / "validate_skills.py"
    if not validator.is_file():
        print(f"Note: no validator at {validator}; skipping target validation.", flush=True)
        return
    result = subprocess.run(
        [sys.executable, str(validator)],
        cwd=target_repo,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise BundleError(
            f"target validation failed ({validator.relative_to(target_repo)}); "
            "see output above"
        )


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Bundle the bmad-sdlc skill into the sdlc-plugins repository."
    )
    parser.add_argument(
        "--target-repo",
        default=str(repo_root.parent / "sdlc-plugins"),
        help="sdlc-plugins checkout (default: sibling of this repository)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="skip the target repository's scripts/validate_skills.py",
    )
    args = parser.parse_args(argv)

    source_skill = repo_root / ".agents" / "skills" / SKILL_NAME
    target_repo = Path(args.target_repo).expanduser().resolve()
    plugin_dir = target_repo / "plugins" / PLUGIN_NAME
    target_skill = plugin_dir / "skills" / SKILL_NAME
    marketplace_path = target_repo / MARKETPLACE_REL

    try:
        if not (source_skill / "SKILL.md").is_file():
            raise BundleError(f"source skill not found at {source_skill}")
        if not (source_skill / "scripts" / "sdlc_plan.py").is_file():
            raise BundleError("source skill is missing scripts/sdlc_plan.py")
        if not (target_repo / "plugins").is_dir():
            raise BundleError(
                f"{target_repo} is not an sdlc-plugins checkout: missing plugins/"
            )
        if not marketplace_path.is_file():
            raise BundleError(f"missing {marketplace_path}")

        marketplace = read_json_object(marketplace_path, str(MARKETPLACE_REL))
        version = resolve_lockstep_version(target_repo, marketplace, source_skill)
        metadata = shared_metadata(target_repo, plugin_dir)

        print(f"Syncing {source_skill} -> {target_skill}", flush=True)
        copy_tree_safe(source_skill, target_skill)
        removed = remove_stale(source_skill, target_skill)
        prune_empty_dirs(target_skill)
        if removed:
            print(f"Removed non-bundle entries: {', '.join(sorted(removed))}", flush=True)

        verify_skill_frontmatter(target_skill / "SKILL.md")
        if target_skill.parent.name != "skills":
            raise BundleError("internal error: unexpected skill layout")

        manifest_path = plugin_dir / "plugin.json"
        write_json_object(manifest_path, build_manifest(version, metadata))
        print(f"Wrote {manifest_path} (version {version})", flush=True)

        action = update_marketplace(marketplace, version, metadata)
        write_json_object(marketplace_path, marketplace)
        print(f"{action.capitalize()} {PLUGIN_NAME!r} in {MARKETPLACE_REL}", flush=True)

        if not args.no_validate:
            run_target_validator(target_repo)
    except BundleError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
