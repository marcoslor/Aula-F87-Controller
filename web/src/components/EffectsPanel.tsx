'use client';
import { useState } from 'react';
import { EFFECTS, hexToRgb } from '@/lib/protocol';
import type { EffectOptions } from '@/lib/webhid';

interface EffectsPanelProps {
    onApply: (effectNum: number, opts: EffectOptions) => Promise<void>;
}

export function EffectsPanel({ onApply }: EffectsPanelProps) {
    const [activeEffect, setActiveEffect] = useState<number | null>(null);
    const [color, setColor] = useState('#ff0000');
    const [colorful, setColorful] = useState(false);
    const [speed, setSpeed] = useState(4);
    const [brightness, setBrightness] = useState(4);
    const [applying, setApplying] = useState(false);

    const hasColor = activeEffect ? EFFECTS[activeEffect].color : true;
    const hasSpeed = activeEffect ? EFFECTS[activeEffect].speed : true;

    const handleApply = async () => {
        if (!activeEffect) return;
        setApplying(true);
        try {
            const isColorful = hasColor ? colorful : true;
            await onApply(activeEffect, {
                colorRgb: isColorful ? null : hexToRgb(color),
                colorful: isColorful,
                speed: hasSpeed ? speed : null,
                brightness,
            });
        } finally {
            setApplying(false);
        }
    };

    return (
        <div className="space-y-4">
            {/* Effects grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
                {Object.entries(EFFECTS).map(([num, eff]) => (
                    <button
                        key={num}
                        onClick={() => setActiveEffect(parseInt(num))}
                        className={`text-left px-3 py-2.5 rounded-lg text-sm transition-all duration-150
              ${activeEffect === parseInt(num)
                                ? 'bg-violet-600/20 border border-violet-500/60 text-violet-300 shadow-md shadow-violet-600/10'
                                : 'bg-zinc-800/60 border border-zinc-700/50 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'
                            }`}
                    >
                        <span className="text-zinc-600 mr-1.5">{num}.</span>
                        {eff.name}
                    </button>
                ))}
            </div>

            {/* Controls */}
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm
                      grid grid-cols-1 sm:grid-cols-2 gap-5">
                {/* Color */}
                <div className={`space-y-2 ${!hasColor ? 'opacity-50 grayscale' : ''}`}>
                    <label className="text-[0.7rem] uppercase tracking-wider text-zinc-500 font-medium">Color</label>
                    <div className="flex gap-2 items-center">
                        <input
                            type="color"
                            value={color}
                            onChange={e => setColor(e.target.value)}
                            disabled={!hasColor || colorful}
                            className="w-full h-9 rounded-lg border border-zinc-700 bg-zinc-800 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        />
                        <button
                            onClick={() => setColorful(!colorful)}
                            disabled={!hasColor}
                            className={`text-xs px-3 py-2 rounded-md whitespace-nowrap transition-all duration-200 disabled:cursor-not-allowed
                ${(!hasColor || colorful)
                                    ? 'bg-amber-500/15 border border-amber-500/50 text-amber-400'
                                    : 'bg-zinc-800 border border-zinc-700 text-zinc-500 hover:text-zinc-300'
                                }`}
                        >
                            {hasColor ? 'Colorful' : 'Colorful Only'}
                        </button>
                    </div>
                    <p className="text-xs text-zinc-600">
                        {!hasColor ? 'This effect only supports colorful mode.' : (colorful ? 'Mode: Colorful (rainbow)' : `Custom: ${color}`)}
                    </p>
                </div>

                {/* Speed */}
                <div className={`space-y-2 ${!hasSpeed ? 'opacity-50 grayscale pointer-events-none' : ''}`}>
                    <label className="text-[0.7rem] uppercase tracking-wider text-zinc-500 font-medium">
                        Speed <span className="text-zinc-400">{hasSpeed ? speed : 'N/A'}</span>
                    </label>
                    <input
                        type="range" min={0} max={4} step={1} value={hasSpeed ? speed : 2}
                        onChange={e => setSpeed(parseInt(e.target.value))}
                        disabled={!hasSpeed}
                        className="w-full accent-violet-500"
                    />
                </div>

                {/* Brightness */}
                <div className="space-y-2">
                    <label className="text-[0.7rem] uppercase tracking-wider text-zinc-500 font-medium">
                        Brightness <span className="text-zinc-400">{brightness}</span>
                    </label>
                    <input
                        type="range" min={0} max={4} step={1} value={brightness}
                        onChange={e => setBrightness(parseInt(e.target.value))}
                        className="w-full accent-violet-500"
                    />
                </div>

                {/* Apply */}
                <div className="flex items-end">
                    <button
                        onClick={handleApply}
                        disabled={!activeEffect || applying}
                        className="w-full py-2.5 rounded-lg font-semibold text-sm transition-all duration-200
              bg-violet-600 text-white hover:bg-violet-500 shadow-lg shadow-violet-600/20
              disabled:opacity-40 disabled:cursor-default disabled:shadow-none"
                    >
                        {applying ? 'Applying...' : 'Apply Effect'}
                    </button>
                </div>
            </div>
        </div>
    );
}
