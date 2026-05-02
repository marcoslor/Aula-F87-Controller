"""
AULA F87 — High-rate streaming animation engine.

Two streaming modes are supported, both using the OEM 20-byte output-report
protocol (report ID 0x13):

  * Audio stream (cmd=0x88):
        Mirrors the OEM "Audio Dance" visualizer path. Verified against
        captures/macos-host-wireshark-vm/effect/*.pcapng: the OEM sends NO preamble, NO config
        write, NO save. It just starts sending 0x88 frames (idle frames
        keep the mode alive between beats). Cadence in the OEM app is
        ~28–30 fps active (35 ms median between frame starts), ~1 Hz
        keepalive during silence.

  * Per-key RGB stream (cmd=0x02):
        Per-frame full RGB for every key. Requires self-define (effect 21)
        to be armed once. Heavier (28 fragments per frame) but supports
        arbitrary color-per-key-per-frame.

Echoes are intentionally NOT read in the hot path — fire-and-forget writes
match the OEM's behaviour and are required for 30 fps+.
"""

import time
from aula.protocol import (REPORT_ID, CMD_WRITE, CMD_SAVE, SUBCMD_CONFIG,
                           SUBCMD_CONFIRM, SELF_DEFINE_EFFECT,
                           _build, _checksum)
from aula.device import _find_device, _read_config, _tx_bulk, _tx_rx
from aula.effects import _CFG_TEMPLATE
from aula.layout import _build_perkey_map, _build_palette


# ── Command bytes used only by the streaming engine ─────────────────────
CMD_AUDIO = 0x88

# Audio stream fragment layout (confirmed against macos-host-wireshark-vm/effect/*.pcapng):
#   [0] 0x13 report id
#   [1] 0x88 command
#   [2] subcmd = total fragment count (0x01..0x0E) — varies per frame
#   [3] seq   = 0..subcmd-1
#   [4] datalen:
#         IDLE   → 0x23 (special no-op marker)
#         ACTIVE → 0x10 + N, where N is the number of data bytes in THIS
#                  fragment. Non-last fragments are always full (N=14,
#                  so 0x1E); the last fragment may carry fewer bytes.
#   [5..5+N-1] up to 14 data bytes per fragment: a continuous stream of
#              (R, G, B, count, indices...) color groups. Groups may span
#              fragment boundaries.
#   [19] checksum
_AUDIO_DATA_OFFSET = 5
_AUDIO_DATA_PER_FRAG = 14
_AUDIO_DL_FULL = 0x10 + _AUDIO_DATA_PER_FRAG  # 0x1E
_AUDIO_DL_IDLE = 0x23


def build_audio_idle_frame():
    """Build the OEM 'no beat' idle frame.

    Confirmed byte-for-byte against macos-host-wireshark-vm/effect/*.pcapng:
        13 88 01 00 23 00 00 00 00 00 00 00 00 00 00 00 00 00 00 bf
    """
    f = bytearray(20)
    f[0] = REPORT_ID
    f[1] = CMD_AUDIO
    f[2] = 0x01
    f[3] = 0x00
    f[4] = _AUDIO_DL_IDLE
    f[19] = _checksum(f)
    return bytes(f)


_MAX_DATA_BYTES = 14 * _AUDIO_DATA_PER_FRAG   # 196


