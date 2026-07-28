#!/usr/bin/env python3
"""Trace Generic XT BIOS boot focusing on F78D loop."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'ref8088'))
from runner import Reference8088


def main():
    spec = json.loads(Path('config/cpu8088.json').read_text())
    cpu = Reference8088(spec)
    cpu.memory[:] = Path('build/guest-genxt.reu').read_bytes()
    cpu.reset()

    seen_states = {}
    io_writes = []
    io_reads = []
    int_events = []
    
    max_steps = 60000
    
    for index in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        opcode = trace.get('opcode')
        status = trace['status']
        
        # Track ALL I/O writes/reads
        if mnemonic == 'OUT':
            port = trace.get('port', -1)
            val = trace.get('value', -1)
            if isinstance(port, int):
                io_writes.append((index, port, val))
                
        if mnemonic.startswith(('IN ',)):
            port = trace.get('port', -1)
            if isinstance(port, int):
                io_reads.append((index, port))
        
        # Track INT events
        if mnemonic.startswith(('INT ', 'CALL FAR')) or mnemonic == 'IRET':
            target = trace.get('target', '?')
            int_events.append((index, mnemonic, target))
            
        # Detect loops around F78D area
        if (cs == 0xF000) and (ip >= 0xF780) and (ip <= 0xF7A0):
            state_key = (cs, ip)
            count = seen_states.get(state_key, 0) + 1
            seen_states[state_key] = count
            
            if count % 50 == 0:
                ax = trace['after'].get('AX', '?')
                bx = trace['after'].get('BX', '?')
                cx = trace['after'].get('CX', '?')
                dx = trace['after'].get('DX', '?')
                sp = trace['after'].get('SP', '?')
                flags_hex = format(trace['after'].get('FLAGS', 0), '04X')
                print(f"[{index}] @{cs:04X}:{ip:04X} x{count} AX={ax:#06x} BX={bx:#06x} CX={cx:#06x} DX={dx:#06x} SP={sp:#06x} FL={flags_hex}")
        
        # Stop at unsupported instruction
        if status != 'ok' and status != 'halted':
            stopped_at = index
            break

    print("\n=== Last 200 I/O writes ===")
    for ts, port, val in io_writes[-200:]:
        print(f"  [{ts}] OUT ${port:04X}, ${val:02X}")
    
    print("\n=== All I/O reads ===")
    for ts, port in io_reads:
        print(f"  [{ts}] IN to port ${port:04X}")
    
    print("\n=== Last 30 INT/IRET events ===")
    for ts, mnem, tgt in int_events[-30:]:
        print(f"  [{ts}] {mnem} -> {tgt}")


if __name__ == '__main__':
    main()
