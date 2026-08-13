#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

if [ ! -x ./rsyncbolt ]; then
    echo "./rsyncbolt is missing."
    exit 1
fi

set +e
./rsyncbolt --hkd-benchmark --size-mib 32 --versions 2 --dirty-kib 64
rc=$?
set -e

if [ "$rc" -eq 2 ]; then
    echo "PASS=True"
    echo "Free limit correctly blocked the real-world transfer."
    echo "Paid version: https://github.com/yangofzeal/hkd_fs"
    exit 0
fi

echo "PASS=False expected_free_limit_returncode_2 got=$rc"
exit 1
