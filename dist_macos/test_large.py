#!/usr/bin/env python
from __future__ import print_function
import os
import subprocess
import sys
import webbrowser

CHECKOUT = "https://buy.stripe.com/00w14g9KP3bV8rEgblgUM07"
SIZE_MIB = os.environ.get("SIZE_MIB", "4096")
DIRTY_KIB = os.environ.get("DIRTY_KIB", "64")
VERSIONS = os.environ.get("VERSIONS", "2")

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    bolt = os.path.join(here, "rsyncbolt")
    if not os.path.isfile(bolt) or not os.access(bolt, os.X_OK):
        print("ERROR: expected executable ./rsyncbolt beside test_large.py")
        return 2

    p = subprocess.Popen([bolt, "--hkd-version"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode:
        if err:
            sys.stderr.write(err.decode("utf-8", "replace"))
        return p.returncode

    version = (out or b"").decode("utf-8", "replace").upper()
    if "EDITION=FREE" in version:
        print("PAID_REQUIRED=True")
        print("test_large.py requires rsyncbolt Paid.")
        print(CHECKOUT)
        try:
            webbrowser.open(CHECKOUT, new=2)
        except Exception:
            pass
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
