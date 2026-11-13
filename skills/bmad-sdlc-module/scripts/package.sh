#!/usr/bin/env bash
# Build the distributable module package from the canonical skill source.
#
# Authoring state (.analysis/, .memlog.md, evals, caches) is intentionally
# excluded: it is not runtime content and must not ship. The unit tests ship
# because BMAD's script scan expects scripts/tests/ to exist, and they are
# portable in a normal skills-directory install.
#
# Usage:
#   scripts/package.sh          rebuild skills/bmad-sdlc atomically
#   scripts/package.sh --check  compare the canonical tree with the packaged
#                               copy and exit non-zero on drift
set -euo pipefail

module_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="$(cd "$module_root/../.." && pwd)"
source_dir="$repo_root/.agents/skills/bmad-sdlc"
target_dir="$module_root/skills/bmad-sdlc"
mode="${1:-build}"

if [[ "$mode" != "build" && "$mode" != "--check" ]]; then
  echo "usage: $0 [--check]" >&2
  exit 2
fi

if [[ ! -f "$source_dir/SKILL.md" ]]; then
  echo "error: canonical skill not found at $source_dir" >&2
  exit 1
fi

copy_tree() {
  local dest="$1"
  mkdir -p "$dest"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude '/.analysis/' \
      --exclude '/.memlog.md' \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      --exclude '.DS_Store' \
      --exclude '/evals/' \
      "$source_dir/" "$dest/"
  else
    cp -R "$source_dir/." "$dest/"
    rm -rf "$dest/.analysis" "$dest/evals"
    rm -f "$dest/.memlog.md"
    find "$dest" -name '__pycache__' -type d -prune -exec rm -rf {} +
    find "$dest" -name '*.pyc' -delete
    find "$dest" -name '.DS_Store' -delete
  fi
}

if [[ "$mode" == "--check" ]]; then
  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/bmad-sdlc-package.XXXXXX")"
  trap 'rm -rf "$tmp_dir"' EXIT
  copy_tree "$tmp_dir"
  if diff -r -q -x '__pycache__' -x '*.pyc' "$tmp_dir" "$target_dir" >/dev/null 2>&1; then
    echo "package is in sync: $target_dir"
    exit 0
  fi
  echo "error: packaged copy has drifted; run scripts/package.sh" >&2
  diff -r -q -x '__pycache__' -x '*.pyc' "$tmp_dir" "$target_dir" >&2 || true
  exit 1
fi

# Build beside the target, then move into place only after the copy succeeds;
# a failed copy cannot leave the module without a skill.
staging="$module_root/skills/.bmad-sdlc.staging"
rm -rf "$staging"
trap 'rm -rf "$staging"' EXIT
copy_tree "$staging"

if [[ ! -f "$staging/SKILL.md" || ! -f "$staging/scripts/sdlc_plan.py" ]]; then
  echo "error: packaged copy is missing SKILL.md or scripts/sdlc_plan.py" >&2
  exit 1
fi

rm -rf "$target_dir"
mv "$staging" "$target_dir"
trap - EXIT
echo "packaged $target_dir"
