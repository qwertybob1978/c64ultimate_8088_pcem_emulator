#!/usr/bin/env python3
"""Deep trace around the BIOS keyboard-wait loop."""
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

    seen = {}
    max_steps = 80000
    
    # Track specific addresses near E845-E852
    target_range_start = 0xE840
    target_range_end = 0xE860
    
    int_08_count = 0
    int_09_count = 0
    out_events = []
    
    for idx in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        status = trace['status']
        
        key = (cs, ip)
        seen[key] = seen.get(key, 0) + 1
        
        # Watch INT execution
        if mnemonic.startswith('INT ') and len(out_events) < 100:
            vec = trace.get('interrupt_vector')
            if vec == 0x08:
                int_08_count += 1
            elif vec == 0x09:
                int_09_count += 1
            print(f"[{idx}] {cs:04X}:{ip:04X} {mnemonic}")
            
        # Track OUT instructions
        if mnemonic == 'OUT' and len(out_events) < 100:
            port = trace.get('port', -1)
            val = trace.get('value', -1)
            if isinstance(port, int):
                out_events.append((idx, f'{cs:04X}:{ip:04X}', mnemonic, f'{port:#04X}', f'{val:#02X}'))
                
        # Print when entering/exiting the wait-loop region
        if target_range_start <= ip <= target_range_end:
            bda_phys = 0x40 * 16
            kb_head = cpu.memory[bda_phys + 0x1A] | (cpu.memory[bda_phys + 0x1B] << 8)
            kb_tail = cpu.memory[bda_phys + 0x1C] | (cpu.memory[bda_phys + 0x1D] << 8)
            
            loop_cnt = seen.get((cs, ip), 0)
            ax = trace['after'].get('AX', 0)
            bx = trace['after'].get('BX', 0)
            cx = trace['after'].get('CX', 0)
            sp = trace['after'].get('SP', 0)
            flags = format(trace['after'].get('FLAGS', 0), '04X')
            
            if idx % 5000 == 0 or loop_cnt > 50:
                print(
                    f"[{idx}] @{cs:04X}:{ip:04X} x{loop_cnt} "
                    f"AX={ax:#06x} BX={bx:#06x} CX={cx:#06x} SP={sp:#06x} FL={flags} "
                    f"KBH={kb_head:#06x} KBT={kb_tail:#06x}"
                )

    print(f"\n=== Summary ===")
    print(f"Total steps: {max_steps}")
    print(f"INT 0x08 fired: {int_08_count}")
    print(f"INT 0x09 fired: {int_09_count}")
    
    print("\n=== First 30 I/O writes ===")
    for ev in out_events[:30]:
        print(f"  [{ev[0]}] {ev[1]} OUT {ev[3]}, {ev[4]}")
        
    print("\n=== Top 10 most-looped addresses ===")
    sorted_states = sorted(seen.items(), key=lambda x: -x[1])[:10]
    for (c, i), cnt in sorted_states:
        print(f"  @{c:04X}:{i:04X}: {cnt} times")


if __name__ == '__main__':
    main()
