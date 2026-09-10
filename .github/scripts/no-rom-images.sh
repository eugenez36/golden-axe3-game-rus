#!/usr/bin/env bash
# Refuse ROM images: used by the pre-commit hook and by the CI guard job.
set -euo pipefail
status=0
for f in "$@"; do
  [ -f "$f" ] || continue
  case "$f" in
    *.bin|*.gen|*.smd|*.32x) echo "ROM image by extension: $f"; status=1; continue ;;
  esac
  if [ "$(stat -c %s "$f")" -ge 524288 ] && head -c 272 "$f" | grep -aq 'SEGA MEGA DRIVE\|SEGA GENESIS'; then
    echo "Mega Drive ROM by header: $f"; status=1
  fi
done
exit $status
