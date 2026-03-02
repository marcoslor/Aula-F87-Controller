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

    candidates = []
    fallback = []

    for vid, pid, label in [(WIRED_VID, WIRED_PID, "wired"),
                            (WIRELESS_VID, WIRELESS_PID, "wireless")]:
        devs = hid.enumerate(vid, pid)
        for d in devs:
            up = d["usage_page"]
            # Only consider vendor-specific pages (0xFF00–0xFFFF)
            if not (0xFF00 <= up <= 0xFFFF):
                continue
            if prefer_page is not None and up != prefer_page:
                fallback.append((d, label))
            else:
                candidates.append((d, label))

    if not candidates:
        candidates = fallback

    if not candidates:
        return (None, None, None)

    def _open(info):
        # Backward-compatible constructor for different `hid` package versions.
        # Older API: hid.device() + open_path().
        # Newer API: hid.Device(path=...).
        if hasattr(hid, "device"):
            dev = hid.device()
            dev.open_path(info["path"])
            return dev
        if hasattr(hid, "Device"):
            try:
                return hid.Device(path=info["path"])
            except Exception:
                # Retry with VID/PID selector in case path-based open is blocked.
                return hid.Device(info["vendor_id"], info["product_id"])
        raise RuntimeError(
            "Unsupported `hid` package API: expected `device()` or `Device()`."
        )

    last_error = None
    for info, mode in candidates:
        try:
            dev = _open(info)
            return (dev, mode, info)
        except Exception as e:
            last_error = (mode, info, e)
            continue

    if last_error is None:
        return (None, None, None)

    best_mode, _, err = last_error
    import platform
    _os = platform.system()
    if _os == "Darwin":
        _hint = (
            "  On macOS this is usually an IOKit permission issue, not a Python issue.\n"
            "    1) Grant your terminal app Input Monitoring access:\n"
            "       System Settings > Privacy & Security > Input Monitoring.\n"
            "    2) Re-plug the keyboard (or remove/re-pair the wireless adapter).\n"
            "    3) Alternatively, use the web app controller."
        )
    elif _os == "Linux":
        _hint = (
            "  On Linux, HID devices are owned by root by default.\n"
            "    Add a udev rule so your user can open the device without sudo:\n"
            "      echo 'SUBSYSTEM==\"hidraw\", ATTRS{idVendor}==\"258a\", "
            "MODE=\"0660\", GROUP=\"plugdev\"' \\\n"
            "        | sudo tee /etc/udev/rules.d/99-aula-f87.rules\n"
            "      sudo udevadm control --reload-rules && sudo udevadm trigger\n"
            "    Then add yourself to the plugdev group (log out and back in):\n"
            "      sudo usermod -aG plugdev $USER"
        )
    else:
        _hint = "  Ensure your user has permission to open HID devices."
    raise RuntimeError(
        f"Cannot open HID device ({best_mode}): {err}\n{_hint}"
    ) from err


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
