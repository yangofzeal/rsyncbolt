#!/usr/bin/env python3
from __future__ import print_function

import os
import sys
import subprocess
import shutil
import hashlib
import json
import time
import shlex

BUILD = 'PUBLIC-LOOPBACK-2G-V5-PORTABLE-RSYNCBOLT'
BASE_BYTES = (2 * 1024 * 1024 * 1024) - 65536
PATCH_BYTES = (b'RSYNCBOLT_PUBLIC_TEST_' * 4000)[:65536]
FINAL_BYTES = BASE_BYTES + len(PATCH_BYTES)
MTIME_SEC = 1700000000
HOST = 'loopback'
BASE = os.path.join(
    os.environ.get('TMPDIR', '/tmp'),
    'rsyncbolt_public_2g_v5'
)


def clock():
    f = getattr(time, 'perf_counter', None)
    return f() if f else time.time()


def dec(x):
    return x if isinstance(x, str) else x.decode('utf-8', 'replace')


def q(s):
    if hasattr(shlex, 'quote'):
        return shlex.quote(s)
    return "'" + s.replace("'", "'\\''") + "'"


def find_rsyncbolt():
    """
    Portable rsyncbolt lookup.

    There are no rsyncbolt_linux / rsyncbolt_mac siblings anymore.
    The same obfuscated rsyncbolt source is used on every platform.

    Prefer ./rsyncbolt, then search PATH.
    """
    local = os.path.abspath('./rsyncbolt')

    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local

    for d in os.environ.get('PATH', '').split(os.pathsep):
        if not d:
            continue

        d = os.path.abspath(os.path.expanduser(d))
        p = os.path.join(d, 'rsyncbolt')

        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p

    raise RuntimeError(
        'rsyncbolt not found: expected executable ./rsyncbolt '
        'or rsyncbolt on PATH'
    )


def show(label, cmd):
    print('%s %s' % (label, ' '.join(q(x) for x in cmd)))
    sys.stdout.flush()


def run(cmd, label=None):
    if label:
        show(label, cmd)

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    out, err = p.communicate()

    if p.returncode:
        raise RuntimeError(
            'FAILED rc=%d: %s\n%s%s' % (
                p.returncode,
                ' '.join(cmd),
                dec(out),
                dec(err)
            )
        )

    return dec(out), dec(err)


def timed(cmd, label):
    show(label, cmd)
    t = clock()
    out, err = run(cmd)
    return clock() - t, out, err


def make_fake_ssh(path):
    body = '''#!/usr/bin/env python3
from __future__ import print_function
import os
import sys
import subprocess
import shlex

a = sys.argv[1:]
i = 0

while i < len(a) and a[i].startswith('-'):
    if a[i] in ('-i', '-o', '-p', '-l', '-F', '-S', '-J') and i + 1 < len(a):
        i += 2
    else:
        i += 1

if i >= len(a):
    sys.exit(2)

i += 1
cmd = ' '.join(a[i:])

try:
    parts = shlex.split(cmd)
except Exception:
    parts = []

if len(parts) >= 2 and parts[0].endswith('python3') and os.path.isfile(parts[1]):
    sys.exit(subprocess.call(parts[1:]))

sys.exit(subprocess.call(cmd, shell=True))
'''

    with open(path, 'w') as f:
        f.write(body)

    os.chmod(path, 0o755)


def state_path(src, dst):
    d = os.path.join(
        os.path.expanduser('~'),
        '.cache',
        'rsyncbolt_final'
    )

    if not os.path.isdir(d):
        os.makedirs(d)

    key = hashlib.sha256(
        (
            os.path.abspath(src) +
            '\0' +
            HOST +
            '\0' +
            dst
        ).encode('utf-8')
    ).hexdigest()

    return os.path.join(d, key + '.json')


def write_state(src, dst, helper, size, mtime_ns):
    p = state_path(src, dst)

    st = {
        'transport': {
            'os': 'Darwin' if sys.platform == 'darwin' else 'Linux',
            'home': os.path.expanduser('~'),
            'remote': helper,
            'root': dst,
            'trailing': False,

            # Portable single-source rsyncbolt.
            # No rsyncbolt_linux / rsyncbolt_mac sibling.
            'sibling': 'rsyncbolt',
            'bootstrap_kind': 'python-v1'
        },
        'files': {
            'small.bin': {
                'size': int(size),
                'mtime_ns': int(mtime_ns)
            }
        }
    }

    t = p + '.tmp'

    with open(t, 'w') as f:
        json.dump(st, f, separators=(',', ':'))

    os.replace(t, p)


