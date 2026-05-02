# USB captures

Wireshark `.pcapng` files used to reverse-engineer AULA F87 HID traffic. **Provenance matters:** USBPcap-style captures (VM or Windows) expose full control-transfer payloads; plain macOS host captures are often less useful for decoding.

## Capture setups

### `windows-npcap-wireshark/`

Captured on **native Windows** with **[Npcap](https://npcap.com/)** (or WinPcap successor) and **Wireshark**, with USBPcap or equivalent so control transfers show the full HID payload.


| File                               | Notes                                                                         |
| ---------------------------------- | ----------------------------------------------------------------------------- |
| `pearl-faliling-jade-plate.pcapng` | OEM effect (wired USB-C path in capture context)                              |
| `raining-silk.pcapng`              | OEM effect                                                                    |
| `raining-silk-2-4.pcapng`          | Same class of effect on **2.4 GHz** receiver (20-byte `0x13` / `0x88` stream) |


### `macos-host-wireshark-vm/`

Captured with **Wireshark on the macOS host** while the OEM app ran inside a **Windows VM** (e.g. UTM) with USB passed through. Payload layout matches USBPcap-style traces; timing and filtering may differ from native Windows.


| Path              | Contents                                                         |
| ----------------- | ---------------------------------------------------------------- |
| `effect/`         | Audio-dance and related effect sessions (numbered `1-…` … `5-…`) |
| `effects/`        | Built-in lighting effect samples (`01-fixed` … `09-neon_stream`) |
| `config-changes/` | Sleep, brightness, speed, reset, and other setting experiments   |
| `self-define/`    | Per-key RGB (effect #21) experiments                             |


### `oem-app-dump/`

OEM Windows app assets (not pcapng): `KB.ini`, effect tables, strings — reference for LED indices and effect names.

## Tools

```bash
pip install -r captures/tools/requirements.txt
python captures/tools/parse_captures.py captures/macos-host-wireshark-vm/effect/1-audio-dance-soft-gain1-smoothness-4-colorful.pcapng
```

## Opening in Wireshark

Use display filters such as `usb` / URB metadata as appropriate for your capture type. For 20-byte AULA frames, look for payloads starting with report id `0x13`.