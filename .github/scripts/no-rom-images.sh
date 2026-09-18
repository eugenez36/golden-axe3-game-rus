#!/usr/bin/env bash
# Refuse ROM images: used by the pre-commit hook and by the CI guard job.
#
# Portable on purpose (GNU and BSD userlands): no `stat -c`, and the header
# probe is read into a variable so `pipefail` cannot turn an early-exiting
# `grep -q` into a false negative.
set -euo pipefail
status=0
for f in "$@"; do
  [ -f "$f" ] || continue
  case "$f" in
    *.bin|*.gen|*.smd|*.32x) echo "ROM image by extension: $f"; status=1; continue ;;
  esac
  size=$(wc -c < "$f")
  if [ "$size" -ge 524288 ]; then
    header=$(head -c 272 "$f" | LC_ALL=C tr -d '\000')
    case "$header" in
      *"SEGA MEGA DRIVE"*|*"SEGA GENESIS"*) echo "Mega Drive ROM by header: $f"; status=1 ;;
    esac
  fi
done
exit $status
