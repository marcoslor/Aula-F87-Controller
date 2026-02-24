# AULA F87 HID Protocol

Reverse-engineered from USB captures of the OEM Windows app (Wireshark + USBPcap).
Confirmed working on macOS via `aula_f87.py`.

## USB Identifiers

| Mode | VID | PID |
|------|------|------|
| Wired | `0x258A` | `0x010C` |
| Wireless (2.4G dongle) | `0x3554` | `0xFA09` |

The keyboard exposes multiple HID collections. Control messages use **vendor-specific** collections (usage page `0xFF00`–`0xFFFF`). On the wireless dongle, both `0xFF02` and `0xFF04` accept commands identically.

## Fragment Layout

All communication uses **20-byte HID Output Reports**. There are no 520-byte packets — the keyboard speaks in individual 20-byte fragments:

```
Byte   Purpose
----   -------
 [0]   Report ID       (always 0x13)
 [1]   Command         (see Command Table)
 [2]   Sub-command     (0x0A=config, 0x25=palette, 0x1C=per-key, 0x01=confirm)
 [3]   Sequence        (fragment index within a multi-fragment message)
[4–18] Payload         (15 bytes, depends on command)
 [19]  Checksum        (sum of bytes 0–18, mod 256)
```

Every fragment sent by the host receives an **echo** — the keyboard returns the same 20 bytes. Always read the echo before sending the next fragment.

## Command Table

| Cmd byte | Name | Direction | Description |
|----------|------|-----------|-------------|
| `0x44` | READ | Host→KB | Request current config (keyboard responds with 10 fragments) |
| `0x04` | WRITE | Host→KB | Write config (10 fragments, keyboard echoes each) |
| `0x09` | COLOR | Host→KB | Write color palette (37 fragments, keyboard echoes each) |
| `0x02` | PERKEY | Host→KB | Write per-key color map (28 fragments, keyboard echoes each) |
| `0x0A` | SAVE | Host→KB | Commit changes to flash |
| `0x88` | AUDIO | Host→KB | Stream audio visualization data (variable fragments, keyboard echoes each) |

## Effect Change Sequence

The OEM app always performs these 4 phases in order. Skipping any phase causes the keyboard to ignore the change.

### Phase 1: Read Current Config

Send one READ/CONFIRM fragment:

```
TX: 13 44 01 00  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  [checksum]
     ^  ^  ^  ^
     |  |  |  seq=0
     |  |  subcmd=CONFIRM (0x01)
     |  cmd=READ (0x44)
     report_id=0x13
```

The keyboard responds with 10 fragments (seq 0–9), each with `cmd=0x44, subcmd=0x0A`:

```
RX: 13 44 0A 00  0E 00 BB SS 01 00 00 04 04 07 AF EE 20 03 00  [checksum]
                              ^^                   ^^  ^^  ^^
                              |                    |   |   color mode
                              |                    |   effect number (SW index 1-18 or 21)
                              brightness (0-4)     apply flag (must be 0x00 on write)
```

### Phase 2: Write Config (Read-Modify-Write)

Take the 10 fragments from phase 1, change `cmd` from `0x44` to `0x04`, modify the desired bytes in seq 0, recalculate checksum, and send all 10 back. The keyboard echoes each fragment.

**Config fragment 0 (seq=0) key bytes:**

| Offset | Purpose | Values |
|--------|---------|--------|
| 6 | Brightness | 0–4 (only in older understanding; see Per-Effect Table below for actual storage) |
| 7 | Speed | 0–4 (only in older understanding; see Per-Effect Table below for actual storage) |
| 8 | Confirm flag | **Must be `0x01`** on write |
| 14 | Apply flag | **Must be `0x00`** on write. The keyboard sets this to `0x01` after applying. Writing `0x01` is a no-op. |
| 15 | Effect number | 1–18 (built-in) or 21 (self-define / per-key) |
| 17 | Color mode | `0x01` = custom color or colorful, `0x03` = default |

Fragments seq 1–9 contain per-effect settings, key mapping / zone data, and are passed through unchanged (except for the per-effect table entries if adjusting speed/brightness).

### Per-Effect Speed & Brightness Table

Each effect stores its own brightness and speed values in config fragments 4–6. The layout uses paired bytes `[brightness] [speed_byte]` for each effect:

```
cfg[4]: [0E FFFF] [eff1_B eff1_S] [eff2_B eff2_S] [eff3_B eff3_S] [eff4_B eff4_S] [eff5_B eff5_S] [eff6_B eff6_S]
cfg[5]: [0E]      [eff7_B eff7_S] [eff8_B eff8_S] [eff9_B eff9_S] [eff10_B eff10_S] [eff11_B eff11_S] [eff12_B eff12_S] [eff13_B eff13_S]
cfg[6]: [0E]      [eff14_B eff14_S] [eff15_B eff15_S] [eff16_B eff16_S] [eff17_B eff17_S] [eff18_B eff18_S] [pad]
```

