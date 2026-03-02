#!/usr/bin/env bun
/**
 * Automated screenshot and demo video capture for README/documentation
 *
 * Usage:
 *   bun run capture            # Run while dev server is already running
 *   bun run capture:start      # Auto-start dev server, capture, then stop
 *
 * Output: docs/screenshots/
 *   effects-panel.png
 *   perkey-panel.png
 *   settings-panel.png
 *   mobile-view.png
 *   demo.webm
 */

import { chromium, type BrowserContext, type Page } from 'playwright';
import { spawn, type ChildProcess } from 'child_process';
import { mkdir, readdir, unlink, access, rename } from 'fs/promises';
import { join, resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = resolve(__dirname, '../../docs/screenshots');
const BASE_URL = 'http://localhost:3000';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

// Tighter viewport — just wide enough for the full keyboard layout
const VIEWPORT = { width: 980, height: 700 };

let devServer: ChildProcess | null = null;

// ── Helpers ────────────────────────────────────────────────────────────────

async function ensureCleanDir(dir: string) {
  try { await access(dir); } catch { /* doesn't exist yet */ }
  await mkdir(dir, { recursive: true });

  // Remove old screenshots / videos
  const entries = await readdir(dir).catch(() => []);
  for (const entry of entries) {
    if (/\.(png|webm)$/.test(entry)) await unlink(join(dir, entry));
  }
}

async function startDevServer(): Promise<void> {
  console.log('🚀 Starting dev server...');
  return new Promise((resolve, reject) => {
    devServer = spawn('bun', ['run', 'dev'], {
      cwd: resolve(__dirname, '..'),
      stdio: 'pipe',
    });

    let out = '';
    devServer.stdout?.on('data', (d) => {
      out += d.toString();
      if (out.includes('Ready') || out.includes('localhost:3000')) {
        setTimeout(resolve, 1500);
      }
    });

    const timer = setTimeout(() => {
      if (!out.includes('Ready') && !out.includes('localhost:3000'))
        reject(new Error('Dev server did not start in time'));
      else resolve();
    }, 30_000);

    devServer.on('close', () => clearTimeout(timer));
  });
}

async function waitForServer(page: Page, retries = 30): Promise<void> {
  for (let i = 0; i < retries; i++) {
    try {
      await page.goto(BASE_URL, { timeout: 2000 });
      return;
    } catch {
      process.stdout.write('.');
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  throw new Error('Server did not become ready');
}

async function stopDevServer() {
  if (devServer) {
    console.log('🛑 Stopping dev server...');
    devServer.kill('SIGTERM');
    await new Promise(r => setTimeout(r, 2000));
  }
}

// ── Screenshots ─────────────────────────────────────────────────────────────

async function captureScreenshots() {
  console.log('\n📸 Capturing screenshots...');

  const browser = await chromium.launch({ headless: true, executablePath: CHROME });
  const ctx = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 2 });
  const page = await ctx.newPage();

  await waitForServer(page);

  // ── Effects panel ──────────────────────────────────────────────────────
  console.log('  📷 effects-panel');
  await page.goto(BASE_URL);
  await page.waitForLoadState('networkidle');
  await page.locator('button:has-text("3.Rainbow")').first().click();
  await page.waitForTimeout(300);
  await cropAndSave(page, join(OUT_DIR, 'effects-panel.png'));

  // ── Per-Key Colors ─────────────────────────────────────────────────────
  console.log('  📷 perkey-panel');
  await page.locator('button:has-text("Per-Key Colors")').click();
  await page.waitForTimeout(400);
  // Paint Esc red, WASD blue, arrows green to make it look interesting
  await paintKey(page, 'Esc',   '#ff3333');
  await paintKeys(page, ['W','A','S','D'], '#3399ff');
  await paintKeys(page, ['←','↑','↓','→'], '#33ff88');
  await cropAndSave(page, join(OUT_DIR, 'perkey-panel.png'));

  // ── Settings ──────────────────────────────────────────────────────────
  console.log('  📷 settings-panel');
  await page.locator('button:has-text("Settings")').click();
  await page.waitForTimeout(400);
  await cropAndSave(page, join(OUT_DIR, 'settings-panel.png'));

  // ── Mobile view ───────────────────────────────────────────────────────
  console.log('  📷 mobile-view');
  await page.setViewportSize({ width: 390, height: 844 }); // iPhone 14 Pro
  await page.goto(BASE_URL);
  await page.waitForLoadState('networkidle');
  await cropAndSave(page, join(OUT_DIR, 'mobile-view.png'));

  await ctx.close();
  await browser.close();
  console.log('✅ Screenshots done');
}

async function cropAndSave(page: Page, path: string) {
  // Measure actual content height to avoid giant black footer
  const contentH = await page.evaluate(() => {
    return Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight,
    );
  });
  const vp = page.viewportSize()!;
  const clip = { x: 0, y: 0, width: vp.width, height: Math.min(contentH, vp.height) };
  await page.screenshot({ path, clip });
}

