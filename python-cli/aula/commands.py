import time



from aula.protocol import CMD_WRITE, CMD_COLOR, CMD_SAVE, SUBCMD_CONFIG, SUBCMD_PALETTE, SUBCMD_CONFIRM, \
                          WIRED_VID, WIRED_PID, WIRELESS_VID, WIRELESS_PID, SELF_DEFINE_EFFECT, \
                          _decode_speed_byte, _effect_table_loc, _encode_speed_byte, _checksum, _build
from aula.device import _find_device, _read_config, _tx_bulk, _tx_rx
from aula.layout import KEY_GROUPS, KEY_NAMES, _parse_color, _build_palette, _build_perkey_map
from aula.effects import EFFECTS, _CFG_TEMPLATE, _PAL_TEMPLATE, _PAL_ZEROS, _PAL_LAST


def cmd_scan():
    print("Scanning for AULA F87...")
    print("=" * 60)
    import hid
    found = False
    for vid, pid, label in [(WIRED_VID, WIRED_PID, "wired"),
                            (WIRELESS_VID, WIRELESS_PID, "wireless")]:
        devs = hid.enumerate(vid, pid)
        if not devs:
            print(f"  {label}: not connected")
            continue
        found = True
        print(f"\n  {label} (0x{vid:04X}:0x{pid:04X}) - {len(devs)} collection(s):")
        for d in devs:
            up = d["usage_page"]
            tag = " ** vendor **" if 0xFF00 <= up <= 0xFFFF else ""
            print(f"    iface={d['interface_number']}  page=0x{up:04X}  usage=0x{d['usage']:04X}{tag}")
    if not found:
        print("  No AULA keyboard found.")
        return 1
    return 0


def cmd_list():
    print("Available Effects (AULA F87)")
    print("=" * 60)
    print(f"{'#':<4} {'Name':<22} {'Speed':<6} {'Color'}")
    print("-" * 60)
    for n, e in EFFECTS.items():
        spd = "yes" if e["speed"] else "-"
        clr = "--color / --colorful" if e["color"] else "--colorful only"
        print(f"{n:<4} {e['name']:<22} {spd:<6} {clr}")
    print("=" * 60)
    print("\nUsage:")
    print("  effect 2 --color 255 0 0       # Respire in red")
    print("  effect 2 --colorful -s 3       # Respire rainbow, speed 3")
    print("  effect 3                       # Rainbow (always colorful)")
    print("  effect 1 --color 0 255 0 -b 2  # Fixed green, brightness 2")
    return 0


def cmd_read():
    dev, mode, info = _find_device()
    if not dev:
        print("Keyboard not found.")
        return 1
    print(f"Connected: {mode} (page=0x{info['usage_page']:04X})")
    config = _read_config(dev, timeout_ms=500, max_reads=15)
    for i, r in enumerate(config):
        if not r:
            continue
        ann = ""
        if r[3] == 0:
            eff_num = r[15]
            name = EFFECTS.get(eff_num, {}).get("name", "?")
            tbl_seq, tbl_off = _effect_table_loc(eff_num) if 1 <= eff_num <= 18 else (None, None)
            if tbl_seq is not None and config[tbl_seq]:
                bright = config[tbl_seq][tbl_off]
                spd, is_cf = _decode_speed_byte(config[tbl_seq][tbl_off + 1])
                cm = "colorful" if is_cf else "single-color"
                ann = f"  <- effect={eff_num}({name}) bright={bright} speed={spd} [{cm}]"
            else:
                ann = f"  <- effect={eff_num}({name})"
        print(f"  [{i:2}] {r.hex()}{ann}")
    dev.close()
    return 0


