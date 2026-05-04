# Streaming Animations

Notes on pushing arbitrary keyboard frames at high frame rate and how to
verify which reverse-engineered protocol actually applies to your hardware.

## Background — two RE stories

There are two RE write-ups for AULA / SinoWealth keyboards in the wild:

| | This repo | [aula-rgb-controller](https://github.com/veysiemrah/aula-rgb-controller) |
|---|---|---|
| Report ID | `0x13` | `0x06` |
| Transport | 20-byte HID **output reports** | 520-byte HID **feature reports** |
| Source | Direct USB captures of the OEM app (see `captures/README.md`: `windows-npcap-wireshark/` vs `macos-host-wireshark-vm/`) | OpenRGB's generic SinoWealth model + their own captures |
| Direct-mode cmd | `0x88` (audio stream, brightness-only) + `0x02` (per-key RGB) | `0x08` (interleaved RGB, unconfirmed) |
| Claimed animation rate | Not previously measured here | ~25 fps capped |

The two protocols are **not alternative encodings of the same thing** —
they are different commands across different HID collections. Both can
coexist; one may be silent on your firmware.

## Probe: which path does your device actually speak?

Run:

```bash
python aula_f87.py probe
```

This enumerates every HID collection for VID `0x258A:0x010C` (wired) and
`0x3554:0xFA09` (wireless), sends the **OEM 20-byte READ/CONFIRM** to the
vendor collections, and sends the **OpenRGB 520-byte model query** as a
feature report. The verdict at the end tells you which code paths are
viable on your hardware:

- **Both answered** — both protocols coexist; the aula-rgb-controller
  `cmd 0x08` direct mode is worth trying as an alternative animation path.
- **Only OEM answered** — stick with this repo's protocol; the 520-byte
  family doesn't apply to your firmware.
- **Only OpenRGB answered** — the firmware differs from what our captures
  documented; revisit the RE.
- **Neither answered** — permissions issue (macOS Input Monitoring, Linux
  udev), not a protocol issue.

## Streaming model

The two animation paths this repo now implements both use the OEM
20-byte `0x13` wire format (the one proven by your captures):

### `cmd=0x88` — wireless/audio color-group stream

Lightweight when used like the OEM app: sparse color groups, usually
3–6 × 20-byte fragments per active frame. It is not equivalent to the
wired 520-byte direct-mode framebuffer.

**Fragment layout** (verified byte-for-byte against `captures/macos-host-wireshark-vm/effect/*.pcapng`):

| Byte | Meaning |
|---|---|
| 0 | `0x13` report id |
| 1 | `0x88` command |
| 2 | subcmd = total fragment count (1..14). Varies per frame. |
| 3 | seq = 0..subcmd-1 |
| 4 | datalen marker: `0x23` for the idle/no-op frame, otherwise `0x10 + N` where N is the number of data bytes in *this* fragment (full frags are `0x1E`, last frag is partial) |
| 5..18 | up to 14 data bytes (color groups, see below) |
| 19 | 8-bit checksum of bytes 0..18 |

**Data encoding** (decoded by cross-referencing VM USBPcap captures):

The data bytes are a stream of **color groups**, concatenated back-to-back:

| Field | Size | Meaning |
|---|---|---|
| R | 1 | Red channel 0–255 |
| G | 1 | Green channel 0–255 |
| B | 1 | Blue channel 0–255 |
| count | 1 | Number of LED indices that follow |
| indices | count | Hardware LED indices to set to this color |

Groups repeat until the end of the data stream. LEDs not mentioned in
any group are off. A single color group can span fragment boundaries —
the firmware reassembles fragments into a contiguous byte stream before
parsing.

**Example** (from `captures/windows-npcap-wireshark/raining-silk-2-4.pcapng`, first active frame):

```
data: 00 00 ff 07 01 02 56 61 45 51 5c 00 ff 00 06 31 37 26 2c 38 3e c8 00 00 04 08 0f 1b 21
      ├──blue───┤ 7 LEDs──────────────┤ ├──green──┤ 6 LEDs────────────┤ ├──red───┤ 4 LEDs──┤
```

This encodes 3 color groups lighting 17 LEDs total.

**Capacity:** 14 fragments × 14 bytes = 196 bytes max, but practical
wireless animations should stay well below that. A full 87-key rainbow
can be encoded with quantization, but it takes ~13 fragments and is
visibly less stable over the 2.4 GHz receiver. The OEM visualizer
naturally uses 3–6 fragments, 3–14 color groups, and about 15–25 LEDs
per active frame, which is the shape synthesized animations should
prefer.

**Idle frame** (no LEDs, keepalive):

```
13 88 01 00 23 00 00 00 00 00 00 00 00 00 00 00 00 00 00 bf
```

**No preamble needed** — the OEM app sends no config write, palette, or
save before streaming. `arm_audio_stream()` only sends a few idle
frames to let the keyboard enter audio-dance mode.

**Measured OEM cadence** (from wireless captures):
- active frames: usually 3–6 fragments
- active LEDs: median ~18, max ~22 in `captures/windows-npcap-wireshark/raining-silk-2-4.pcapng`
- inter-fragment: ~12 ms
- silent: idle frames at ~1 Hz keepalive

Best for: visualizer-style effects, sparse moving bands, beat flashes,
heatmap overlays, and other effects where only part of the keyboard
changes per frame. Use wired direct mode for full-board, every-key,
every-frame gradients.

### `cmd=0x02` — per-key RGB (self-define)

Heavy. Each frame is **28** × 20-byte fragments (three 9-fragment color
planes + trailer). Full arbitrary RGB per key per frame.

Best for: true custom animations where each key must be a different
color that changes every frame.

## Usage

```python
from aula.stream import StreamEngine

eng = StreamEngine(inter_frag_delay=0.012)  # OEM cadence
eng.open()

# Option A — color-group stream (no heavy arming; OEM doesn't do any)
eng.arm_audio_stream()
for frame in my_source:                          # frame = {led: (r,g,b)}
    eng.send_audio(frame)
# send one idle frame ~1 Hz during silence so mode stays live
eng.send_idle()

# Option B — full per-key RGB stream (this one DOES need a config arm)
eng.arm_perkey_stream()
for frame in my_source:                          # frame = {led: (r,g,b)}
    eng.send_perkey(frame)

eng.close()
```

The hot-path `send_*` methods are **fire-and-forget** — they do not wait
for keyboard echoes. That's the whole trick: reading echoes synchronously
is what held previous write paths to effect-change rates, not animation
rates.

## Replay — prove the wire works

Before trusting synthesized frames, replay an OEM capture verbatim:

```bash
# Play back the audio-dance reference capture at real time
python aula_f87.py replay ../captures/macos-host-wireshark-vm/effect/1-audio-dance-soft-gain1-smoothness-4-colorful.pcapng

# 2× speed, 3 iterations
python aula_f87.py replay ../captures/macos-host-wireshark-vm/effect/5-mountains-and-flowing-w-with-sample-mp3-playing.pcapng --speed 2 --loop 3

# Floor the fragment gap at 5ms (useful if pcapng timestamps are coarse)
python aula_f87.py replay <file>.pcapng --min-frag-delay-ms 5
```

If replay produces the same visible animation the OEM app produced in
that capture, the wire path, timing, and checksum are all correct and
any remaining issue is in the data-byte encoding (which only matters
for *synthesized* frames, not replay).

## Benchmark

The `bench` subcommand runs a known animation for a fixed duration and
reports achieved FPS plus per-frame latency percentiles:

```bash
# Brightness-only animation, as fast as possible, 5 seconds
python aula_f87.py bench audio wave

# Match the OEM's pacing (~12ms between fragments)
python aula_f87.py bench audio sweep --frag-delay-ms 12 -d 10

# Full RGB rainbow
python aula_f87.py bench perkey rainbow -d 5

# Capped to a target framerate (to confirm stability)
python aula_f87.py bench audio wave --fps 30 -d 15
```

Sample output shape:

```
Result: 540 frames in 5.00s = 108.0 fps
        7560 fragments = 1512 frags/s (~30240 B/s)
Per-frame latency:
        avg=8.45ms  p50=7.98ms  p95=12.10ms  p99=15.30ms  max=22.00ms
```

Interpretation:

- **`audio` mode**: FPS should scale with how many keys you touch per
  frame. Touching all 87 keys (the bench default) needs 13 fragments →
  fragment rate × 13 ≈ expected FPS. A sparse beat-flash animation can
  run at far higher FPS.
- **`perkey` mode**: Always 28 fragments per frame. Upper bound is
  USB interrupt poll rate / 28. Typical PCs sustain 20–40 fps here.
- `p99` and `max` latencies matter more than `avg` for animation
  smoothness — jitter shows up as stutter regardless of average FPS.

## Known limits

- macOS IOKit + `hid` introduces per-write overhead of ~0.5–2ms
  regardless of payload size. Linux hidraw is typically 3–5× faster.
- The keyboard's USB endpoint has a finite FIFO. Past a certain rate the
  host write call will block until the keyboard drains the queue — that
  shows up in the latency `max`, not as dropped frames.
- No keepalive is required for `cmd=0x88` / `cmd=0x02` — unlike the
  OpenRGB `cmd=0x08` direct mode (which reverts after ~1s of silence),
  these commands apply persistently until the next effect change.
