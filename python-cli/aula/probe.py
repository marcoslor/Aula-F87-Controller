"""
AULA F87 — HID descriptor probe and protocol-path verification.

Used to confirm which reverse-engineered protocol family actually works on
the connected keyboard. Answers two questions:

  1. Does the device expose a 520-byte feature-report interface
     (OpenRGB / aula-rgb-controller style, report ID 0x06)?
  2. Does the device accept the OEM 20-byte output-report protocol
     (this repository's RE, report ID 0x13)?

Both can be true. A caller can use the output to decide which code path
to take for direct-mode animation.
"""

import time

from aula.protocol import (REPORT_ID, CMD_READ, SUBCMD_CONFIRM,
                           WIRED_VID, WIRED_PID, WIRELESS_VID, WIRELESS_PID,
                           _build)


# ── OpenRGB / aula-rgb-controller constants ──────────────────────────────
# Report ID used by the SinoWealth "520-byte feature report" protocol.
OPENRGB_REPORT_ID = 0x06
OPENRGB_REPORT_SIZE = 520
OPENRGB_CMD_QUERY_MODEL = 0x82


def _describe_collection(d):
    """Render a single HID collection dict as a one-line string."""
    iface = d.get("interface_number", -1)
    up = d.get("usage_page", 0)
    usage = d.get("usage", 0)
    in_size = d.get("input_report_byte_length", 0)
    out_size = d.get("output_report_byte_length", 0)
    feat_size = d.get("feature_report_byte_length", 0)
    vendor = " vendor" if 0xFF00 <= up <= 0xFFFF else ""
    return (
        f"iface={iface:2}  page=0x{up:04X}  usage=0x{usage:04X}{vendor}"
        f"  in={in_size:<4} out={out_size:<4} feat={feat_size}"
    )


def _try_openrgb_query(info):
    """Attempt the 520-byte feature-report model query on this collection.

    Returns (ok, response_or_error_str).
    """
    import hid

    # Build OpenRGB query packet
    buf = bytearray(OPENRGB_REPORT_SIZE)
    buf[0] = OPENRGB_REPORT_ID
    buf[1] = OPENRGB_CMD_QUERY_MODEL
    buf[2] = 0x01
    buf[4] = 0x01
    buf[6] = 0x06

    # Open the collection
    try:
        if hasattr(hid, "device"):
            dev = hid.device()
            dev.open_path(info["path"])
        else:
            dev = hid.Device(path=info["path"])
    except Exception as e:
        return (False, f"open failed: {e}")

    try:
        # send_feature_report API differs slightly between `hid` variants
        if not hasattr(dev, "send_feature_report"):
            return (False, "driver has no send_feature_report")
        try:
            n = dev.send_feature_report(bytes(buf))
        except Exception as e:
            return (False, f"send_feature_report raised: {e}")

        if n is None or n < 0:
            return (False, f"send_feature_report returned {n}")

        time.sleep(0.05)

        # Try to read feature report back. Same API variance.
        resp = None
        try:
            if hasattr(dev, "get_feature_report"):
                resp = bytes(dev.get_feature_report(OPENRGB_REPORT_ID, OPENRGB_REPORT_SIZE))
        except Exception as e:
            return (False, f"get_feature_report raised: {e}")

        if resp is None or len(resp) == 0:
            return (False, "empty response")

        return (True, resp)
    finally:
        try:
            dev.close()
        except Exception:
            pass


def _try_oem_handshake(info):
    """Attempt the OEM 20-byte READ/CONFIRM handshake on this collection.

    Returns (ok, first_response_or_error_str).
    """
    import hid

    try:
        if hasattr(hid, "device"):
            dev = hid.device()
            dev.open_path(info["path"])
        else:
            dev = hid.Device(path=info["path"])
    except Exception as e:
        return (False, f"open failed: {e}")

    try:
        frame = _build(CMD_READ, SUBCMD_CONFIRM, 0, bytes(15))
        dev.write(frame)
        time.sleep(0.05)
        data = dev.read(20, timeout=300)
        if not data:
            return (False, "no response within 300ms")
        return (True, bytes(data))
    except Exception as e:
        return (False, f"exception: {e}")
    finally:
        try:
            dev.close()
        except Exception:
            pass


