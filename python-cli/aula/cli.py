"""
AULA F87 — CLI entry point (argparse).
"""

import argparse
import sys


def main(argv=None):
    from aula.animations import ANIMATIONS as _ANIMATIONS

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
    p_eff = sub.add_parser("effect", help="Set a lighting effect (0=OFF, supported built-ins)")
    p_eff.add_argument("effect_num", type=int, help="Effect number")
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
    p_sleep.add_argument("minutes", type=int, choices=range(0, 61),
                         help="Minutes until sleep (0 = disable, max 60)")

    # debounce
    p_debounce = sub.add_parser("debounce", help="Set debounce time (key response time)")
    p_debounce.add_argument("level", type=int, choices=[1, 2, 3, 4, 5],
                            help="Debounce time in milliseconds (1-5)")

    # reset
    sub.add_parser("reset", help="Factory reset all lighting settings")

    # animate — run named animations on auto-detected transport (same generators as web app)
    _anim_epilog = (
        "Animations (same generators as the web Custom animations panel):\n  "
        + "\n  ".join(sorted(_ANIMATIONS.keys()))
        + "\n\nExamples:\n"
        "  %(prog)s --list\n"
        "  %(prog)s sine -d 15 --fps 20\n"
        "  %(prog)s fire --transport wireless"
    )
    p_anim = sub.add_parser(
        "animate",
        help="Run a named built-in animation (auto-detects wired/wireless)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_anim_epilog,
    )
    p_anim.add_argument("name", nargs="?", default=None,
                        help="Animation name (omit or use --list to print all names)")
    p_anim.add_argument("-l", "--list", action="store_true",
                        help="List animation names and exit")
    p_anim.add_argument("-d", "--duration", type=float, default=10.0,
                        help="Duration in seconds (default 10)")
    p_anim.add_argument("--fps", type=float, default=20.0,
                        help="Target FPS (default 20)")
    p_anim.add_argument("--transport", choices=["auto", "wired", "wireless"],
                        default="auto", help="Force a transport (default: auto)")

    # probe — identify which protocol paths the device actually supports
    sub.add_parser(
        "probe",
        help="Dump HID collections and probe both RE protocol families "
             "(OEM 20-byte 0x13 vs OpenRGB 520-byte 0x06)",
    )

    # bench — sustained-FPS streaming benchmark
    p_bench = sub.add_parser(
        "bench",
        help="Benchmark sustained streaming framerate",
    )
    p_bench.add_argument("mode", choices=["audio", "perkey"],
                         help="audio=cmd 0x88 (brightness only), perkey=cmd 0x02 (full RGB)")
    p_bench.add_argument("anim", help="Animation: audio={wave,sweep,idle} perkey={rainbow,pulse}")
    p_bench.add_argument("-d", "--duration", type=float, default=5.0,
                         help="Seconds to stream (default 5)")
    p_bench.add_argument("--fps", type=float, default=0,
                         help="Target FPS (0 = as fast as possible)")
    p_bench.add_argument("--color", nargs=3, type=int, metavar=("R", "G", "B"),
                         help="Base color for audio mode (default 255 255 255)")
    p_bench.add_argument("-e", "--effect", type=int, default=1,
                         help="Effect to arm for audio mode (default 1=Fixed on)")
    p_bench.add_argument("--page", type=lambda x: int(x, 0),
                         help="Prefer HID usage page")
    p_bench.add_argument("--frag-delay-ms", type=float, default=0.0,
                         help="Inter-fragment sleep in ms (OEM uses ~12)")

    # replay — play back OEM pcapng bytes verbatim
    p_rep = sub.add_parser(
        "replay",
        help="Replay a pcapng capture of OEM USB traffic to the keyboard",
    )
    p_rep.add_argument("path", help="Path to a .pcapng file")
    p_rep.add_argument("--speed", type=float, default=1.0,
                       help="Playback speed multiplier (default 1.0)")
    p_rep.add_argument("--loop", type=int, default=1,
                       help="Replay N times (default 1)")
    p_rep.add_argument("--min-frag-delay-ms", type=float, default=0.0,
                       help="Floor on inter-fragment sleep (ms)")
    p_rep.add_argument("--cmd", type=lambda x: int(x, 0), default=0x88,
                       help="Filter to a single cmd byte (default 0x88; -1 = all)")
    p_rep.add_argument("--page", type=lambda x: int(x, 0),
                       help="Prefer HID usage page")

    # direct — test 520-byte direct-mode LED control
    p_direct = sub.add_parser(
        "direct",
        help="Test 520-byte direct mode",
    )
    p_direct.add_argument("action", choices=["probe", "blank", "test", "replay", "rainbow"],
                          help="probe=transport test, blank=all off, test=solid color, "
                               "replay=pcapng playback, rainbow=animated")
    p_direct.add_argument("--device", choices=["wired", "wireless", "auto"],
                          default="wired",
                          help="Device transport to use (default: wired)")
    p_direct.add_argument("--color", nargs=3, type=int, metavar=("R", "G", "B"),
                          default=[255, 0, 0],
                          help="Color for 'test' mode (default: 255 0 0)")
    p_direct.add_argument("--path", help="pcapng file for 'replay' mode")
    p_direct.add_argument("--speed", type=float, default=1.0,
                          help="Playback speed for replay (default 1.0)")
    p_direct.add_argument("--loop", type=int, default=1,
                          help="Replay loop count (default 1)")
    p_direct.add_argument("-d", "--duration", type=float, default=5.0,
                          help="Duration for 'rainbow' mode (default 5s)")
    p_direct.add_argument("--fps", type=float, default=20.0,
                          help="Target FPS for 'rainbow' mode (default 20)")
    p_direct.add_argument("--no-enable", action="store_true",
                          help="Skip the direct-mode enable sequence")

    # wireless — 2.4GHz receiver animation path (20-byte Report 0x13 over control)
    p_wireless = sub.add_parser(
        "wireless",
        help="Test 2.4GHz receiver animation stream",
    )
    p_wireless.add_argument("action", choices=["probe", "idle", "replay"],
                            help="probe=transport test, idle=no-op frame, "
                                 "replay=pcapng playback")
    p_wireless.add_argument("--path", help="pcapng file for 'replay' mode")
    p_wireless.add_argument("--speed", type=float, default=1.0,
                            help="Playback speed for replay (default 1.0)")
    p_wireless.add_argument("--loop", type=int, default=1,
                            help="Replay loop count (default 1)")
    p_wireless.add_argument("-d", "--duration", type=float, default=5.0,
                            help="Duration for 'rainbow' mode (default 5s)")
    p_wireless.add_argument("--fps", type=float, default=20.0,
                            help="Target FPS for 'rainbow' mode (default 20)")
    p_wireless.add_argument("--frag-delay-ms", type=float, default=12.0,
                            help="Inter-fragment sleep for synthesized frames (default 12)")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    from aula.commands import (cmd_scan, cmd_list, cmd_read, cmd_effect,
                               cmd_perkey, cmd_raw, cmd_sleep, cmd_debounce, cmd_reset)
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
    elif args.command == "debounce":
        return cmd_debounce(args.level)
    elif args.command == "reset":
        return cmd_reset()
    elif args.command == "animate":
        from aula.animate_cmd import cmd_animate
        from aula.animations import ANIMATIONS

        if args.list or args.name is None:
            print("Available animations:")
            for name in sorted(ANIMATIONS):
                doc = (ANIMATIONS[name].__doc__ or "").strip()
                line = doc.split("\n")[0] if doc else ""
                suffix = f" — {line}" if line else ""
                print(f"  {name}{suffix}")
            return 0
        return cmd_animate(
            name=args.name,
            duration=args.duration,
            fps=args.fps,
            transport=args.transport,
        )
    elif args.command == "probe":
        from aula.probe import cmd_probe
        return cmd_probe()
    elif args.command == "bench":
        from aula.bench import cmd_bench
        return cmd_bench(
            mode=args.mode,
            anim=args.anim,
            duration=args.duration,
            target_fps=args.fps,
            color=args.color,
            effect=args.effect,
            page=args.page,
            inter_frag_delay=args.frag_delay_ms / 1000.0,
        )
    elif args.command == "replay":
        from aula.bench import cmd_replay
        return cmd_replay(
            path=args.path,
            speed=args.speed,
            loop=args.loop,
            min_frag_delay=args.min_frag_delay_ms / 1000.0,
            cmd_filter=(None if args.cmd == -1 else args.cmd),
            page=args.page,
        )
    elif args.command == "direct":
        from aula.direct_cmd import cmd_direct
        return cmd_direct(
            action=args.action,
            color=tuple(args.color),
            path=args.path,
            speed=args.speed,
            loop=args.loop,
            duration=args.duration,
            fps=args.fps,
            skip_enable=args.no_enable,
            device=args.device,
        )
    elif args.command == "wireless":
        from aula.wireless import cmd_wireless
        return cmd_wireless(
            action=args.action,
            path=args.path,
            speed=args.speed,
            loop=args.loop,
            duration=args.duration,
            fps=args.fps,
            frag_delay=args.frag_delay_ms / 1000.0,
        )

    return 0
