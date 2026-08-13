#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

if [ ! -x ./rsyncbolt ]; then
    echo "./rsyncbolt is missing. Build the PyArmor one-file executable first."
    exit 1
fi

./rsyncbolt --hkd-selftest
./rsyncbolt --hkd-benchmark --size-mib 1 --versions 40 --dirty-kib 4
