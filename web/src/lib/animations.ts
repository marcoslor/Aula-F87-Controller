/**
 * AULA F87 — Animation generators for the webapp.
 *
 * Each generator takes elapsed time (seconds) and returns a Map of
 * led_index → [r, g, b]. These match the Python CLI animations.
 */

import { KB_ROWS } from './protocol';

// Physical position lookup: ledIndex → { row: 0..1, col: 0..1 }
type LedPos = { row: number; col: number };
const LED_POS = new Map<number, LedPos>();
const ALL_LEDS: number[] = [];

const ROWS: number[][] = [];
for (let ri = 0; ri < KB_ROWS.length; ri++) {
  const row: number[] = [];
  for (const entry of KB_ROWS[ri]) {
    if (Array.isArray(entry)) {
      const [, idx] = entry as [string, number, number];
      row.push(idx);
      ALL_LEDS.push(idx);
    }
  }
  ROWS.push(row);
}

const N_ROWS = ROWS.length;
for (let ri = 0; ri < N_ROWS; ri++) {
  const row = ROWS[ri];
  for (let ci = 0; ci < row.length; ci++) {
    LED_POS.set(row[ci], {
      row: ri / Math.max(N_ROWS - 1, 1),
      col: ci / Math.max(row.length - 1, 1),
    });
  }
}

function hsv(h: number, s = 1.0, v = 1.0): [number, number, number] {
  h = ((h % 1.0) + 1.0) % 1.0;
  const i = Math.floor(h * 6);
  const f = h * 6 - i;
  const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  let r = 0, g = 0, b = 0;
  switch (i % 6) {
    case 0: r = v; g = t; b = p; break;
    case 1: r = q; g = v; b = p; break;
    case 2: r = p; g = v; b = t; break;
    case 3: r = p; g = q; b = v; break;
    case 4: r = t; g = p; b = v; break;
    case 5: r = v; g = p; b = q; break;
  }
  return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

export type AnimationFn = (t: number) => Map<number, [number, number, number]>;

export const sineWave: AnimationFn = (t) => {
  const colors = new Map<number, [number, number, number]>();
  for (const [led, pos] of LED_POS) {
    const hue = pos.col + t * 0.3;
    const val = 0.5 + 0.5 * Math.sin(pos.col * Math.PI * 4 - t * 4.0);
    colors.set(led, hsv(hue, 1.0, val));
  }
  return colors;
};

export const rain: AnimationFn = (t) => {
  const colors = new Map<number, [number, number, number]>();
  const dropSpeed = 3.0;
  const nDrops = 6;
  for (const [led, pos] of LED_POS) {
    let bestV = 0;
    for (let d = 0; d < nDrops; d++) {
      const dropCol = ((d * 0.618 + t * 0.1) % 1.0 + 1.0) % 1.0;
      const colDist = Math.abs(pos.col - dropCol);
      if (colDist > 0.06) continue;
      const dropY = ((t * dropSpeed + d * 1.7) % 2.0) - 0.5;
      const rowDist = Math.abs(pos.row - dropY);
      if (rowDist < 0.3) {
        const v = Math.max(0, 1 - rowDist / 0.3) * (1 - colDist / 0.06);
        bestV = Math.max(bestV, v);
      }
    }
    if (bestV > 0.05) colors.set(led, hsv(0.55, 0.8, bestV));
  }
  return colors;
};

export const fire: AnimationFn = (t) => {
  const colors = new Map<number, [number, number, number]>();
  for (const [led, pos] of LED_POS) {
    const heat = Math.max(0, 1.0 - pos.row * 0.7);
    const flicker = 0.5 + 0.5 * Math.sin(pos.col * 13.7 + t * 7.0);
    const flicker2 = 0.5 + 0.5 * Math.sin(pos.col * 7.3 - t * 5.0 + pos.row * 3.0);
    const v = heat * (0.4 + 0.6 * flicker * flicker2);
    if (v < 0.05) continue;
    const hue = 0.0 + 0.08 * (1.0 - pos.row);
    colors.set(led, hsv(hue, 1.0 - pos.row * 0.3, Math.min(1.0, v)));
  }
  return colors;
};

export const breathing: AnimationFn = (t) => {
  const v = 0.5 + 0.5 * Math.sin(t * 2.0);
  const hue = t * 0.05;
  const color = hsv(hue, 1.0, v);
  const colors = new Map<number, [number, number, number]>();
  for (const led of ALL_LEDS) colors.set(led, color);
  return colors;
};

export const snake: AnimationFn = (t) => {
  const path: number[] = [];
  for (let ri = 0; ri < ROWS.length; ri++) {
    const row = ri % 2 === 0 ? [...ROWS[ri]].reverse() : ROWS[ri];
    path.push(...row);
  }
  const n = path.length;
  const head = Math.floor(t * 16.0) % n;
  const tailLen = 10;
  const hue = (t * 0.08) % 1.0;
  const colors = new Map<number, [number, number, number]>();
  for (let offset = 0; offset < tailLen; offset++) {
    const led = path[((head - offset) % n + n) % n];
    const scale = (tailLen - offset) / tailLen;
    colors.set(led, hsv(hue, 1.0, scale));
  }
  return colors;
};

export const rainbow: AnimationFn = (t) => {
  const colors = new Map<number, [number, number, number]>();
  for (const [led, pos] of LED_POS) {
    colors.set(led, hsv(pos.col + t * 0.3));
  }
  return colors;
};

export const waveVertical: AnimationFn = (t) => {
  const colors = new Map<number, [number, number, number]>();
  for (const [led, pos] of LED_POS) {
    const v = 0.5 + 0.5 * Math.sin(pos.row * Math.PI * 3 - t * 3.0);
    colors.set(led, hsv(0.6 + pos.row * 0.15, 0.8, v));
  }
  return colors;
};

export const sparkle: AnimationFn = (t) => {
  const colors = new Map<number, [number, number, number]>();
  const frame = Math.floor(t * 20);
  for (const led of ALL_LEDS) {
    const seed = (led * 7919 + frame * 104729) % 100;
    if (seed < 8) {
      const hue = (led * 0.0618 + t * 0.1) % 1.0;
      colors.set(led, hsv(hue, 0.7, 1.0));
    }
  }
  return colors;
};

export const ANIMATIONS: Record<string, { name: string; fn: AnimationFn }> = {
  sine: { name: 'Sine Wave', fn: sineWave },
  rain: { name: 'Rain', fn: rain },
  fire: { name: 'Fire', fn: fire },
  breathing: { name: 'Breathing', fn: breathing },
  snake: { name: 'Snake', fn: snake },
  rainbow: { name: 'Rainbow', fn: rainbow },
  wave: { name: 'Vertical Wave', fn: waveVertical },
  sparkle: { name: 'Sparkle', fn: sparkle },
};
