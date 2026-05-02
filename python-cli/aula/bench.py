"""
AULA F87 — Sustained-framerate benchmark for the streaming engine.

Runs a known-shape animation for a fixed duration and reports:
  * Frames actually sent
  * Fragments sent (fragments-per-second ≈ USB throughput)
  * Average / p50 / p95 / p99 per-frame latency
  * Achieved vs requested FPS

Two modes match aula/stream.py:
  * audio   — cmd 0x88, brightness-only, lightweight
  * perkey  — cmd 0x02, full RGB per-frame, heavyweight

The animations cycle through all 87 keys each frame so a full board refresh
is actually exercised — no free rides from sparse updates.
"""

import math
import os
import time

from aula.stream import StreamEngine
from aula.layout import KEY_NAMES


_ALL_LED_INDICES = sorted(set(KEY_NAMES.values()))


# ── Frame generators ────────────────────────────────────────────────────

def _audio_wave(t, speed=2.0):
    """Full-RGB sin wave across all keys (0x88 color-group encoding)."""
    colors = {}
    n = len(_ALL_LED_INDICES)
    for i, led in enumerate(_ALL_LED_INDICES):
        phase = (i / max(n - 1, 1)) * math.tau + t * speed
        r = int(127 + 127 * math.sin(phase))
        g = int(127 + 127 * math.sin(phase + math.tau / 3))
        b = int(127 + 127 * math.sin(phase + 2 * math.tau / 3))
        colors[led] = (r, g, b)
    return colors


def _audio_sweep(t, speed=3.0):
    """Bright head running across keys, fading trail."""
    n = len(_ALL_LED_INDICES)
    head = int((t * speed * n) % n)
    colors = {}
    for i, led in enumerate(_ALL_LED_INDICES):
        d = abs(i - head)
        d = min(d, n - d)
        v = max(0, 255 - d * 40)
        if v:
            colors[led] = (v, v, v)
    return colors


def _audio_idle(t):
    return {}  # engine turns this into the single idle frame


def _rgb_rainbow(t, speed=1.5):
    """Per-key full-RGB rainbow sweep."""
    n = len(_ALL_LED_INDICES)
    colors = {}
    for i, led in enumerate(_ALL_LED_INDICES):
        phase = (i / max(n - 1, 1)) * math.tau + t * speed
        r = int(127 + 127 * math.sin(phase))
        g = int(127 + 127 * math.sin(phase + math.tau / 3))
        b = int(127 + 127 * math.sin(phase + 2 * math.tau / 3))
        colors[led] = (r, g, b)
    return colors


def _rgb_solid_pulse(t, speed=2.0):
    """Whole keyboard pulses between two colors."""
    v = 0.5 + 0.5 * math.sin(t * speed)
    r = int(255 * v)
    g = int(40 + 60 * (1 - v))
    colors = {led: (r, g, 0) for led in _ALL_LED_INDICES}
    return colors


AUDIO_ANIMS = {
    "wave":  _audio_wave,
    "sweep": _audio_sweep,
    "idle":  _audio_idle,
}
RGB_ANIMS = {
    "rainbow": _rgb_rainbow,
    "pulse":   _rgb_solid_pulse,
}


# ── Benchmark ───────────────────────────────────────────────────────────

def _percentile(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(p * (len(s) - 1)))))
    return s[k]


