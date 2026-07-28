#!/usr/bin/env python3
"""Capture ALL I/O events from reference model execution."""
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

    all_io_events = []
    
    max_steps = 5000
    
    for index in range(max_steps):
        trace = cpu.step()
        
        # Check io_events list directly (not mnemonic string!)
        io_events = trace.get('io', [])
        
        if io_events:
            print(f"[{index}] @{cs:04X}:{ip:04X} {mnemonic}")
            for evt in io_events:
                if isinstance(evt, dict):
                    port = evt.get('port')
                    value = evt.get('value')
                    direction = evt.get('direction', '?')
                    
                    if port is not None and value is not None:
                        all_io_events.append((index, port, value))
                        
                        if len(all_io_events) <= 100:
                            print(f"      {direction}: Port ${port:#04X} <- ${value:#04X}" if direction == "write" else f"{direction}: Port ${port:#04X} -> ${value:#04X}")
                
                elif isinstance(evt, tuple) and len(evt) >= 2:
                    port, value = evt[0], evt[1]
                    all_io_events.append((index, port, value))
                    
                    if len(all_io_events) <= 100:
                        print(f"      write: Port ${port:#04X} <- ${value:#04X}")
        
        cs = trace['cs']
        ip = trace['ip']
        mnemonic = trace.get('mnemonic', '')
    
    print(f"\n=== SUMMARY ===")
    print(f"Total OUT/IN operations captured: {len(all_io_events)}")
    
    # Group by port number
    from collections import Counter, defaultdict
    port_counts = Counter(p for _, p, _ in all_io_events)
    port_values = defaultdict(set)
    for _, p, v in all_io_events:
        port_values[p].add(v)
    
    print("\nPort access frequency:")
    for port, count in sorted(port_counts.items(), key=lambda x: -x[1]):
        vals = sorted(port_values[port])[:10]
        print(f"  @{port:#06X}: {count} accesses, values={vals}")
    
    # Categorize ports
    print("\n=== PORT CATEGORIES ===")
    vga_ports = [(i,p,v) for i,p,v in all_io_events if 0xC0 <= p <= 0xDF or 0x3C0 <= p <= 0x3DF]
    fdc_ports = [(i,p,v) for i,p,v in all_io_events if 0xF0 <= p <= 0xFF or 0x3F0 <= p <= 0x3FF]
    pic_ports = [(i,p,v) for i,p,v in all_io_events if 0x20 <= p <= 0x21 or 0x200 <= p <= 0x201]
    pit_ports = [(i,p,v) for i,p,v in all_io_events if 0x40 <= p <= 0x43 or 0x240 <= p <= 0x243]
    ppi_ports = [(i,p,v) for i,p,v in all_io_events if 0x60 <= p <= 0x63 or 0x260 <= p <= 0x263]
    dma_ports = [(i,p,v) for i,p,v in all_io_events if 0x00 <= p <= 0x0F or 0x200 <= p <= 0x20F]
    
    print(f"VGA sequencer (0xC0-0xDF): {len(vga_ports)} accesses")
    for idx, port, val in vga_ports[:20]:
        print(f"  [{idx}] Port ${port:#04X} <- ${val:#04X}")
    
    print(f"\nFDC-range (0xF0-0xFF): {len(fdc_ports)} accesses")
    for idx, port, val in fdc_ports[:20]:
        print(f"  [{idx}] Port ${port:#04X} <- ${val:#04X}")
    
    print(f"\nPIC (0x20-0x21): {len(pic_ports)} accesses")
    for idx, port, val in pic_ports[:20]:
        print(f"  [{idx}] Port ${port:#04X} {'->' if 'read' in str(val) else '<-'} ${val:#04X}")
    
    print(f"\nPIT (0x40-0x43): {len(pit_ports)} accesses")
    for idx, port, val in pit_ports[:20]:
        print(f"  [{idx}] Port ${port:#04X} {'->' if 'read' in str(val) else '<-'} ${val:#04X}")
    
    print(f"\nPPI/Keyboard (0x60-0x63): {len(ppi_ports)} accesses")
    for idx, port, val in ppi_ports[:20]:
        print(f"  [{idx}] Port ${port:#04X} {'->' if 'read' in str(val) else '<-'} ${val:#04X}")


if __name__ == '__main__':
    main()
