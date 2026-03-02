# AULA F87 Python CLI

Command-line tool to control AULA F87 keyboard lighting over USB HID.

## Requirements

- Python 3.9+
- [`uv`](https://docs.astral.sh/uv/) (recommended) **or** pip

> `uv run` handles dependencies automatically via PEP 723 inline metadata.
> With pip, install from `requirements.txt` instead.

---

## Setup

### macOS

1. **Install hidapi via Homebrew:**

   ```sh
   brew install hidapi
   ```

2. **Grant Input Monitoring access to your terminal app:**

   System Settings → Privacy & Security → Input Monitoring → enable your terminal (e.g. Terminal.app, iTerm2, Ghostty).

3. **Re-plug the keyboard** (or re-pair the wireless USB adapter) after granting access.

4. **Run** (no `sudo` required):

   ```sh
   uv run aula_f87.py scan
   ```

   Or with pip:

   ```sh
   pip install -r requirements.txt
   python aula_f87.py scan
   ```

---

### Ubuntu / Debian

1. **Install hidapi:**

   ```sh
   sudo apt install libhidapi-hidraw0
   ```

2. **Add a udev rule** so your user can open the device without `sudo`:

   ```sh
   echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="258a", MODE="0660", GROUP="plugdev"' \
     | sudo tee /etc/udev/rules.d/99-aula-f87.rules
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```

3. **Add yourself to the `plugdev` group**, then log out and back in:

   ```sh
   sudo usermod -aG plugdev $USER
   ```

4. **Run** (no `sudo` required after the udev rule is active):

   ```sh
   uv run aula_f87.py scan
   ```

   Or with pip:

   ```sh
   pip install -r requirements.txt
   python aula_f87.py scan
   ```

---

## Commands

| Command | Description |
|---|---|
| `scan` | Show connected AULA F87 device info |
| `list` | List all available lighting effects |
| `effect <number>` | Set a lighting effect (see below) |
| `perkey <key:#RRGGBB ...>` | Set per-key RGB colors |
| `read` | Read current keyboard configuration |
| `sleep <0\|5\|10\|15>` | Set sleep timer in minutes (0 = disable) |
| `debounce <1\|2\|3\|4\|5>` | Set debounce time in milliseconds (1-5ms) |
| `reset` | Factory reset all lighting |
| `raw <hex>` | Send a raw 20-byte HID fragment (debug) |

### Effects

| # | Name | Speed | Color |
|---|---|---|---|
| 0 | OFF | — | — |
| 1 | Fixed on | — | yes |
| 2 | Respire | yes | yes |
| 3 | Rainbow | yes | — |
| 4 | Flash away | yes | yes |
| 5 | Raindrops | yes | yes |
| 7 | Ripples shining | yes | yes |
| 8 | Stars twinkle | yes | yes |
| 10 | Retro snake | yes | yes |
| 11 | Neon stream | yes | yes |
| 12 | Reaction | yes | yes |
| 13 | Sine wave | yes | yes |
| 15 | Rotating windmill | yes | — |
| 16 | Colorful waterfall | yes | — |
| 17 | Blossoming | yes | — |

### Examples

```sh
# Turn lighting off
uv run aula_f87.py effect 0

# Fixed red
uv run aula_f87.py effect 1 --color 255 0 0

# Rainbow at max speed
uv run aula_f87.py effect 3 --speed 4

# Per-key: set Escape red, WASD green
uv run aula_f87.py perkey esc:#ff0000 wasd:#00ff00

# Set debounce to 3ms (default)
uv run aula_f87.py debounce 3

# List available key names
uv run aula_f87.py perkey --list-keys
```
