'use client';

import { useState } from 'react';
import { useKeyboard } from '@/hooks/useKeyboard';
import { ConnectionBar } from '@/components/ConnectionBar';
import { EffectsPanel } from '@/components/EffectsPanel';
import { PerKeyPanel } from '@/components/PerKeyPanel';
import { SettingsPanel } from '@/components/SettingsPanel';
import { LogPanel } from '@/components/LogPanel';

type Tab = 'effects' | 'perkey' | 'settings';

export default function Home() {
  const kb = useKeyboard();
  const [tab, setTab] = useState<Tab>('effects');

  const tabs: { id: Tab; label: string }[] = [
    { id: 'effects', label: 'Effects' },
    { id: 'perkey', label: 'Per-Key Colors' },
    { id: 'settings', label: 'Settings' },
  ];

  return (
    <main className="flex flex-col items-center px-4 py-8 min-h-screen">
      {/* Header */}
      <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
        AULA F87
      </h1>
      <p className="text-xs text-zinc-600 mt-1 mb-6">WebHID Keyboard Controller</p>

      {/* Connection */}
      <ConnectionBar
        connected={kb.connected}
        status={kb.status}
        onConnect={kb.connect}
      />

      {/* Tab bar */}
      <div className="w-full max-w-[920px] flex gap-1 mb-4 bg-zinc-900/60 rounded-lg p-1 border border-zinc-800">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-2 text-sm rounded-md font-medium transition-all duration-200
              ${tab === t.id
                ? 'bg-violet-600/20 text-violet-300 border border-violet-500/40'
                : 'text-zinc-500 hover:text-zinc-300 border border-transparent'
              }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Panel content */}
      <div className="w-full max-w-[920px] mb-6">
        {tab === 'effects' && <EffectsPanel onApply={kb.doSetEffect} />}
        {tab === 'perkey' && <PerKeyPanel onApply={kb.doApplyPerKey} />}
        {tab === 'settings' && <SettingsPanel onSetSleep={kb.doSetSleep} onFactoryReset={kb.doFactoryReset} />}
      </div>

      {/* Log */}
      <LogPanel logs={kb.logs} />
    </main>
  );
}
