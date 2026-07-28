#!/usr/bin/env python3
"""Trace first 100k steps of reference model to capture full POST I/O pattern."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'ref8088'))
from runner import Reference8088
import json


def main():
    spec = json.loads(Path('config/cpu8088.json').read_text())
    cpu = Reference8088(spec)

    # Load guest image into memory (same as other scripts)
    data = Path('build/guest-genxt.reu').read_bytes()
    cpu.memory[:len(data)] = data

    print(f"Memory size: {len(cpu.memory)} bytes")
    print(f"After load: CS={cpu.registers['CS']:#06X} IP={cpu.registers['IP']:#04X}")

    # Reset sets CS=FFFF IP=0000 per standard x86 behavior
    cpu.reset()
    print(f"After reset: CS={cpu.registers['CS']:#06X} IP={cpu.registers['IP']:#04X}")

    phys = ((cpu.registers["CS"] << 4) + cpu.registers["IP"]) & 0xFFFFF
    if phys < len(data):
        print(f"First byte physical address: {phys:#07X}, value: ${data[phys]:#04X}")
    else:
        print(f"No data at {phys:#07X}")

    outs = []
    ins = []
    max_steps = 100000

    for index in range(max_steps):
        trace = cpu.step()

        mnemonic = str(trace.get('mnemonic', ''))
        cs = int(trace.get('cs', 0) or 0)
        ip = int(trace.get('ip', 0) or 0)

        if mnemonic == 'OUT':
            port = trace.get('port')
            val = trace.get('value')
            if isinstance(port, int):
                outs.append((index, port, val))

        if mnemonic == 'IN':
            port = trace.get('port')
            if isinstance(port, int):
                ins.append((index, port))

        # Print every 1000 steps and on interesting events
        if index % 1000 == 0 or mnemonic in ('INT', 'HLT', 'STI', 'CLI'):
            ax = int(trace.get('ax', 0) or 0)
            cx = int(trace.get('cx', 0) or 0)
            dx = int(trace.get('dx', 0) or 0)
            bx = int(trace.get('bx', 0) or 0)
            sp = int(trace.get('sp', 0) or 0)
            bp = int(trace.get('bp', 0) or 0)
            si = int(trace.get('si', 0) or 0)
            di = int(trace.get('di', 0) or 0)
            fl = trace.get('flags', '?')

            print(f"[{index:>6d}] @{cs:X}:{ip:04X} AX={ax:04X} BX={bx:04X} CX={cx:04X} DX={dx:04X} SP={sp:04X} FL={fl}")

    print(f"\n=== SUMMARY ===")
    print(f"Total OUT ops: {len(outs)}, IN ops: {len(ins)}")

    # Group by port number
    from collections import Counter
    port_counts = Counter(p for _, p, _ in outs)
    print("\nPort access frequency (top 30):")
    for port, count in sorted(port_counts.items(), key=lambda x: -x[1])[:30]:
        vals = set(v for _, p, v in outs if p == port)
        print(f"  @{port:#06X}: {count} accesses, values={sorted(vals)[:15]}")

    # Check VGA sequencer ports ($C0-$DF)
    vga_outs = [(i, p, v) for i, p, v in outs if 0xC0 <= p <= 0xDF]
    print(f"\nVGA sequencer ports (0xC0-0xDF): {len(vga_outs)} accesses")
    if vga_outs:
        for idx, port, val in vga_outs[:30]:
            print(f"  [{idx}] @{port:#06X} <- ${val:#04X}")

    # Also check FDC and other high-page ports
    fdc_outs = [(i, p, v) for i, p, v in outs if 0xF0 <= p <= 0xFF]
    print(f"\nFDC-range ports (0xF0-0xFF): {len(fdc_outs)} accesses")
    if fdc_outs:
        for idx, port, val in fdc_outs[:20]:
            print(f"  [{idx}] @{port:#06X} <- ${val:#04X}")


if __name__ == '__main__':
    main()