def cmd_bench(mode, anim, duration=5.0, target_fps=0, color=None,
              effect=1, page=None, inter_frag_delay=0.0):
    """Run a streaming benchmark.

    mode:             'audio' (cmd 0x88) or 'perkey' (cmd 0x02)
    anim:             key in AUDIO_ANIMS or RGB_ANIMS
    duration:         seconds of streaming to measure
    target_fps:       0 = as-fast-as-possible, otherwise pace to this rate
    color:            ignored in audio mode (0x88 doesn't take a palette)
    effect:           ignored in audio mode for the same reason
    inter_frag_delay: seconds to sleep between fragments (OEM uses ~0.012)
    """
    if mode == "audio":
        if anim not in AUDIO_ANIMS:
            print(f"Unknown audio anim '{anim}'. Choose from: {', '.join(AUDIO_ANIMS)}")
            return 1
        gen = AUDIO_ANIMS[anim]
    elif mode == "perkey":
        if anim not in RGB_ANIMS:
            print(f"Unknown rgb anim '{anim}'. Choose from: {', '.join(RGB_ANIMS)}")
            return 1
        gen = RGB_ANIMS[anim]
    else:
        print(f"Unknown mode '{mode}'. Choose 'audio' or 'perkey'.")
        return 1

    print(f"AULA F87 stream benchmark — mode={mode} anim={anim}")
    print(f"  duration={duration:.1f}s  target_fps={'max' if not target_fps else target_fps}"
          f"  inter_frag_delay={inter_frag_delay * 1000:.1f}ms")

    engine = StreamEngine(inter_frag_delay=inter_frag_delay)
    try:
        mode_label, info = engine.open(prefer_page=page)
    except RuntimeError as e:
        print(f"  {e}")
        return 1
    print(f"  Connected: {mode_label} (page=0x{info['usage_page']:04X})")

    # Arm
    print(f"  Arming device for {mode} stream...")
    t0_arm = time.monotonic()
    if mode == "audio":
        engine.arm_audio_stream()
    else:
        engine.arm_perkey_stream()
    print(f"  Armed in {(time.monotonic() - t0_arm) * 1000:.0f}ms")

    frame_period = 1.0 / target_fps if target_fps else 0.0
    latencies_ms = []

    print(f"  Streaming for {duration:.1f}s...")
    start = time.monotonic()
    deadline = start + duration
    next_due = start
    frames = 0
    fragments = 0

    try:
        while True:
            now = time.monotonic()
            if now >= deadline:
                break

            if frame_period and now < next_due:
                time.sleep(max(0.0, next_due - now))

            tf0 = time.monotonic()
            t = tf0 - start

            if mode == "audio":
                n = engine.send_audio(gen(t))
            else:
                n = engine.send_perkey(gen(t))

            latencies_ms.append((time.monotonic() - tf0) * 1000.0)
            frames += 1
            fragments += n

            if frame_period:
                next_due += frame_period
                # Don't let the pacer fall arbitrarily behind
                if next_due < time.monotonic() - frame_period:
                    next_due = time.monotonic()
    except KeyboardInterrupt:
        print("  (interrupted)")
    finally:
        elapsed = time.monotonic() - start
        engine.close()

    if elapsed <= 0 or frames == 0:
        print("  No frames sent.")
        return 1

    fps = frames / elapsed
    frag_s = fragments / elapsed
    print()
    print(f"  Result: {frames} frames in {elapsed:.2f}s = {fps:.1f} fps")
    print(f"          {fragments} fragments = {frag_s:.0f} frags/s (~{frag_s * 20:.0f} B/s)")
    print(f"  Per-frame latency:")
    print(f"          avg={sum(latencies_ms) / len(latencies_ms):.2f}ms"
          f"  p50={_percentile(latencies_ms, 0.50):.2f}ms"
          f"  p95={_percentile(latencies_ms, 0.95):.2f}ms"
          f"  p99={_percentile(latencies_ms, 0.99):.2f}ms"
          f"  max={max(latencies_ms):.2f}ms")

    return 0


# ── Capture replay ──────────────────────────────────────────────────────

def cmd_replay(path, speed=1.0, loop=1, min_frag_delay=0.0,
               cmd_filter=0x88, page=None):
    """Replay a pcapng capture of OEM USB traffic to the keyboard.

    This bypasses all of our frame construction and sends the exact
    bytes the OEM sent. If replay works on hardware but our synthesized
    frames don't, the delta pinpoints the encoding difference.

    Args:
        path:            pcapng file
        speed:           playback rate multiplier (default 1.0 = real time)
        loop:            how many times to replay the whole file
        min_frag_delay:  floor on inter-fragment sleep (s). Useful when
                         original gaps are ~0 because of USB batching.
        cmd_filter:      HID cmd byte to keep (default 0x88). None = all.
    """
    from aula.capture import fragments_with_gaps

    if not os.path.exists(path):
        print(f"Capture not found: {path}")
        return 1

    frags = fragments_with_gaps(path, cmd_filter=cmd_filter)
    if not frags:
        print(f"No fragments found in {path}")
        return 1

    total_time = sum(g for g, _ in frags) / max(speed, 1e-3)
    cmd_label = f"0x{cmd_filter:02X}" if cmd_filter is not None else "all"
    print(f"AULA F87 capture replay")
    print(f"  file     : {path}")
    print(f"  frags    : {len(frags)}")
    print(f"  speed    : {speed}x  ->  ~{total_time * loop:.1f}s total "
          f"({loop} loop{'s' if loop != 1 else ''})")
    print(f"  cmd_filt : {cmd_label}")

    engine = StreamEngine()
    try:
        mode_label, info = engine.open(prefer_page=page)
    except RuntimeError as e:
        print(f"  {e}")
        return 1
    print(f"  Connected: {mode_label} (page=0x{info['usage_page']:04X})")

    t0 = time.monotonic()
    try:
        engine.replay_fragments(frags, speed=speed, loop=loop,
                                min_frag_delay=min_frag_delay)
    except KeyboardInterrupt:
        print("  (interrupted)")
    finally:
        elapsed = time.monotonic() - t0
        engine.close()

    frag_s = engine.total_fragments / max(elapsed, 1e-6)
    print(f"  Done: {engine.total_fragments} fragments in {elapsed:.2f}s "
          f"({frag_s:.0f} frags/s)")
    return 0
