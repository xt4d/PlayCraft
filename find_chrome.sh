#!/usr/bin/env bash

set -euo pipefail

candidates=("${CHROME_PATH:-}")
windows=false

case "$(uname -s)" in
  Darwin)
    candidates+=(
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
      "${HOME:-}/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
      "/Applications/Chromium.app/Contents/MacOS/Chromium"
      "${HOME:-}/Applications/Chromium.app/Contents/MacOS/Chromium"
    )
    ;;
  Linux)
    candidates+=(
      "$(type -P google-chrome-stable || true)"
      "$(type -P google-chrome || true)"
      "/opt/google/chrome/google-chrome"
      "$(type -P chromium || true)"
      "$(type -P chromium-browser || true)"
      "/snap/bin/chromium"
    )
    ;;
  MINGW*|MSYS*|CYGWIN*)
    windows=true
    program_files_x86=$(printenv 'ProgramFiles(x86)' || true)
    for directory in "${ProgramW6432:-${ProgramFiles:-}}" "$program_files_x86" "${LOCALAPPDATA:-}"; do
      if [[ -n "$directory" ]]; then
        candidates+=("$directory/Google/Chrome/Application/chrome.exe")
      fi
    done
    candidates+=("$(type -P chrome.exe || true)")
    ;;
  *)
    printf 'error: unsupported operating system\n' >&2
    exit 1
    ;;
esac

for candidate in "${candidates[@]}"; do
  if "$windows"; then
    candidate=${candidate//\\//}
  fi
  if [[ -f "$candidate" && -x "$candidate" ]]; then
    if "$windows"; then
      cygpath -am -- "$candidate"
    elif [[ "$candidate" == /* ]]; then
      printf '%s\n' "$candidate"
    else
      printf '%s/%s\n' "$PWD" "$candidate"
    fi
    exit 0
  fi
done

printf 'error: Google Chrome or Chromium executable was not found\n' >&2
exit 1
