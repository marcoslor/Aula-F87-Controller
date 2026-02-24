"""
AULA F87 — CLI entry point (argparse).
"""

import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="aula_f87",
        description="AULA F87 Keyboard Controller — USB HID lighting control",
    )
    sub = parser.add_subparsers(dest="command")

    # scan
    sub.add_parser("scan", help="Scan for connected AULA F87 keyboards")

    # list
    sub.add_parser("list", help="List available lighting effects")

    # read
    sub.add_parser("read", help="Read current keyboard configuration")

    # effect
    p_eff = sub.add_parser("effect", help="Set a lighting effect (1-18)")
    p_eff.add_argument("effect_num", type=int, help="Effect number (1-18)")
    p_eff.add_argument("--color", nargs=3, type=int, metavar=("R", "G", "B"),
                       help="Custom color (0-255 each)")
    p_eff.add_argument("--colorful", action="store_true",
                       help="Use rainbow / colorful mode")
    p_eff.add_argument("-s", "--speed", type=int, choices=range(5),
                       help="Animation speed (0-4)")
    p_eff.add_argument("-b", "--brightness", type=int, choices=range(5),
                       help="Brightness level (0-4)")
    p_eff.add_argument("--page", type=lambda x: int(x, 0),
                       help="Prefer HID usage page (e.g. 0xFF00)")
    p_eff.add_argument("--fast", action="store_true",
                       help="Skip USB read delays for near-instant apply")

    # perkey
    p_pk = sub.add_parser("perkey", help="Set per-key RGB colors")
    p_pk.add_argument("keys", nargs="*",
                      help="key:#RRGGBB pairs (e.g. esc:#ff0000 wasd:#00ff00)")
    p_pk.add_argument("--page", type=lambda x: int(x, 0),
                      help="Prefer HID usage page")
    p_pk.add_argument("--list-keys", action="store_true",
                      help="Show available key names and groups")

    # raw
    p_raw = sub.add_parser("raw", help="Send a raw 20-byte HID fragment (hex)")
    p_raw.add_argument("hex", help="40 hex chars (20 bytes)")

    # sleep
    p_sleep = sub.add_parser("sleep", help="Set sleep timer (auto-off)")
    p_sleep.add_argument("minutes", type=int, choices=[0, 5, 10, 15],
                         help="Minutes until sleep (0 = disable)")

    # reset
    sub.add_parser("reset", help="Factory reset all lighting settings")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    from aula.commands import (cmd_scan, cmd_list, cmd_read, cmd_effect,
                               cmd_perkey, cmd_raw, cmd_sleep, cmd_reset)
    from aula.layout import KEY_NAMES, KEY_GROUPS

    if args.command == "scan":
        return cmd_scan()
    elif args.command == "list":
        return cmd_list()
    elif args.command == "read":
        return cmd_read()
    elif args.command == "effect":
        return cmd_effect(
            args.effect_num,
            color_rgb=tuple(args.color) if args.color else None,
            colorful=args.colorful,
            speed=args.speed,
            brightness=args.brightness,
            page=args.page,
            fast=args.fast,
        )
    elif args.command == "perkey":
        if args.list_keys:
            print("Key names:")
            for name, idx in sorted(KEY_NAMES.items(), key=lambda x: x[1]):
                print(f"  {name:<10} (LED {idx})")
            print("\nGroups:")
            for name, keys in KEY_GROUPS.items():
                print(f"  {name:<10} → {', '.join(keys)}")
            return 0
        if not args.keys:
            print("Provide key:color pairs. Use --list-keys for names.")
            return 1
        return cmd_perkey(args.keys, page=args.page)
    elif args.command == "raw":
        return cmd_raw(args.hex)
    elif args.command == "sleep":
        return cmd_sleep(args.minutes)
    elif args.command == "reset":
        return cmd_reset()

    return 0
