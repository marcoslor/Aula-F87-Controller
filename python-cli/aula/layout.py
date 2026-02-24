"""
AULA F87 — Key names, LED index mappings, groups, and color palette/map builders.
"""

from aula.protocol import CMD_PERKEY, SUBCMD_PERKEY, _build
from aula.effects import _PAL_TEMPLATE, _PAL_ZEROS, _PAL_LAST

# ── Key name → LED index (from KB.ini) ───────────────────────────────────
KEY_NAMES = {
    # F-row
    "esc": 0, "f1": 12, "f2": 18, "f3": 24, "f4": 30,
    "f5": 36, "f6": 42, "f7": 48, "f8": 54, "f9": 60,
    "f10": 66, "f11": 72, "f12": 78, "prtsc": 84, "scrlk": 90, "pause": 96,
    # Number row
    "`": 1, "1": 7, "2": 13, "3": 19, "4": 25, "5": 31,
    "6": 37, "7": 43, "8": 49, "9": 55, "0": 61,
    "-": 67, "=": 73, "bksp": 79, "ins": 85, "home": 91, "pgup": 97,
    # QWERTY row
    "tab": 2, "q": 8, "w": 14, "e": 20, "r": 26, "t": 32,
    "y": 38, "u": 44, "i": 50, "o": 56, "p": 62,
    "[": 68, "]": 74, "\\": 80, "del": 86, "end": 92, "pgdn": 98,
    # Home row
    "caps": 3, "a": 9, "s": 15, "d": 21, "f": 27, "g": 33,
    "h": 39, "j": 45, "k": 51, "l": 57, ";": 63, "'": 69, "enter": 81,
    # Shift row
    "lshift": 4, "z": 10, "x": 16, "c": 22, "v": 28, "b": 34,
    "n": 40, "m": 46, ",": 52, ".": 58, "/": 64, "rshift": 82, "up": 94,
    # Bottom row
    "lctrl": 5, "lwin": 11, "lalt": 17, "space": 35,
    "ralt": 53, "fn": 59, "app": 65, "rctrl": 83,
    "left": 89, "down": 95, "right": 101,
}

# ── Group aliases ────────────────────────────────────────────────────────
KEY_GROUPS = {
    "wasd":    ["w", "a", "s", "d"],
    "arrows":  ["up", "down", "left", "right"],
    "fkeys":   [f"f{i}" for i in range(1, 13)],
    "numrow":  [str(i) for i in range(1, 10)] + ["0"],
}


# ── Color parsing ────────────────────────────────────────────────────────
def _parse_color(color_str):
    """Parse '#RRGGBB' or 'RRGGBB' hex string into (r, g, b) tuple."""
    s = color_str.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Expected 6 hex chars, got '{color_str}'")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


# ── Palette builder ──────────────────────────────────────────────────────
def _build_palette(color_rgb=None):
    """Build 37 palette payloads (15 bytes each).

    If color_rgb is provided, sets the custom color slot in fragment 1.
    Returns list of 37 bytes objects.
    """
    payloads = []
    for i in range(37):
        if i < len(_PAL_TEMPLATE):
            p = bytearray(_PAL_TEMPLATE[i])
        elif i == 36:
            p = bytearray(_PAL_LAST)
        else:
            p = bytearray(_PAL_ZEROS)

        # Custom color goes in fragment 1, payload offsets 8/9/10 (RGB) + 12 (active)
        if i == 1 and color_rgb:
            p[8] = color_rgb[0]
            p[9] = color_rgb[1]
            p[10] = color_rgb[2]
            p[12] = 0xFF
        payloads.append(bytes(p))
    return payloads


# ── Per-key color map builder ────────────────────────────────────────────
def _build_perkey_map(key_colors):
    """Build 28 per-key color map frames (complete 20-byte frames).

    Args:
        key_colors: dict of led_index -> (r, g, b)

    Returns:
        list of 28 bytes objects (ready to send via _tx_bulk).
    """
    # 3 planes × 126 entries each
    R = bytearray(126)
    G = bytearray(126)
    B = bytearray(126)

    for idx, (r, g, b) in key_colors.items():
        if 0 <= idx < 126:
            R[idx] = r
            G[idx] = g
            B[idx] = b

    frames = []
    seq = 0

    # R plane: seq 0–8  (9 fragments × 14 bytes = 126 entries)
    for s in range(9):
        payload = bytearray(15)
        payload[0] = 0x0E
        for j in range(14):
            payload[1 + j] = R[s * 14 + j]
        frames.append(_build(CMD_PERKEY, SUBCMD_PERKEY, seq, payload))
        seq += 1

    # G plane: seq 9–17
    for s in range(9):
        payload = bytearray(15)
        payload[0] = 0x0E
        for j in range(14):
            payload[1 + j] = G[s * 14 + j]
        frames.append(_build(CMD_PERKEY, SUBCMD_PERKEY, seq, payload))
        seq += 1

    # B plane: seq 18–26
    for s in range(9):
        payload = bytearray(15)
        payload[0] = 0x0E
        for j in range(14):
            payload[1 + j] = B[s * 14 + j]
        frames.append(_build(CMD_PERKEY, SUBCMD_PERKEY, seq, payload))
        seq += 1

    # Trailer: seq 27
    trailer = bytearray(15)
    trailer[0] = 0x06
    trailer[3] = 0x5A
    trailer[4] = 0xA5
    frames.append(_build(CMD_PERKEY, SUBCMD_PERKEY, seq, trailer))

    return frames
