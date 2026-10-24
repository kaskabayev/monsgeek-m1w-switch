# monsgeek-m1w-switch

Goal: switch the MonsGeek M1W between Mac and Windows modes without the physical switch under the Caps Lock keycap.

Status: on firmware 1.08 the firmware's built-in Cmd/Option swap follows only the physical switch. No OS flag, key action or profile key moves it. A host-side `SET_PROFILE` to a profile with swapped keys works, but needs a script on each host. The Fn-layer OS mode **can** be set from a key. See [Results](#results) and [Recommended setup](#recommended-setup).

All findings come from one keyboard, tested over USB on Windows. Treat other firmware versions as unverified.

## Device

| Item | Value |
|---|---|
| Model | MonsGeek M1W, ISO, 82 keys |
| USB ID | `3151:4015`, manufacturer string `ROYUAN` |
| Firmware | 1.08 (`GET 0x80` → `08 01`) |
| Device ID | 983 = `0x03D7` (`GET 0x8F` → `d7 03`), `yc500_m1wnosled_soc` |
| Driver class | `CommonKbYc500` → `CommonKbYc200` → `CommonKbYzw` in the MonsGeek web driver |

HID interfaces:

| Interface | Usage page / usage | Reports | Use |
|---|---|---|---|
| MI_00 | 0x01 / 0x06 | in 9, out 2 | Boot keyboard |
| MI_01 COL01 | 0x0C / 0x01 | in 3 | Consumer keys |
| MI_01 COL02 | 0x01 / 0x80 | in 2 | System control |
| MI_01 COL03 | 0x01 / 0x06 | in 16 | NKRO keyboard |
| MI_01 COL04 | 0x01 / 0x02 | in 8 | Mouse |
| MI_01 COL05 | 0xFFFF / 0x01 | in 4, report ID 5 | Vendor events |
| MI_02 | 0xFFFF / 0x02 | feature 65, report ID 0 | Vendor commands |

## Protocol

### Command frame

- Send a 64-byte feature report (report ID 0) to MI_02. Then read a feature report back.
- Byte 0 is the command. Bytes 1–6 are parameters. Byte 7 is the checksum. Bytes 8+ are the payload.
- Checksum: `b[7] = 255 - (sum(b[0..6]) & 0xFF)`.
- Most GET replies echo the command in byte 0. `0x89` and `0x90` return raw data with no echo.
- Wait about 0.5 s between writes. One of eight back-to-back writes was dropped with no error. Read back after each write.

### Command IDs (YC500 numbering)

**Warning:** the M1W does not use the RY5088 numbering in `monsgeek-akko-linux/docs/PROTOCOL.md`. For example, `0x09` is SET_KEYMATRIX here, not SET_KBOPTION. `0x02` is factory reset.

Verified on this device:

| ID | Name | Format / result |
|---|---|---|
| `0x80` | GET_REV | `80 08 01` → v1.08 |
| `0x8F` | GET_USB_VERSION | `8f d7 03` → device ID 983 |
| `0x85` | GET_PROFILE | byte 1 = active profile, 0-based |
| `0x05` | SET_PROFILE | `05 <profile>`. Works. |
| `0x86` | GET_KBOPTION | `86 <idx>` → byte 2 = flags, byte 3 = Fn matrix, byte 4 = power save |
| `0x06` | SET_KBOPTION | `06 <idx> <flags> <fn> <ps>`. Accepted and saved. See results. |
| `0x89` | GET_KEYMATRIX | `89 <profile> <page 0-7>` → 64 raw bytes per page, 8 pages |
| `0x90` | GET_FN | `90 <table> <page 0-7>` → 64 raw bytes per page, 8 pages |
| `0x13` | SET_KEYMATRIX_SIMPLE | `13 xx <key> 00 00 00 00 <chk> <a0 a1 a2 a3>`. **Byte 1 is ignored. It writes to the active profile.** |
| `0x15` | SET_FN_SIMPLE | `15 <table> <key> 00 00 00 00 <chk> <a0 a1 a2 a3>`. Byte 1 selects the table. |
| `0x97` | GET_AUTOOS_EN | Reply is identical to the request. Support is unproven. |

