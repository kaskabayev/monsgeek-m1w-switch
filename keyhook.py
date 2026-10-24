"""Log modifier/F-key/media key-downs for N seconds via WH_KEYBOARD_LL (Windows, ctypes).

Other keys are not logged, so normal typing is never recorded."""
import ctypes
import sys
import threading
import time
from ctypes import wintypes as W

u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)

NAMES = {0x5B: "LWIN", 0x5C: "RWIN", 0xA4: "LALT", 0xA5: "RALT", 0xA2: "LCTRL", 0xA3: "RCTRL",
         0xA0: "LSHIFT", 0xA1: "RSHIFT", 0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4", 0x74: "F5", 0x75: "F6",
         0xAD: "VOL_MUTE", 0xAE: "VOL_DOWN", 0xAF: "VOL_UP", 0xB3: "PLAY_PAUSE"}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", W.DWORD), ("scanCode", W.DWORD), ("flags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, W.WPARAM, W.LPARAM)
u32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, W.HINSTANCE, W.DWORD]
u32.SetWindowsHookExW.restype = ctypes.c_void_p
u32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, W.WPARAM, W.LPARAM]
u32.CallNextHookEx.restype = ctypes.c_ssize_t
k32.GetModuleHandleW.restype = W.HMODULE


@HOOKPROC
def proc(n, wp, lp):
    if n == 0 and wp in (0x100, 0x104):  # WM_KEYDOWN, WM_SYSKEYDOWN
        k = ctypes.cast(lp, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if k.vkCode in NAMES or 0x70 <= k.vkCode <= 0x7B:
            print(time.strftime("%H:%M:%S"), f"vk=0x{k.vkCode:02x} {NAMES.get(k.vkCode, '')} scan=0x{k.scanCode:02x}",
                  flush=True)
    return u32.CallNextHookEx(None, n, wp, lp)


secs = float(sys.argv[1]) if len(sys.argv) > 1 else 60
hook = u32.SetWindowsHookExW(13, proc, k32.GetModuleHandleW(None), 0)
tid = k32.GetCurrentThreadId()
threading.Timer(secs, lambda: u32.PostThreadMessageW(tid, 0x12, 0, 0)).start()  # WM_QUIT
print(f"hooked={bool(hook)} for {secs}s", flush=True)
msg = W.MSG()
while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
    pass
u32.UnhookWindowsHookEx(hook)
