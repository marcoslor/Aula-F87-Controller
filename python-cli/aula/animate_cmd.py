"""
CLI command: animate — run animations on either wired or wireless transport.

Auto-detects connected device and uses the appropriate protocol:
  - Wired (USB-C):     520-byte direct mode at up to ~20 fps, full RGB
  - Wireless (2.4GHz): 20-byte 0x88 color-groups, sparse, ~20 fps
"""

import time

from aula.animations import ANIMATIONS


def cmd_animate(name, duration=10.0, fps=20.0, transport="auto"):
    """Run a named animation."""
    if name not in ANIMATIONS:
        print(f"Unknown animation '{name}'.")
        print(f"Available: {', '.join(sorted(ANIMATIONS))}")
        return 1

    gen = ANIMATIONS[name]

    if transport == "auto":
        dev, label = _open_any()
    elif transport == "wired":
        dev, label = _open_wired()
    elif transport == "wireless":
        dev, label = _open_wireless()
    else:
        print(f"Unknown transport '{transport}'. Use: auto, wired, wireless")
        return 1

    if dev is None:
        return 1

    print(f"AULA F87 animate — {label}")
    print(f"  Animation: {name}  Duration: {duration:.1f}s  FPS: {fps:.0f}")

    period = 1.0 / fps if fps > 0 else 0.0

    try:
        start = time.monotonic()
        deadline = start + duration
        frames = 0
        while time.monotonic() < deadline:
            t0 = time.monotonic()
            t = t0 - start
            colors = gen(t)
            try:
                _send(dev, label, colors)
            except RuntimeError as e:
                msg = str(e).lower()
                if "disconnect" in msg:
                    print(f"  Stopped: {e}")
                    break
                raise
            frames += 1
            if period:
                remaining = period - (time.monotonic() - t0)
                if remaining > 0:
                    time.sleep(remaining)
    except KeyboardInterrupt:
        print("\n  (interrupted)")
    finally:
        elapsed = time.monotonic() - start
        _finish(dev, label)
        actual_fps = frames / max(elapsed, 1e-6)
        print(f"  Result: {frames} frames in {elapsed:.2f}s = {actual_fps:.1f} fps")

    return 0


def _open_any():
    """Try wired first (smoother), then wireless."""
    dev, label = _open_wired()
    if dev is not None:
        return dev, label
    return _open_wireless()


def _open_wired():
    try:
        from aula.direct import DirectModeDevice, enable_direct_mode
        dev = DirectModeDevice()
        label_str, vid, pid = dev.open(prefer="wired")
        try:
            enable_direct_mode(dev)
        except Exception:
            pass
        time.sleep(0.01)
        return dev, "wired"
    except (RuntimeError, OSError):
        return None, None


def _open_wireless():
    try:
        from aula.wireless import WirelessStreamDevice
        dev = WirelessStreamDevice(inter_report_delay=0.0)
        dev.open()
        return dev, "wireless"
    except (RuntimeError, OSError):
        print("  No AULA F87 device found (wired or wireless).")
        return None, None


def _send(dev, label, colors):
    if label == "wired":
        from aula.direct import DirectModeDevice
        frame = DirectModeDevice.build_frame(colors)
        dev.send_frame(frame)
    else:
        dev.send_audio(colors)


def _finish(dev, label):
    if label == "wired":
        from aula.direct import DirectModeDevice, disable_direct_mode
        try:
            dev.send_frame(DirectModeDevice.build_blank_frame())
            disable_direct_mode(dev)
        except Exception:
            pass
        dev.close()
    else:
        try:
            dev.send_idle()
        except Exception:
            pass
        dev.close()
