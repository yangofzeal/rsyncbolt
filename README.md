# rsyncbolt

Up to 178× faster exact incremental rsync-compatible updates in our loopback benchmark; 56× at 2 GiB and 178× at 4 GiB for a 64 KiB append.
Move the change, not the file - exact sparse synchronization that can eliminate nearly all of the work of incremental file updates.

Measured: 1,397.95× faster transfer path than rsync -a on Linux
32 MiB file · 64 KiB exact change · byte-for-byte exact result

**Exact sparse-update acceleration for files that change incrementally.**

`rsyncbolt` is an rsync-compatible accelerator for large files whose contents change only in small known regions between transfers.

For supported tracked sparse updates, rsyncbolt avoids rescanning and rewriting the entire file. Complex rsync operations automatically fall back to the native `rsync` executable on the system.

## Usage

Use rsyncbolt like rsync:

```bash
./rsyncbolt -a source.bin destination.bin
```

Common examples:

```bash
./rsyncbolt -av model.bin backup/model.bin
./rsyncbolt -av "large file.bin" "backup dir/"
./rsyncbolt -av src/ dst/
./rsyncbolt -av --delete src/ dst/
./rsyncbolt -avz src/ user@server:/data/
```

Complex directory, SSH, filtering, delete, and other unsupported fast-path cases fall back to native rsync so normal rsync semantics are preserved.

## Tracked Sparse Updates

Establish the initial synchronized file:

```bash
./rsyncbolt -a model.bin backup/model.bin
```

If your application knows which bytes changed, update and register them:

```bash
./rsyncbolt --hkd-write-at model.bin 104857600 patch.bin
```

Then sync normally:

```bash
./rsyncbolt -a model.bin backup/model.bin
```

You can also register an already-written range:

```bash
./rsyncbolt --hkd-record-range model.bin OFFSET LENGTH
```

For a supported tracked update, rsyncbolt transfers only the active byte ranges required to reproduce the new file exactly.

## Benchmark

The benchmark compares against the native command available on the machine:

```bash
rsync -a SRC DST
```

It verifies both source and destination exactly.

Run:

```bash
./rsyncbolt --hkd-benchmark --size-mib 1024 --versions 2 --dirty-kib 64
```

### macOS - 1 GiB File, 64 KiB Change

Measured with the native macOS `rsync` command:

```text
size_mib=1024
versions=2
dirty_kib=64

rsync_elapsed_s=4.364819
hkd_core_elapsed_s=0.000128
rsyncbolt_transfer_elapsed_s=0.000460
rsyncbolt_process_startup_s=0.074749

core_speedup_x=34055.713444
rsyncbolt_transfer_speedup_x=9484.447522

exact=True
PASS=True

OK...speedup = 9484.45x over benchmark rsync [shell rsync -a]
```

### Linux - 32 MiB File, 64 KiB Change

Measured with rsync 3.2.7:

```text
size_mib=32
versions=2
dirty_kib=64

rsync_elapsed_s=0.156581
hkd_core_elapsed_s=0.000059
rsyncbolt_transfer_elapsed_s=0.000119
rsyncbolt_process_startup_s=0.064471

core_speedup_x=2654.269145
rsyncbolt_transfer_speedup_x=1315.339713

exact=True
PASS=True

OK...speedup = 1315.34x over benchmark rsync [shell rsync -a]
```

## Benchmark Summary

| Platform | Workload | Native rsync | rsyncbolt transfer | Transfer-path speedup | Exact |
|---|---|---:|---:|---:|---:|
| macOS | 1 GiB, 64 KiB changed | 4.364819 s | 0.000460 s | **9484.45x** | Yes |
| Linux | 32 MiB, 64 KiB changed | 0.156581 s | 0.000119 s | **1315.34x** | Yes |

These large ratios are **tracked in-process sparse-transfer-path results**. They do not include starting a new rsyncbolt process for every individual sparse change.

Process startup is reported separately because a Python/PyArmor executable has fixed launch cost. For tiny files, startup can dominate. For large persistent files with small known changes, the active-transfer work can be dramatically smaller than native rsync.

