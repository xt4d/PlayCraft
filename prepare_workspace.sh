#!/usr/bin/env bash

set -euo pipefail

if [[ $# -gt 2 || -z "${1:-}" ]]; then
  echo "Usage: $0 GAME_DIRECTORY [WORKSPACE_DIRECTORY]" >&2
  exit 2
fi

if [[ ! -f "$1/index.html" ]]; then
  printf 'error: game directory needs index.html: %s\n' "$1" >&2
  exit 1
fi

game_dir=$(CDPATH= cd -P -- "$1" && pwd -P)
workspace_dir="${2:-${game_dir}-workspace}"
mkdir -p -- "$workspace_dir"
workspace_dir=$(CDPATH= cd -P -- "$workspace_dir" && pwd -P)
if [[ "$workspace_dir" == "$game_dir" || "$workspace_dir" == "${game_dir%/}/"* ]]; then
  echo "error: the workspace must be outside the game directory" >&2
  exit 1
fi

iteration_dir="$workspace_dir/iter0"
mkdir -- "$iteration_dir"

trap 'rm -rf -- "$iteration_dir"' EXIT
cp -a -- "$game_dir/." "$iteration_dir/"

rm -rf -- "$iteration_dir/logs" "$iteration_dir/tmp" "$iteration_dir/temp" \
  "$iteration_dir/.tmp" "$iteration_dir/.browser-test"
find "$iteration_dir" -name .git -prune -exec rm -rf -- {} +
find "$iteration_dir" \( -type f -o -type l \) \
  \( -name '*.log' -o -name '*.tmp' -o -name '*.temp' -o -name '.DS_Store' \) \
  -exec rm -f -- {} +

gitignore="$iteration_dir/.gitignore"
if [[ -L "$gitignore" ]]; then
  {
    rm -- "$gitignore"
    cat > "$gitignore"
  } < "$gitignore"
fi
if [[ ! -f "$gitignore" ]] || ! grep -Fxq 'logs/' "$gitignore"; then
  if [[ -s "$gitignore" ]]; then
    printf '\n' >> "$gitignore"
  fi
  printf 'logs/\n' >> "$gitignore"
fi

if command -v git >/dev/null 2>&1; then
  git -C "$iteration_dir" init -q
  git -C "$iteration_dir" config --local user.email "run"
  git -C "$iteration_dir" config --local user.name "run"
  git -C "$iteration_dir" add -A
  git -C "$iteration_dir" commit -qm "Initial game for iter0"
fi
trap - EXIT

printf 'Prepared %s\n' "$iteration_dir"
