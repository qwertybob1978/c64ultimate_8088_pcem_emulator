#!/usr/bin/env python3
"""Trace ALL OUT DX,AL executions showing exact DX port values."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'ref8088'))
from runner import Reference8088
import json
from collections import Counter


def main():
    spec = json.loads(Path('config/cpu8088.json').read_text())
    cpu = Reference8088(spec)
    cpu.memory[:] = Path('build/guest-genxt.reu').read_bytes()
    cpu.reset()

    outs = []
    
    max_steps = 100000
    
    for index in range(max_steps):
        trace = cpu.step()
        
        mnemonic = trace.get('mnemonic', '')
        
        if mnemonic == 'OUT':
            port = trace.get('port')
            val = trace.get('value')
            
            if isinstance(port, int):
                outs.append((index, port, val))
                
                # Show first 50 OUTs
                if len(outs) <= 50:
                    print(f"[{index}] @{port:#06X} <- ${val:#04X}")
    
    print(f"\nTotal OUT operations traced: {len(outs)}")
    
    # Group by port number
    port_counts = Counter(p for _, p, _ in outs)
    print("\nPort access frequency (top 20):")
    for port, count in sorted(port_counts.items(), key=lambda x: -x[1])[:20]:
        vals = set(v for _, p, v in outs if p == port)
        print(f"  @{port:#06X}: {count} accesses, values={sorted(vals)[:10]}")
    
    # Check for VGA sequencer ports ($C0-$DF)
    vga_outs = [(i,p,v) for i,p,v in outs if 0xC0 <= p <= 0xDF]
    print(f"\nVGA sequencer ports (0xC0-0xDF): {len(vga_outs)} accesses")
    for idx, port, val in vga_outs[:30]:
        print(f"  [{idx}] @{port:#06X} <- ${val:#04X}")
    
    # Also check FDC and other high-page ports
    fdc_outs = [(i,p,v) for i,p,v in outs if 0xF0 <= p <= 0xFF]
    print(f"\nFDC-range ports (0xF0-0xFF): {len(fdc_outs)} accesses")
    for idx, port, val in fdc_outs[:20]:
        print(f"  [{idx}] @{port:#06X} <- ${val:#04X}")


if __name__ == '__main__':
    main()
