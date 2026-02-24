'use client';
import { useEffect, useRef } from 'react';

interface LogPanelProps {
    logs: string[];
}

export function LogPanel({ logs }: LogPanelProps) {
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
    }, [logs]);

    return (
        <div
            ref={ref}
            className="w-full max-w-[920px] bg-zinc-900/80 border border-zinc-800 rounded-lg p-4
                 font-mono text-[0.7rem] text-zinc-500 max-h-48 overflow-y-auto
                 whitespace-pre-wrap break-all backdrop-blur-sm"
        >
            {logs.length === 0
                ? 'Ready. Connect keyboard to start.'
                : logs.join('\n')
            }
        </div>
    );
}
