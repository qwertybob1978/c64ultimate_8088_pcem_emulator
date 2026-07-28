#!/usr/bin/env python3
"""Quick trace of Generic XT BIOS execution to find stall point."""
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

    seen = {}  # (cs, ip) -> count
    max_steps = 50000
    
    for idx in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        status = trace['status']
        
        key = (cs, ip)
        seen[key] = seen.get(key, 0) + 1
        
        # Print first few interesting events
        if idx < 500 and mnemonic.startswith(('INT ', 'CALL FAR', 'JMP FAR')):
            target = trace.get('target', '?')
            print(f"[{idx}] {cs:04X}:{ip:04X} {mnemonic} -> {target}")
        
        elif idx >= 500 and idx % 5000 == 0:
            ax = trace['after'].get('AX', 0)
            bx = trace['after'].get('BX', 0)
            cx = trace['after'].get('CX', 0)
            sp = trace['after'].get('SP', 0)
            flags = format(trace['after'].get('FLAGS', 0), '04X')
            
            bda_phys = 0x40 * 16
            kb_head = cpu.memory[bda_phys + 0x1A] | (cpu.memory[bda_phys + 0x1B] << 8)
            kb_tail = cpu.memory[bda_phys + 0x1C] | (cpu.memory[bda_phys + 0x1D] << 8)
            
            loop_count = seen.get((cs, ip), 0)
            print(f"[{idx}] @{cs:04X}:{ip:04X} x{loop_count} AX={ax:#06x} BX={bx:#06x} CX={cx:#06x} SP={sp:#06x} FL={flags} KBH={kb_head:#06x} KBT={kb_tail:#06x}")
        
        if status not in ('ok', 'halted'):
            print(f"\n*** STOPPED at step {idx}: op=${trace.get('opcode', '?')} status={status}")
            return
    
    print(f"\nReached {max_steps} steps")


if __name__ == '__main__':
    main()
