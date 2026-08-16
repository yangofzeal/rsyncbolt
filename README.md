# rsyncbolt

**Move the change, not the file.**

`rsyncbolt` is an rsync-compatible accelerator for large files with
small incremental changes. It preserves exact output and uses native
`rsync` compatibility fallback when an operation is outside its
accelerated path.

Recent Unlimited benchmarks:

-   **Linux remote SSH:** 53.60× faster --- 2 GiB file, 64 KiB append.
-   **macOS remote SSH:** 28.32× faster --- 2 GiB file, 64 KiB append.
-   **Linux loopback:** 235.16× faster --- 4 GiB file, 64 KiB append.
-   **macOS loopback:** 122.32× faster --- 4 GiB file, 64 KiB append.

All reported runs produced exact destination files. Speedup depends on
file size, change sparsity, storage, network, and SSH overhead.

## Usage

Use `rsyncbolt` like `rsync`:

``` bash
./rsyncbolt -avt source.bin backup/
./rsyncbolt -avt src/ dst/
./rsyncbolt -avt --delete src/ dst/
```

Remote SSH uses normal rsync syntax:

``` bash
rsync -pt \
  -e "ssh -i ~/pem/key.pem" \
  large.bin \
  ubuntu@server:/data/
```

``` bash
./rsyncbolt -pt \
  -e "ssh -i ~/pem/key.pem" \
  large.bin \
  ubuntu@server:/data/
```

No rsyncbolt-specific SSH syntax is required.

## Real Remote Benchmark Results

### Linux → Linux over SSH

Unlimited packaged Linux build, 2 GiB file with a 64 KiB incremental
append:

``` text
COMMAND 'rsync' '-pt' '-e' 'ssh -i /home/ubuntu/pem/key.pem' \
'large.bin' 'ubuntu@server:/tmp/benchmark/native/'

COMMAND './rsyncbolt' '-pt' '-e' 'ssh -i /home/ubuntu/pem/key.pem' \
'large.bin' 'ubuntu@server:/tmp/benchmark/bolt/'

EAST_BENCHMARK
SIZE_MIB   2048
PATCH_KIB  64
RSYNC      34.314610 s
RSYNCBOLT  0.640203 s
SPEEDUP    53.60x
EXACT      YES
30X_PLUS   YES
PASS       YES

RSYNCBOLT_REMOTE_EXACT
remote_os=Linux sibling=rsyncbolt_linux bootstrapped=False
files_changed=1 chunks_sent=1 raw_active_bytes=65536
wire_payload_bytes=437
PASS=True
```

### macOS → Linux over SSH

Unlimited source build on macOS, 2 GiB file with a 64 KiB incremental
append:

``` text
COMMAND rsync -pt -e 'ssh -i ~/pem/key.pem' \
large.bin ubuntu@server:/tmp/benchmark/native/

COMMAND python3 rsyncbolt_unlimited.py -pt -e 'ssh -i ~/pem/key.pem' \
large.bin ubuntu@server:/tmp/benchmark/bolt/

EAST_BENCHMARK
SIZE_MIB   2048
PATCH_KIB  64
RSYNC      26.309420 s
RSYNCBOLT  0.928865 s
SPEEDUP    28.32x
EXACT      YES

RSYNCBOLT_REMOTE_EXACT
remote_os=Linux sibling=rsyncbolt_linux bootstrapped=False
files_changed=1 chunks_sent=1 raw_active_bytes=65536
wire_payload_bytes=437
PASS=True
```

The important fast-path result is that a 64 KiB change required one
changed chunk:

``` text
chunks_sent=1
raw_active_bytes=65536
```

instead of treating the entire 2 GiB file as active data.

## Larger Loopback Results

The included public tests also exercise the same sparse-update path
without requiring a public server:

  -------------------------------------------------------------------------------
  Platform         File     Change       rsync   rsyncbolt       Speedup Exact
  ---------- ---------- ---------- ----------- ----------- ------------- --------
  Linux           4 GiB     64 KiB 59.866868 s  0.254574 s   **235.16×** Yes

  macOS           4 GiB     64 KiB 30.572189 s  0.249935 s   **122.32×** Yes

  Linux           2 GiB     64 KiB 34.511984 s  0.243727 s   **141.60×** Yes

  macOS           2 GiB     64 KiB 14.935974 s  0.285632 s    **52.29×** Yes
  -------------------------------------------------------------------------------

Run:

``` bash
python test.py
python test_large.py
```

If `/tmp` is too small, put the test fixtures on another filesystem:

``` bash
mkdir -p /mnt/bigdisk/tmp
export TMPDIR=/mnt/bigdisk/tmp
python test.py
python test_large.py
```

## How It Works

For an established synchronized file, rsyncbolt records exact changed
ranges. If a large file has only a small known change, the accelerated
path can process the changed region instead of rediscovering the change
across the whole file.

For example:

``` text
file size = 2 GiB
change    = 64 KiB
```

The measured fast path above reported:

``` text
files_changed=1
chunks_sent=1
raw_active_bytes=65536
```

The result remains byte-for-byte exact.

## Compatibility

`rsyncbolt` has two paths:

**Fast path:** supported exact incremental file and directory-tree
updates, including SSH remote synchronization through the appropriate
`rsyncbolt_linux` or `rsyncbolt_mac` helper.

**Compatibility path:** operations outside the safe accelerator are
delegated to native `rsync`, preserving rsync behavior rather than
approximating unsupported semantics.

The compatibility test suite covers cases such as symlinks, dangling
symlinks, UTF-8 and unusual filenames, dotfiles, empty directories,
permissions, mtimes, trailing-slash behavior, and `--delete`.

## Free and Unlimited

The **Free edition supports files up to 2 GiB** and can run `test.py`.

`test_large.py` uses a 4 GiB file and therefore requires Unlimited; the
Free build directs the user to the Unlimited edition.

## Buy rsyncbolt Unlimited

**Buy rsyncbolt Unlimited:**

https://buy.stripe.com/00w14g9KP3bV8rEgblgUM07

## Also See

https://github.com/yangofzeal/hkd_fs