def build_audio_frames(led_colors, quantize=64):
    """Build one 0x88 animation frame (list of 20-byte fragments).

    The 0x88 data encoding (decoded from VM USBPcap captures) is a
    stream of color groups, each:

        R  G  B  count  index1  index2  ...  indexN

    Groups repeat until end of data. LEDs not mentioned are off.

    The protocol caps at 14 fragments (196 data bytes). Quantizing
    channels to the nearest ``quantize`` step merges similar colors into
    fewer, larger groups. If the data still doesn't fit, the quantization
    step is doubled automatically until it does (adaptive fallback).

    Args:
        led_colors: dict of led_index → (r, g, b). LEDs with (0,0,0) are
                    omitted. LEDs sharing the same color are grouped.
        quantize:   channel rounding step (0 to disable). 64 gives ≤4^3
                    possible colors which keeps the 87-key keyboard well
                    within the 14-fragment limit.

    Returns:
        List[bytes] of 1..14 fragments (20 bytes each).
    """
    if not led_colors:
        return [build_audio_idle_frame()]

    from collections import defaultdict

    q = max(1, quantize) if quantize else 1

    while True:
        color_to_leds = defaultdict(list)
        for idx, (r, g, b) in led_colors.items():
            if not (r or g or b):
                continue
            rq = min(255, ((r + q // 2) // q) * q)
            gq = min(255, ((g + q // 2) // q) * q)
            bq = min(255, ((b + q // 2) // q) * q)
            color_to_leds[(rq & 0xFF, gq & 0xFF, bq & 0xFF)].append(idx & 0xFF)

        if not color_to_leds:
            return [build_audio_idle_frame()]

        # Serialize largest groups first so truncation (if any) hits the
        # smallest groups — visually least impactful.
        data = bytearray()
        for (r, g, b), indices in sorted(
            color_to_leds.items(), key=lambda kv: len(kv[1]), reverse=True
        ):
            for i in range(0, len(indices), 255):
                chunk = indices[i:i + 255]
                data.extend([r, g, b, len(chunk)])
                data.extend(chunk)

        if len(data) <= _MAX_DATA_BYTES or q >= 256:
            break
        q *= 2  # coarsen and retry

    return _pack_data_into_fragments(data)


def build_audio_frames_raw(data):
    """Build fragments from a pre-encoded data byte stream.

    Useful when the caller has already serialized (R,G,B,count,indices)
    groups and just needs fragmentation + framing.
    """
    if not data:
        return [build_audio_idle_frame()]
    return _pack_data_into_fragments(data)


def _pack_data_into_fragments(data):
    """Split a data byte stream into 0x88 fragments."""
    chunks = []
    for i in range(0, len(data), _AUDIO_DATA_PER_FRAG):
        chunks.append(bytes(data[i:i + _AUDIO_DATA_PER_FRAG]))

    if len(chunks) > 14:
        chunks = chunks[:14]

    total = len(chunks)
    frames = []
    for seq, chunk in enumerate(chunks):
        f = bytearray(20)
        f[0] = REPORT_ID
        f[1] = CMD_AUDIO
        f[2] = total
        f[3] = seq
        is_last = (seq == total - 1)
        f[4] = (0x10 + len(chunk)) if is_last else _AUDIO_DL_FULL
        for j, byte in enumerate(chunk):
            f[_AUDIO_DATA_OFFSET + j] = byte
        f[19] = _checksum(f)
        frames.append(bytes(f))
    return frames


# ── Engine ──────────────────────────────────────────────────────────────

class StreamEngine:
    """Long-lived HID session for high-rate frame writes.

    Usage:
        eng = StreamEngine()
        eng.open()
        eng.arm_audio_stream(color_rgb=(255, 0, 0))   # prime palette
        for frame_pairs in my_source:
            eng.send_audio(frame_pairs)
        eng.close()

    Echoes are intentionally NOT read in the hot path (wait_read=False),
    which cuts per-fragment latency dramatically at the cost of not
    detecting individual frame errors. Use with `benchmark()` to see the
    actual sustained rate.
    """

    def __init__(self, inter_frag_delay=0.0):
        """
        inter_frag_delay: seconds to sleep between consecutive fragments.
            The OEM pacing is ~12 ms/fragment. Setting 0 matches our
            ideal throughput; set 0.002–0.012 to throttle deliberately.
        """
        self.dev = None
        self.mode = None
        self._raw_info = None
        self._total_frames = 0
        self._total_fragments = 0
        self._inter_frag_delay = float(inter_frag_delay)

    # -- lifecycle --

    def open(self, prefer_page=None):
        dev, mode_label, info = _find_device(prefer_page=prefer_page)
        if not dev:
            raise RuntimeError("Keyboard not found")
        self.dev = dev
        self._raw_info = (mode_label, info)
        return mode_label, info

    def close(self):
        if self.dev:
            try:
                self.dev.close()
            except Exception:
                pass
            self.dev = None

    # -- arming (one-time per session) --

    def arm_audio_stream(self, warmup_idles=4):
        """Prepare the keyboard for cmd 0x88 brightness streaming.

        The OEM app does NOT write config, palette, or save before
        streaming 0x88 — it just starts. We mirror that: send a handful
        of idle frames first to give the keyboard a chance to enter
        audio-dance mode cleanly, then hand control to the caller.
        """
        if self.dev is None:
            raise RuntimeError("open() first")
        idle = build_audio_idle_frame()
        for _ in range(max(0, warmup_idles)):
            self.dev.write(idle)
            time.sleep(0.012)  # OEM's median inter-fragment spacing
        self.mode = "audio"

    def arm_perkey_stream(self):
        """Prepare keyboard for cmd 0x02 per-key RGB streaming (effect 21)."""
        if self.dev is None:
            raise RuntimeError("open() first")

        config = _read_config(self.dev, timeout_ms=300, max_reads=12)
        got = all(c is not None for c in config)

        write_frags = []
        for seq in range(10):
            if got:
                f = bytearray(config[seq])
                f[1] = CMD_WRITE
                if seq == 0:
                    f[8] = 0x01
                    f[14] = 0x00
                    f[15] = SELF_DEFINE_EFFECT
                    f[17] = 0x01
                f[19] = _checksum(f)
            else:
                p = bytearray(_CFG_TEMPLATE[seq])
                if seq == 0:
                    p[4] = 0x01
                    p[10] = 0x00
                    p[11] = SELF_DEFINE_EFFECT
                    p[13] = 0x01
                f = bytearray(_build(CMD_WRITE, SUBCMD_CONFIG, seq, p))
            write_frags.append(bytes(f))
        _tx_bulk(self.dev, write_frags, wait_read=True)

        # Save so mode sticks
        save = _build(CMD_SAVE, SUBCMD_CONFIRM, 0, bytes([0x04, 0x07] + [0x00] * 13))
        _tx_rx(self.dev, save, wait_read=True)

        self.mode = "perkey"

    # -- hot path --

    def send_audio(self, led_colors):
        """Fire-and-forget one 0x88 frame.

        led_colors: dict of led_index → (r, g, b).
        """
        if self.dev is None:
            raise RuntimeError("open() first")
        frames = build_audio_frames(led_colors)
        self._write_frags(frames)
        self._total_frames += 1
        self._total_fragments += len(frames)
        return len(frames)

    def send_idle(self):
        """Send a single 0x88 idle keepalive frame."""
        if self.dev is None:
            raise RuntimeError("open() first")
        self.dev.write(build_audio_idle_frame())
        self._total_frames += 1
        self._total_fragments += 1

    def send_raw(self, frame):
        """Write a single pre-built 20-byte fragment verbatim.

        Used by the capture-replay path to send OEM bytes exactly.
        """
        if self.dev is None:
            raise RuntimeError("open() first")
        self.dev.write(bytes(frame))
        self._total_fragments += 1

    def send_perkey(self, key_colors):
        """Fire-and-forget one 0x02 per-key RGB frame."""
        if self.dev is None:
            raise RuntimeError("open() first")
        frames = _build_perkey_map(key_colors)
        self._write_frags(frames)
        self._total_frames += 1
        self._total_fragments += len(frames)
        return len(frames)

    def _write_frags(self, frames):
        d = self._inter_frag_delay
        if d <= 0:
            for f in frames:
                self.dev.write(f)
        else:
            last = len(frames) - 1
            for i, f in enumerate(frames):
                self.dev.write(f)
                if i != last:
                    time.sleep(d)

    # -- capture replay --

    def replay_fragments(self, fragments, speed=1.0, loop=1,
                         min_frag_delay=0.0):
        """Replay a sequence of pre-recorded 20-byte fragments.

        Args:
            fragments: iterable of (delay_s_from_previous, 20-byte-bytes).
            speed:     >1.0 replays faster; 0.5 half speed.
            loop:      number of times to replay the whole stream.
            min_frag_delay: lower bound on inter-fragment sleep (s).
        """
        if self.dev is None:
            raise RuntimeError("open() first")
        frags = list(fragments)
        for _ in range(max(1, loop)):
            for gap, frame in frags:
                delay = max(min_frag_delay, (gap or 0.0) / max(speed, 1e-3))
                if delay > 0:
                    time.sleep(delay)
                self.dev.write(bytes(frame))
                self._total_fragments += 1

    # -- counters --

    @property
    def total_frames(self):
        return self._total_frames

    @property
    def total_fragments(self):
        return self._total_fragments
