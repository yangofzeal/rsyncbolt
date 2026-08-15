#!/usr/bin/env python
from __future__ import print_function
import os
import subprocess
import sys

# Works with BOTH Free and Paid.
# Free is allowed to exercise a large sparse logical file only inside
# ./rsyncbolt --benchmark. Normal Free transfers remain capped at 1 MiB.
SIZE_MIB = os.environ.get("SIZE_MIB", "1024")
DIRTY_KIB = os.environ.get("DIRTY_KIB", "64")
VERSIONS = os.environ.get("VERSIONS", "2")

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    bolt = os.path.join(here, "rsyncbolt")
    if not os.path.isfile(bolt) or not os.access(bolt, os.X_OK):
        print("ERROR: expected executable ./rsyncbolt beside test.py")
        return 2

    cmd = [
        bolt, "--benchmark",
        "--size-mib", SIZE_MIB,
        "--versions", VERSIONS,
        "--dirty-kib", DIRTY_KIB,
    ]
    print("command=./rsyncbolt --benchmark --size-mib %s --versions %s --dirty-kib %s" %
          (SIZE_MIB, VERSIONS, DIRTY_KIB))
    return subprocess.call(cmd)

if __name__ == "__main__":
    raise SystemExit(main())
