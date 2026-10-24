"""MonsGeek/RongYuan vendor HID feature-report tool (Windows, ctypes, no deps).

usage: rycmd.py get <cmd_hex> [param bytes hex ...]      (allowlisted YC500 GET only)
       rycmd.py set <cmd_hex> [param bytes hex ...] --i-know  (allowlisted SET only)
       rycmd.py listen [seconds]                         (vendor event reports, ID 5)
       rycmd.py monitor [seconds]                        (poll presence + 0x80/0x86, log changes)
"""
import ctypes
import sys
import time
from ctypes import wintypes as W

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from hidenum import hid, k32, hid_paths  # noqa: E402

VID_PID = "vid_3151&pid_4015"
GENERIC_RW = 0x80000000 | 0x40000000
# YC500 numbering (CommonKbYzw/Yc200/Yc500). 0x02 = factory reset, 0x09 = keymatrix write,
# 0xAC = flash erase, 0xB0/B1/C0/C1 = bootloaders: never send those.
SAFE_GET = {0x80, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8B, 0x8C, 0x8F, 0x90, 0x91, 0x92, 0x97}
SAFE_SET = {0x05, 0x06, 0x13, 0x15, 0x17}  # PROFILE, KBOPTION, SET_KEYMATRIX_SIMPLE, SET_FN_SIMPLE, AUTOOS_EN
FEAT_LEN = 65

hid.HidD_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, W.ULONG]
hid.HidD_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, W.ULONG]
k32.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]


def open_path(match, required=True):
    for p in hid_paths():
        if VID_PID in p.lower() and match in p.lower():
            h = k32.CreateFileW(p, GENERIC_RW, 3, None, 3, 0, None)
            if h in (None, ctypes.c_void_p(-1).value):
                if not required:
                    return None
                sys.exit(f"open failed {ctypes.get_last_error()}: {p}")
            return h
    if required:
        sys.exit(f"no interface matching {match}")
    return None


def frame(data):
    d = list(data) + [0] * (8 - len(data)) if len(data) < 8 else list(data)
    d[7] = 255 - (sum(d[:7]) & 0xFF)
    return d


def xfer(h, data):
    buf = (ctypes.c_ubyte * FEAT_LEN)(0, *frame(data))
    if not hid.HidD_SetFeature(h, buf, FEAT_LEN):
        sys.exit(f"SetFeature failed {ctypes.get_last_error()}")
    for _ in range(5):
        time.sleep(0.05)
        rb = (ctypes.c_ubyte * FEAT_LEN)()
        if not hid.HidD_GetFeature(h, rb, FEAT_LEN):
            sys.exit(f"GetFeature failed {ctypes.get_last_error()}")
        if rb[1] == data[0]:
            return bytes(rb[1:])
    return bytes(rb[1:])


def listen(secs):
    h = open_path("mi_01&col05")
    end = time.time() + secs
    buf = (ctypes.c_ubyte * 4)()
    n = W.DWORD()
    print(f"listening {secs}s on vendor input (blocking reads)...", flush=True)
    while time.time() < end:
        if k32.ReadFile(h, buf, 4, ctypes.byref(n), None):
            print(time.strftime("%H:%M:%S"), bytes(buf[: n.value]).hex(" "), flush=True)


def monitor(secs):
    import threading

    def events():
        buf, n = (ctypes.c_ubyte * 4)(), W.DWORD()
        while True:
            h = open_path("mi_01&col05", required=False)
            while h and k32.ReadFile(h, buf, 4, ctypes.byref(n), None):
                print(time.strftime("%H:%M:%S"), "EVENT", bytes(buf[: n.value]).hex(" "), flush=True)
            if h:
                k32.CloseHandle(h)
            time.sleep(0.3)

    threading.Thread(target=events, daemon=True).start()
    last, end = None, time.time() + secs
    print(f"monitoring {secs}s", flush=True)
    while time.time() < end:
        h = open_path("mi_02", required=False)
        if h is None:
            state = "ABSENT"
        else:
            try:
                state = " | ".join(xfer(h, d)[:5].hex(" ") for d in ([0x80], [0x86, 0], [0x86, 1]))
            except SystemExit as e:
                state = f"ERR {e}"
            k32.CloseHandle(h)
        if state != last:
            print(time.strftime("%H:%M:%S"), state, flush=True)
            last = state
        time.sleep(0.3)


def main(argv):
    if not argv:
        sys.exit(__doc__)
    if argv[0] == "listen":
        return listen(float(argv[1]) if len(argv) > 1 else 30)
    if argv[0] == "monitor":
        return monitor(float(argv[1]) if len(argv) > 1 else 180)
    data = [int(x, 16) for x in argv[1:] if x != "--i-know"]
    if argv[0] == "get" and data[0] not in SAFE_GET:
        sys.exit(f"get allowed only for {sorted(hex(c) for c in SAFE_GET)}")
    if argv[0] == "set" and (data[0] not in SAFE_SET or "--i-know" not in argv):
        sys.exit(f"set allowed only for {sorted(hex(c) for c in SAFE_SET)} with --i-know")
    h = open_path("mi_02")
    r = xfer(h, data)
    print(r.hex(" "))


if __name__ == "__main__":
    main(sys.argv[1:])
