#!/usr/bin/env python3
"""Trace FDC-related port accesses during boot to identify exact failure."""
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

    # Track I/O events at key ports
    fdc_ports = {0x3F0, 0x3F1, 0x3F2, 0x3F3, 0x3F4, 0x3F5, 0x3F6, 0x3F7}
    pic_ports = {0x20, 0x21}
    dma_ports = set(range(0x00, 0x10)) | {0x81}
    
    io_events = []
    max_steps = 50000
    
    for idx in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        status = trace['status']
        opcode = trace.get('opcode')
        
        # Collect all I/O events
        for evt in trace.get('io_events', []):
            port = evt.get('port', -1)
            direction = evt.get('direction', '?')
            value = evt.get('value', -1)
            
            if port in fdc_ports or port in pic_ports or port in dma_ports:
                io_events.append((idx, cs, ip, mnemonic, port, direction, value))
                
                # Print first few and any interesting patterns
                if len(io_events) <= 20 or (port == 0x3F5 and direction == 'out'):
                    print(f"[{idx:>6d}] @{cs:04X}:{ip:04X} {mnemonic:<12s} "
                          f"{'OUT' if direction=='out' else 'IN':>3s} "
                          f"PRT:${port:X} VAL=${value:02X}")
        
        # Check for halt/invalid
        if status not in ('ok', 'halted'):
            print(f"\n*** STOPPED step={idx} op=${opcode:#04x} status={status}")
            break
    
    print(f"\n=== SUMMARY ===")
    print(f"Total steps traced: {max_steps}")
    print(f"FDC/PIC/DMA I/O events captured: {len(io_events)}")
    
    # Show last 10 events before end
    if len(io_events) > 10:
        print("\nLast 10 I/O events:")
        for time, cs, ip, mne, port, dir, val in io_events[-10:]:
            print(f"  [{time:>6d}] @{cs:04X}:{ip:04X} {mne:<12s} "
                  f"{'OUT' if dir=='out' else 'IN':>3s} PRT:${port:X} VAL=${val:02X}")


if __name__ == '__main__':
    raise SystemExit(main())
