#!/usr/bin/env bash
# Build the distributable module package from the canonical skill source.
#
# Authoring state (.analysis/, .memlog.md, caches) is intentionally excluded:
# it is not runtime content and must not ship to users.
set -euo pipefail

module_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="$(cd "$module_root/../.." && pwd)"
source_dir="$repo_root/.agents/skills/bmad-sdlc"
target_dir="$module_root/skills/bmad-sdlc"

if [[ ! -f "$source_dir/SKILL.md" ]]; then
  echo "error: canonical skill not found at $source_dir" >&2
  exit 1
fi

rm -rf "$target_dir"
mkdir -p "$target_dir"

if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '/.analysis/' \
    --exclude '/.memlog.md' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    "$source_dir/" "$target_dir/"
else
  cp -R "$source_dir/." "$target_dir/"
  rm -rf "$target_dir/.analysis"
  rm -f "$target_dir/.memlog.md"
  find "$target_dir" -name '__pycache__' -type d -prune -exec rm -rf {} +
  find "$target_dir" -name '*.pyc' -delete
  find "$target_dir" -name '.DS_Store' -delete
fi

if [[ ! -f "$target_dir/evals/cases.json" ]]; then
  echo "error: packaged copy is missing evals/cases.json" >&2
  exit 1
fi

echo "packaged $target_dir"