**Fragment byte offsets for each effect:**

| Effect(s) | Config seq | First byte offset |
|-----------|------------|-------------------|
| 1–6       | 4          | 7 + (N-1)×2       |
| 7–13      | 5          | 5 + (N-7)×2       |
| 14–18     | 6          | 5 + (N-14)×2      |

**Brightness byte:** Direct value 0–4.

**Speed byte encoding:**

```
Bits:  [speed:4][mode:4]
         ^^^^    ^^^^
         0-4     0x7 = colorful (rainbow)
                 0x0 = single-color
```

The high nibble stores the speed (0–4). The low nibble stores the color mode: `0x7` for colorful/rainbow, `0x0` for single-color. Example: `0x47` = speed 4, colorful.

### Phase 3: Write Color Palette

Send 37 fragments with `cmd=0x09, subcmd=0x25`, seq 0x00–0x24. The payload contains RGB triplets for the effect's color slots. The final fragment (seq 0x24) has a `0x5AA5` trailer as an end marker.

**Palette fragment 1 (seq=1) custom color slot:**

| Offset | Purpose | Values |
|--------|---------|--------|
| 8 | Red | 0–255 |
| 9 | Green | 0–255 |
| 10 | Blue | 0–255 |
| 12 | Active flag | `0xFF` when custom color is active |

The OEM app sends this palette on every effect change, even for effects that don't use custom colors.

### Phase 4: Save

Send one SAVE/CONFIRM fragment:

```
TX: 13 0A 01 00  04 07 00 00 00 00 00 00 00 00 00 00 00 00 00  [checksum]
```

## Per-Key RGB Mode (Self-Define)

Fully implemented in `aula_f87.py`. Uses effect number **21** (`0x15`, "Self_define") with a dedicated per-key color map protocol.

### Sequence

1. **Read config** — same as Phase 1 above
2. **Write config** — set effect to 21, confirm flag=`0x01`, apply flag=`0x00`, color mode=`0x01`
3. **Write per-key map** — 28 fragments with `cmd=0x02, subcmd=0x1C`
4. **Save** — same as Phase 4 above

### Per-Key Color Map Layout

The map uses 3 separate color planes (R, G, B), each spanning 9 fragments of 14 bytes, covering 126 LED indices. Fragment 27 is a trailer.

```
Total: 28 fragments  (seq 0–27)
  Plane R:  seq  0– 8  (9 fragments × 14 bytes = 126 entries)
  Plane G:  seq  9–17
  Plane B:  seq 18–26
  Trailer:  seq 27     (6 bytes: [0x06 ... 0x5A 0xA5 ...])
```

**Each fragment payload (bytes 4–18):**

| Offset | Purpose |
|--------|---------|
| 4 | `0x0E` (data marker) |
| 5–18 | 14 color values for consecutive LED indices |

LED index within a plane: `fragment_within_plane × 14 + byte_position` (0-indexed within the 14 data bytes).

**Trailer fragment (seq 27):**

```
Payload: 06 00 00 5A A5 00 00 00 00 00 00 00 00 00 00
                  ^^^^^ end marker
```

## Critical Discovery: Byte 14 (Apply Flag)

The most important protocol detail: **byte 14 of config fragment 0 must be `0x00` when writing.** The keyboard firmware sets it to `0x01` after applying a config. If you read the current config and write it back without clearing byte 14, the keyboard treats it as "already applied" and ignores the write entirely.

This was the key fix that made the script work.

## Checksum

```
checksum = sum(fragment[0:19]) & 0xFF
```

Simple modular sum of the first 19 bytes, stored in byte 19.

## 19 Supported Effects

The effect number in byte 15 is the **software index** (1st column of `LedOpt` in KB.ini), not the hardware ID:

| # | Name | Speed | Color |
|---|------|-------|-------|
| 1 | Fixed_on | no | yes |
| 2 | Respire | yes | yes |
| 3 | Rainbow | yes | no |
| 4 | Flash_away | yes | yes |
| 5 | Raindrops | yes | yes |
| 6 | Rainbow_wheel | yes | yes |
| 7 | Ripples_shining | yes | yes |
| 8 | Stars_twinkle | yes | yes |
| 9 | Shadow_disappear | yes | yes |
| 10 | Retro_snake | yes | yes |
| 11 | Neon_stream | yes | yes |
| 12 | Reaction | yes | yes |
| 13 | Sine_wave | yes | yes |
| 14 | Retinue_scanning | yes | yes |
| 15 | Rotating_windmill | yes | no |
| 16 | Colorful_waterfall | yes | no |
| 17 | Blossoming | yes | no |
| 18 | Rotating_storm | yes | yes |
| 21 | Self_define (per-key) | no | no |

