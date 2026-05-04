"""
AULA F87 — Direct-mode LED control via 520-byte HID Feature Reports.

This module implements the "real" animation protocol as captured from the
OEM Windows app over USB-C (wired).  The keyboard accepts per-LED RGB
frames at ~20 fps via USB control transfers (SET_REPORT, Feature Report
ID 0x06, cmd 0x08).

Transport: because pyusb auto-claims HID interfaces (which stops normal
keyboard input on macOS), we bypass pyusb and call libusb_control_transfer
directly. Endpoint-0 control transfers do not require claiming the
interface, so the keyboard remains usable while frames are streaming.

Protocol reference (confirmed via captures + aula-rgb-controller RE):

    520-byte Feature Report layout:
      d[0]      = 0x06   report ID
      d[1]      = 0x08   CMD_SET_LEDS (direct mode)
      d[2..3]   = 0x00   reserved
      d[4]      = 0x01   zone (always 1 for main LEDs)
      d[5]      = 0x00   offset (always 0)
      d[6]      = 0x7A   num_leds = 122
      d[7]      = 0x01   (unknown, always 1)
      d[8..373] = 122 × (R, G, B) — interleaved RGB, 3 bytes per LED
      d[374..519] = zero padding

    USB Control Transfer:
      bmRequestType = 0x21  (host→device, class, interface)
      bRequest      = 0x09  (SET_REPORT)
      wValue        = 0x0306 (Feature=3 << 8 | ReportID=0x06)
      wIndex        = 1     (interface 1)
"""

import struct
import time

from aula.protocol import WIRED_VID, WIRED_PID, WIRELESS_VID, WIRELESS_PID

REPORT_ID = 0x06
CMD_DIRECT = 0x08
REPORT_SIZE = 520
NUM_LEDS = 122
LED_DATA_OFFSET = 8

# USB control transfer constants
_BM_REQUEST_TYPE = 0x21
_B_REQUEST_SET_REPORT = 0x09
_W_VALUE = (0x03 << 8) | REPORT_ID  # Feature report, ID 0x06
_IFACE = 1
_TIMEOUT_MS = 1000


