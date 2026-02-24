'use client';
import { useState, useMemo, useCallback } from 'react';
import { KB_ROWS, hexToRgb, rgbToHex, type KeyEntry } from '@/lib/protocol';

interface PerKeyPanelProps {
    onApply: (keyColors: Record<number, [number, number, number]>) => Promise<void>;
}

const UNIT = 37; // px per unit width

export function PerKeyPanel({ onApply }: PerKeyPanelProps) {
    const [keyColors, setKeyColors] = useState<Record<number, [number, number, number]>>({});
    const [selectedKeys, setSelectedKeys] = useState<Set<number>>(new Set());
    const [paintColor, setPaintColor] = useState('#ff0000');
    const [applying, setApplying] = useState(false);

    const toggleKey = useCallback((ledIdx: number, shift: boolean) => {
        setSelectedKeys(prev => {
            const next = shift ? new Set(prev) : new Set<number>();
            if (next.has(ledIdx)) next.delete(ledIdx);
            else next.add(ledIdx);
            return next;
        });
    }, []);

    const selectAll = useCallback(() => {
        const all = new Set<number>();
        for (const row of KB_ROWS)
            for (const entry of row)
                if (typeof entry !== 'number') all.add(entry[1]);
        setSelectedKeys(all);
    }, []);

    const clearSelection = useCallback(() => setSelectedKeys(new Set()), []);

    const paintSelected = useCallback(() => {
        const rgb = hexToRgb(paintColor);
        setKeyColors(prev => {
            const next = { ...prev };
            for (const idx of selectedKeys) next[idx] = rgb;
            return next;
        });
    }, [paintColor, selectedKeys]);

    const clearAllColors = useCallback(() => {
        setKeyColors({});
        setSelectedKeys(new Set());
    }, []);

    const handleApply = async () => {
        setApplying(true);
        try { await onApply(keyColors); }
        finally { setApplying(false); }
    };

    return (
        <div className="space-y-4">
            {/* Toolbar */}
            <div className="flex flex-wrap gap-2 items-center">
                <label className="text-xs text-zinc-500">Paint color:</label>
                <input
                    type="color"
                    value={paintColor}
                    onChange={e => setPaintColor(e.target.value)}
                    className="w-10 h-8 rounded border border-zinc-700 bg-zinc-800 cursor-pointer"
                />
                <button onClick={selectAll} className="px-3 py-1.5 text-xs rounded-md bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-200 transition-all">
                    Select All
                </button>
                <button onClick={clearSelection} className="px-3 py-1.5 text-xs rounded-md bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-200 transition-all">
                    Deselect
                </button>
                <button onClick={paintSelected} className="px-3 py-1.5 text-xs rounded-md bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-200 transition-all">
                    Paint Selected
                </button>
                <button onClick={clearAllColors} className="px-3 py-1.5 text-xs rounded-md bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-200 transition-all">
                    Clear All
                </button>
                <button
                    onClick={handleApply}
                    disabled={applying}
                    className="ml-auto px-4 py-1.5 text-xs font-semibold rounded-md bg-violet-600 text-white hover:bg-violet-500
                     disabled:opacity-40 disabled:cursor-default transition-all shadow-md shadow-violet-600/20"
                >
                    {applying ? 'Applying...' : 'Apply Per-Key'}
                </button>
            </div>

            {/* Keyboard */}
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 overflow-x-auto backdrop-blur-sm">
                <div className="flex flex-col gap-[3px]" style={{ minWidth: 780 }}>
                    {KB_ROWS.map((row, ri) => (
                        <div key={ri} className="flex gap-[3px]" style={{ height: 34 }}>
                            {row.map((entry, ci) => {
                                if (typeof entry === 'number') {
                                    // Calculate precise pixel width from units, including natural gap
                                    const widthPx = Math.round(entry * UNIT) + (entry > 0 ? 3 : 0);
                                    return <div key={ci} className="shrink-0" style={{ width: widthPx }} />;
                                }
                                const [label, ledIdx, width] = entry;
                                const rgb = keyColors[ledIdx];
                                const isSelected = selectedKeys.has(ledIdx);
                                const hasColor = rgb && (rgb[0] || rgb[1] || rgb[2]);
                                const lum = rgb ? rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114 : 0;

                                return (
                                    <div
                                        key={ci}
                                        onClick={(e) => toggleKey(ledIdx, e.shiftKey)}
                                        className={`h-[34px] flex items-center justify-center rounded text-[0.65rem]
                      cursor-pointer select-none transition-all duration-100 px-1 whitespace-nowrap
                      ${isSelected ? 'ring-1 ring-violet-500 shadow-sm shadow-violet-500/30' : ''}
                      ${!hasColor ? 'bg-zinc-800 border border-zinc-700 text-zinc-400 hover:border-zinc-500' : ''}`}
                                        style={{
                                            width: Math.round(width * UNIT - 3),
                                            ...(hasColor ? {
                                                background: rgbToHex(rgb[0], rgb[1], rgb[2]),
                                                color: lum > 128 ? '#111' : '#fff',
                                                borderColor: rgbToHex(
                                                    Math.min(255, rgb[0] + 40),
                                                    Math.min(255, rgb[1] + 40),
                                                    Math.min(255, rgb[2] + 40)
                                                ),
                                                borderWidth: 1, borderStyle: 'solid',
                                            } : {}),
                                        }}
                                    >
                                        {label}
                                    </div>
                                );
                            })}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
