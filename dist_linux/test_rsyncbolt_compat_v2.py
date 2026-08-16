#!/usr/bin/env python3
from __future__ import print_function

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile

BUILD = "RSYNCBOLT_RSYNC_COMPAT_V2"

def dec(x):
    return x if isinstance(x, str) else x.decode("utf-8", "replace")

def q(s):
    try:
        import shlex
        return shlex.quote(s)
    except Exception:
        return "'" + s.replace("'", "'\\''") + "'"

def run(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return p.returncode, dec(out), dec(err)

def choose_client():
    src = os.path.abspath("./rsyncbolt_unlimited.py")
    exe = os.path.abspath("./rsyncbolt")
    if os.path.isfile(src):
        return [sys.executable, src], "source"
    if os.path.isfile(exe) and os.access(exe, os.X_OK):
        return [exe], "packaged"
    raise RuntimeError(
        "need sibling ./rsyncbolt_unlimited.py or executable ./rsyncbolt"
    )

def write_file(path, data, mode=None, mtime=None):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "wb") as f:
        f.write(data)
    if mode is not None:
        os.chmod(path, mode)
    if mtime is not None:
        os.utime(path, (mtime, mtime))

def make_fixture(root):
    os.makedirs(root)

    # Ordinary file.
    write_file(os.path.join(root, "plain.txt"),
               b"plain\n", 0o640, 1700000101)

    # Spaces in name.
    write_file(os.path.join(root, "name with spaces.txt"),
               b"spaces\n", 0o600, 1700000102)

    # UTF-8 name and UTF-8 contents.
    write_file(os.path.join(root, u"café-雪-δ.txt"),
               u"utf8-✓\n".encode("utf-8"), 0o644, 1700000103)

    # Hidden file and hidden directory.
    write_file(os.path.join(root, ".hidden"),
               b"dotfile\n", 0o600, 1700000104)
    os.makedirs(os.path.join(root, ".hidden_dir"))
    write_file(os.path.join(root, ".hidden_dir", "inside"),
               b"inside\n", 0o644, 1700000105)

    # Empty directory.
    os.makedirs(os.path.join(root, "empty dir"))

    # Deep nesting + executable bit.
    write_file(os.path.join(root, "nested", "deep", "run.sh"),
               b"#!/bin/sh\necho hi\n", 0o751, 1700000106)

    # Name beginning with '-'.
    write_file(os.path.join(root, "-looks-like-option"),
               b"dash\n", 0o644, 1700000107)

    # Shell metacharacters are literal filename characters.
    write_file(os.path.join(root, "semi;colon$(echo nope).txt"),
               b"literal\n", 0o644, 1700000108)

    # Newline in filename (legal POSIX filename).
    write_file(os.path.join(root, "line\nbreak.txt"),
               b"newline-name\n", 0o644, 1700000109)

    # Quotes, brackets, wildcard-looking characters.
    write_file(os.path.join(root, "quote'and\"double[1]*?.txt"),
               b"quoted\n", 0o644, 1700000110)

    # Symlinks: regular, directory, dangling, and relative parent traversal.
    if hasattr(os, "symlink"):
        os.symlink("plain.txt", os.path.join(root, "link-to-plain"))
        os.symlink("nested", os.path.join(root, "link-to-dir"))
        os.symlink("does-not-exist", os.path.join(root, "dangling-link"))
        os.makedirs(os.path.join(root, "links"))
        os.symlink("../plain.txt", os.path.join(root, "links", "relative-parent-link"))

    # Directory metadata.
    os.chmod(os.path.join(root, "nested"), 0o750)
    os.utime(os.path.join(root, "nested"), (1700000111, 1700000111))
    os.chmod(os.path.join(root, "empty dir"), 0o700)
    os.utime(os.path.join(root, "empty dir"), (1700000112, 1700000112))

def snapshot(root):
    out = []

    def rec(cur, rel):
        names = os.listdir(cur)
        names.sort(key=lambda n: os.fsencode(n))
        for name in names:
            p = os.path.join(cur, name)
            r = name if not rel else rel + "/" + name
            st = os.lstat(p)
            mode = stat.S_IMODE(st.st_mode)
            mtime = int(st.st_mtime)

            if stat.S_ISLNK(st.st_mode):
                out.append((r, "L", mode, mtime, os.readlink(p)))
            elif stat.S_ISDIR(st.st_mode):
                out.append((r, "D", mode, mtime, None))
                rec(p, r)
            elif stat.S_ISREG(st.st_mode):
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    while True:
                        b = f.read(1024 * 1024)
                        if not b:
                            break
                        h.update(b)
                out.append(
                    (r, "F", mode, mtime, st.st_size, h.hexdigest())
                )
            else:
                out.append(
                    (r, "OTHER", mode, mtime, stat.S_IFMT(st.st_mode))
                )
    rec(root, "")
    return out

def compare(a, b):
    sa = snapshot(a)
    sb = snapshot(b)
    if sa == sb:
        return True, ""

    n = max(len(sa), len(sb))
    for i in range(n):
        aa = sa[i] if i < len(sa) else "<missing>"
        bb = sb[i] if i < len(sb) else "<missing>"
        if aa != bb:
            return False, (
                "FIRST_DIFF_NATIVE=%r\nFIRST_DIFF_RSYNCBOLT=%r\n"
                "NATIVE_COUNT=%d RSYNCBOLT_COUNT=%d"
                % (aa, bb, len(sa), len(sb))
            )
    return False, "snapshots differ"

