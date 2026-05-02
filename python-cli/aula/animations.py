"""
AULA F87 — Animation generators.

Each generator is a callable with signature:

    gen(t: float, n_leds: int) -> dict[int, tuple[int,int,int]]

where `t` is elapsed time in seconds and `n_leds` is the total LED count.
Returns a dict of led_index → (r, g, b).

These are transport-agnostic: they work with both the wired 520-byte
direct mode and the wireless 20-byte 0x88 color-group protocol.
"""

import colorsys
import math

from aula.layout import KEY_NAMES

# Physical row layout (left-to-right, top-to-bottom)
ROWS = [
    [KEY_NAMES[k] for k in row]
    for row in [
        ["esc", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9",
         "f10", "f11", "f12", "prtsc", "scrlk", "pause"],
        ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9",
         "0", "-", "=", "bksp", "ins", "home", "pgup"],
        ["tab", "q", "w", "e", "r", "t", "y", "u", "i", "o",
         "p", "[", "]", "\\", "del", "end", "pgdn"],
        ["caps", "a", "s", "d", "f", "g", "h", "j", "k", "l",
         ";", "'", "enter"],
        ["lshift", "z", "x", "c", "v", "b", "n", "m", ",", ".",
         "/", "rshift", "up"],
        ["lctrl", "lwin", "lalt", "space", "ralt", "fn", "app", "rctrl",
         "left", "down", "right"],
    ]
]

ALL_LEDS = sorted(set(KEY_NAMES.values()))
N_LEDS = len(ALL_LEDS)
N_ROWS = len(ROWS)
MAX_COL = max(len(row) for row in ROWS)

# Physical position lookup: led_index → (row 0..5, col_fraction 0..1)
_LED_POS = {}
for ri, row in enumerate(ROWS):
    for ci, led in enumerate(row):
        _LED_POS[led] = (ri / max(N_ROWS - 1, 1), ci / max(len(row) - 1, 1))


def _hsv(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


# ─── Animations ──────────────────────────────────────────────────────────

def sine_wave(t, n_leds=N_LEDS):
    """Horizontal sine wave: hue shifts left-to-right, oscillates over time."""
    colors = {}
    for led, (row_f, col_f) in _LED_POS.items():
        hue = col_f + t * 0.3
        val = 0.5 + 0.5 * math.sin(col_f * math.tau * 2 - t * 4.0)
        colors[led] = _hsv(hue, 1.0, val)
    return colors


def rain(t, n_leds=N_LEDS):
    """Vertical rain: drops fall from top to bottom in columns."""
    colors = {}
    drop_speed = 3.0
    n_drops = 6
    for led, (row_f, col_f) in _LED_POS.items():
        best_v = 0.0
        for d in range(n_drops):
            drop_col = (d * 0.618 + t * 0.1) % 1.0
            col_dist = abs(col_f - drop_col)
            if col_dist > 0.06:
                continue
            drop_y = ((t * drop_speed + d * 1.7) % 2.0) - 0.5
            row_dist = abs(row_f - drop_y)
            if row_dist < 0.3:
                v = max(0.0, 1.0 - row_dist / 0.3) * (1.0 - col_dist / 0.06)
                best_v = max(best_v, v)
        if best_v > 0.05:
            colors[led] = _hsv(0.55, 0.8, best_v)
    return colors


def fire(t, n_leds=N_LEDS):
    """Fire effect: warm colors rising from bottom."""
    colors = {}
    for led, (row_f, col_f) in _LED_POS.items():
        # Hotter at bottom (row_f=1), cooler at top (row_f=0)
        heat = max(0, 1.0 - row_f * 0.7)
        flicker = 0.5 + 0.5 * math.sin(col_f * 13.7 + t * 7.0)
        flicker2 = 0.5 + 0.5 * math.sin(col_f * 7.3 - t * 5.0 + row_f * 3.0)
        v = heat * (0.4 + 0.6 * flicker * flicker2)
        if v < 0.05:
            continue
        hue = 0.0 + 0.08 * (1.0 - row_f)  # red at bottom, orange/yellow up
        colors[led] = _hsv(hue, 1.0 - row_f * 0.3, min(1.0, v))
    return colors


def breathing(t, n_leds=N_LEDS):
    """Whole-board breathing with slow hue rotation."""
    v = 0.5 + 0.5 * math.sin(t * 2.0)
    hue = t * 0.05
    color = _hsv(hue, 1.0, v)
    return {led: color for led in ALL_LEDS}


def snake(t, n_leds=N_LEDS):
    """Boustrophedon snake: zigzags across rows."""
    path = []
    for ri, row in enumerate(ROWS):
        path.extend(reversed(row) if ri % 2 == 0 else row)

    n = len(path)
    head = int(t * 16.0) % n
    tail_len = 10
    hue = (t * 0.08) % 1.0

    colors = {}
    for offset in range(tail_len):
        led = path[(head - offset) % n]
        scale = (tail_len - offset) / tail_len
        colors[led] = _hsv(hue, 1.0, scale)
    return colors


def rainbow(t, n_leds=N_LEDS):
    """Full-board rainbow sweep (works best on wired direct mode)."""
    colors = {}
    for led, (row_f, col_f) in _LED_POS.items():
        hue = col_f + t * 0.3
        colors[led] = _hsv(hue)
    return colors


def wave_vertical(t, n_leds=N_LEDS):
    """Vertical wave: brightness pulses from top to bottom."""
    colors = {}
    for led, (row_f, col_f) in _LED_POS.items():
        v = 0.5 + 0.5 * math.sin(row_f * math.tau * 1.5 - t * 3.0)
        hue = 0.6 + row_f * 0.15
        colors[led] = _hsv(hue, 0.8, v)
    return colors


def sparkle(t, n_leds=N_LEDS):
    """Random-ish sparkle using deterministic hash."""
    colors = {}
    frame = int(t * 20)
    for led in ALL_LEDS:
        seed = (led * 7919 + frame * 104729) % 100
        if seed < 8:
            hue = (led * 0.0618 + t * 0.1) % 1.0
            colors[led] = _hsv(hue, 0.7, 1.0)
    return colors


# ─── Registry ────────────────────────────────────────────────────────────

ANIMATIONS = {
    "sine": sine_wave,
    "rain": rain,
    "fire": fire,
    "breathing": breathing,
    "snake": snake,
    "rainbow": rainbow,
    "wave": wave_vertical,
    "sparkle": sparkle,
}
