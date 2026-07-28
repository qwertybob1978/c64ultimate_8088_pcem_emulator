#!/usr/bin/env python3
"""Trace around F000:F065 to find why INT 06 fires repeatedly."""
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

    # Check initial IVT for int 06
    print("=== Initial IVT[6] ===")
    vec_phys = 0x06 * 4
    ip_init = cpu.memory[vec_phys] | (cpu.memory[vec_phys + 1] << 8)
    cs_init = cpu.memory[vec_phys + 2] | (cpu.memory[vec_phys + 3] << 8)
    print(f"  IP={ip_init:#06X} CS={cs_init:#06X}")

    seen = {}
    max_steps = 70000
    
    int_06_count = 0
    int_00_count = 0
    trace_events = []
    
    for idx in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        status = trace['status']
        opcode = trace.get('opcode')
        
        key = (cs, ip)
        seen[key] = seen.get(key, 0) + 1
        
        if mnemonic == 'INT imm8':
            vec = trace.get('interrupt_vector')
            if vec == 0x06:
                int_06_count += 1
                ax = trace['after'].get('AX', 0)
                bx = trace['after'].get('BX', 0)
                cx = trace['after'].get('CX', 0)
                sp = trace['after'].get('SP', 0)
                flags = format(trace['after'].get('FLAGS', 0), '04X')
                
                if int_06_count <= 5 or int_06_count % 50 == 0:
                    print(f"[{idx}] INT 06 @{cs:04X}:{ip:04X} AX={ax:#06x} SP={sp:#06x} FL={flags}")
                    
                    # Show what's at the current IVT entry
                    cur_vec_phys = 0x06 * 4
                    cur_ip = cpu.memory[cur_vec_phys] | (cpu.memory[cur_vec_phys + 1] << 8)
                    cur_cs = cpu.memory[cur_vec_phys + 2] | (cpu.memory[cur_vec_phys + 3] << 8)
                    print(f"       Current IVT[6]: {cur_cs:04X}:{cur_ip:04X}")
            
            elif vec == 0x00:
                int_00_count += 1
            
            if len(trace_events) < 100 and int_06_count > 0:
                target = trace.get('target', '?')
                trace_events.append((idx, f'{cs:04X}:{ip:04X}', mnemonic, str(target)))

    print(f"\n=== Summary ===")
    print(f"Total steps traced: {max_steps}")
    print(f"INT 06 fired: {int_06_count} times")
    print(f"INT 00 fired: {int_00_count} times")
    
    # Check final IVT state
    print("\n=== Final IVT entries ===")
    for i in range(16):
        vec_phys = i * 4
        ip_val = cpu.memory[vec_phys] | (cpu.memory[vec_phys + 1] << 8)
        cs_val = cpu.memory[vec_phys + 2] | (cpu.memory[vec_phys + 3] << 8)
        if ip_val != 0 or cs_val != 0:
            print(f"  INT {i:02d}: CS:{cs_val:04X} IP:{ip_val:04X}")
    
    # Show code around F065
    print(f"\n=== Code near F000:F065 ===")
    base_phys = 0xF000 * 16 + 0xF065 - 0xF065  # map to ROM area
    rom_offset = (0xF000 * 16 + 0xF065) & 0xFFFFF
    print("Bytes around F065:")
    for offset in range(-5, 20):
        addr = rom_offset + offset
        byte_val = cpu.memory[addr]
        meta = None
        for entry in spec['opcodes']:
            for opc in range(entry['first'], entry['last'] + 1):
                pass  # too slow, skip detailed decode
    
    print(f"  [{-5:+4}] @{rom_offset-5:#07X} ${byte_val&0xFF:02X}" if False else "")
    
    # Print bytes at F065 region
    start_off = 0xF060
    end_off = 0xF090
    print("\nROM bytes F060-F08F:")
    row = []
    for off in range(start_off, min(end_off, 0x100000)):
        b = cpu.memory[off]
        row.append(f'{b:02X}')
        if len(row) == 16:
            print(f'  @{start_off:X}:{(off-15):04X}-@{end_off:X}:{(off+1):04X} {" ".join(row)}')
            row = []
    if row:
        padding = ['--'] * (16 - len(row))
        print(f'  ... {" ".join(row + padding)}')


if __name__ == '__main__':
    main()
