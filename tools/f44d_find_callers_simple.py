"""Simple search for all CALL/JMP instructions in ROM."""
from pathlib import Path

rom = bytearray(Path("third_party/roms/genxt/pcxt.rom").read_bytes())

def phys(off):
    return off + 0xFE000

print("=" * 70)
print("=== Scanning ENTIRE ROM for CALL/JMP patterns ===")
print()

# Search ALL possible CALL/JMP patterns in entire ROM
for start_off in range(0, max(0, len(rom)-3)):
    b0 = rom[start_off]
    
    # E8 xx xx = CALL rel16 (near call)
    if b0 == 0xE8 and start_off + 2 < len(rom):
        disp = rom[start_off+1] | (rom[start_off+2] << 8)
        if disp & 0x8000: disp -= 0x10000
        target_phys = phys(start_off) + 3 + disp
        
        # Check if this lands near any interesting regions
        targets_of_interest = [0x143B, 0x144A, 0x1450, 0x2B3, 0x4A2, 0x4D0]
        
        for interest_addr in targets_of_interest:
            if abs(target_phys - phys(interest_addr)) <= 50:
                print(f"\n[{phys(start_off):05X}] E8 → CALL [{target_phys:05X}] (disp ${disp:#06X})")
                
                # Show context around target location  
                t_off = target_phys - 0xFE000
                for j in range(t_off, min(t_off+15, len(rom))):
                    cb = rom[j]
                    
                    cdec = ""
                    cn = j + 1
                    
                    if cb == 0xBA and j+2 < len(rom):
                        dx_val = rom[j+1] | (rom[j+2] << 8)
                        port = dx_val & 0xFFFF
                        cdec = f"MOV DX,#${port:04X}"
                        cn = j + 3
                    elif cb == 0xEC:
                        cdec = "IN AL,dx"
                    elif cb == 0xEE:
                        cdec = "OUT dx,AL"
                    elif cb == 0xA8 and j+1 < len(rom):
                        v = rom[j+1]
                        cdec = f"TEST AL,#${v:02X}"
                        cn = j + 2
                    elif cb in [0x74, 0x75] and j+1 < len(rom):
                        d = rom[j+1]
                        if d > 0x7F: d -= 0x100
                        tgt = phys(j) + 2 + d
                        cond = "JNE" if cb == 0x75 else "JE"
                        loop_marker = ' <-- LOOP' if abs(d) <= 6 else ''
                        cdec = f"{cond} {d:+d} -> [{tgt:05X}]{loop_marker}"
                        cn = j + 2
                    elif cb == 0xFA:
                        cdec = "CLI"
                    elif cb == 0xFB:
                        cdec = "STI"
                    elif cb == 0xC3:
                        cdec = "RET"
                    
                    if cdec:
                        marker = ' <<< TARGET' if abs(phys(j) - target_phys) <= 6 else ''
                        print(f"[{phys(j):05X}] {cb:02X} {' '*max(1, 30-len(cdec))}{cdec}{marker}")

    # EB xx = JMP rel8  
    elif b0 == 0xEB and start_off + 1 < len(rom):
        disp = rom[start_off+1]
        if disp > 0x7F: disp -= 0x100
        target_phys = phys(start_off) + 2 + disp
        
        targets_of_interest = [0x143B, 0x144A, 0x1450, 0x2B3, 0x4A2, 0x4D0]
        
        for interest_addr in targets_of_interest:
            if abs(target_phys - phys(interest_addr)) <= 50:
                print(f"\n[{phys(start_off):05X}] EB → JMP [{target_phys:05X}] (disp ${disp:#04X})")


print("\n\n=== Also checking for INT instructions near our stall region ===")
# Maybe BIOS uses INT to enter these routines?
for start_off in range(max(0, 0xFE00), min(len(rom)-1)):
    b0 = rom[start_off]
    
    if b0 == 0xCD and start_off + 1 < len(rom):
        int_num = rom[start_off+1]
        addr = phys(start_off)
        
        decoded = ""
        next_off = start_off + 2
        
        nb = rom[next_off] if next_off < len(rom) else 0xFF
        if nb == 0xBA and next_off+2 < len(rom):
            dx_val = rom[next_off+1] | (rom[next_off+2] << 8)
            port = dx_val & 0xFFFF
            decoded = f"; after INT #{int_num:#04X}: MOV DX,#${port:04X}"
        
        print(f"[{addr:05X}] CD ${int_num:02X} INT #{int_num:#04X} {decoded}")