def cmd_probe(verbose=False):
    """Enumerate all HID collections and probe both protocol paths.

    Exits 0 on success.
    """
    import hid

    print("AULA F87 — HID Protocol Probe")
    print("=" * 70)

    found_any = False
    for vid, pid, label in [(WIRED_VID, WIRED_PID, "wired"),
                             (WIRELESS_VID, WIRELESS_PID, "wireless")]:
        devs = hid.enumerate(vid, pid)
        if not devs:
            print(f"\n  {label} (0x{vid:04X}:0x{pid:04X}): not connected")
            continue

        found_any = True
        print(f"\n  {label} (0x{vid:04X}:0x{pid:04X}) — {len(devs)} collection(s):")
        for d in devs:
            print(f"    {_describe_collection(d)}")

        # Only probe vendor-specific collections (usage page 0xFF00-0xFFFF).
        vendor_collections = [d for d in devs
                              if 0xFF00 <= d.get("usage_page", 0) <= 0xFFFF]
        if not vendor_collections:
            print("    (no vendor-specific collections — skipping protocol probe)")
            continue

        print(f"\n  Protocol probe — {label}:")
        print("  " + "-" * 68)

        # === Test 1: OEM 20-byte output report (report ID 0x13) ===
        oem_hits = []
        for d in vendor_collections:
            ok, resp = _try_oem_handshake(d)
            tag = "OK" if ok else "FAIL"
            detail = ""
            if ok and isinstance(resp, (bytes, bytearray)):
                detail = f"  <- {resp[:8].hex()}..."
            elif not ok:
                detail = f"  <- {resp}"
            up = d["usage_page"]
            print(f"    [OEM 20b / 0x13] page=0x{up:04X}  {tag}{detail}")
            if ok:
                oem_hits.append(d)

        # === Test 2: OpenRGB 520-byte feature report (report ID 0x06) ===
        openrgb_hits = []
        for d in vendor_collections:
            feat = d.get("feature_report_byte_length", 0)
            # Only bother if the collection claims to support large feature reports
            too_small = (feat and feat < OPENRGB_REPORT_SIZE)
            if too_small:
                up = d["usage_page"]
                print(f"    [OpenRGB 520b / 0x06] page=0x{up:04X}  SKIP"
                      f"  (feature report size = {feat} < {OPENRGB_REPORT_SIZE})")
                continue
            ok, resp = _try_openrgb_query(d)
            tag = "OK" if ok else "FAIL"
            detail = ""
            if ok and isinstance(resp, (bytes, bytearray)):
                detail = f"  <- {resp[:14].hex()}..."
            elif not ok:
                detail = f"  <- {resp}"
            up = d["usage_page"]
            print(f"    [OpenRGB 520b / 0x06] page=0x{up:04X}  {tag}{detail}")
            if ok:
                openrgb_hits.append(d)

        # === Verdict ===
        print("\n  Verdict:")
        if oem_hits and openrgb_hits:
            print("    * Both protocols answered. The device exposes BOTH the OEM")
            print("      20-byte (0x13) path AND the OpenRGB/SinoWealth 520-byte")
            print("      (0x06 feature report) path. The aula-rgb-controller direct")
            print("      mode (cmd 0x08) may be portable.")
        elif oem_hits:
            print("    * Only the OEM 20-byte protocol responded. The")
            print("      aula-rgb-controller 520-byte feature-report family is not")
            print("      applicable on this firmware. Stick with the 0x13 path.")
        elif openrgb_hits:
            print("    * Only the OpenRGB 520-byte feature-report protocol responded.")
            print("      The OEM 20-byte handshake is silent — either the firmware")
            print("      differs or the wrong collection was chosen.")
        else:
            print("    * Neither protocol responded. Check permissions (macOS Input")
            print("      Monitoring, Linux udev rule) and re-plug the keyboard.")

    if not found_any:
        print("\n  No AULA keyboard found.")
        return 1
    return 0
