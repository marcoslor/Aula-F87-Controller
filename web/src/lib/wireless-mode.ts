/**
 * AULA F87 — 2.4GHz wireless animation stream via WebHID.
 *
 * The wireless receiver rejects the wired 520-byte Feature Report protocol.
 * It accepts 20-byte Output Reports:
 *
 *   report id 0x13, cmd 0x88
 *
 * Data is encoded as repeated color groups:
 *
 *   R G B count index1 index2 ... indexN
 *
 * WebHID strips the report id, so `sendReport(0x13, bytes[1..19])` is used.
 */

import { REPORT_ID, checksum, WIRELESS_PID, WIRELESS_VID } from './protocol';

const CMD_AUDIO = 0x88;
const AUDIO_DATA_OFFSET = 5;
const AUDIO_DATA_PER_FRAG = 14;
const AUDIO_DL_FULL = 0x10 + AUDIO_DATA_PER_FRAG; // 0x1e
const AUDIO_DL_IDLE = 0x23;

export function isWirelessDevice(device: HIDDevice): boolean {
  return device.vendorId === WIRELESS_VID && device.productId === WIRELESS_PID;
}

export function buildWirelessIdleFrame(): Uint8Array {
  const frame = new Uint8Array(20);
  frame[0] = REPORT_ID;
  frame[1] = CMD_AUDIO;
  frame[2] = 0x01;
  frame[3] = 0x00;
  frame[4] = AUDIO_DL_IDLE;
  frame[19] = checksum(frame);
  return frame;
}

export function buildWirelessFrames(
  ledColors: Map<number, [number, number, number]>,
  quantize = 64,
  maxReports = 6,
): Uint8Array[] {
  if (ledColors.size === 0) return [buildWirelessIdleFrame()];

  let q = quantize > 0 ? Math.max(1, quantize) : 1;
  let data = new Uint8Array();
  const maxDataBytes = Math.max(1, Math.min(14, maxReports)) * AUDIO_DATA_PER_FRAG;

  while (true) {
    const groups = new Map<string, { rgb: [number, number, number]; indices: number[] }>();

    for (const [idx, [r, g, b]] of ledColors) {
      if (!r && !g && !b) continue;

      const rq = Math.min(255, Math.floor((r + Math.floor(q / 2)) / q) * q);
      const gq = Math.min(255, Math.floor((g + Math.floor(q / 2)) / q) * q);
      const bq = Math.min(255, Math.floor((b + Math.floor(q / 2)) / q) * q);
      const key = `${rq},${gq},${bq}`;

      let group = groups.get(key);
      if (!group) {
        group = { rgb: [rq, gq, bq], indices: [] };
        groups.set(key, group);
      }
      group.indices.push(idx & 0xff);
    }

    if (groups.size === 0) return [buildWirelessIdleFrame()];

    const bytes: number[] = [];
    const sortedGroups = [...groups.values()].sort((a, b) => b.indices.length - a.indices.length);
    for (const { rgb: [r, g, b], indices } of sortedGroups) {
      for (let i = 0; i < indices.length; i += 255) {
        const chunk = indices.slice(i, i + 255);
        bytes.push(r, g, b, chunk.length, ...chunk);
      }
    }

    data = Uint8Array.from(bytes);
    if (data.length <= maxDataBytes || q >= 256) break;
    q *= 2;
  }

  return packWirelessData(data, maxReports);
}

export async function sendWirelessFrame(device: HIDDevice, report: Uint8Array) {
  if (report.length !== 20 || report[0] !== REPORT_ID) {
    throw new Error('wireless report must be 20 bytes and start with 0x13');
  }
  await device.sendReport(REPORT_ID, report.slice(1));
}

export async function sendWirelessAnimationFrame(
  device: HIDDevice,
  ledColors: Map<number, [number, number, number]>,
  maxReports = 6,
) {
  const reports = buildWirelessFrames(ledColors, 64, maxReports);
  for (const report of reports) {
    await sendWirelessFrame(device, report);
  }
  return reports.length;
}

export async function sendWirelessIdle(device: HIDDevice) {
  await sendWirelessFrame(device, buildWirelessIdleFrame());
}

function packWirelessData(data: Uint8Array, maxReports = 14): Uint8Array[] {
  const chunks: Uint8Array[] = [];
  for (let i = 0; i < data.length; i += AUDIO_DATA_PER_FRAG) {
    chunks.push(data.slice(i, i + AUDIO_DATA_PER_FRAG));
  }

  const capped = chunks.slice(0, Math.max(1, Math.min(14, maxReports)));
  const total = capped.length;

  return capped.map((chunk, seq) => {
    const frame = new Uint8Array(20);
    frame[0] = REPORT_ID;
    frame[1] = CMD_AUDIO;
    frame[2] = total;
    frame[3] = seq;
    frame[4] = seq === total - 1 ? 0x10 + chunk.length : AUDIO_DL_FULL;
    frame.set(chunk, AUDIO_DATA_OFFSET);
    frame[19] = checksum(frame);
    return frame;
  });
}