def cmd_effect(effect_num, color_rgb=None, colorful=False,
               speed=None, brightness=None, page=None, fast=False):
    if effect_num not in EFFECTS:
        print(f"Unknown effect {effect_num}. Valid: 1-18 (see 'list').")
        return 1

    eff = EFFECTS[effect_num]
    tgt_seq, tgt_off = _effect_table_loc(effect_num)

    desc = f"Setting #{effect_num}: {eff['name']}"
    if color_rgb:
        desc += f"  color=({color_rgb[0]},{color_rgb[1]},{color_rgb[2]})"
    if colorful:
        desc += "  [colorful]"
    if brightness is not None:
        desc += f"  bright={brightness}"
    if speed is not None:
        desc += f"  speed={speed}"
    print(desc)

    dev, mode, info = _find_device(prefer_page=page)
    if not dev:
        print("Keyboard not found.")
        return 1
    print(f"  Connected: {mode} (page=0x{info['usage_page']:04X})")

    # Phase 1: Read current config
    got_config = False
    if not fast:
        config = _read_config(dev, timeout_ms=300, max_reads=12)
        got_config = all(c is not None for c in config)
        if got_config:
            old_eff = config[0][15]
            old_name = EFFECTS.get(old_eff, {}).get("name", "?")
            o_seq, o_off = _effect_table_loc(old_eff) if 1 <= old_eff <= 18 else (None, None)
            if o_seq and config[o_seq]:
                ob = config[o_seq][o_off]
                os, oc = _decode_speed_byte(config[o_seq][o_off + 1])
                print(f"  Current: #{old_eff} ({old_name}) bright={ob} speed={os}"
                      f" [{'colorful' if oc else 'single-color'}]")
            else:
                print(f"  Current: #{old_eff} ({old_name})")

    # Phase 2: Write config (read-modify-write)
    write_frags = []
    for seq in range(10):
        if got_config:
            f = bytearray(config[seq])
            f[1] = CMD_WRITE
            if seq == 0:
                f[8] = 0x01
                f[14] = 0x00
                f[15] = effect_num
                f[17] = 0x01 if (color_rgb or colorful) else 0x03
            if seq == tgt_seq:
                if brightness is not None:
                    f[tgt_off] = brightness
                cur_spd, cur_cf = _decode_speed_byte(f[tgt_off + 1])
                new_spd = speed if speed is not None else cur_spd
                new_cf = colorful if colorful else (not color_rgb and cur_cf)
                f[tgt_off + 1] = _encode_speed_byte(new_spd, new_cf)
            f[19] = _checksum(f)
        else:
            p = bytearray(_CFG_TEMPLATE[seq])
            if seq == 0:
                p[4] = 0x01
                p[10] = 0x00
                p[11] = effect_num
                p[13] = 0x01 if (color_rgb or colorful) else 0x03
            if seq == tgt_seq:
                pay_off = tgt_off - 4
                if brightness is not None:
                    p[pay_off] = brightness
                cur_spd = (p[pay_off + 1] >> 4) & 0xF
                cur_cf = (p[pay_off + 1] & 0xF) == 0x7
                new_spd = speed if speed is not None else cur_spd
                new_cf = colorful if colorful else (not color_rgb and cur_cf)
                p[pay_off + 1] = _encode_speed_byte(new_spd, new_cf)
            f = bytearray(_build(CMD_WRITE, SUBCMD_CONFIG, seq, p))
        write_frags.append(bytes(f))

    echoes = _tx_bulk(dev, write_frags, "cfg ", wait_read=not fast)
    print(f"  Config: {len(echoes)}/10 OK")

    # Phase 3: Color palette
    if color_rgb or not fast:
        palette = _build_palette(color_rgb=color_rgb)
        pal_frags = [_build(CMD_COLOR, SUBCMD_PALETTE, i, p) for i, p in enumerate(palette)]
        echoes = _tx_bulk(dev, pal_frags, "pal ", wait_read=not fast)
        print(f"  Palette: {len(echoes)}/37 OK")

    # Phase 4: Save
    save = _build(CMD_SAVE, SUBCMD_CONFIRM, 0, bytes([0x04, 0x07] + [0x00] * 13))
    echo = _tx_rx(dev, save, wait_read=not fast)
    print(f"  Save: {'OK' if echo else 'OK (delayed echo)'}")

    # Phase 5: Verify
    if not fast:
        verify = _read_config(dev, timeout_ms=300, max_reads=12)
        if all(v is not None for v in verify):
            v_seq, v_off = _effect_table_loc(effect_num)
            if verify[v_seq]:
                vb = verify[v_seq][v_off]
                vs, vc = _decode_speed_byte(verify[v_seq][v_off + 1])
                vm = "colorful" if vc else "single-color"
                print(f"  Verify: effect={effect_num}({eff['name']}) bright={vb} speed={vs} [{vm}]")

    dev.close()
    print(f"  -> {eff['name']} active!")
    return 0


