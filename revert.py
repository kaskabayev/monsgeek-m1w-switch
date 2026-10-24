"""Restore keymaps (0x89) and Fn tables (0x90) to the dumps in original/. Windows Python.

usage: python.exe revert.py [--dry-run]
Writes only entries that differ. Keymap writes go to the active profile, so each
profile is selected in turn and the original active profile is restored at the end.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rycmd import open_path, xfer  # noqa: E402

ORIG = Path(__file__).parent / "original"
DRY = "--dry-run" in sys.argv


def load(name):
    return [bytes.fromhex(line.split()[1]) for line in (ORIG / name).read_text().splitlines()]


def dump(h, cmd, idx):
    return b"".join(xfer(h, [cmd, idx, page])[:64] for page in range(8))


def write(h, data):
    if DRY:
        print("  would send", bytes(data).hex(" "))
        return
    xfer(h, data)
    time.sleep(0.5)


def diffs(cur, orig):
    return [i for i in range(128) if cur[i * 4:i * 4 + 4] != orig[i * 4:i * 4 + 4]]


h = open_path("mi_02")
for t, orig in enumerate(load("fn.txt")):
    for i in diffs(dump(h, 0x90, t), orig):
        print(f"fn table {t} key {i}: restore {orig[i * 4:i * 4 + 4].hex()}")
        write(h, [0x15, t, i, 0, 0, 0, 0, 0, *orig[i * 4:i * 4 + 4]])

active = xfer(h, [0x85])[1]
touched = False
for p, orig in enumerate(load("keymatrix.txt")):
    todo = diffs(dump(h, 0x89, p), orig)
    if not todo:
        continue
    touched = True
    write(h, [0x05, p])
    for i in todo:
        print(f"profile {p + 1} key {i}: restore {orig[i * 4:i * 4 + 4].hex()}")
        write(h, [0x13, p, i, 0, 0, 0, 0, 0, *orig[i * 4:i * 4 + 4]])
if touched:
    write(h, [0x05, active])
if DRY:
    sys.exit(print("dry run done"))

# Writes can drop silently, so verify against the dumps.
left = [f"fn table {t} keys {d}" for t, o in enumerate(load("fn.txt")) if (d := diffs(dump(h, 0x90, t), o))]
left += [f"profile {p + 1} keys {d}" for p, o in enumerate(load("keymatrix.txt")) if (d := diffs(dump(h, 0x89, p), o))]
if left:
    sys.exit("NOT restored, run again: " + "; ".join(left))
print("done: all tables match original/")
