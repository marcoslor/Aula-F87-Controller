"""
pcapng utilities — extract 20-byte HID fragments from USBPcap captures
so they can be replayed through the streaming engine.

We deliberately use a tiny dependency-free scanner rather than pyshark /
tshark — the 20-byte report-ID-0x13 frames are trivial to find in any
USBPcap payload (scan for 0x13 at any offset, validate the trailing
checksum, and accept).
"""

import os

from pcapng import FileScanner  # python-pcapng


def _hid_fragments_from_packet(raw):
    """Yield 20-byte HID fragments (report id 0x13) found anywhere in `raw`."""
    for i in range(len(raw) - 20 + 1):
        c = raw[i:i + 20]
        if c[0] != 0x13:
            continue
        if sum(c[:19]) & 0xFF != c[19]:
            continue
        yield bytes(c)
        return  # at most one per packet


def extract_fragments(path, cmd_filter=None):
    """Return [(ts_ns, frag_bytes), ...] sorted by timestamp.

    Args:
        path: path to a pcapng file.
        cmd_filter: if set, keep only fragments whose cmd byte matches.
    """
    out = []
    with open(path, "rb") as f:
        for block in FileScanner(f):
            if block.__class__.__name__ != "EnhancedPacket":
                continue
            ts_ns = (block.timestamp_high << 32 | block.timestamp_low)
            raw = bytes(block.packet_data)
            for frag in _hid_fragments_from_packet(raw):
                if cmd_filter is not None and frag[1] != cmd_filter:
                    continue
                out.append((ts_ns, frag))
    out.sort(key=lambda x: x[0])
    return out


def fragments_with_gaps(path, cmd_filter=None):
    """Return [(gap_seconds, frag_bytes), ...] ready for StreamEngine.replay.

    The first fragment gets gap=0.
    """
    raw = extract_fragments(path, cmd_filter=cmd_filter)
    if not raw:
        return []
    out = []
    prev_ts = None
    for ts, frag in raw:
        if prev_ts is None:
            out.append((0.0, frag))
        else:
            # Timestamps from pcapng USBPcap are typically µs resolution,
            # expressed as high<<32|low with the if_tsresol option. We treat
            # the delta as a raw integer and divide by 1e6 which matches the
            # default 6-digit precision used by USBPcap / Wireshark.
            out.append(((ts - prev_ts) / 1_000_000, frag))
        prev_ts = ts
    return out


def default_capture_dir():
    """Return the canonical captures/ directory relative to this repo."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", "captures"))
