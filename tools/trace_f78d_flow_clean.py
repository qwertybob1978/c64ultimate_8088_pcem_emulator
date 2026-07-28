#!/usr/bin/env python3
"""Trace full instruction flow leading into F78D loop."""
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

    print("=== Full instruction trace during F78D loop ===")
    
    max_steps = 55000
    
    for index in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        opcode = trace.get('opcode')
        prev_ip = trace.get('prev_ip', -1)
        prev_cs = trace.get('prev_cs', -1)
        target = trace.get('target', None)
        
        phys_addr = cs * 16 + ip
        
        # Only show instructions near our loop area (within +/-500 bytes)
        if (cs == 0xF000 and 0xF700 <= ip <= 0xF9A0) or \
           (phys_addr >= 0xFF700 and phys_addr <= 0xFF9A0):
            
            info = f"[{index}] @{cs:04X}:{ip:04X} ({phys_addr:#06x}) {mnemonic}"
            if opcode is not None:
                info += f" op=${opcode:02X}"
            if target is not None:
                info += f" -> {target}"
            if prev_ip != -1:
                info += f" (from @{prev_cs:04X}:{prev_ip:04x})"
                
            print(info)
            
            # Limit output to avoid flooding
            if index > max_steps - 500:
                break


if __name__ == '__main__':
    main()
