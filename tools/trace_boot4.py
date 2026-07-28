#!/usr/bin/env python3
"""Trace exactly what happens at F000:F065 and E845."""
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

    # Dump ROM code at key addresses BEFORE running
    print("=== Code at F000:F065 ===")
    cs_ip = (0xF000, 0xF065)
    for offset in range(-5, 30):
        phys = ((cs_ip[0] << 4) + (cs_ip[1] + offset)) & 0xFFFFF
        byte_val = cpu.memory[phys]
        mnemonic = '?'
        try:
            entry = cpu.opcodes.get(byte_val)
            if entry:
                mnemonic = entry['mnemonic'][:12].ljust(12)
        except:
            pass
        print(f'  [{offset:+3d}] phys={phys:#07X} ${byte_val:02X} {mnemonic}')

    print("\n=== Code at F000:E845 (keyboard wait loop per CONTINUATION.md) ===")
    for offset in range(-5, 20):
        phys = ((0xF000 << 4) + (0xE845 + offset)) & 0xFFFFF
        byte_val = cpu.memory[phys]
        mnemonic = '?'
        try:
            entry = cpu.opcodes.get(byte_val)
            if entry:
                mnemonic = entry['mnemonic'][:12].ljust(12)
        except:
            pass
        print(f'  [{offset:+3d}] phys=${phys:05X} ${byte_val:02X} {mnemonic}')

    # Now trace execution through the first INT call to see full context
    print("\n=== Tracing from reset through first few hundred steps ===")
    
    for idx in range(500):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        opcode = trace.get('opcode')
        status = trace['status']
        
        # Print all interesting events early on
        if idx < 200 and (mnemonic.startswith(('INT ', 'CALL FAR', 'JMP FAR')) or 
                          mnemonic == 'OUT' or mnemonic == 'IN'):
            target = trace.get('target', '?')
            port = trace.get('port', -1)
            val = trace.get('value', -1)
            
            extra = ''
            if mnemonic == 'OUT':
                extra = f' port={port:#04x} val={val}'
            elif mnemonic.startswith('INT'):
                extra = f' -> {target}'
                
            print(f"  [{idx:04d}] @{cs:04X}:{ip:04X} {mnemonic}{extra}")
        
        if status not in ('ok', 'halted'):
            print(f"\n*** STOPPED at step {idx}: op=${opcode:#04x} status={status}")
            return
    
    # Now fast-forward to where we hit F000:F065 repeatedly
    seen = {}
    max_steps = 30000
    
    for idx in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        status = trace['status']
        
        key = (cs, ip)
        seen[key] = seen.get(key, 0) + 1
        
        # When we enter E845 region, slow down
        if 0xE840 <= ip <= 0xE860:
            bda_phys = 0x40 * 16
            kb_head = cpu.memory[bda_phys + 0x1A] | (cpu.memory[bda_phys + 0x1B] << 8)
            kb_tail = cpu.memory[bda_phys + 0x1C] | (cpu.memory[bda_phys + 0x1D] << 8)
            
            loop_cnt = seen.get((cs, ip), 0)
            ax = trace['after'].get('AX', 0)
            bx = trace['after'].get('BX', 0)
            cx = trace['after'].get('CX', 0)
            sp = trace['after'].get('SP', 0)
            flags = format(trace['after'].get('FLAGS', 0), '04X')
            
            if idx % 2000 == 0 or loop_cnt > 20:
                print(
                    f"[{idx:06d}] @{cs:04X}:{ip:04X} x{loop_cnt} "
                    f"AX={ax:#06x} BX={bx:#06x} CX={cx:#06x} SP={sp:#06x} FL={flags} "
                    f"KBH={kb_head:#06x} KBT={kb_tail:#06x}"
                )

    print("\n=== Top 15 most-looped addresses ===")
    sorted_states = sorted(seen.items(), key=lambda x: -x[1])[:15]
    for (c, i), cnt in sorted_states:
        print(f"  @{c:04X}:{i:04X}: {cnt} times")


if __name__ == '__main__':
    main()
