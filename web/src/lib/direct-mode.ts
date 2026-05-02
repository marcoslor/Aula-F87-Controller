/**
 * AULA F87 — Wired (USB-C) Direct Mode via WebHID.
 *
 * Uses 520-byte Feature Reports (Report ID 0x06, cmd 0x08) to set
 * per-LED RGB at ~20 fps. WebHID's sendFeatureReport handles the
 * SET_REPORT control transfer automatically.
 *
 * Protocol:
 *   d[0]     = 0x06 (report ID, stripped by WebHID — we send bytes 1..519)
 *   d[1]     = 0x08 (CMD_SET_LEDS)
 *   d[4]     = 0x01 (zone)
 *   d[6]     = 0x7A (num_leds = 122)
 *   d[7]     = 0x01
 *   d[8..373]= 122 × (R, G, B) interleaved
 */

import type { LogFn } from './webhid';

export const DIRECT_REPORT_ID = 0x06;
export const CMD_SET_LEDS = 0x08;
export const DIRECT_NUM_LEDS = 122;
const LED_DATA_OFFSET = 8;
const REPORT_SIZE = 520;

// Enable/disable reports
const ENABLE_SEQUENCE = [
  { reportId: 0x39, data: [0x20, 0x06, 0x00, 0x01, 0x00] },
  { reportId: 0x3c, data: [0x20, 0x01, 0x00] },
  { reportId: 0x39, data: [0x20, 0x06, 0x01, 0x01, 0x00] },
];

const DISABLE_REPORT = { reportId: 0x3c, data: [0x20, 0x00, 0x00] };

export function buildDirectFrame(ledColors: Map<number, [number, number, number]>): Uint8Array {
  const buf = new Uint8Array(REPORT_SIZE - 1); // WebHID strips report ID
  buf[0] = CMD_SET_LEDS;
  buf[3] = 0x01; // zone
  buf[5] = DIRECT_NUM_LEDS; // 0x7A
  buf[6] = 0x01;

  for (const [idx, [r, g, b]] of ledColors) {
    const off = LED_DATA_OFFSET - 1 + idx * 3; // -1 because no report ID prefix
    if (off + 2 < buf.length) {
      buf[off] = r;
      buf[off + 1] = g;
      buf[off + 2] = b;
    }
  }
  return buf;
}

export function buildBlankFrame(): Uint8Array {
  return buildDirectFrame(new Map());
}

async function sendSmallFeatureReport(device: HIDDevice, reportId: number, data: number[]) {
  const ab = new ArrayBuffer(REPORT_SIZE - 1);
  const buf = new Uint8Array(ab);
  for (let i = 0; i < data.length; i++) buf[i] = data[i];
  await device.sendFeatureReport(reportId, ab);
}

export async function enableDirectMode(device: HIDDevice, log: LogFn) {
  log('Enabling direct mode...');
  for (const { reportId, data } of ENABLE_SEQUENCE) {
    try {
      await sendSmallFeatureReport(device, reportId, data);
    } catch {
      // Non-fatal — some firmware versions don't need this
    }
    await new Promise(r => setTimeout(r, 5));
  }
}

export async function disableDirectMode(device: HIDDevice, log: LogFn) {
  try {
    await sendSmallFeatureReport(device, DISABLE_REPORT.reportId, DISABLE_REPORT.data);
    log('Direct mode disabled.');
  } catch {
    // Best-effort
  }
}

export async function sendDirectFrame(device: HIDDevice, frame: Uint8Array) {
  const ab = new ArrayBuffer(frame.byteLength);
  new Uint8Array(ab).set(frame);
  await device.sendFeatureReport(DIRECT_REPORT_ID, ab);
}

export function isDirectModeCapable(device: HIDDevice): boolean {
  return device.collections.some(c => {
    if (!c.featureReports) return false;
    return c.featureReports.some(r => r.reportId === DIRECT_REPORT_ID);
  });
}
