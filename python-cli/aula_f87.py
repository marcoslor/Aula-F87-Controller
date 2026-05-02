#!/usr/bin/env python3
# /// script
# dependencies = ["hid>=1.0.6", "python-pcapng>=2.1.1", "pyusb>=1.0.0"]
# ///
"""
AULA F87 Keyboard Controller - Python CLI

Control AULA F87 keyboard lighting via USB HID.
Protocol reverse-engineered from pcapng captures of the OEM Windows app.

Usage:
    uv run aula_f87.py <command>

Commands:
    scan                     Show HID device info
    effect <number>          Set built-in effect (0 = off)
    animate [name]           Run built-in animations (same generators as web); see animate --help
    list                     Show available effects
    read                     Read current keyboard config
    perkey <key:#color ...>  Set per-key RGB colors
    sleep <0|5|10|15>        Set sleep timer (minutes, 0=off)
    debounce <1|2|3|4|5>     Set debounce time in milliseconds (1-5ms)
    reset                    Factory reset lighting
    raw <hex>                Send raw 20-byte fragment (debugging)
    probe                    Probe HID descriptors + both RE protocol families
    bench <mode> <anim>      Sustained-FPS benchmark (mode=audio|perkey)
    replay <pcapng>          Replay captured OEM 20-byte fragments (wireless)
    direct <action>          520-byte direct mode (wired USB-C, needs sudo)
    wireless <action>        2.4GHz Report 0x13 animation stream

Examples:
    uv run aula_f87.py animate --list
    uv run aula_f87.py animate sine -d 12 --fps 24 --transport auto
"""

import sys
from aula.cli import main

if __name__ == "__main__":
    sys.exit(main())
