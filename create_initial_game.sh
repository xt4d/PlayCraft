#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 || -z "$1" || ! "$2" =~ [^[:space:]] ]]; then
  echo "Usage: $0 GAME_DIRECTORY GAME_PROMPT" >&2
  exit 2
fi

game_dir="$1"
game_prompt="$2"

mkdir -p -- "$game_dir"
python run_codex.py \
  --project-dir "$game_dir" \
  --prompts-file "prompts/create.md" \
  --insert game_prompt "$game_prompt"