def cmd_raw(hex_str):
    hex_str = hex_str.replace(" ", "").replace(":", "")
    if len(hex_str) != 40:
        print(f"Need 40 hex chars (20 bytes), got {len(hex_str)}")
        return 1
    frag = bytes.fromhex(hex_str)
    dev, mode, _ = _find_device()
    if not dev:
        print("Keyboard not found.")
        return 1
    print(f"TX: {frag.hex()}")
    dev.write(frag)
    time.sleep(0.05)
    for i in range(12):
        try:
            data = dev.read(20, timeout=300)
            if not data:
                break
            print(f"RX[{i}]: {bytes(data).hex()}")
        except Exception:
            break
    dev.close()
    return 0


def cmd_perkey(key_specs, page=None):
    """Set per-key colors. key_specs: list of 'key:#RRGGBB' or 'group:#RRGGBB'."""
    key_colors = {}  # led_index -> (r, g, b)

    for spec in key_specs:
        if ':' not in spec:
            print(f"Invalid spec '{spec}'. Use key:#RRGGBB (e.g. esc:#ff0000)")
            return 1
        name, color_str = spec.split(':', 1)
        name = name.lower().strip()
        try:
            color = _parse_color(color_str)
        except ValueError as e:
            print(f"Bad color in '{spec}': {e}")
            return 1

        # Resolve key name or group
        if name in KEY_GROUPS:
            for k in KEY_GROUPS[name]:
                key_colors[KEY_NAMES[k]] = color
        elif name in KEY_NAMES:
            key_colors[KEY_NAMES[name]] = color
        else:
            print(f"Unknown key '{name}'. See 'perkey --list-keys'.")
            return 1

    count = len(key_colors)
    print(f"Setting {count} key(s) to custom colors")

    dev, mode, info = _find_device(prefer_page=page)
    if not dev:
        print("Keyboard not found.")
        return 1
    print(f"  Connected: {mode} (page=0x{info['usage_page']:04X})")

    # Phase 1: Read config
    config = _read_config(dev, timeout_ms=300, max_reads=12)
    got_config = all(c is not None for c in config)

    # Phase 2: Write config with effect=21 (self-define)
    write_frags = []
    for seq in range(10):
        if got_config:
            f = bytearray(config[seq])
            f[1] = CMD_WRITE
            if seq == 0:
                f[8] = 0x01
                f[14] = 0x00
                f[15] = SELF_DEFINE_EFFECT
                f[17] = 0x01
            f[19] = _checksum(f)
        else:
            p = bytearray(_CFG_TEMPLATE[seq])
            if seq == 0:
                p[4] = 0x01
                p[10] = 0x00
                p[11] = SELF_DEFINE_EFFECT
                p[13] = 0x01
            f = bytearray(_build(CMD_WRITE, SUBCMD_CONFIG, seq, p))
        write_frags.append(bytes(f))
    echoes = _tx_bulk(dev, write_frags, "cfg ")
    print(f"  Config: {len(echoes)}/10 OK")

    # Phase 3: Per-key color map
    perkey_frags = _build_perkey_map(key_colors)
    echoes = _tx_bulk(dev, perkey_frags, "key ")
    print(f"  PerKey: {len(echoes)}/28 OK")

    # Phase 4: Save
    save = _build(CMD_SAVE, SUBCMD_CONFIRM, 0, bytes([0x04, 0x07] + [0x00] * 13))
    echo = _tx_rx(dev, save)
    print(f"  Save: {'OK' if echo else 'OK (delayed echo)'}")

    dev.close()
    print(f"  -> {count} key(s) colored!")
    return 0


