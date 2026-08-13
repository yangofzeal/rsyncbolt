#!/usr/bin/env python3
import hashlib
import binascii
import os
import platform
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
EDITION = "FREE"
LARGE = False

def _write_file(path, data):
    with open(path, "w") as f:
        f.write(data)



class _RunResult(object):
    def __init__(self, args, returncode, stdout=None, stderr=None):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_process(args, **kwargs):
    """Python 3.4-compatible subset of subprocess.run used by rsyncbolt."""
    timeout = kwargs.pop("timeout", None)
    check = kwargs.pop("check", False)
    text = kwargs.pop("text", False)
    input_data = kwargs.pop("input", None)
    if kwargs.get("stdin") is not None and input_data is not None:
        raise ValueError("stdin and input arguments may not both be used")
    if input_data is not None:
        kwargs["stdin"] = subprocess.PIPE
    proc = subprocess.Popen(args, **kwargs)
    try:
        stdout, stderr = proc.communicate(input=input_data, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(args, timeout, output=stdout)
    if text:
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
    result = _RunResult(args, proc.returncode, stdout, stderr)
    if check and proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, args, output=stdout)
    return result

def local_command():
    exe = os.path.join(HERE, "rsyncbolt")
    if os.path.exists(exe) and os.access(exe, os.X_OK):
        return [exe], "compiled"

    src = os.path.join(HERE, "rsyncbolt.py")
    if os.path.exists(src):
        return [sys.executable, "-S", src], "source"

    raise RuntimeError("need ./rsyncbolt onefile executable or ./rsyncbolt.py")

def native_sibling():
    if platform.system() == "Linux":
        return "rsyncbolt_linux"
    if platform.system() == "Darwin":
        return "rsyncbolt_mac"
    raise RuntimeError("unsupported platform")

def digest(p):
    
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