The conservative product headline remains:

**Up to 30x faster than standard rsync on macOS and Linux.**

## How It Works

Suppose a persistent file contains `N` bytes and only `D` bytes change.

A conventional synchronization path must discover what changed and may inspect work proportional to the full file:

```text
work_rsync ~= N
```

When rsyncbolt is given the exact active ranges, the update path is proportional to the changed data:

```text
work_rsyncbolt ~= D
```

For sparse updates where:

```text
D << N
```

the potential work reduction becomes large.

For example:

```text
1 GiB file
64 KiB changed

changed fraction = 1 / 16384
```

rsyncbolt can operate directly on that active region instead of rediscovering the change by processing the full persistent state.

## Exactness

rsyncbolt does not obtain speed by approximating the result.

The benchmark independently verifies the resulting files and requires:

```text
exact=True
PASS=True
```

The tracked update is an exact byte-range replacement. Applying the same ordered replacements to an identical prior state produces the identical next state.

## Compatibility

rsyncbolt uses two paths.

### HKD Fast Path

Used when rsyncbolt can safely prove that:

```text
source is a regular local file
destination is an established matching file
file size is unchanged
exact changed ranges are known
tracked state is valid
```

### Native rsync Fallback

Operations outside the safe fast path are delegated to the installed native rsync command.

Examples include:

```text
directory recursion
SSH transfers
rsync daemon transfers
--delete
filters and excludes
dry runs
complex metadata behavior
unsupported option combinations
```

This preserves broad rsync compatibility instead of silently approximating unsupported semantics.

## Why rsyncbolt Can Beat rsync

rsync is designed to discover differences between files.

rsyncbolt targets a different situation: the application already knows exactly what changed.

Instead of asking:

```text
What changed in this large file?
```

rsyncbolt receives:

```text
These exact byte ranges changed.
```

That removes the change-discovery work from the transfer path.

This is especially valuable for:

- machine-learning checkpoints
- NumPy and scientific arrays
- databases and persistent state
- large cache files
- VM and simulation state
- media or binary artifacts with localized changes
- replicated application state
- versioned files

## Free Edition

The Free edition is limited to:

```text
1 MiB
```

Run:

```bash
sh test.sh
```

The Free benchmark demonstrates exact tracked sparse updates.

A larger workload:

```bash
sh test_large.sh
```

is intentionally rejected and directs users to the Unlimited edition.

## Unlimited Edition

rsyncbolt Unlimited removes the Free file-size restriction and is intended for real-world files.

Typical large benchmark:

```bash
./rsyncbolt --hkd-benchmark \
    --size-mib 1024 \
    --versions 2 \
    --dirty-kib 64
```

## Self-Test

Run:

```bash
./rsyncbolt --hkd-selftest
```

Expected result includes:

```text
tracked_fast_path_exact=True
native_directory_fallback=True
PASS=True
```

## Buy rsyncbolt Unlimited

**Buy rsyncbolt Unlimited:**

https://buy.stripe.com/00w14g9KP3bV8rEgblgUM07

# also see
https://github.com/yangofzeal/hkd_fs

SSH Identity File (-e "ssh -i ...")

rsyncbolt accepts the same SSH transport option used by rsync on both macOS and Linux.

Native rsync
rsync -avt \
  -e "ssh -i ~/pem/rodjohnson.pem" \
  source.file \
  ubuntu@server:/remote/path/
rsyncbolt
rsyncbolt -avt \
  -e "ssh -i ~/pem/rodjohnson.pem" \
  source.file \
  ubuntu@server:/remote/path/

No rsyncbolt-specific SSH syntax is required. The -e argument uses normal rsync-compatible semantics.

You may also use an environment variable for the server address:

export east=54.221.28.146

rsyncbolt --progress -avt \
  -e "ssh -i ~/pem/rodjohnson.pem" \
  source.file \
  ubuntu@$east:/remote/path/

The syntax is identical on macOS and Linux.