async function paintKey(page: Page, label: string, hex: string) {
  await page.locator('input[type="color"]').first().evaluate(
    (el, h) => { (el as HTMLInputElement).value = h; el.dispatchEvent(new Event('input', { bubbles: true })); },
    hex,
  );
  const key = page.locator(`div`, { hasText: new RegExp(`^${label}$`) }).first();
  if (await key.count() > 0) {
    await key.click();
    await page.locator('button:has-text("Paint Selected")').click();
    await page.locator('button:has-text("Deselect")').click();
  }
}

async function paintKeys(page: Page, labels: string[], hex: string) {
  await page.locator('input[type="color"]').first().evaluate(
    (el, h) => { (el as HTMLInputElement).value = h; el.dispatchEvent(new Event('input', { bubbles: true })); },
    hex,
  );
  for (const [i, label] of labels.entries()) {
    const key = page.locator(`div`, { hasText: new RegExp(`^${label}$`) }).first();
    if (await key.count() > 0) {
      await key.click({ modifiers: i > 0 ? ['Shift'] : [] });
    }
  }
  await page.locator('button:has-text("Paint Selected")').click();
  await page.locator('button:has-text("Deselect")').click();
}

// ── Video ────────────────────────────────────────────────────────────────────

async function captureVideo() {
  console.log('\n🎬 Recording demo video...');

  const browser = await chromium.launch({ headless: true, executablePath: CHROME });
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 1,
    recordVideo: { dir: OUT_DIR, size: VIEWPORT },
  });
  const page = await ctx.newPage();

  // Load page and wait for full React hydration
  await page.goto(BASE_URL);
  await page.waitForLoadState('networkidle');
  // Wait until the tab bar is interactive
  await page.waitForSelector('button:has-text("Effects")', { timeout: 15_000 });
  await page.waitForTimeout(1000);

  // Browse through the tabs
  await page.locator('button:has-text("Per-Key Colors")').click();
  await page.waitForTimeout(1500);

  await page.locator('button:has-text("Settings")').click();
  await page.waitForTimeout(1500);

  await page.locator('button:has-text("Effects")').click();
  await page.waitForTimeout(1000);

  // Close page then context — ctx.close() finalises + encodes the recording
  // Note: page.video()?.path() can hang in some Playwright builds; avoid it
  await page.close();
  await ctx.close();
  await browser.close();

  // Give ffmpeg a moment to finish muxing
  await new Promise(r => setTimeout(r, 2000));

  // Find and rename the temp .webm file Playwright left in OUT_DIR
  const files = await readdir(OUT_DIR);
  const raw = files.find(f => f.endsWith('.webm') && f !== 'demo.webm');
  if (raw) {
    const dest = join(OUT_DIR, 'demo.webm');
    await rename(join(OUT_DIR, raw), dest);
    const size = Bun.file(dest).size;
    console.log(`✅ Video saved → docs/screenshots/demo.webm (${Math.round(size / 1024)}KB)`);
  } else {
    console.warn('⚠️  No .webm found in output dir');
  }
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const autoStart = args.includes('--start');

  try {
    if (autoStart) await startDevServer();

    await ensureCleanDir(OUT_DIR);
    await captureScreenshots();
    await captureVideo();

    const files = await readdir(OUT_DIR);
    console.log('\n🎉 Done! Files in docs/screenshots/:');
    files.sort().forEach(f => console.log(`  ${f}`));
  } catch (err) {
    console.error('\n❌', err);
    process.exit(1);
  } finally {
    if (autoStart) await stopDevServer();
  }
}

main();
