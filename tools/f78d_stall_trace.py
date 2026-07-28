#!/usr/bin/env python3
"""Trace specifically the F78D stall region showing OUT DX,AL port values."""
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

    target_phys_start = 0xFF788
    max_steps = 50000
    
    print("=== Tracing F78D STALL REGION ===")
    
    # Track when we first reach near target
    reached_target = False
    stall_outs = []
    
    for index in range(max_steps):
        trace = cpu.step()
        
        cs = trace['cs']
        ip = trace['ip']
        mnemonic = trace.get('mnemonic', '')
        
        phys_executing = ((cs << 4) + ip) & 0xFFFFF
        
        if not reached_target and abs(phys_executing - target_phys_start) < 0x10:
            reached_target = True
            ax_val = trace['after'].get('AX', 0)
            dx_val = trace['after'].get('DX', 0)
            print(f"[{index}] FIRST REACHED TARGET @{cs:04X}:{ip:04X} PHYS={phys_executing:#07X}")
            print(f"         AX={ax_val:#06X} DX={dx_val:#06X}")
        
        # Capture ALL IO events after reaching target (first 20 loops worth)
        io_events = trace.get('io', [])
        if io_events and reached_target and len(stall_outs) < 200:
            for evt in io_events:
                if isinstance(evt, dict):
                    port = evt.get('port')
                    value = evt.get('value')
                    
                    if port is not None and value is not None:
                        stall_outs.append((index, port, value))
                        
                        # Show every OUT with context
                        print(f"[{index}] @{cs:04X}:{ip:04X} {mnemonic:20s} "
                              f"OUT Port ${port:#06X} <- ${value:#04X} "
                              f"(AX={trace['after']['AX']:04X})")
        
        # Detect repeated stalls at same IP
        if reached_target and ip == 0xF78D or ip == 0xF78F or ip == 0xF794:
            pass  # Expected during stall loop
    
    print(f"\n=== SUMMARY OF F78D STALL ===")
    print(f"Total I/O ops captured during stall: {len(stall_outs)}")
    
    from collections import Counter, defaultdict
    port_counts = Counter(p for _, p, _ in stall_outs)
    port_values = defaultdict(list)
    for idx, p, v in stall_outs:
        port_values[p].append(v)
    
    print("\nPorts accessed during F78D stall:")
    for port, count in sorted(port_counts.items(), key=lambda x: -x[1]):
        vals = port_values[port]
        unique_vals = sorted(set(vals))[:5]
        print(f"  @{port:#06X}: {count} accesses, values={unique_vals}, first=${vals[0]:#04X}")


if __name__ == '__main__':
    main()
