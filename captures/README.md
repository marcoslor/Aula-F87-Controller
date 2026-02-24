# USB Captures

Wireshark (USBPcap) captures of the OEM Windows app communicating with the AULA F87 keyboard. Used to reverse-engineer the HID protocol documented in `docs/PROTOCOL.md`.

## Directory Layout

```
captures/
├── effects/            14 captures — one per built-in effect (01–14)
├── config-changes/     25 captures — brightness, speed, color, sleep, reset experiments
├── self-define/         6 captures — per-key RGB mode (effect #21)
├── oem-app/            OEM Windows driver (OemDrv.exe, KB.ini configs, skins)
│   └── Dev/kb/         KB.ini files for wired, wireless, and F87PRO variants
└── tools/              parse_captures.py — pcapng → decoded HID transactions
```

## Opening Captures

Open `.pcapng` files in [Wireshark](https://www.wireshark.org/). Filter with `usb.transfer_type == 0x00` for control transfers or look for 20-byte payloads starting with `0x13`.

## Parse Tool

```bash
pip install pyshark   # see tools/requirements.txt
python captures/tools/parse_captures.py captures/effects/01-fixed.pcapng
```
