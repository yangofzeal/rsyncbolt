#!/usr/bin/env bash
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BOLT="$HERE/rsyncbolt"
TMP="${TMPDIR:-/tmp}/rsyncbolt_easy.$$"
trap 'rm -f "$TMP"' EXIT

if [ ! -x "$BOLT" ]; then
  echo "ERROR: put executable ./rsyncbolt beside test_easy.sh"
  exit 2
fi

# 31 versions means 30 tiny updates.
"$BOLT" --benchmark --size-mib 32 --versions 31 --dirty-kib 64 > "$TMP"

RSYNC30=$(awk -F= '/^rsync_elapsed_s=/{print $2}' "$TMP")
BOLT30=$(awk -F= '/^rsyncbolt_cli_equivalent_s=/{print $2}' "$TMP")
EXACT=$(awk '/^EXACT/{print $2}' "$TMP")
ONE_RSYNC=$(awk -v x="$RSYNC30" 'BEGIN{printf "%.6f",x/30.0}')
PER_UPDATE=$(awk -v r="$RSYNC30" -v b="$BOLT30" 'BEGIN{printf "%.2f",r/b}')
THIRTY_FIT=$(awk -v r="$ONE_RSYNC" -v b="$BOLT30" 'BEGIN{print (b<=r)?"YES":"NO"}')
RANGE=$(awk -v x="$PER_UPDATE" 'BEGIN{print (x>=30 && x<=90)?"YES":"NO"}')

printf '%s\n' "========================================"
printf '%s\n' "RSYNCBOLT: 30 UPDATES VS 1 RSYNC"
printf '%s\n' "========================================"
printf 'One average rsync:       %s seconds\n' "$ONE_RSYNC"
printf '30 rsyncbolt updates:    %s seconds\n' "$BOLT30"
printf 'rsyncbolt speed/update:  %sx\n' "$PER_UPDATE"
printf '30 bolt updates fit:     %s\n' "$THIRTY_FIT"
printf '30x-to-90x range:        %s\n' "$RANGE"
printf 'Exact:                   %s\n' "$EXACT"
printf '%s\n' "========================================"
printf '%s\n' "Kid-simple meaning:"
printf '%s\n' "30 rsyncbolt updates take less time than one normal rsync update."