All effects support brightness 0–4. Effects with "Speed: yes" support speed 0–4.
Effects with "Color: yes" support both `--color R G B` (single color) and `--colorful` (rainbow) modes.

## Key Map (87-key TKL)

LED indices from KB.ini `K#` entries:

| Row | Keys (name=led_index) |
|-----|----------------------|
| F-row | Esc=0, F1=12, F2=18, F3=24, F4=30, F5=36, F6=42, F7=48, F8=54, F9=60, F10=66, F11=72, F12=78, PrtSc=84, ScrLk=90, Pause=96 |
| Number | \`=1, 1=7, 2=13, 3=19, 4=25, 5=31, 6=37, 7=43, 8=49, 9=55, 0=61, -=67, ==73, Bksp=79, Ins=85, Home=91, PgUp=97 |
| QWERTY | Tab=2, Q=8, W=14, E=20, R=26, T=32, Y=38, U=44, I=50, O=56, P=62, [=68, ]=74, \\=80, Del=86, End=92, PgDn=98 |
| Home | Caps=3, A=9, S=15, D=21, F=27, G=33, H=39, J=45, K=51, L=57, ;=63, '=69, Enter=81 |
| Shift | LShift=4, Z=10, X=16, C=22, V=28, B=34, N=40, M=46, ,=52, .=58, /=64, RShift=82, Up=94 |
| Ctrl | LCtrl=5, LWin=11, LAlt=17, Space=35, RAlt=53, Fn=59, App=65, RCtrl=83, Left=89, Down=95, Right=101 |

### Key Group Aliases

For convenience, the following group names can be used to address multiple keys at once:

| Group | Keys |
|-------|------|
| `wasd` | W, A, S, D |
| `arrows` | Up, Down, Left, Right |
| `fkeys` | F1–F12 |
| `numrow` | 1–0 |

## Audio Streaming Mode (Audio Dance)

Reverse-engineered from pcapng captures of the OEM "Audio Dance" feature. The PC performs all audio processing host-side and streams per-key brightness updates to the keyboard in real-time.

### Protocol

Uses `cmd=0x88` with **no read/config/save phases** — just stream directly.

| Field | Value | Notes |
|-------|-------|-------|
| byte 1 | `0x88` | Audio streaming command |
| byte 2 (subcmd) | `0x01`–`0x0E` | Number of fragments in this frame |
| byte 3 | `0x00`–`N` | Fragment sequence, resets each frame |
| byte 4 | `0x1E` (non-last) / `0x10+N` (last) | Payload length marker |
| bytes 5–18 | Data | `(brightness, led_index)` pairs |
| byte 19 | Checksum | Standard `sum(0:19) & 0xFF` |

**Idle frame**: subcmd=`0x01`, single fragment, payload `0x23` + zeros.

**Active frame**: subcmd = number of fragments = `ceil(data_bytes / 14)`. Each fragment carries 14 bytes of data (except the last, which may be shorter). The OEM app sends each frame 3–5 times for redundancy.

**Data encoding**: A stream of `(brightness, led_index)` byte pairs, only for keys with brightness > 0. Brightness is 0–255, led_index matches the key map.

**Last fragment datalen**: `0x10 + actual_data_bytes_in_this_fragment`. For example, if the last fragment has 6 data bytes, byte 4 = `0x16`.

### Audiobar Layout

The OEM `ET/audiobar.txt` defines the key-to-bar mapping. The keyboard is divided into 11 vertical columns (frequency bands), each with up to 6 height levels (bottom-to-top). Each cell lists the keys that light up at that bar level:

```
Col 0 (bass):  LCtrl,LWin → LShift → Caps → Tab,Q → `,1 → Esc
Col 1:         LAlt → Z,X → A,S → Q,W → 2,3 → F1,F2
Col 2:         C,V → D,F → E,R → 4,5 → F3,F4
...
Col 10 (treble): Right×3 → PgDn → PgUp → Pause
```

The host captures audio, computes FFT into 11 band levels (0–6), and lights up keys from the bottom of each column upward based on the band energy.

## Direct RGB Mode (OpenRGB-compatible)

Not yet implemented in `aula_f87.py`. OpenRGB uses Feature Reports (report ID `0x06`) with 520-byte buffers for per-key RGB control. This is a separate protocol path from the effect control described above and requires keepalive packets every ~500ms.

## References

- [OpenRGB Sinowealth Controller](https://gitlab.com/CalcProgrammer1/OpenRGB/-/tree/master/Controllers/SinowealthController/SinowealthKeyboard10cController) — direct RGB protocol
- [SignalRGB AULA Plugin](https://github.com/NollieL/SignalRgb_CN_Key) — key map reference
- [sinowealth-kb-tool](https://github.com/carlossless/sinowealth-kb-tool) — firmware backup/restore
