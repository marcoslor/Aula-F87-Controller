'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { ANIMATIONS, type AnimationFn } from '@/lib/animations';
import { buildDirectFrame, sendDirectFrame, enableDirectMode, disableDirectMode, buildBlankFrame } from '@/lib/direct-mode';
import { isWirelessDevice, sendWirelessAnimationFrame, sendWirelessIdle } from '@/lib/wireless-mode';

interface AnimationsPanelProps {
  device: HIDDevice | null;
  log: (msg: string) => void;
}

export function AnimationsPanel({ device, log }: AnimationsPanelProps) {
  const [running, setRunning] = useState<string | null>(null);
  const [fps, setFps] = useState(20);
  const rafRef = useRef<number | null>(null);
  const runningRef = useRef(false);
  const transport = device?.opened ? (isWirelessDevice(device) ? 'wireless' : 'wired') : null;

  const stop = useCallback(async () => {
    runningRef.current = false;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    setRunning(null);
    if (device?.opened) {
      try {
        if (isWirelessDevice(device)) {
          await sendWirelessIdle(device);
        } else {
          await sendDirectFrame(device, buildBlankFrame());
          await disableDirectMode(device, log);
        }
      } catch { /* best effort */ }
    }
  }, [device, log]);

  useEffect(() => {
    return () => {
      runningRef.current = false;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, []);

  const start = useCallback(async (name: string, fn: AnimationFn) => {
    if (!device?.opened) {
      log('Not connected!');
      return;
    }

    if (runningRef.current) await stop();

    const useWireless = isWirelessDevice(device);
    log(`Starting animation: ${name} (${useWireless ? '2.4GHz wireless' : 'USB-C direct'})`);
    if (!useWireless) {
      await enableDirectMode(device, log);
    }

    runningRef.current = true;
    setRunning(name);

    const period = 1000 / fps;
    let lastFrame = 0;
    let frameIndex = 0;

    const loop = async (now: number) => {
      if (!runningRef.current) return;

      const elapsed = now - lastFrame;
      if (elapsed >= period) {
        const t = frameIndex / fps;
        const colors = fn(t);
        try {
          if (useWireless) {
            await sendWirelessAnimationFrame(device, colors);
          } else {
            const frame = buildDirectFrame(colors);
            await sendDirectFrame(device, frame);
          }
          frameIndex++;
          lastFrame = performance.now();
        } catch (err) {
          log(`Animation error: ${err instanceof Error ? err.message : String(err)}`);
          await stop();
          return;
        }
      }

      if (runningRef.current) {
        rafRef.current = requestAnimationFrame(loop);
      }
    };

    rafRef.current = requestAnimationFrame(loop);
  }, [device, fps, log, stop]);

  const entries = Object.entries(ANIMATIONS);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-zinc-500">
          {transport === 'wireless'
            ? '2.4GHz wireless: uses 20-byte 0x88 color-group output reports'
            : transport === 'wired'
              ? 'USB-C direct mode: uses 520-byte Feature Reports'
              : 'Connect USB-C or the 2.4GHz dongle to run animations'}
        </p>
        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-400">FPS:</label>
          <input
            type="number"
            min={5}
            max={30}
            value={fps}
            onChange={(e) => setFps(Math.max(5, Math.min(30, Number(e.target.value))))}
            className="w-14 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {entries.map(([key, { name, fn }]) => (
          <button
            key={key}
            onClick={() => running === key ? stop() : start(key, fn)}
            className={[
              'px-3 py-3 rounded-lg text-sm font-medium transition-all duration-200 border',
              running === key
                ? 'bg-violet-600/30 border-violet-500 text-violet-200 shadow-lg shadow-violet-500/10'
                : 'bg-zinc-800/60 border-zinc-700 text-zinc-300 hover:bg-zinc-700/60 hover:border-zinc-600',
            ].join(' ')}
          >
            {running === key ? `■ ${name}` : name}
          </button>
        ))}
      </div>

      {running && (
        <button
          onClick={stop}
          className="w-full py-2 rounded-lg text-sm font-medium bg-red-600/20 border border-red-500/40 text-red-300 hover:bg-red-600/30 transition-colors"
        >
          Stop Animation
        </button>
      )}
    </div>
  );
}
