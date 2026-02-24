'use client';
import { useState, useCallback, useRef } from 'react';
import { WIRED_VID, WIRED_PID, WIRELESS_VID, WIRELESS_PID, hex } from '@/lib/protocol';
import { setEffect, applyPerKey, setSleepTimer, factoryReset, type EffectOptions } from '@/lib/webhid';

export function useKeyboard() {
    const [device, setDevice] = useState<HIDDevice | null>(null);
    const [connected, setConnected] = useState(false);
    const [status, setStatus] = useState('Not connected');
    const [logs, setLogs] = useState<string[]>([]);
    const logsRef = useRef<string[]>([]);

    const log = useCallback((msg: string) => {
        const ts = new Date().toLocaleTimeString('en', { hour12: false, fractionalSecondDigits: 3 });
        const entry = `[${ts}] ${msg}`;
        logsRef.current = [...logsRef.current, entry];
        setLogs([...logsRef.current]);
        console.log(msg);
    }, []);

    const connect = useCallback(async (vendorFilter: boolean) => {
        if (device?.opened) {
            await device.close();
            setDevice(null);
            setConnected(false);
            setStatus('Disconnected');
            log('Disconnected');
            return;
        }

        try {
            let filters: HIDDeviceFilter[];
            if (vendorFilter) {
                filters = [];
                for (let page = 0xff00; page <= 0xff04; page++) {
                    filters.push({ vendorId: WIRED_VID, productId: WIRED_PID, usagePage: page });
                    filters.push({ vendorId: WIRELESS_VID, productId: WIRELESS_PID, usagePage: page });
                }
                log('Requesting device (vendor pages)...');
            } else {
                filters = [
                    { vendorId: WIRED_VID, productId: WIRED_PID },
                    { vendorId: WIRELESS_VID, productId: WIRELESS_PID },
                ];
                log('Requesting device (any)...');
            }

            const [dev] = await navigator.hid.requestDevice({ filters });
            if (!dev) { log('No device selected'); return; }
            await dev.open();
            setDevice(dev);
            setConnected(true);

            const vid = dev.vendorId.toString(16).padStart(4, '0');
            const pid = dev.productId.toString(16).padStart(4, '0');
            log(`Connected: ${dev.productName || 'AULA F87'} (${vid}:${pid})`);

            const hasVendor = dev.collections.some(c => c.usagePage >= 0xff00);
            setStatus(hasVendor
                ? `Connected: ${dev.productName || 'AULA F87'} (${vid}:${pid})`
                : '⚠ Wrong interface — no vendor collection'
            );
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            log(`Error: ${msg}`);
            setStatus(`Error: ${msg}`);
        }
    }, [device, log]);

    const doSetEffect = useCallback(async (effectNum: number, opts: EffectOptions) => {
        if (!device?.opened) { log('Not connected!'); return; }
        try { await setEffect(device, effectNum, opts, log); }
        catch (err: unknown) { log(`ERROR: ${err instanceof Error ? err.message : String(err)}`); }
    }, [device, log]);

    const doApplyPerKey = useCallback(async (keyColors: Record<number, [number, number, number]>) => {
        if (!device?.opened) { log('Not connected!'); return; }
        try { await applyPerKey(device, keyColors, log); }
        catch (err: unknown) { log(`ERROR: ${err instanceof Error ? err.message : String(err)}`); }
    }, [device, log]);

    const doSetSleep = useCallback(async (minutes: number) => {
        if (!device?.opened) { log('Not connected!'); return; }
        try { await setSleepTimer(device, minutes, log); }
        catch (err: unknown) { log(`ERROR: ${err instanceof Error ? err.message : String(err)}`); }
    }, [device, log]);

    const doFactoryReset = useCallback(async () => {
        if (!device?.opened) { log('Not connected!'); return; }
        try { await factoryReset(device, log); }
        catch (err: unknown) { log(`ERROR: ${err instanceof Error ? err.message : String(err)}`); }
    }, [device, log]);

    return {
        connected, status, logs, log,
        connect, doSetEffect, doApplyPerKey, doSetSleep, doFactoryReset,
    };
}