def one_case(name, native_cmd, bolt_cmd, native_root, bolt_root):
    print("")
    print("CASE " + name)
    print("NATIVE_COMMAND    " + " ".join(q(x) for x in native_cmd))
    rc1, out1, err1 = run(native_cmd)
    print("RSYNCBOLT_COMMAND " + " ".join(q(x) for x in bolt_cmd))
    rc2, out2, err2 = run(bolt_cmd)

    same, diff = compare(native_root, bolt_root)
    rc_same = (rc1 == rc2)
    ok = rc_same and same

    print("NATIVE_RC         %d" % rc1)
    print("RSYNCBOLT_RC      %d" % rc2)
    print("RETURN_CODE_MATCH %s" % ("YES" if rc_same else "NO"))
    print("TREE_MATCH        %s" % ("YES" if same else "NO"))

    if out2.strip():
        print("--- rsyncbolt stdout ---")
        print(out2.rstrip())
    if err2.strip():
        print("--- rsyncbolt stderr ---")
        print(err2.rstrip())
    if not same:
        print(diff)

    return ok

def main():
    print("RSYNCBOLT_TEST_BUILD " + BUILD)
    client, kind = choose_client()
    print("CLIENT_KIND=" + kind)
    print("CLIENT=" + " ".join(q(x) for x in client))

    td = tempfile.mkdtemp(prefix="rsyncbolt_compat_")
    try:
        src = os.path.join(td, "src")
        make_fixture(src)

        results = []

        # 1. Archive semantics with trailing slash:
        # copies contents of src into destination.
        native1 = os.path.join(td, "native_archive")
        bolt1 = os.path.join(td, "bolt_archive")
        os.makedirs(native1)
        os.makedirs(bolt1)
        results.append(one_case(
            "ARCHIVE_SYMLINK_UTF8_WEIRD_NAMES",
            ["rsync", "-a", src + "/", native1 + "/"],
            client + ["-a", src + "/", bolt1 + "/"],
            native1, bolt1
        ))

        # 2. No trailing slash:
        # rsync creates a src directory inside destination.
        native2 = os.path.join(td, "native_no_slash")
        bolt2 = os.path.join(td, "bolt_no_slash")
        os.makedirs(native2)
        os.makedirs(bolt2)
        results.append(one_case(
            "TRAILING_SLASH_QUIRK",
            ["rsync", "-a", src, native2 + "/"],
            client + ["-a", src, bolt2 + "/"],
            native2, bolt2
        ))

        # 3. --delete removes destination-only entries.
        native3 = os.path.join(td, "native_delete")
        bolt3 = os.path.join(td, "bolt_delete")
        shutil.copytree(native1, native3, symlinks=True)
        shutil.copytree(bolt1, bolt3, symlinks=True)
        write_file(os.path.join(native3, "DESTINATION_ONLY"), b"junk\n")
        write_file(os.path.join(bolt3, "DESTINATION_ONLY"), b"junk\n")
        results.append(one_case(
            "DELETE_QUIRK",
            ["rsync", "-a", "--delete", src + "/", native3 + "/"],
            client + ["-a", "--delete", src + "/", bolt3 + "/"],
            native3, bolt3
        ))

        # 4. Existing destination file changes type from regular file to symlink.
        native4 = os.path.join(td, "native_type_change")
        bolt4 = os.path.join(td, "bolt_type_change")
        os.makedirs(native4)
        os.makedirs(bolt4)
        shutil.copy2(os.path.join(src, "plain.txt"),
                     os.path.join(native4, "link-to-plain"))
        shutil.copy2(os.path.join(src, "plain.txt"),
                     os.path.join(bolt4, "link-to-plain"))
        results.append(one_case(
            "FILE_TO_SYMLINK_REPLACEMENT",
            ["rsync", "-a", src + "/", native4 + "/"],
            client + ["-a", src + "/", bolt4 + "/"],
            native4, bolt4
        ))

        # 5. Existing destination directory contains stale nested data,
        # but without --delete rsync intentionally leaves it behind.
        native5 = os.path.join(td, "native_no_delete")
        bolt5 = os.path.join(td, "bolt_no_delete")
        os.makedirs(native5)
        os.makedirs(bolt5)
        write_file(os.path.join(native5, "stale", "keep-me"), b"stale\n")
        write_file(os.path.join(bolt5, "stale", "keep-me"), b"stale\n")
        results.append(one_case(
            "NO_DELETE_LEAVES_STALE_FILES",
            ["rsync", "-a", src + "/", native5 + "/"],
            client + ["-a", src + "/", bolt5 + "/"],
            native5, bolt5
        ))

        ok = all(results)

        print("")
        print("RSYNC_COMPATIBILITY_RESULTS")
        labels = [
            "ARCHIVE_SYMLINK_UTF8_WEIRD_NAMES",
            "TRAILING_SLASH_QUIRK",
            "DELETE_QUIRK",
            "FILE_TO_SYMLINK_REPLACEMENT",
            "NO_DELETE_LEAVES_STALE_FILES",
        ]
        for label, passed in zip(labels, results):
            print("%-36s %s" % (label, "YES" if passed else "NO"))
        print("PASS                                 %s" %
              ("YES" if ok else "NO"))

        return 0 if ok else 1
    finally:
        shutil.rmtree(td, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
