'use client';

interface ConnectionBarProps {
    connected: boolean;
    status: string;
    onConnect: (vendorFilter: boolean) => void;
}

export function ConnectionBar({ connected, status, onConnect }: ConnectionBarProps) {
    return (
        <div className="w-full max-w-[920px] flex flex-col items-center gap-3 mb-6">
            <div className="flex gap-3 items-center">
                <button
                    onClick={() => onConnect(true)}
                    className={`px-6 py-2.5 rounded-lg font-medium text-sm transition-all duration-200
            ${connected
                            ? 'bg-emerald-500/10 border border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/20'
                            : 'bg-violet-600 border border-violet-500 text-white hover:bg-violet-500 shadow-lg shadow-violet-600/20'
                        }`}
                >
                    {connected ? 'Disconnect' : 'Connect Keyboard'}
                </button>
                <button
                    onClick={() => onConnect(false)}
                    className="px-4 py-2 rounded-lg text-xs text-zinc-500 border border-zinc-700 hover:border-zinc-500 hover:text-zinc-300 transition-all"
                >
                    Connect (any)
                </button>
            </div>
            <p className="text-xs text-zinc-500">{status}</p>
        </div>
    );
}
