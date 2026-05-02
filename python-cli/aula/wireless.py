"""
AULA F87 — wireless 2.4GHz animation transport.

The 2.4GHz receiver does not accept the wired 520-byte Report 0x06 direct
mode. VM-side USBPcap captures show the OEM app sends 20-byte Report 0x13
frames as HID Output Reports over endpoint-0 control transfers:

    SETUP: 21 09 13 02 01 00 14 00
           |  |  |     |     |
           |  |  |     |     +-- wLength = 20
           |  |  |     +-------- wIndex = interface 1
           |  |  +-------------- wValue = 0x0213 (Output report, ID 0x13)
           |  +----------------- SET_REPORT
           +-------------------- host->device, class, interface

The data phase is the familiar 20-byte OEM frame, e.g.:

    13 88 01 00 23 ... bf

Like the wired direct-mode backend, this uses raw libusb control transfers
without claiming the interface, so normal keyboard input remains functional.
"""

import os
import struct
import time

from aula.protocol import WIRELESS_VID, WIRELESS_PID
from aula.stream import build_audio_frames, build_audio_idle_frame
from aula.usb_raw import RawUSBDevice

_BM_REQUEST_TYPE = 0x21
_B_REQUEST_SET_REPORT = 0x09
_W_VALUE_OUTPUT_13 = (0x02 << 8) | 0x13
_IFACE = 1
_TIMEOUT_MS = 1000


class WirelessStreamDevice:
    """Raw USB control-transfer sender for wireless Report 0x13 frames."""

    def __init__(self, inter_report_delay=0.012):
        self._raw = None
        self._total_frames = 0
        self._total_reports = 0
        self._inter_report_delay = inter_report_delay

    @property
    def connected(self):
        return self._raw is not None and self._raw.connected

    @property
    def total_frames(self):
        return self._total_frames

    @property
    def total_reports(self):
        return self._total_reports

    def open(self):
        raw = RawUSBDevice()
        if not raw.open(WIRELESS_VID, WIRELESS_PID):
            raise RuntimeError(
                "Wireless receiver not found.\n"
                "  Connect the 2.4GHz receiver and try again."
            )
        self._raw = raw
        return "wireless", WIRELESS_VID, WIRELESS_PID

    def close(self):
        if self._raw is not None:
            self._raw.close()
            self._raw = None

    def send_report(self, report):
        """Send one 20-byte Report 0x13 output report."""
        if self._raw is None:
            raise RuntimeError("not connected")
        data = bytes(report)
        if len(data) != 20 or data[0] != 0x13:
            raise ValueError("wireless output report must be 20 bytes and start with 0x13")
        ret = self._raw.ctrl_transfer(
            _BM_REQUEST_TYPE,
            _B_REQUEST_SET_REPORT,
            _W_VALUE_OUTPUT_13,
            _IFACE,
            data,
            _TIMEOUT_MS,
        )
        self._total_reports += 1
        return ret

    def send_audio(self, led_colors, quantize=64):
        """Send one synthesized 0x88 animation frame.

        led_colors: dict of led_index → (r, g, b).
        """
        reports = build_audio_frames(led_colors, quantize=quantize)
        for i, report in enumerate(reports):
            self.send_report(report)
            if self._inter_report_delay and i != len(reports) - 1:
                time.sleep(self._inter_report_delay)
        self._total_frames += 1
        return len(reports)

    def send_idle(self):
        self.send_report(build_audio_idle_frame())
        self._total_frames += 1


def extract_wireless_reports(path):
    """Extract [(gap_seconds, report20), ...] from a USBPcap pcapng.

    Looks for 28-byte control transfer payloads:
      8-byte SETUP packet + 20-byte Report 0x13 data phase.
    """
    from pcapng import FileScanner

    frames = []
    prev_ts = None
    with open(path, "rb") as f:
        for block in FileScanner(f):
            if block.__class__.__name__ != "EnhancedPacket":
                continue
            ts = (block.timestamp_high << 32) | block.timestamp_low
            raw = bytes(block.packet_data)
            if len(raw) < 27:
                continue
            header_len = struct.unpack_from("<H", raw, 0)[0]
            irp_info = raw[16]
            if irp_info & 1:
                continue
            data_len = struct.unpack_from("<I", raw, 23)[0]
            payload = raw[header_len:header_len + data_len]
            if len(payload) != 28:
                continue
            if payload[:8] != bytes.fromhex("21 09 13 02 01 00 14 00"):
                continue
            report = payload[8:]
            if len(report) != 20 or report[0] != 0x13:
                continue
            if (sum(report[:19]) & 0xFF) != report[19]:
                continue
            gap = 0.0 if prev_ts is None else (ts - prev_ts) / 1_000_000
            prev_ts = ts
            frames.append((gap, bytes(report)))
    return frames


def cmd_wireless(action, path=None, speed=1.0, loop=1, duration=5.0, fps=20.0,
                 frag_delay=0.012):
    dev = WirelessStreamDevice(inter_report_delay=frag_delay)
    try:
        label, vid, pid = dev.open()
    except RuntimeError as e:
        print(f"  {e}")
        return 1
    print(f"AULA F87 wireless stream — {label} ({vid:#06x}:{pid:#06x})")

    try:
        if action == "probe":
            ret = dev.send_report(build_audio_idle_frame())
            print(f"  OK: receiver accepted Report 0x13 ({ret} bytes)")
            return 0
        if action == "idle":
            dev.send_idle()
            print("  Sent idle frame.")
            return 0
        if action == "replay":
            if not path:
                print("  --path required for replay mode")
                return 1
            return _replay(dev, path, speed=speed, loop=loop)
    except KeyboardInterrupt:
        print("\n  (interrupted)")
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        dev.close()
    return 0


def _replay(dev, path, speed=1.0, loop=1):
    if not os.path.exists(path):
        print(f"  File not found: {path}")
        return 1
    frames = extract_wireless_reports(path)
    if not frames:
        print(f"  No wireless Report 0x13 control transfers found in {path}")
        return 1

    total_time = sum(gap for gap, _ in frames) / max(speed, 0.001)
    print(f"  Reports : {len(frames)}")
    print(f"  Speed   : {speed}x -> ~{total_time * max(1, loop):.1f}s total")

    start = time.monotonic()
    sent = 0
    for _ in range(max(1, loop)):
        for gap, report in frames:
            delay = gap / max(speed, 0.001)
            if delay > 0:
                time.sleep(delay)
            dev.send_report(report)
            sent += 1
    elapsed = time.monotonic() - start
    print(f"  Done: {sent} reports in {elapsed:.2f}s ({sent / max(elapsed, 1e-6):.1f} reports/s)")
    return 0


