#!/usr/bin/env bash
# chaos.sh — make random file changes to test tidgit
# Usage: ./testground/chaos.sh [count]  (default: 5 changes)

set -euo pipefail
cd "$(git rev-parse --show-toplevel)/testground"

COUNT="${1:-5}"
WORDS=(foo bar baz qux zap nix emu owl yak cod elk gnu)
EXTS=(txt py js md csv json)

rand() { echo $(( RANDOM % $1 )); }
pick() { local arr=("$@"); echo "${arr[$(rand ${#arr[@]})]}"; }
stamp() { date +%s%N | tail -c 8; }

for ((i = 1; i <= COUNT; i++)); do
  action=$(rand 4)
  name="file_$(pick "${WORDS[@]}")_$(stamp).$(pick "${EXTS[@]}")"

  # find an existing file (if any) for modify/delete actions
  existing=$(find . -maxdepth 1 -type f ! -name 'chaos.sh' | shuf -n1 2>/dev/null || true)

  case $action in
    0|1)  # create new file
      lines=$(( RANDOM % 20 + 3 ))
      for ((l = 0; l < lines; l++)); do
        echo "$(pick "${WORDS[@]}") $(pick "${WORDS[@]}") $(( RANDOM % 1000 )) — line $l"
      done > "$name"
      echo "  + created $name ($lines lines)"
      ;;
    2)  # modify existing file
      if [[ -n "$existing" ]]; then
        echo "$(pick "${WORDS[@]}") changed at $(date +%T)" >> "$existing"
        sed -i '' "s/$(pick "${WORDS[@]}")/CHANGED/" "$existing" 2>/dev/null || true
        echo "  ~ modified $existing"
      else
        echo "hello world $(stamp)" > "$name"
        echo "  + created $name (nothing to modify yet)"
      fi
      ;;
    3)  # delete existing file
      if [[ -n "$existing" ]]; then
        echo "  - deleted $existing"
        rm "$existing"
      else
        echo "data $(stamp)" > "$name"
        echo "  + created $name (nothing to delete yet)"
      fi
      ;;
  esac
done

echo ""
echo "Done — $COUNT changes made in testground/"
