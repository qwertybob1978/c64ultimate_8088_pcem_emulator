#!/usr/bin/env python3
"""Trace ALL significant events during boot to find exact stall point."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'ref8088'))
from runner import Reference8088


def main():
    spec = json.loads(Path('config/cpu8088.json').read_text())
    cpu = Reference8088(spec)
    cpu.memory[:] = Path('build/guest-genxt.reu').read_bytes()
    cpu.reset()

    # Track all interesting events
    events = []
    seen_ips = {}
    max_steps = 200000
    
    for idx in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        status = trace['status']
        opcode = trace.get('opcode')
        
        key = (cs, ip)
        seen_ips[key] = seen_ips.get(key, 0) + 1
        
        # Record ALL non-trivial events
        if mnemonic.startswith(('INT ', 'IRET', 'CALL FAR', 'JMP FAR', 'RET', 
                                'PUSHF', 'POPF', 'CLI', 'STI', 'HLT',
                                'IN ', 'OUT ', 'NMI', 'IRQ')):
            port = trace.get('port', -1)
            val = trace.get('value', -1)
            target = trace.get('target', '?')
            
            extra = ''
            if mnemonic == 'OUT':
                extra = f' PRT:${port:X} VAL=${val:02X}'
            elif mnemonic == 'IN':
                extra = f' PRT:${port:X} RES=${val:02X}'
            elif mnemonic.startswith('INT'):
                vec = trace.get('interrupt_vector', -1)
                extra = f' VEC={vec:#x} -> {target}'
                
            events.append((idx, f'{cs:04X}:{ip:04X}', mnemonic, extra))
            
        # Check halt/invalid
        if status not in ('ok', 'halted'):
            print(f"\n*** STOPPED step={idx} @{cs:04X}:{ip:04X} op=${opcode:#04x} status={status}")
            break
    
    print("=== TOP 30 MOST-FREQUENTLY HIT CS:IP LOCATIONS ===")
    sorted_ips = sorted(seen_ips.items(), key=lambda x: x[1], reverse=True)[:30]
    for (cs, ip), count in sorted_ips:
        phys = ((cs << 4) + ip) & 0xFFFFF
        entry = cpu.opcodes.get(cpu.memory[phys])
        mne = entry['mnemonic'][:15].ljust(15) if entry else '?'
        rom_start = 0xFE000
        rom_end = 0x100000
        in_rom = "ROM" if rom_start <= phys < rom_end else "RAM"
        print(f"  [{count:>6d}] @{cs:04X}:{ip:04X} ({in_rom}) {mne}")
    
    print("\n=== FIRST 50 NON-TRIVIAL EVENTS ===")
    for time, addr, mne, extra in events[:50]:
        print(f"  [{time:>7d}] {addr} {mne}{extra}")
    
    print(f"\n... total non-trivial events: {len(events)} ...")
    
    # Show last 20 events
    if len(events) > 20:
        print("\n=== LAST 20 EVENTS ===")
        for time, addr, mne, extra in events[-20:]:
            print(f"  [{time:>7d}] {addr} {mne}{extra}")


if __name__ == '__main__':
    raise SystemExit(main())
