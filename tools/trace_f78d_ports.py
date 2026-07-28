#!/usr/bin/env python3
"""Trace OUT DX,AL executions showing exact DX port values near F78D region."""
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

    out_count = 0
    
    max_steps = 100000
    
    # Track all OUT operations
    outs = []
    
    for index in range(max_steps):
        trace = cpu.step()
        
        mnemonic = trace.get('mnemonic', '')
        
        # Track ALL OUT instructions with their port and value
        if mnemonic == 'OUT':
            port = trace.get('port')
            val = trace.get('value')
            
            if isinstance(port, int):
                out_count += 1
                outs.append((index, port, val))
                
                # Show first 30 OUTs
                if out_count <= 30:
                    print(f"[{index}] @{port:#06X} <- ${val:#04X}")
    
    print(f"\nTotal OUT operations traced: {out_count}")
    
    # Group by port number
    from collections import Counter
    port_counts = Counter(p for _, p, _ in outs)
    print("\nPort access frequency:")
    for port, count in sorted(port_counts.items(), key=lambda x: -x[1])[:20]:
        print(f"  @{port:#06X}: {count} accesses")
    
    # Check for VGA sequencer ports ($C0-$DF)
    vga_outs = [(i,p,v) for i,p,v in outs if 0xC0 <= p <= 0xDF]
    print(f"\nVGA sequencer ports (0xC0-0xDF): {len(vga_outs)} accesses")
    for idx, port, val in vga_outs[:20]:
        print(f"  [{idx}] @{port:#06X} <- ${val:#04X}")


if __name__ == '__main__':
    import sys
    main()
