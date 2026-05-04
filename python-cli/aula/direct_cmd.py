"""
CLI command: direct — test 520-byte direct-mode LED control.
"""

import math
import os
import struct
import time


def cmd_direct(action, color=(255, 0, 0), path=None, speed=1.0,
               loop=1, duration=5.0, fps=20.0, skip_enable=False,
               device="wired"):
    from aula.direct import (
        DirectModeDevice, enable_direct_mode, disable_direct_mode,
        NUM_LEDS, LED_DATA_OFFSET, REPORT_SIZE,
    )

    dev = DirectModeDevice()
    try:
        label, vid, pid = dev.open(prefer=device)
    except RuntimeError as e:
        print(f"  {e}")
        return 1
    print(f"AULA F87 direct mode — {label} ({vid:#06x}:{pid:#06x})")

    if not skip_enable:
        print("  Sending enable sequence (0x39 / 0x3C)...")
        try:
            enable_direct_mode(dev)
        except Exception as e:
            print(f"  Enable failed (non-fatal): {e}")
        time.sleep(0.01)

    try:
        if action == "probe":
            return _probe_direct(dev)
        elif action == "blank":
            return _blank(dev)
        if action == "test":
            return _test_solid(dev, color)
        elif action == "replay":
            if not path:
                print("  --path required for replay mode")
                return 1
            return _replay_capture(dev, path, speed, loop)
        elif action == "rainbow":
            return _rainbow_anim(dev, duration, fps)
    except KeyboardInterrupt:
        print("\n  (interrupted)")
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if not skip_enable:
            try:
                disable_direct_mode(dev)
            except Exception:
                pass
        dev.close()

    return 0


def _probe_direct(dev):
    """Send one blank direct-mode frame to test transport support."""
    from aula.direct import DirectModeDevice

    print("  Probing with one blank 520-byte frame...")
    ret = dev.send_frame(DirectModeDevice.build_blank_frame())
    print(f"  OK: device accepted {ret} bytes")
    return 0


def _blank(dev):
    """Blank all LEDs once."""
    from aula.direct import DirectModeDevice

    ret = dev.send_frame(DirectModeDevice.build_blank_frame())
    print(f"  Blanked ({ret} bytes).")
    return 0


def _test_solid(dev, color):
    """Send a solid color frame with keepalive for 5s, then blank."""
    from aula.direct import DirectModeDevice, NUM_LEDS

    r, g, b = color
    print(f"  Solid color: ({r}, {g}, {b}) — holding for 5s")
    colors = {i: (r, g, b) for i in range(NUM_LEDS)}
    frame = DirectModeDevice.build_frame(colors)

    # Direct mode reverts after ~1s without updates; send at ~2 fps
    start = time.monotonic()
    sent = 0
    while time.monotonic() - start < 5.0:
        ret = dev.send_frame(frame)
        sent += 1
        if sent == 1:
            print(f"  First frame: {ret} bytes")
        time.sleep(0.5)

    blank = DirectModeDevice.build_blank_frame()
    dev.send_frame(blank)
    print(f"  Done ({sent} frames). Blanked.")
    return 0


def _replay_capture(dev, path, speed, loop):
    """Replay 528-byte SET_REPORT control transfers from a pcapng."""
    if not os.path.exists(path):
        print(f"  File not found: {path}")
        return 1

    frames = _extract_528_frames(path)
    if not frames:
        print(f"  No 528-byte SET_REPORT frames found in {path}")
        return 1

    total_time = sum(g for g, _ in frames) / max(speed, 0.001)
    print(f"  Frames     : {len(frames)}")
    print(f"  Speed      : {speed}x -> ~{total_time * loop:.1f}s total")

    t0 = time.monotonic()
    sent = 0
    for lp in range(max(1, loop)):
        for gap, report in frames:
            delay = max(0, gap / max(speed, 0.001))
            if delay > 0:
                time.sleep(delay)
            dev.send_frame(report)
            sent += 1

    elapsed = time.monotonic() - t0
    frag_s = sent / max(elapsed, 1e-6)
    print(f"  Done: {sent} frames in {elapsed:.2f}s ({frag_s:.1f} fps)")
    return 0


def _rainbow_anim(dev, duration, target_fps):
    """Animated rainbow sweep across all LEDs."""
    from aula.direct import DirectModeDevice, NUM_LEDS

    print(f"  Rainbow animation: {duration:.1f}s at {target_fps:.0f} fps")
    period = 1.0 / target_fps if target_fps > 0 else 0

    start = time.monotonic()
    deadline = start + duration
    frames = 0
    latencies = []

    while time.monotonic() < deadline:
        t0 = time.monotonic()
        t = t0 - start

        colors = {}
        for i in range(NUM_LEDS):
            phase = (i / max(NUM_LEDS - 1, 1)) * math.tau + t * 2.0
            r = int(127 + 127 * math.sin(phase))
            g = int(127 + 127 * math.sin(phase + math.tau / 3))
            b = int(127 + 127 * math.sin(phase + 2 * math.tau / 3))
            colors[i] = (r, g, b)

        frame = DirectModeDevice.build_frame(colors)
        dev.send_frame(frame)
        frames += 1
        latencies.append((time.monotonic() - t0) * 1000)

        if period > 0:
            remaining = period - (time.monotonic() - t0)
            if remaining > 0:
                time.sleep(remaining)

    elapsed = time.monotonic() - start
    fps_actual = frames / max(elapsed, 1e-6)
    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0

    print(f"  Result: {frames} frames in {elapsed:.2f}s = {fps_actual:.1f} fps")
    print(f"  Latency: p50={p50:.1f}ms  p99={p99:.1f}ms  max={max(latencies):.1f}ms")

    blank = DirectModeDevice.build_blank_frame()
    dev.send_frame(blank)
    return 0


def _extract_528_frames(path):
    """Extract (gap_seconds, 520-byte-report) from a USBPcap pcapng.

    USBPcap wraps control transfers as 8-byte SETUP + data.
    We look for 528-byte OUT packets where SETUP indicates SET_REPORT
    and extract the 520-byte feature report payload.
    """
    from pcapng import FileScanner

    frames = []
    prev_ts = None

    with open(path, "rb") as f:
        for block in FileScanner(f):
            if block.__class__.__name__ != "EnhancedPacket":
                continue
            ts = block.timestamp_high * (2**32) + block.timestamp_low
            raw = bytes(block.packet_data)

            if len(raw) < 27:
                continue
            header_len = struct.unpack_from("<H", raw, 0)[0]
            irp_info = raw[16]
            if (irp_info & 1) != 0:
                continue
            data_len = struct.unpack_from("<I", raw, 23)[0]
            payload = raw[header_len:header_len + data_len]

            if len(payload) != 528:
                continue
            # Verify SETUP: bmRequestType=0x21, bRequest=0x09 (SET_REPORT)
            if payload[0] != 0x21 or payload[1] != 0x09:
                continue

            report = payload[8:]  # 520-byte feature report

            gap = 0.0
            if prev_ts is not None:
                gap = (ts - prev_ts) / 1_000_000
            prev_ts = ts
            frames.append((gap, bytes(report)))

    return frames
