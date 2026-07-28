#!/usr/bin/env python3
"""Trace ALL I/O events and key memory writes during Generic XT BIOS boot."""
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

    max_steps = 50000
    
    # Collect all interesting events
    out_events = []       # (step, port_hex, value_hex)
    int_fired = []        # (step, vec_num, target_cs_ip)
    mem_writes_bda = []   # (step, phys_addr, value) - BDA region
    pit_outs = []         # PIT writes specifically
    pic_outs = []         # PIC writes specifically
    
    seen_states = {}
    
    for idx in range(max_steps):
        trace = cpu.step()
        
        cs = trace['after']['CS']
        ip = trace['after']['IP']
        mnemonic = trace.get('mnemonic', '')
        status = trace['status']
        
        key = (cs, ip)
        seen_states[key] = seen_states.get(key, 0) + 1
        
        # Track OUT instructions
        if mnemonic == 'OUT':
            port = trace.get('port')
            val = trace.get('value')
            if isinstance(port, int) and isinstance(val, int):
                entry = (idx, f'{port:#04X}', f'{val:#02X}')
                out_events.append(entry)
                
                if 0x40 <= port <= 0x43:
                    pit_outs.append(entry)
                elif port in (0x20, 0x21):
                    pic_outs.append(entry)
                    
                # Stop collecting after we have enough data
                if len(out_events) > 200:
                    break
        
        # Track INT execution
        if mnemonic.startswith(('INT ', 'CALL FAR')):
            vec = trace.get('interrupt_vector')
            target = trace.get('target', '?')
            if vec is not None:
                int_fired.append((idx, vec, target))
        
        # Track memory writes to IVT/BDA region (physical 0x00000-0x003FF)
        if trace.get('memory_write'):
            mw = trace['memory_write']
            addr = mw.get('address', -1)
            if isinstance(addr, int) and 0 <= addr < 0x400:
                mem_writes_bda.append((idx, f'{addr:#05X}', f"{mw.get('value', 0):#02X}"))

    print("=== I/O Events ===")
    print(f"Total OUT events captured: {len(out_events)}")
    print("\n--- First 60 OUT events ---")
    for ev in out_events[:60]:
        marker = ""
        if ev[1] in ('$0020', '$0021'):
            marker = " [PIC]"
        elif ev[1].startswith('$004'):
            marker = " [PIT]"
        print(f"  [{ev[0]:>5d}] OUT {ev[1]}, {ev[2]}{marker}")
    
    print("\n--- PIC writes only ---")
    for ev in pic_outs:
        print(f"  [{ev[0]:>5d}] OUT {ev[1]}, {ev[2]}")
    
    print("\n--- PIT writes only ---")
    for ev in pit_outs:
        print(f"  [{ev[0]:>5d}] OUT {ev[1]}, {ev[2]}")
    
    print("\n--- Memory writes to BDA/IVT region ---")
    for ev in mem_writes_bda[:80]:
        print(f"  [{ev[0]:>5d}] MEM[{ev[1]}] = {ev[2]}")
    
    print("\n--- Interrupt vectors fired ---")
    for ev in int_fired[:30]:
        print(f"  [{ev[0]:>5d}] {ev[1]} -> {ev[2]}")
    
    print("\n=== Top 10 most-looped addresses ===")
    sorted_states = sorted(seen_states.items(), key=lambda x: -x[1])[:10]
    for (c, i), cnt in sorted_states:
        print(f"  @{c:04X}:{i:04X}: {cnt} times")


if __name__ == '__main__':
    main()
