#!/usr/bin/env python3
"""Deep trace around F000:F065 showing full context before/after INT 06."""
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

    # Track key state changes
    int_06_count = 0
    max_steps = 100000
    
    # Record last N steps for pattern detection
    recent_events = []
    
    for idx in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        status = trace['status']
        opcode = trace.get('opcode')
        
        if mnemonic == 'INT imm8':
            vec = trace.get('interrupt_vector')
            if vec == 0x06:
                int_06_count += 1
                
                ax = trace['after'].get('AX', 0)
                bx = trace['after'].get('BX', 0)
                cx = trace['after'].get('CX', 0)
                sp = trace['after'].get('SP', 0)
                flags = format(trace['after'].get('FLAGS', 0), '04X')
                
                print(f"\n=== INT 06 #{int_06_count} at step {idx} ===")
                print(f"  @{cs:04X}:{ip:04X}")
                print(f"  AX={ax:#06X} BX={bx:#06X} CX={cx:#06X} SP={sp:#06X} FL={flags}")
                
                # Show IVT[6] vector
                ivt_phys = 0x06 * 4
                cur_ip = cpu.memory[ivt_phys] | (cpu.memory[ivt_phys + 1] << 8)
                cur_cs = cpu.memory[ivt_phys + 2] | (cpu.memory[ivt_phys + 3] << 8)
                print(f"  IVT[6]: CS:{cur_cs:04X} IP:{cur_ip:04X}")
                
                # Decode bytes around F065 to see what instruction triggered this
                phys_f065 = ((0xF000 << 4) + 0xF065) & 0xFFFFF
                print(f"\n  Code near F065:")
                for offset in [-4, -3, -2, -1, 0, 1, 2, 3, 4]:
                    p = (phys_f065 + offset) & 0xFFFFF
                    b = cpu.memory[p]
                    entry = cpu.opcodes.get(b)
                    mne = entry['mnemonic'][:12].ljust(12) if entry else '?'
                    marker = " <-- HERE" if offset == 0 else ""
                    print(f"    [{offset:+3d}] ${p:05X}: ${b:02X} ({mne}){marker}")

        elif mnemonic.startswith(('OUT ', 'IN')) and opcode is not None:
            port = trace.get('port', -1)
            val = trace.get('value', -1)
            recent_events.append((idx, f'{mnemonic} PRT:${port:X} VAL:${val:X}' if mnemonic=='OUT' else f'{mnemonic} PRT:${port:X}'))
            
        elif mnemonic == 'PUSH' or mnemonic == 'POP':
            reg = trace.get('operand', '')
            recent_events.append((idx, f'{mnemonic} {reg}'))
        
        # Keep only last 20 events before each INT 06
        if len(recent_events) > 20:
            recent_events = recent_events[-20:]
    
    print(f"\n=== SUMMARY ===")
    print(f"Total steps traced: {max_steps}")
    print(f"INT 06 fired: {int_06_count} times")
    print(f"Last 20 I/O/push/pop events before final INT 06:")
    for evt_time, desc in recent_events[-20:]:
        print(f"  step {evt_time:>7d}: {desc}")


if __name__ == '__main__':
    raise SystemExit(main())
