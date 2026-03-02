# AULA F87 Controller

Open-source lighting controller for the AULA F87 keyboard. Supports both a browser-based web app (WebHID) and a Python CLI (USB HID).

Protocol reverse-engineered from USB captures of the OEM Windows app.

---

## Web App

A Next.js app that communicates with the keyboard directly from the browser via the [WebHID API](https://developer.mozilla.org/en-US/docs/Web/API/WebHID_API).

**Live:** https://aula-f87-controller.vercel.app

No drivers or software installation required — works in Chromium-based browsers that support WebHID.

### Running locally

```sh
cd web
bun install
bun dev
```

Open http://localhost:3000.

---

## Python CLI

A command-line tool for scripting and automation. Works on macOS and Linux without `sudo`.

See [`python-cli/README.md`](python-cli/README.md) for setup instructions and usage.

Quick start:

```sh
cd python-cli
uv run aula_f87.py list
uv run aula_f87.py effect 3        # Rainbow
uv run aula_f87.py effect 0        # Off
```

---

## Protocol

HID protocol notes are in [`docs/PROTOCOL.md`](docs/PROTOCOL.md).
