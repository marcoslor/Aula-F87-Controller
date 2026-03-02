'use client';
import { useState } from 'react';

interface SettingsPanelProps {
    onSetSleep: (minutes: number) => Promise<void>;
    onSetDebounce: (level: number) => Promise<void>;
    onFactoryReset: () => Promise<void>;
}

export function SettingsPanel({ onSetSleep, onSetDebounce, onFactoryReset }: SettingsPanelProps) {
    const [sleepMinutes, setSleepMinutes] = useState(0);
    const [debounceLevel, setDebounceLevel] = useState(3);
    const [applyingSleep, setApplyingSleep] = useState(false);
    const [applyingDebounce, setApplyingDebounce] = useState(false);
    const [resetting, setResetting] = useState(false);

    const handleSleep = async () => {
        setApplyingSleep(true);
        try { await onSetSleep(sleepMinutes); }
        finally { setApplyingSleep(false); }
    };

    const handleDebounce = async () => {
        setApplyingDebounce(true);
        try { await onSetDebounce(debounceLevel); }
        finally { setApplyingDebounce(false); }
    };

    const handleReset = async () => {
        if (!confirm('Factory reset all lighting settings? This cannot be undone.')) return;
        setResetting(true);
        try { await onFactoryReset(); }
        finally { setResetting(false); }
    };

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Sleep Timer */}
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm space-y-3">
                <h3 className="text-sm font-medium text-zinc-300">Sleep Timer</h3>
                <p className="text-xs text-zinc-600">Auto-off after inactivity</p>
                <select
                    value={sleepMinutes}
                    onChange={e => setSleepMinutes(parseInt(e.target.value))}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-violet-500"
                >
                    <option value={0}>Off</option>
                    <option value={5}>5 minutes</option>
                    <option value={10}>10 minutes</option>
                    <option value={15}>15 minutes</option>
                </select>
                <button
                    onClick={handleSleep}
                    disabled={applyingSleep}
                    className="w-full py-2 rounded-lg text-sm font-medium transition-all duration-200 bg-violet-600 text-white hover:bg-violet-500 shadow-md shadow-violet-600/20 disabled:opacity-40 disabled:cursor-default"
                >
                    {applyingSleep ? 'Setting...' : 'Set Sleep Timer'}
                </button>
            </div>

            {/* Debounce Setting */}
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm space-y-3">
                <h3 className="text-sm font-medium text-zinc-300">Debounce Time</h3>
                <p className="text-xs text-zinc-600">Key response time (lower = faster)</p>
                <select
                    value={debounceLevel}
                    onChange={e => setDebounceLevel(parseInt(e.target.value))}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-violet-500"
                >
                    <option value={1}>1 ms (fastest)</option>
                    <option value={2}>2 ms</option>
                    <option value={3}>3 ms (default)</option>
                    <option value={4}>4 ms</option>
                    <option value={5}>5 ms (most stable)</option>
                </select>
                <button
                    onClick={handleDebounce}
                    disabled={applyingDebounce}
                    className="w-full py-2 rounded-lg text-sm font-medium transition-all duration-200 bg-violet-600 text-white hover:bg-violet-500 shadow-md shadow-violet-600/20 disabled:opacity-40 disabled:cursor-default"
                >
                    {applyingDebounce ? 'Setting...' : 'Set Debounce'}
                </button>
            </div>

            {/* Factory Reset */}
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm space-y-3 sm:col-span-2">
                <h3 className="text-sm font-medium text-zinc-300">Factory Reset</h3>
                <p className="text-xs text-zinc-600">Restore all default lighting settings</p>
                <button
                    onClick={handleReset}
                    disabled={resetting}
                    className="w-full py-2 rounded-lg text-sm font-medium transition-all duration-200 bg-red-600/20 border border-red-500/40 text-red-400 hover:bg-red-600/30 hover:border-red-500/60 disabled:opacity-40 disabled:cursor-default"
                >
                    {resetting ? 'Resetting...' : 'Factory Reset'}
                </button>
            </div>
        </div>
    );
}
