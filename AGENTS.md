# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

AULA F87 is an open-source WebHID keyboard controller for the AULA F87 mechanical keyboard. The repo has three components:


| Component      | Path          | Purpose                                                                                                                                                                           |
| -------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Web app**    | `web/`        | Next.js 16 (React 19, Tailwind 4) browser-based controller using WebHID API                                                                                                       |
| **Python CLI** | `python-cli/` | CLI tool using `hid` (libhidapi) for direct USB HID control                                                                                                                       |
| **Captures**   | `captures/`   | pcapng by provenance: `windows-npcap-wireshark/` (native Windows + Npcap + Wireshark), `macos-host-wireshark-vm/` (Wireshark on macOS host, Windows VM); see `captures/README.md` |


### Web app (primary service)

- **Package manager**: Bun (lockfile is `web/bun.lock`). Run `bun install` in `web/`.
- **Dev server**: `bun run dev` in `web/` → [http://localhost:3000](http://localhost:3000)
- **Lint**: `bun run lint` in `web/` (runs ESLint 9 flat config). Expect 4 non-blocking warnings (unused vars, custom font).
- **Build**: `bun run build` in `web/` (production build via Turbopack).
- **No backend or database** — the web app is entirely client-side. All keyboard communication happens via the browser's WebHID API.
- **WebHID requires Chrome/Edge** — Firefox and Safari do not support it. A physical AULA F87 keyboard is needed for end-to-end HID communication testing, but all UI functionality works without hardware.

### Python CLI

- Install deps: `pip install -r python-cli/requirements.txt` (just the `hid` package).
- Run: `python python-cli/aula_f87.py --help` to verify. Actual keyboard commands require a connected AULA F87 via USB.
- On macOS, `brew install hidapi` is also needed.

### Gotchas

- The `vercel.json` in `web/` uses Bun. Always use `bun` commands, not `npm`.
- Next.js 16 uses `reactCompiler: true` in `next.config.ts` — this requires `babel-plugin-react-compiler` (already in devDependencies).
- No automated test suite exists in the repo (no `test` script in `package.json`).

### Conventional Commits

All commits must follow [Conventional Commits](https://www.conventionalcommits.org/) format:


| Prefix      | Use for                                           |
| ----------- | ------------------------------------------------- |
| `feat:`     | New features                                      |
| `fix:`      | Bug fixes                                         |
| `docs:`     | Documentation changes                             |
| `chore:`    | Maintenance, tooling, dependencies                |
| `refactor:` | Code refactoring without behavior change          |
| `test:`     | Adding or updating tests                          |
| `style:`    | Code style changes (formatting, semicolons, etc.) |


Examples:

- `feat: add debounce setting to CLI and webapp`
- `fix: debounce write reliability`
- `docs: update README with debounce examples`

## Learned User Preferences

- CLI-driven animations must keep normal keyboard typing functional while the animation is playing; if streaming blocks key input, redesign the approach instead of accepting it.
- Keep documentation scoped by product surface: preserve the CLI README for CLI details and use a project README for repo-wide web app plus CLI documentation.
- Keep docs and screenshot tooling out of the web app runtime/build dependency graph so Vercel/Next builds are not affected by README asset generation.
- Web app state should reset cleanly when the current HID device disconnects, including stopping animation loops and clearing connected UI state.

## Learned Workspace Facts

- AULA F87 debounce is stored in `config[0]` at frame offset 8 (payload offset 4); values `0x00`-`0x04` map to 1ms-5ms.
- AULA F87 sleep timer is stored in `config[1][15]` using `minutes * 2` encoding; exposing 0-60 minutes is protocol-compatible, but values above the original presets still need hardware validation.
- The wired AULA F87 identifies as `0x258A:0x010C`; the 2.4 GHz wireless receiver identifies as `0x3554:0xFA09` and exposes vendor HID pages `0xFF02` and `0xFF04`.
- Wired OEM animation protocol uses 520-byte Feature Reports (Report ID `0x06`, cmd `0x08`) with 122 LEDs in interleaved RGB at ~20 fps, sent as SET_REPORT control transfers to interface 1.
- Wireless (2.4 GHz) OEM animation protocol uses 20-byte Report `0x13` (cmd `0x88`) sent as SET_REPORT Output Report control transfers; in WebHID use `sendReport(0x13, 19-byte body)`, not wired Feature Reports.
- Wireless `0x88` data encoding groups LEDs by color: `(R, G, B, count, index1..indexN)` — replay of captured frames works, but synthesized encoding still needs validation.
- Raw `libusb_control_transfer` via ctypes (bypassing pyusb's auto interface claiming) sends frames without detaching the macOS kernel HID driver, keeping keyboard input functional during CLI animations and avoiding the need for sudo on wired.
- OEM self-define mode is per-key color control, and effect id `0`/OFF should still be applicable as a real keyboard effect.