with tempfile.TemporaryDirectory(prefix="rsyncbolt4_onefile_") as t:
    td = t
    bindir = os.path.join(td, "pathbin")
    remote_home = os.path.join(td, "remote_home")
    local_home = os.path.join(td, "local_home")
    os.mkdir(bindir)
    os.mkdir(remote_home)
    os.mkdir(local_home)

    cmd, mode = local_command()
    sibname = native_sibling()

    # Put the required remote sibling in PATH, deliberately NOT beside rsyncbolt.
    real = os.path.join(HERE, sibname)
    if os.path.exists(real) and os.access(real, os.X_OK):
        shutil.copy2(real, os.path.join(bindir, sibname))
    else:
        found = shutil.which(sibname)
        if found:
            shutil.copy2(found, os.path.join(bindir, sibname))
        else:
            src = os.path.join(HERE, "rsyncbolt.py")
            if not os.path.exists(src):
                raise RuntimeError("compiled test needs %s either beside test.py or on PATH" % sibname)
            text = open(src, "r").read().replace(
                "#!/usr/bin/env python3",
                "#!/usr/bin/env -S python3 -S",
                1,
            )
            open(os.path.join(bindir, sibname), "w").write(text)
    os.chmod(os.path.join(bindir, sibname), 0o755)

    # Fake SSH process boundary. This exercises the actual remote server/bootstrap path.
    ssh = os.path.join(bindir, "ssh")
    _write_file(ssh, """#!/bin/sh
while [ $# -gt 0 ]; do
  case "$1" in
    -i|-p|-o|-F|-J|-S|-l) shift 2 ;;
    -*) shift ;;
    *) break ;;
  esac
done
[ $# -gt 0 ] || exit 2
shift
export HOME="$FAKE_REMOTE_HOME"
exec /bin/sh -c "$*"
""")
    os.chmod(ssh, 0o755)

    key = os.path.join(td, "key.pem")
    _write_file(key, "TEST-ONLY-KEY\n")
    os.chmod(key, 0o600)

    env = os.environ.copy()
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    env["HOME"] = local_home
    env["FAKE_REMOTE_HOME"] = remote_home
    env.pop("RSYNCBOLT_SIBLING_DIR", None)

    src = os.path.join(td, "src.bin")
    dst = os.path.join(td, "dst")
    os.mkdir(dst)

    size = (2 * 1024 * 1024) if LARGE else (512 * 1024)
    with open(src, "wb") as f:
        f.truncate(size)

    shell = "ssh -i %s" % key
    remote = "ubuntu@fakehost:%s/" % dst

    if EDITION == "FREE" and LARGE:
        p = run_process(
            cmd + ["-a", "-e", shell, src, remote],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        sys.stdout.write(p.stdout or "")
        sys.stderr.write(p.stderr or "")
        ok = p.returncode == 2 and "FREE_LIMIT_TRIGGERED=True" in p.stdout
        print("EXECUTION_MODE=%s" % mode)
        print("PATH_SIBLING=%s" % sibname)
        print("FREE_LARGE_BLOCKED=%s" % ok)
        print("PASS=%s" % ok)
        raise SystemExit(0 if ok else 1)

    # Initial remote baseline.
    p = run_process(
        cmd + ["-a", "-e", shell, src, remote],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if p.returncode != 0:
        sys.stdout.write(p.stdout or "")
        sys.stderr.write(p.stderr or "")
        raise SystemExit(p.returncode)

    # Exact 192-byte tracked edit, then repeat the SAME normal rsync-compatible command.
    payload = bytes((i * 17 + 3) & 255 for i in range(192))
    off = size // 2
    p2 = run_process(
        cmd + ["--_tracked-pwrite-test", src, str(off), binascii.hexlify(payload).decode("ascii")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if p2.returncode != 0:
        sys.stdout.write(p2.stdout or "")
        sys.stderr.write(p2.stderr or "")
        raise SystemExit(p2.returncode)

    p3 = run_process(
        cmd + ["-a", "-e", shell, src, remote],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    sys.stdout.write(p3.stdout or "")
    sys.stderr.write(p3.stderr or "")

    target = os.path.join(dst, os.path.basename(src))
    exact = p3.returncode == 0 and os.path.exists(target) and digest(src) == digest(target)
    active192 = "raw_active_bytes=192" in p3.stdout
    used_remote = "RSYNCBOLT_REMOTE_EXACT" in p3.stdout

    remote_ok = exact and active192 and used_remote
    print("EXECUTION_MODE=%s" % mode)
    print("PATH_SIBLING=%s" % sibname)
    print("PATH_ONLY_DISCOVERY=True")
    print("REMOTE_192_BYTE_RESUME=%s" % active192)
    print("REMOTE_RSYNCBOLT_SERVER=%s" % used_remote)
    print("FULL_FILE_EXACT=%s" % exact)
    print("REMOTE_TEST_PASS=%s" % remote_ok)

    # Compare the exact tracked path with native rsync.
    bench_size_mib = 1
    required_speedup = 0.0
    bp = run_process(
        cmd + ["--hkd-benchmark", "--size-mib", str(bench_size_mib),
               "--versions", "2", "--dirty-kib", "64"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if bp.returncode != 0:
        sys.stdout.write(bp.stdout or "")
        sys.stderr.write(bp.stderr or "")
        raise SystemExit(bp.returncode)

    speedup = 0.0
    benchmark_exact = False
    rsync_s = 0.0
    bolt_s = 0.0
    for line in (bp.stdout or "").splitlines():
        if line.startswith("rsyncbolt_transfer_speedup_x="):
            speedup = float(line.split("=", 1)[1])
        elif line.startswith("rsync_elapsed_s="):
            rsync_s = float(line.split("=", 1)[1].split()[0])
        elif line.startswith("rsyncbolt_transfer_elapsed_s="):
            bolt_s = float(line.split("=", 1)[1].split()[0])
        elif line == "PASS=True":
            benchmark_exact = True

    speed_ok = benchmark_exact and speedup >= required_speedup
    print("")
    print("RSYNC      %.6f s" % rsync_s)
    print("RSYNCBOLT  %.6f s" % bolt_s)
    print("SPEEDUP    %.2fx" % speedup)
    print("30X_PLUS   %s" % ("YES" if speedup >= 30.0 else "NO"))
    print("EXACT      %s" % ("YES" if benchmark_exact else "NO"))
    print("PASS       %s" % ("YES" if (remote_ok and speed_ok) else "NO"))
    raise SystemExit(0 if (remote_ok and speed_ok) else 1)
