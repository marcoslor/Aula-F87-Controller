"""
AULA F87 HID Protocol — constants, frame builders, and encoding helpers.
"""

# ── USB Identifiers ──────────────────────────────────────────────────────
WIRED_VID    = 0x258A
WIRED_PID    = 0x010C
WIRELESS_VID = 0x3554
WIRELESS_PID = 0xFA09

# ── Report / command bytes ───────────────────────────────────────────────
REPORT_ID = 0x13

CMD_READ   = 0x44
CMD_WRITE  = 0x04
CMD_COLOR  = 0x09
CMD_PERKEY = 0x02
CMD_SAVE   = 0x0A

SUBCMD_CONFIG  = 0x0A
SUBCMD_PALETTE = 0x25
SUBCMD_PERKEY  = 0x1C
SUBCMD_CONFIRM = 0x01

SELF_DEFINE_EFFECT = 21  # 0x15


# ── Checksum ─────────────────────────────────────────────────────────────
def _checksum(data):
    """Sum of bytes 0–18, mod 256."""
    return sum(data[0:19]) & 0xFF


# ── Frame builder ────────────────────────────────────────────────────────
def _build(cmd, subcmd, seq, payload):
    """Build a 20-byte HID output report frame.

    Args:
        cmd:     Command byte (e.g. CMD_WRITE).
        subcmd:  Sub-command byte (e.g. SUBCMD_CONFIG).
        seq:     Sequence number (fragment index).
        payload: 15-byte payload (bytes or list).

    Returns:
        bytes: 20-byte frame with checksum.
    """
    f = bytearray(20)
    f[0] = REPORT_ID
    f[1] = cmd
    f[2] = subcmd
    f[3] = seq
    for i in range(min(15, len(payload))):
        f[4 + i] = payload[i]
    f[19] = _checksum(f)
    return bytes(f)


# ── Per-effect table location ────────────────────────────────────────────
def _effect_table_loc(n):
    """Return (config_seq, byte_offset) for effect n's brightness/speed pair.

    Effects 1–6  → cfg[4], offset 7 + (n-1)*2
    Effects 7–13 → cfg[5], offset 5 + (n-7)*2
    Effects 14–18→ cfg[6], offset 5 + (n-14)*2
    """
    if 1 <= n <= 6:
        return (4, 7 + (n - 1) * 2)
    if 7 <= n <= 13:
        return (5, 5 + (n - 7) * 2)
    if 14 <= n <= 18:
        return (6, 5 + (n - 14) * 2)
    # Fallback for self-define (21) — safe default
    return (4, 7)


# ── Speed byte encoding ─────────────────────────────────────────────────
def _encode_speed_byte(speed, colorful):
    """Encode speed (0–4) and colorful flag into a single byte.

    High nibble = speed, low nibble = 0x7 (colorful) or 0x0 (single-color).
    """
    return (speed << 4) | (0x07 if colorful else 0x00)


def _decode_speed_byte(b):
    """Decode a speed byte into (speed, is_colorful)."""
    return ((b >> 4) & 0xF, (b & 0xF) == 0x7)
