"""
AULA F87 — HID device discovery, read/write transactions.
"""

import time
from aula.protocol import (REPORT_ID, CMD_READ, SUBCMD_CONFIG, SUBCMD_CONFIRM,
                           WIRED_VID, WIRED_PID, WIRELESS_VID, WIRELESS_PID,
                           _checksum, _build)


def _find_device(prefer_page=None):
    """Find and open the AULA F87 HID device.

    Args:
        prefer_page: Optional usage_page to prefer (e.g. 0xFF00).

    Returns:
        (dev, mode_str, info_dict) or (None, None, None) if not found.
    """
    import hid

    best = None
    best_mode = None

    for vid, pid, label in [(WIRED_VID, WIRED_PID, "wired"),
                            (WIRELESS_VID, WIRELESS_PID, "wireless")]:
        devs = hid.enumerate(vid, pid)
        for d in devs:
            up = d["usage_page"]
            # Only consider vendor-specific pages (0xFF00–0xFFFF)
            if not (0xFF00 <= up <= 0xFFFF):
                continue
            if prefer_page is not None and up != prefer_page:
                # Track as fallback
                if best is None:
                    best = d
                    best_mode = label
                continue
            best = d
            best_mode = label
            if prefer_page is not None:
                break  # exact match found
        if best is not None and prefer_page is not None and best["usage_page"] == prefer_page:
            break

    if best is None:
        return (None, None, None)

    dev = hid.device()
    try:
        dev.open_path(best["path"])
    except Exception as e:
        # macOS may deny HID access when not running as root
        raise RuntimeError(
            f"Cannot open HID device ({best_mode}): {e}\n"
            "  On macOS, run with: sudo -E env DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run ..."
        ) from e

    return (dev, best_mode, best)


def _read_config(dev, timeout_ms=500, max_reads=15):
    """Read 10 config fragments from the keyboard.

    Sends a READ/CONFIRM command and collects up to max_reads responses.

    Returns:
        list of 10 elements — each either bytes(20) or None.
    """
    read_frame = _build(CMD_READ, SUBCMD_CONFIRM, 0, bytes(15))
    dev.write(read_frame)
    time.sleep(0.05)

    config = [None] * 10
    for _ in range(max_reads):
        data = dev.read(20, timeout=timeout_ms)
        if not data:
            break
        raw = bytes(data)
        if len(raw) >= 20 and raw[0] == REPORT_ID and raw[1] == CMD_READ and raw[2] == SUBCMD_CONFIG:
            seq = raw[3]
            if 0 <= seq < 10:
                config[seq] = raw
    return config


def _tx_rx(dev, frame, wait_read=True):
    """Send a frame and optionally read the echo.

    Returns:
        bytes or None.
    """
    dev.write(frame)
    if not wait_read:
        return None
    time.sleep(0.003)
    data = dev.read(20, timeout=200)
    return bytes(data) if data else None


def _tx_bulk(dev, frames, label="", wait_read=True):
    """Send multiple frames, collecting echoes.

    Returns:
        list of echo bytes received.
    """
    echoes = []
    for f in frames:
        echo = _tx_rx(dev, f, wait_read=wait_read)
        if echo:
            echoes.append(echo)
    return echoes
