#!/usr/bin/env python3
"""Trace Generic XT BIOS boot to find where it stops or loops."""
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

    # Dump first few IVT entries from initial state (all zeros)
    print("=== Initial IVT (before BIOS runs) ===")
    for i in range(8):
        vec_addr = i * 4
        ip_val = cpu.memory[vec_addr] | (cpu.memory[vec_addr + 1] << 8)
        cs_val = cpu.memory[vec_addr + 2] | (cpu.memory[vec_addr + 3] << 8)
        print(f"  INT {i:02d}: IP={ip_val:#06x} CS={cs_val:#06x}")

    seen_states = {}
    max_steps = 50000
    stopped_at = max_steps
    last_cs_ip = "F000:FFFF"
    
    # Track specific events
    int_vectors_fired = []
    io_writes = []
    bda_001a_values = []
    bda_001c_values = []
    pit_writes = []
    pic_writes = []
    
    for index in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        opcode = trace.get('opcode')
        status = trace['status']
        
        # Detect infinite loop
        state_key = (cs, ip)
        count = seen_states.get(state_key, 0) + 1
        seen_states[state_key] = count
        
        if count > 100 and index % 1000 == 0:
            ax = trace['after'].get('AX', '?')
            bx = trace['after'].get('BX', '?')
            cx = trace['after'].get('CX', '?')
            sp = trace['after'].get('SP', '?')
            flags_hex = format(trace['after'].get('FLAGS', 0), '04X')
            
            # Check BDA keyboard buffer pointers
            bda_phys = 0x40 * 16
            bda_001a = cpu.memory[bda_phys + 0x1A] | (cpu.memory[bda_phys + 0x1B] << 8)
            bda_001c = cpu.memory[bda_phys + 0x1C] | (cpu.memory[bda_phys + 0x1D] << 8)
            
            print(
                f"[{index}] Loop @{cs:04X}:{ip:04X} x{count} "
                f"AX={ax:#06x} BX={bx:#06x} CX={cx:#06x} SP={sp:#06x} "
                f"FL={flags_hex} KBH={bda_001a:#06x} KBT={bda_001c:#06x}"
            )
        
        # Watch for INT execution
        if mnemonic.startswith(('INT ', 'CALL FAR')) or mnemonic == 'IRET':
            target = trace.get('target', '?')
            int_vectors_fired.append((index, mnemonic, target))
            if len(int_vectors_fired) <= 20:
                print(f"  [{index}] {mnemonic} -> {target}")

        # Track I/O writes to PIT/PIC ports
        if mnemonic in ('OUT',):
            port = trace.get('port', -1)
            val = trace.get('value', -1)
            if port is not None and isinstance(port, int):
                if 0x40 <= port <= 0x43:
                    pit_writes.append((index, port, val))
                elif port in (0x20, 0x21):
                    pic_writes.append((index, port, val))
                
                io_writes.append((index, port, val))
                if len(io_writes) <= 50:
                    print(f"  [{index}] OUT ${port:04X}, ${val:02X}")

        # Stop at unsupported instruction
        if status != 'ok' and status != 'halted':
            stopped_at = index
            break
    
    if stopped_at < max_steps:
        print(f"\n*** STOPPED at step {stopped_at}: op=${opcode:#04x} status={status}")
    else:
        print(f"\nReached {max_steps} steps without stopping")
    
    # Summary of IVT after execution
    print("\n=== Final IVT (after BIOS ran) ===")
    for i in range(32):
        vec_addr = i * 4
        ip_val = cpu.memory[vec_addr] | (cpu.memory[vec_addr + 1] << 8)
        cs_val = cpu.memory[vec_addr + 2] | (cpu.memory[vec_addr + 3] << 8)
        if ip_val != 0 or cs_val != 0:
            print(f"  INT {i:02d}: CS:{ip_val:04X} IP={cs_val:04X}")
    
    # Show last few states before stop/loop
    print(f"\n=== Last 10 unique states visited ===")
    sorted_states = sorted(seen_states.items(), key=lambda x: -x[1])[:10]
    for (c, i), cnt in sorted_states:
        ax = '?'
        bx = '?'
        cx = '?'
        sp = '?'
        fl = '?'
        for k, v in seen_states.items():
            pass  # We don't have per-state register info easily accessible
        
        print(f"  @{c:04X}:{i:04X} visited {cnt} times")


if __name__ == '__main__':
    main()
