#!/usr/bin/env python3
"""Early BIOS trace showing first 5000 steps with registers/memory/io."""
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

    print("=== First 5000 Steps ===")
    stall_count = 0
    last_ip = None
    
    for index in range(min(5000, len(cpu.memory))):
        trace = cpu.step()
        
        mnemonic = trace.get('mnemonic', '')
        cs = trace['cs']
        ip = trace['ip']
        ax = trace['after'].get('AX', 0)
        dx = trace['after'].get('DX', 0)
        
        # Detect stalls (same IP repeating)
        if ip == last_ip:
            stall_count += 1
        else:
            if stall_count > 5:
                print(f"  [STALL DETECTED] @{cs}:{ip} ({stall_count} repeats)")
            stall_count = 1
        
        last_ip = ip
        
        # Show interesting ops or first/last few
        if index < 10 or index >= 4990 or mnemonic.lower() in ('out', 'in', 'int', 'sti'):
            io_events = trace.get('io', [])
            writes = trace.get('writes', [])
            
            print(f"[{index:5d}] @{cs:04X}:{ip:04X} {mnemonic:20s} AX={ax:04X} DX={dx:04X}", end="")
            if io_events:
                print(f" IO={len(io_events)} events", end="")
            if writes:
                print(f" MEM_Writes={len(writes)}", end="")
            print()
    
    # Summary of unique mnemonics seen
    all_mnemonics = set()
    total_io_events = 0
    total_mem_writes = 0
    
    cpu.reset()
    cpu.memory[:] = Path('build/guest-genxt.reu').read_bytes()
    cpu.reset()
    
    for index in range(5000):
        trace = cpu.step()
        all_mnemonics.add(trace.get('mnemonic', ''))
        total_io_events += len(trace.get('io', []))
        total_mem_writes += len(trace.get('writes', []))
    
    print("\n=== SUMMARY ===")
    print(f"Mnemonics encountered ({len(all_mnemonics)}): {sorted(all_mnemonics)[:30]}...")
    print(f"Total I/O events captured: {total_io_events}")
    print(f"Total memory writes captured: {total_mem_writes}")


if __name__ == '__main__':
    main()
