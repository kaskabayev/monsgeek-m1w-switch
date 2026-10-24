"""Read-only HID enumeration for VID 0x3151 via Windows hid.dll/setupapi (ctypes, no deps)."""
import ctypes
import sys
from ctypes import wintypes as W

VID = 0x3151

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [("D1", W.DWORD), ("D2", W.WORD), ("D3", W.WORD), ("D4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("Guid", GUID), ("Flags", W.DWORD), ("Reserved", ctypes.c_void_p)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", W.ULONG), ("VendorID", W.USHORT), ("ProductID", W.USHORT), ("VersionNumber", W.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", W.USHORT), ("UsagePage", W.USHORT),
        ("InputReportByteLength", W.USHORT), ("OutputReportByteLength", W.USHORT),
        ("FeatureReportByteLength", W.USHORT), ("Reserved", W.USHORT * 17),
        ("NumberLinkCollectionNodes", W.USHORT),
        ("NumberInputButtonCaps", W.USHORT), ("NumberInputValueCaps", W.USHORT), ("NumberInputDataIndices", W.USHORT),
        ("NumberOutputButtonCaps", W.USHORT), ("NumberOutputValueCaps", W.USHORT), ("NumberOutputDataIndices", W.USHORT),
        ("NumberFeatureButtonCaps", W.USHORT), ("NumberFeatureValueCaps", W.USHORT), ("NumberFeatureDataIndices", W.USHORT),
    ]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", W.USHORT), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
        ("BitField", W.USHORT), ("LinkCollection", W.USHORT), ("LinkUsage", W.USHORT), ("LinkUsagePage", W.USHORT),
        ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte), ("IsDesignatorRange", ctypes.c_ubyte),
        ("IsAbsolute", ctypes.c_ubyte), ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte),
        ("BitSize", W.USHORT), ("ReportCount", W.USHORT), ("Reserved2", W.USHORT * 5),
        ("UnitsExp", W.ULONG), ("Units", W.ULONG), ("LogicalMin", W.LONG), ("LogicalMax", W.LONG),
        ("PhysicalMin", W.LONG), ("PhysicalMax", W.LONG),
        ("UsageMin", W.USHORT), ("UsageMax", W.USHORT), ("Pad", W.USHORT * 6),
    ]


DIGCF_PRESENT, DIGCF_DEVICEINTERFACE = 0x2, 0x10
OPEN_EXISTING = 3
FILE_SHARE_RW = 0x3
INVALID_HANDLE = ctypes.c_void_p(-1).value

setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), W.LPCWSTR, W.HWND, W.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), W.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p, W.DWORD, W.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]
hid.HidD_GetAttributes.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS), ctypes.POINTER(W.USHORT), ctypes.c_void_p]
for fn in ("HidD_GetProductString", "HidD_GetManufacturerString", "HidD_GetSerialNumberString"):
    getattr(hid, fn).argtypes = [ctypes.c_void_p, ctypes.c_void_p, W.ULONG]


def hid_paths():
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    hdi = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    i = 0
    while True:
        did = SP_DEVICE_INTERFACE_DATA(cbSize=ctypes.sizeof(SP_DEVICE_INTERFACE_DATA))
        if not setupapi.SetupDiEnumDeviceInterfaces(hdi, None, ctypes.byref(guid), i, ctypes.byref(did)):
            break
        i += 1
        need = W.DWORD()
        setupapi.SetupDiGetDeviceInterfaceDetailW(hdi, ctypes.byref(did), None, 0, ctypes.byref(need), None)
        buf = ctypes.create_string_buffer(need.value)
        ctypes.cast(buf, ctypes.POINTER(W.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        if setupapi.SetupDiGetDeviceInterfaceDetailW(hdi, ctypes.byref(did), buf, need, None, None):
            yield ctypes.wstring_at(ctypes.addressof(buf) + 4)


def hstr(h, fn):
    b = ctypes.create_unicode_buffer(256)
    return b.value if getattr(hid, fn)(h, b, ctypes.sizeof(b)) else None


def value_caps(pp, kind, n):
    if not n:
        return []
    arr = (HIDP_VALUE_CAPS * n)()
    cnt = W.USHORT(n)
    hid.HidP_GetValueCaps(kind, arr, ctypes.byref(cnt), pp)
    return [(c.ReportID, hex(c.UsagePage), c.BitSize, c.ReportCount) for c in arr[: cnt.value]]



if __name__ == "__main__":
    for path in hid_paths():
        if f"vid_{VID:04x}" not in path.lower():
            continue
        h = k32.CreateFileW(path, 0, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
        if h in (None, INVALID_HANDLE):
            print(path, "OPEN FAIL", ctypes.get_last_error())
            continue
        a = HIDD_ATTRIBUTES(Size=ctypes.sizeof(HIDD_ATTRIBUTES))
        hid.HidD_GetAttributes(h, ctypes.byref(a))
        pp = ctypes.c_void_p()
        hid.HidD_GetPreparsedData(h, ctypes.byref(pp))
        caps = HIDP_CAPS()
        hid.HidP_GetCaps(pp, ctypes.byref(caps))
        print(path)
        print(f"  {a.VendorID:04x}:{a.ProductID:04x} ver={a.VersionNumber:04x} "
              f"mfr={hstr(h, 'HidD_GetManufacturerString')!r} prod={hstr(h, 'HidD_GetProductString')!r} "
              f"sn={hstr(h, 'HidD_GetSerialNumberString')!r}")
        print(f"  usage_page=0x{caps.UsagePage:04x} usage=0x{caps.Usage:04x} "
              f"in={caps.InputReportByteLength} out={caps.OutputReportByteLength} feat={caps.FeatureReportByteLength}")
        print(f"  in_vals={value_caps(pp, 0, caps.NumberInputValueCaps)}")
        print(f"  out_vals={value_caps(pp, 1, caps.NumberOutputValueCaps)}")
        print(f"  feat_vals={value_caps(pp, 2, caps.NumberFeatureValueCaps)}")
        hid.HidD_FreePreparsedData(pp)
        k32.CloseHandle(h)
