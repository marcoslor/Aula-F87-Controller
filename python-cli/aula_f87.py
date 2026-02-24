#!/usr/bin/env python3
# /// script
# dependencies = ["hid>=1.0.6"]
# ///
"""
AULA F87 Keyboard Controller - Python CLI

Control AULA F87 keyboard lighting via USB HID.
Protocol reverse-engineered from pcapng captures of the OEM Windows app.

Usage:
    sudo -E env DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run aula_f87.py <command>

Commands:
    scan                     Show HID device info (no sudo needed)
    effect <1-18>            Set built-in effect
    list                     Show available effects
    read                     Read current keyboard config
    perkey <key:#color ...>  Set per-key RGB colors
    sleep <0|5|10|15>        Set sleep timer (minutes, 0=off)
    reset                    Factory reset lighting
    raw <hex>                Send raw 20-byte fragment (debugging)
"""

import sys
from aula.cli import main

if __name__ == "__main__":
    sys.exit(main())