def cmd_sleep(minutes):
    """Set the keyboard sleep timer (auto-off after inactivity).

    Protocol:
        - Read 10 config sequences
        - Set config[0][8] = 0x01 (write flag)
        - Set config[1][15] = minutes * 2 (sleep timer value)
        - Write all 10 sequences back
        - Send SAVE command

    Valid values: 0 (off), 5, 10, 15 minutes.
    """
    if minutes not in (0, 5, 10, 15):
        print(f"Invalid sleep time {minutes}. Use 0, 5, 10, or 15.")
        return 1

    sleep_byte = minutes * 2
    label = f"{minutes} min" if minutes else "Off"
    print(f"Setting sleep timer: {label} (0x{sleep_byte:02X})")

    dev, mode, info = _find_device()
    if not dev:
        print("Keyboard not found.")
        return 1
    print(f"  Connected: {mode} (page=0x{info['usage_page']:04X})")

    # Phase 1: Read current config
    config = _read_config(dev, timeout_ms=300, max_reads=12)
    got_config = all(c is not None for c in config)

    if not got_config:
        print("  Could not read current config. Aborting.")
        dev.close()
        return 1

    # Show current sleep value
    cur_val = config[1][15]
    cur_min = cur_val // 2
    print(f"  Current: {cur_min} min (0x{cur_val:02X})")

    # Phase 2: Modify and write config
    write_frags = []
    for seq in range(10):
        f = bytearray(config[seq])
        f[1] = CMD_WRITE
        if seq == 0:
            f[8] = 0x01  # write/confirm flag
        if seq == 1:
            f[15] = sleep_byte  # sleep timer byte
        f[19] = _checksum(f)
        write_frags.append(bytes(f))

    echoes = _tx_bulk(dev, write_frags, "cfg ")
    print(f"  Config: {len(echoes)}/10 OK")

    # Phase 3: Save
    save = _build(CMD_SAVE, SUBCMD_CONFIRM, 0, bytes([0x04, 0x07] + [0x00] * 13))
    echo = _tx_rx(dev, save)
    print(f"  Save: {'OK' if echo else 'OK (delayed echo)'}")

    dev.close()
    print(f"  -> Sleep timer set to {label}!")
    return 0


def cmd_reset():
    """Factory reset all lighting settings.

    Protocol:
        - Write 10 factory default config payloads (CFG_TEMPLATE)
        - Write 37 factory default palette payloads
        - Send SAVE command
    """
    print("Factory resetting keyboard lighting...")

    dev, mode, info = _find_device()
    if not dev:
        print("Keyboard not found.")
        return 1
    print(f"  Connected: {mode} (page=0x{info['usage_page']:04X})")

    # Phase 1: Write factory default config
    cfg_frags = []
    for seq in range(10):
        p = bytearray(_CFG_TEMPLATE[seq])
        if seq == 0:
            p[4] = 0x01  # write/confirm flag (payload offset = frame offset 8 - 4)
        cfg_frags.append(_build(CMD_WRITE, SUBCMD_CONFIG, seq, p))

    echoes = _tx_bulk(dev, cfg_frags, "cfg ")
    print(f"  Config: {len(echoes)}/10 OK")

    # Phase 2: Write factory default palette
    pal_frags = []
    for i in range(37):
        if i < len(_PAL_TEMPLATE):
            p = _PAL_TEMPLATE[i]
        elif i == 36:
            p = _PAL_LAST
        else:
            p = _PAL_ZEROS
        pal_frags.append(_build(CMD_COLOR, SUBCMD_PALETTE, i, p))

    echoes = _tx_bulk(dev, pal_frags, "pal ")
    print(f"  Palette: {len(echoes)}/37 OK")

    # Phase 3: Save
    save = _build(CMD_SAVE, SUBCMD_CONFIRM, 0, bytes([0x04, 0x07] + [0x00] * 13))
    echo = _tx_rx(dev, save)
    print(f"  Save: {'OK' if echo else 'OK (delayed echo)'}")

    dev.close()
    print("  -> Factory reset complete!")
    return 0