class DirectModeDevice:
    """Low-level USB device handle for 520-byte direct-mode frames.

    Uses raw libusb control transfers (via ctypes) WITHOUT claiming
    the interface. This keeps the macOS kernel HID driver attached so
    the keyboard continues to function normally during animations.

    The wired device is confirmed. The wireless receiver can be probed
    with device="wireless"; if it rejects the transfer with PIPE, it uses
    the separate 20-byte protocol instead.
    """

    def __init__(self):
        self._raw = None
        self._label = None
        self._total_frames = 0

    @property
    def connected(self):
        return self._raw is not None and self._raw.connected

    @property
    def label(self):
        return self._label

    @property
    def total_frames(self):
        return self._total_frames

    def open(self, prefer="wired"):
        """Find and open the AULA F87 device via raw libusb.

        Args:
            prefer: "wired", "wireless", or "auto".
        """
        from aula.usb_raw import RawUSBDevice

        order = []
        if prefer == "wired":
            order = [(WIRED_VID, WIRED_PID, "wired")]
        elif prefer == "wireless":
            order = [(WIRELESS_VID, WIRELESS_PID, "wireless")]
        elif prefer == "auto":
            order = [
                (WIRED_VID, WIRED_PID, "wired"),
                (WIRELESS_VID, WIRELESS_PID, "wireless"),
            ]
        else:
            raise RuntimeError(f"Unknown direct-mode device preference: {prefer}")

        for vid, pid, label in order:
            raw = RawUSBDevice()
            if raw.open(vid, pid):
                self._raw = raw
                self._label = label
                return label, vid, pid

        if prefer == "wireless":
            raise RuntimeError(
                "Wireless receiver not found.\n"
                "  Connect the 2.4GHz receiver and try again."
            )
        if prefer == "wired":
            raise RuntimeError(
                "Wired AULA F87 not found.\n"
                "  Connect the keyboard via USB-C cable and try again."
            )
        raise RuntimeError(
            "AULA F87 not found.\n"
            "  Connect either USB-C wired mode or the 2.4GHz receiver."
        )

    def close(self):
        if self._raw is not None:
            self._raw.close()
            self._raw = None

    def send_frame(self, report_bytes):
        """Send a pre-built 520-byte feature report via USB control transfer.

        Does NOT claim the interface — keyboard input remains functional.
        """
        if self._raw is None:
            raise RuntimeError("not connected")
        ret = self._raw.ctrl_transfer(
            _BM_REQUEST_TYPE,
            _B_REQUEST_SET_REPORT,
            _W_VALUE,
            _IFACE,
            bytes(report_bytes),
            _TIMEOUT_MS,
        )
        self._total_frames += 1
        return ret

    # --- convenience builders ---

    @staticmethod
    def build_frame(led_colors):
        """Build a 520-byte direct-mode frame.

        Args:
            led_colors: dict of led_index → (r, g, b), or a list of 122
                        (r, g, b) tuples indexed by LED position.
        Returns:
            bytes(520)
        """
        buf = bytearray(REPORT_SIZE)
        buf[0] = REPORT_ID
        buf[1] = CMD_DIRECT
        buf[4] = 0x01
        buf[6] = NUM_LEDS
        buf[7] = 0x01

        if isinstance(led_colors, dict):
            for idx, (r, g, b) in led_colors.items():
                off = LED_DATA_OFFSET + idx * 3
                if off + 2 < REPORT_SIZE:
                    buf[off] = r & 0xFF
                    buf[off + 1] = g & 0xFF
                    buf[off + 2] = b & 0xFF
        else:
            for idx, (r, g, b) in enumerate(led_colors):
                off = LED_DATA_OFFSET + idx * 3
                if off + 2 < REPORT_SIZE:
                    buf[off] = r & 0xFF
                    buf[off + 1] = g & 0xFF
                    buf[off + 2] = b & 0xFF

        return bytes(buf)

    @staticmethod
    def build_blank_frame():
        """520-byte frame with all LEDs off (keepalive)."""
        buf = bytearray(REPORT_SIZE)
        buf[0] = REPORT_ID
        buf[1] = CMD_DIRECT
        buf[4] = 0x01
        buf[6] = NUM_LEDS
        buf[7] = 0x01
        return bytes(buf)


# --- Enable/disable direct mode (aula-rgb-controller protocol) ---

_ENABLE_REPORTS = [
    # Report 0x39: param reset
    (0x39, bytes([0x39, 0x20, 0x06, 0x00, 0x01, 0x00])),
    # Report 0x3C: enable direct mode
    (0x3C, bytes([0x3C, 0x20, 0x01, 0x00])),
    # Report 0x39: param confirm
    (0x39, bytes([0x39, 0x20, 0x06, 0x01, 0x01, 0x00])),
]


def _send_small_report(raw_dev, report_id, data, iface=_IFACE):
    """Send a small SET_REPORT (for enable/disable sequence)."""
    wvalue = (0x03 << 8) | report_id
    # Pad to at least the report size the device expects
    padded = bytearray(520)
    padded[:len(data)] = data
    try:
        return raw_dev.ctrl_transfer(
            _BM_REQUEST_TYPE, _B_REQUEST_SET_REPORT,
            wvalue, iface, bytes(padded), _TIMEOUT_MS,
        )
    except Exception:
        return -1


def enable_direct_mode(dev):
    """Send the 3-step enable sequence (Reports 0x39 + 0x3C + 0x39).

    The OEM capture didn't include these, but aula-rgb-controller says
    they're needed. We send them as best-effort; some firmware versions
    may not require them.
    """
    if not dev.connected:
        raise RuntimeError("not connected")
    for report_id, payload in _ENABLE_REPORTS:
        _send_small_report(dev._raw, report_id, payload)
        time.sleep(0.005)


def disable_direct_mode(dev):
    """Send disable report (0x3C with byte[2]=0x00)."""
    if not dev.connected:
        return
    disable = bytes([0x3C, 0x20, 0x00, 0x00])
    _send_small_report(dev._raw, 0x3C, disable)
