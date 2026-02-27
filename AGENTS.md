# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

AULA F87 is an open-source WebHID keyboard controller for the AULA F87 mechanical keyboard. The repo has three components:

| Component | Path | Purpose |
|-----------|------|---------|
| **Web app** | `web/` | Next.js 16 (React 19, Tailwind 4) browser-based controller using WebHID API |
| **Python CLI** | `python-cli/` | CLI tool using `hid` (libhidapi) for direct USB HID control |
| **Captures** | `captures/` | Wireshark pcapng files and parser tool (development reference only) |

### Web app (primary service)

- **Package manager**: Bun (lockfile is `web/bun.lock`). Run `bun install` in `web/`.
- **Dev server**: `bun run dev` in `web/` → http://localhost:3000
- **Lint**: `bun run lint` in `web/` (runs ESLint 9 flat config). Expect 4 non-blocking warnings (unused vars, custom font).
- **Build**: `bun run build` in `web/` (production build via Turbopack).
- **No backend or database** — the web app is entirely client-side. All keyboard communication happens via the browser's WebHID API.
- **WebHID requires Chrome/Edge** — Firefox and Safari do not support it. A physical AULA F87 keyboard is needed for end-to-end HID communication testing, but all UI functionality works without hardware.

### Python CLI

- Install deps: `pip install -r python-cli/requirements.txt` (just the `hid` package).
- Run: `python python-cli/aula_f87.py --help` to verify. Actual keyboard commands require a connected AULA F87 via USB.
- On macOS, `brew install hidapi` is also needed.

### Gotchas

- The `vercel.json` at repo root references `npm install` and `npm run build`, but local development uses Bun (matching `bun.lock`). Both work.
- Next.js 16 uses `reactCompiler: true` in `next.config.ts` — this requires `babel-plugin-react-compiler` (already in devDependencies).
- No automated test suite exists in the repo (no `test` script in `package.json`).