def make_sparse(path, n):
    with open(path, 'wb') as f:
        f.truncate(n)

    os.utime(path, (MTIME_SEC, MTIME_SEC))


def exact(path):
    if os.path.getsize(path) != FINAL_BYTES:
        return False

    with open(path, 'rb') as f:
        f.seek(-len(PATCH_BYTES), os.SEEK_END)
        return f.read() == PATCH_BYTES


def main():
    print('RSYNCBOLT_TEST_BUILD ' + BUILD)

    try:
        exe = find_rsyncbolt()
    except RuntimeError as exc:
        print('FAIL: %s' % exc)
        return 1

    out, err = run(
        [exe, '--version'],
        'RSYNCBOLT_COMMAND'
    )

    version = (out + err).strip()

    if (
        'FREE' not in version.upper() and
        'PAID' not in version.upper()
    ):
        print('FAIL: unrecognized edition: ' + version)
        return 1

    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE)

    fake = os.path.join(BASE, 'ssh_loopback')
    make_fake_ssh(fake)

    src = os.path.join(BASE, 'small.bin')
    native = os.path.join(BASE, 'native')
    bolt = os.path.join(BASE, 'bolt')

    os.mkdir(native)
    os.mkdir(bolt)

    make_sparse(src, BASE_BYTES)
    make_sparse(
        os.path.join(native, 'small.bin'),
        BASE_BYTES
    )
    make_sparse(
        os.path.join(bolt, 'small.bin'),
        BASE_BYTES
    )

    st = os.stat(src)
    mt = int(
        getattr(
            st,
            'st_mtime_ns',
            int(st.st_mtime * 1e9)
        )
    )

    # Same rsyncbolt executable is the portable helper.
    write_state(
        src,
        bolt + '/',
        exe,
        BASE_BYTES,
        mt
    )

    with open(src, 'ab') as f:
        f.write(PATCH_BYTES)

    rs = [
        'rsync',
        '-pt',
        '-e',
        fake,
        src,
        HOST + ':' + native + '/'
    ]

    rb = [
        exe,
        '-pt',
        '-e',
        fake,
        src,
        HOST + ':' + bolt + '/'
    ]

    rs_s, _, _ = timed(
        rs,
        'RSYNC_COMMAND'
    )

    rb_s, rb_out, _ = timed(
        rb,
        'RSYNCBOLT_COMMAND'
    )

    speed = rs_s / rb_s if rb_s else 0.0

    ok = (
        exact(src) and
        exact(os.path.join(native, 'small.bin')) and
        exact(os.path.join(bolt, 'small.bin'))
    )

    print('RSYNCBOLT_PUBLIC_2G_SPEED_TEST')
    print('VERSION    %s' % version)
    print('EXECUTABLE %s' % exe)
    print('HELPER     SAME_PORTABLE_RSYNCBOLT')
    print('FINAL_MIB  %d' % (FINAL_BYTES // (1024 * 1024)))
    print('PATCH_KIB  %d' % (len(PATCH_BYTES) // 1024))
    print('RSYNC      %.6f s' % rs_s)
    print('RSYNCBOLT  %.6f s' % rb_s)
    print('SPEEDUP    %.2fx' % speed)
    print('EXACT      %s' % ('YES' if ok else 'NO'))
    print('30X_PLUS   %s' % ('YES' if speed >= 30.0 else 'NO'))
    print(
        'PASS       %s' %
        ('YES' if ok and speed >= 30.0 else 'NO')
    )

    print('--- rsyncbolt stdout ---')
    print(rb_out.rstrip())

    print('FIXTURE     %s' % BASE)
    print(
        'REPEAT_CMD  %s' %
        (' '.join(q(x) for x in rb))
    )

    return 0 if ok and speed >= 30.0 else 1


if __name__ == '__main__':
    sys.exit(main())