KBOPTION flags byte (from the driver's `getOldKBOption`, bit 1 confirmed on device):

| Bit | Meaning |
|---|---|
| 0 | Win key lock |
| 1 | OS: 1 = Mac, 0 = Windows |
| 3 | WASD/arrow swap |
| 4 | LED off |
| 5 | Side LED off |
| 6 | Keyboard mode |
| 7 | Keyboard lock |

**Do not send these** (from the YC500 driver source; `0x7F` from the RY5088 notes; not tested):

| ID | Name |
|---|---|
| `0x02` | Factory reset |
| `0x09` | SET_KEYMATRIX, chunked full-table write |
| `0x10` | SET_FN, chunked full-table write |
| `0xAC` | Flash chip erase |
| `0x30`, `0x31`, `0xB0`, `0xB1` | OLED bootloader |
| `0x40`, `0x41`, `0xC0`, `0xC1` | MLED bootloader |
| `0x7F` | Enter bootloader |

### Vendor events (MI_01 COL05, report ID 5)

| Bytes | Meaning |
|---|---|
| `05 03 <flags> 02` | OS mode changed. `<flags>` is the KBOPTION flags byte. `02` = Mac. |
| `05 03 <flags> 03` | WASD swap toggled (Fn+W). For example, `0a` = Mac + swapped. |
| `05 0f 01 00` / `05 0f 00 00` | Flash save started / finished |

### Physical switch

- Top (Mac): emits `05 03 02 02`. Cmd/Option are swapped.
- Middle (wired, battery off): emits `05 03 00 02`. This is Windows mode.
- Bottom (Win, wireless): no extra event when coming from the middle.
- The USB device stays connected in all three positions when the cable is plugged in.
- At power-up the firmware sets the OS mode from the switch again. A software-set OS flag does not survive a replug.

### Key matrix

- 128 entries × 4 bytes per profile or Fn table. Six rows per column. Column-major.
- Action format: `[type, b1, b2, b3]`.

| Type | Meaning | Example |
|---|---|---|
| `00` | Key, `[00, 00, keycode, 00]` or `[00, 00, modifier, key]` | `0000e314` = GUI+Q |
| `03` | Consumer, `[03, 00, lo, hi]` | `0300e900` = volume up |
| `08` | Profile, `[08, 00, 04, n]` | Default Fn+F9–F12. **No effect on this firmware.** |
| `0A` | Special function, `[0A, sub, b2, 00]` | See below |
| `0D` | LED control | Fn+arrows, Fn+Home/PgUp/PgDn/End |
| `0E` | Connection, `[0E, 00, n, 00]` | 0/1/2 = BT1–3, 5 = 2.4G, 6 = wired |
| `12` | Shortcut | `1200e32c` = Siri |

Useful key indexes (decimal):

| Index | Key |
|---|---|
| 6 | Knob click, inferred (`0A 0E` = knob mode toggle) |
| 9 | A |
| 15 | S |
| 17 | Key right of Left Ctrl (`LGUI` in profile) |
| 23 | Key left of Space (`LALT` in profile) |
| 59 | Right Alt |
| 65 | Fn |
| 94 / 95 | Knob rotation (volume down / up) |

Indexes are decimal. `rycmd.py` takes hex: 9 → `09`, 15 → `0f`, 17 → `11`, 23 → `17`.

Fn tables: indexes 0 and 1 are Windows. Indexes 2 and 3 are Mac.

Factory Fn bindings (Windows table):

| Combo | Action |
|---|---|
| Fn+E / R / T | `0E` BT1 / BT2 / BT3 |
| Fn+Y | `0E` 2.4G |
| Fn+U | `0E` wired |
| Fn+W | `0A 0A` WASD swap |
| Fn+Win | `0A 03` Win lock |
| Fn+` | `0A 02` |
| Fn+Space | `0A 08` |
| Fn+L | `0A 09` |
| Fn+RAlt | `0A 0B` |
| Fn+RShift | `0A 0C` |
| Fn+RCtrl | `0A 17` |

Sub-code names in the RY5088 firmware map are: 02 game mode, 03 Win lock, 05 OS mode, 08 BT pairing, 09 Fn toggle, 0A WASD, 0B NKRO, 0C Fn lock, 0E knob mode, 17 RCtrl modifier. Only 03, 05, 0A and 0E are confirmed on the M1W.

Full factory dumps: [`original/keymatrix.txt`](original/keymatrix.txt) (profiles 1–4) and [`original/fn.txt`](original/fn.txt) (Fn tables 0–3). One line per table, 512 bytes in hex.

## Results

Each test used a low-level keyboard hook on Windows. It logged the codes from the key left of Space and the key right of Left Ctrl. Windows layout gives `LALT` / `LWIN`. Mac layout gives `LWIN` / `LALT`.

| # | Test | OS event | Fn layer | Cmd/Option swap |
|---|---|---|---|---|
| 1 | Physical switch to top | `05 03 02 02` | Mac | **Yes** |
| 2 | `SET_KBOPTION` flags bit 1 = 1 | none (save only) | not tested | No. Reset on replug. |
| 3 | Fn-table action `[0A 05 01 00]` (OS = Mac) | `05 03 02 02` | Mac (Fn+F6 sent F6) | No |
| 4 | Test 3, then Fn+W twice (layout rebuild) | WASD events | Mac | No |
| 5 | `05 01` (SET_PROFILE, profile 2) + profile 2 with LGUI/LALT swapped | — | — | **Yes** (software only) |
| 6 | Fn-table action `[08 00 04 n]` (profile switch) | none | — | No. Profile did not change. |

Conclusions:

- The built-in Cmd/Option swap follows the physical switch only. It does not follow the OS flag.
- The OS_MODE key action changes only the Fn layer (brightness, Mission Control, media keys).
- Profile-switch key actions do nothing on this firmware, not even the factory Fn+F9–F12.
- `SET_PROFILE` from the host works. A host-side script could therefore select a "Mac" profile. This needs the vendor channel over Bluetooth or the 2.4G dongle, which is not tested.

## Recommended setup

1. Move the switch to the bottom position (Win) one time. Leave it there.
2. Windows: no change.
3. Mac: connect over Bluetooth (Fn+E). Open System Settings → Keyboard → Keyboard Shortcuts → Modifier Keys. Select the MonsGeek and swap Option and Command. macOS stores this per device. If you use the 2.4G dongle on the Mac, set it again for that device.
4. Change computers with Fn+E/R/T (Bluetooth 1–3), Fn+Y (2.4G) or Fn+U (wired).
5. Optional: bind Fn+A to Mac Fn layer and Fn+S to Windows Fn layer:

   ```
   python.exe rycmd.py set 15 <table> 09 00 00 00 00 00 0a 05 01 00 --i-know   # Fn+A -> Mac
   python.exe rycmd.py set 15 <table> 0f 00 00 00 00 00 0a 05 00 00 --i-know   # Fn+S -> Win
   ```

   Run both lines for `<table>` = 00, 01, 02 and 03. Wait 0.5 s between writes. Press the connection key first, then Fn+A. It is not known whether the setting survives a connection change or sleep.

## Tools

The tools use Windows Python 3 with ctypes only, so they need no packages. From WSL, run them with `python.exe`.

| File | Use |
|---|---|
| `hidenum.py` | List all HID interfaces of `3151:*` with usage and report sizes. Read-only. |
| `rycmd.py` | `get <cmd> [params]` (allowlisted GETs), `set <cmd> [params] --i-know` (allowlisted SETs: 05, 06, 13, 15, 17), `listen [s]` (vendor events), `monitor [s]` (poll state). |
| `dumpmat.py` | `dumpmat.py 89 0 1 2 3` dumps keymaps. `dumpmat.py 90 0 1 2 3` dumps Fn tables. |
| `keyhook.py` | Log modifier, F-key and media key presses. It does not log other keys. |
| `revert.py` | Restore all keymaps and Fn tables to `original/`. It checks the result. `--dry-run` shows the planned writes. |

`original/` holds this ISO keyboard's factory dumps. On another board, dump your own tables first, or `revert.py` writes this board's entries onto yours.

Do not run `monitor` during dumps or writes. It shares the feature channel and mixes replies.

## Open questions

- AutoOS (`0x17` / `0x97`): does the firmware support it, and does it change the Cmd/Option swap?
- Can the host reach the vendor channel over Bluetooth or the 2.4G dongle? If yes, a host-side `SET_PROFILE` script could switch the layout automatically.
- What does the switch's Mac mode do to Right Alt and Right Ctrl?
- Does the Fn-layer OS mode survive a connection change or sleep on battery?

## References

- [echtzeit-solutions/monsgeek-akko-linux](https://github.com/echtzeit-solutions/monsgeek-akko-linux): protocol notes, extracted web-driver code (`protocol/hid_protocol_core.js`), RY5088 special-function map (`iot_driver_linux/src/key_action.rs`).
- MonsGeek web driver: classes `CommonKbYzw`, `CommonKbYc200`, `CommonKbYc500`.
