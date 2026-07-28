#!/usr/bin/env python3
"""Detailed trace around F78D loop region."""
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
    
    max_steps = 55000
    
    for index in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        opcode = trace.get('opcode')
        status = trace['status']
        
        # Detect loops around F78D area
        if (cs == 0xF000) and (ip >= 0xF780) and (ip <= 0xF7A0):
            state_key = (cs, ip)
            count = seen_states.get(state_key, 0) + 1
            seen_states[state_key] = count
            
            if count % 25 == 0:
                ax = trace['after'].get('AX', '?')
                bx = trace['after'].get('BX', '?')
                cx = trace['after'].get('CX', '?')
                dx = trace['after'].get('DX', '?')
                sp = trace['after'].get('SP', '?')
                flags_hex = format(trace['after'].get('FLAGS', 0), '04X')
                print(f"[{index}] @{cs:04X}:{ip:04X} x{count} AX={ax:#06x} BX={bx:#06x} CX={cx:#06x} DX={dx:#06x} SP={sp:#06x} FL={flags_hex}")
            
            # Print full context every 5 iterations of the exact same IP
            if state_key[1] == 0xF78D and count % 5 == 0:
                print(f"\n=== Context at @F000:F78D iteration {count} ===")
                print(f"  CS:{ip:04X} AX={trace['after'].get('AX', '?'):04x} "
                      f"BH={trace['after'].get('BH', '?'):02x} BL={trace['after'].get('BL', '?'):02x} "
                      f"CX={trace['after'].get('CX', '?'):04x} FLAGS={format(trace['after'].get('FLAGS', 0), '04X')}")
                
                # Show previous instruction that led here
                prev_trace = None
        
        # Stop at unsupported instruction
        if status != 'ok' and status != 'halted':
            stopped_at = index
            break

    print("\n=== Last 30 unique states in F780-F7A0 region ===")
    sorted_states = sorted(
        [(k, v) for k, v in seen_states.items() if k[0] == 0xF000 and 0xF780 <= k[1] <= 0xF7A0],
        key=lambda x: -x[1]
    )[:30]
    for (c, i), cnt in sorted_states:
        print(f"  @{c:04X}:{i:04X} visited {cnt} times")


if __name__ == '__main__':
    import sys
    main()
