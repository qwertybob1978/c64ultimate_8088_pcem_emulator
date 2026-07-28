#!/usr/bin/env python3
"""Trace OUT DX,AL executions showing exact DX port values."""
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'ref8088'))
from runner import Reference8088


def fmt(val):
    if isinstance(val, int):
        return f"{val:#06x}"
    return "?"


def main():
    spec = json.loads(Path('config/cpu8088.json').read_text())
    cpu = Reference8088(spec)
    cpu.memory[:] = Path('build/guest-genxt.reu').read_bytes()
    cpu.reset()

    out_count = 0
    
    max_steps = 55000
    
    for index in range(max_steps):
        trace = cpu.step()
        
        mnemonic = trace.get('mnemonic', '')
        
        # Track ALL OUT instructions with their port and value
        if mnemonic == 'OUT':
            port = trace.get('port')
            val = trace.get('value')
            
            if isinstance(port, int):
                out_count += 1
                
                # Show first 20 OUTs and then every 100th after that
                if out_count <= 20 or out_count % 100 == 0:
                    print(f"[{index}] OUT ${port:#06X} <- ${val:#04X}")
                
                # Also show any OUT to VGA-related ports ($03D0-$03DF)
                if 0x03D0 <= port <= 0x03DF:
                    print(f"  >>> VGA PORT ACCESS [{out_count}]: @{port:#06X} <- ${val:#04X}")
    
    print(f"\nTotal OUT operations traced: {out_count}")


if __name__ == '__main__':
    import sys
    main()
