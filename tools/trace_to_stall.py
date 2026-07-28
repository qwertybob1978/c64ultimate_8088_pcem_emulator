#!/usr/bin/env python3
"""Trace until we reach physical address near 0xFF78D or detect stall."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'ref8088'))
from runner import Reference8088
import json


def main():
    spec = json.loads(Path('config/cpu8088.json').read_text())
    cpu = Reference8088(spec)
    cpu.memory[:] = Path('build/guest-genxt.reu').read_bytes()
    cpu.reset()

    target_phys = 0xFF78D
    max_steps = 50000
    
    print(f"=== Tracing until reaching physical ~{target_phys:#X} ===")
    
    last_ip = None
    stall_count = 0
    io_events_all = []
    
    for index in range(max_steps):
        trace = cpu.step()
        
        cs = trace['cs']
        ip = trace['ip']
        mnemonic = trace.get('mnemonic', '')
        
        # Calculate current physical address being executed
        phys_executing = ((cs << 4) + ip) & 0xFFFFF
        
        # Check if we're near target
        if abs(phys_executing - target_phys) < 0x100:
            print(f"[{index}] @{cs:04X}:{ip:04X} PHYS={phys_executing:#07X} {mnemonic}")
        
        # Detect stalls
        if ip == last_ip:
            stall_count += 1
            if stall_count == 10:
                print(f"\n*** STALL DETECTED at step {index}: @{cs:04X}:{ip:04X} ({stall_count} repeats) ***")
                break
        else:
            stall_count = 0
        
        last_ip = ip
        
        # Collect all I/O events
        io_events = trace.get('io', [])
        if io_events:
            for evt in io_events:
                if isinstance(evt, dict):
                    port = evt.get('port')
                    value = evt.get('value')
                    direction = evt.get('direction', '?')
                    
                    if port is not None and value is not None:
                        io_events_all.append((index, port, value))
                        
                        # Show interesting ports (VGA, FDC, PIT, PPI, PIC)
                        if (0xC0 <= port <= 0xDF or 
                            0xF0 <= port <= 0xFF or 
                            port in (0x20, 0x21, 0x60, 0x61, 0x63)):
                            print(f"[{index}] @{cs:04X}:{ip:04X} {mnemonic:20s} {direction}: Port ${port:#06X} {'->' if direction=='write' else '<-'} ${value:#04X}")
    
    print(f"\n=== SUMMARY ===")
    print(f"Total steps traced: {min(index+1, max_steps)}")
    print(f"Final IP before end/stall: @{last_ip:04X}")
    print(f"Total I/O operations captured: {len(io_events_all)}")
    
    # Group by port number
    from collections import Counter, defaultdict
    port_counts = Counter(p for _, p, _ in io_events_all)
    port_values = defaultdict(set)
    for _, p, v in io_events_all:
        port_values[p].add(v)
    
    print("\nAll unique ports accessed:")
    for port, count in sorted(port_counts.items(), key=lambda x: -x[1]):
        vals = sorted(port_values[port])[:5]
        print(f"  @{port:#06X}: {count} accesses, values={vals}")


if __name__ == '__main__':
    main()
