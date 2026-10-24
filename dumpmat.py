"""Dump keymatrix (0x89) or Fn matrix (0x90) tables, read-only. usage: dumpmat.py <89|90> <idx>..."""
import sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from rycmd import open_path, xfer, SAFE_GET  # noqa: E402

cmd = int(sys.argv[1], 16)
assert cmd in SAFE_GET and cmd in (0x89, 0x90)
h = open_path("mi_02")
for idx in (int(x) for x in sys.argv[2:]):
    data = b"".join(xfer(h, [cmd, idx, page])[:64] for page in range(8))
    print(f"T{cmd:02x}.{idx}", data.hex())
