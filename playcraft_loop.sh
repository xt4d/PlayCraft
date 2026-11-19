#!/usr/bin/env bash

set -euo pipefail

work_dir="$1"

start_iter=$((10#$2))
end_iter=$((10#$3))

play_time_ms="$4"
render_width="$5"
render_height="$6"

if [[ ! "$play_time_ms" =~ ^[0-9]+(_[0-9]+)*$ || "$play_time_ms" != *[1-9]* ]]; then
  echo "error: play time must be a positive integer in milliseconds" >&2
  exit 2
fi

play_run_cnt=$((10#${7:-1}))
play_run_mode="${8:-seq}"

run_play() {
  local play_index="$1"
  local play_folder="$2"
  local play_output="${code_dir_prev}-play/play-$play_index"

  if [[ ! -f "$play_output/done" ]]; then
    rm -rf "$play_output"

    python player/play.py "$code_dir_prev" \
      --output "$play_output" \
      --width "$render_width" --height "$render_height" \
      --episodes 10 --duration "$play_time_ms" \
      --model-interval 1000 \
      --observation-interval 200 \
      --action-interval 20 \
      --model gpt-6.1-sol \
      --compact-between-episodes \
      --model-timeout 1800_000
  fi
  python player/play_record.py "$play_output" "$play_folder"
}

for ((iteration = start_iter+1; iteration <= end_iter; iteration++)); do
  code_dir_prev="$work_dir/iter$((iteration - 1))"
  code_dir="$work_dir/iter$iteration"

  if [[ -f "$code_dir/logs/implementation.md" ]]; then
    printf 'Skip: iteration %s is already implemented\n' "$iteration"
    continue
  fi

  [[ -d "$code_dir_prev" ]] || {
    echo "error: source directory does not exist: $code_dir_prev" >&2
    exit 1
  }

  # Copy and initialize this iteration only if its directory does not exist.
  if [[ ! -d "$code_dir" ]]; then
    # Archive inherited results, and remove logs and temp.
    cp -a "$code_dir_prev" "$code_dir"
    mkdir -p "$code_dir/logs/history/iter$((iteration - 1))"
    for file in "$code_dir/logs/"*.md; do
      [[ -e "$file" ]] || continue
      mv -- "$file" "$code_dir/logs/history/iter$((iteration - 1))/"
    done
    for play_folder in "$code_dir/logs/"play-*; do
      [[ -d "$play_folder" ]] || continue
      mv -- "$play_folder" "$code_dir/logs/history/iter$((iteration - 1))/"
    done
    rm -f "$code_dir/logs/"*.log
    rm -rf "$code_dir/logs/temp"
  fi

  # Start missing play runs concurrently or sequentially.
  play_pids=()
  play_indices=()
  play_count=0

  for ((play_index = 0; play_index < play_run_cnt; play_index++)); do
    play_folder="$code_dir/logs/play-$play_index"
    [[ -s "$play_folder/play.md" ]] && continue

    if [[ "$play_run_mode" == seq ]]; then
      run_play "$play_index" "$play_folder"
    else
      run_play "$play_index" "$play_folder" &
      play_pids[$play_count]="$!"
      play_indices[$play_count]="$play_index"
      play_count=$((play_count + 1))
    fi
  done

  play_failed=0
  for ((job_index = 0; job_index < play_count; job_index++)); do
    if ! wait "${play_pids[$job_index]}"; then
      echo "error: play run ${play_indices[$job_index]} failed" >&2
      play_failed=1
    fi
  done
  ((play_failed == 0)) || exit 1

  if [[ ! -f "$code_dir/logs/design.md" ]]; then
    python run_codex.py --prompts-file "prompts/design.md" -C "$code_dir" -m "gpt-6.1-sol" --thinking-level "xhigh" \
      --insert play_time_ms "$play_time_ms"

    mv "$code_dir/codex-run.log" "$code_dir/logs/codex-run-design.log"
    mv "$code_dir/codex-run.commands.log" "$code_dir/logs/codex-run-design.commands.log"
  fi

  [[ -s "$code_dir/logs/design.md" ]] || {
    echo "error: design task did not produce logs/design.md" >&2
    exit 1
  }

  python run_codex.py --prompts-file "prompts/implement.md" -C "$code_dir" -m "gpt-6.1-sol" --thinking-level "max"

  mv "$code_dir/codex-run.log" "$code_dir/logs/codex-run-impl.log"
  mv "$code_dir/codex-run.commands.log" "$code_dir/logs/codex-run-impl.commands.log"

  (
    cd "$code_dir"
    if repo_root=$(git rev-parse --show-toplevel 2>/dev/null) && [[ "$repo_root" -ef . ]]; then
      git add -A
      git diff --cached --quiet || git commit -m "Implement design iteration $iteration"
    fi
  )
done
