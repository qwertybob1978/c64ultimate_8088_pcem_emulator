"""Search entire ROM for CALL/JMP targets landing in FF43B-FF45C."""
from pathlib import Path

rom = bytearray(Path("third_party/pcem-roms/genxt/pcxt.rom").read_bytes())

def phys(off):
    return off + 0xFE000

print("=" * 70)
print("=== Scanning ENTIRE ROM (FE000-FEFFF) for paths TO FF43B-FF45C ===")
print(f"Target: [{phys(0x143B):05X} .. {phys(0x145C)}]\n")

# Search ALL possible CALL/JMP patterns in first 32K of ROM
for start_off in range(max(0, len(rom)-10), min(len(rom)-3)):
    b0 = rom[start_off]
    
    # E8 xx xx = CALL rel16 (near call)
    if b0 == 0xE8 and start_off + 2 < len(rom):
        disp = rom[start_off+1] | (rom[start_off+2] << 8)
        if disp & 0x8000: disp -= 0x10000
        target_phys = phys(start_off) + 3 + disp
        
        # Check if this lands near our polling loops
        if abs(target_phys - phys(0x143B)) <= 50 or \
           abs(target_phys - phys(0x2B3)) <= 50:
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
                    cdec = f"{cond} {d:+d} -> [{tgt:05X}]"
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
        
        if abs(target_phys - phys(0x143B)) <= 50 or \
           abs(target_phys - phys(0x2B3)) <= 50:
            print(f"\n[{phys(start_off):05X}] EB → JMP [{target_phys:05X}] (disp ${disp:#04X})")


print("\n\n=== Scanning for CALL/JMP patterns that jump TO FF2B3-FF2C9 ===")
# Also check the CGA polling loop at FF2B3
for start_off in range(max(0, len(rom)-10), min(len(rom)-3)):
    b0 = rom[start_off]
    
    # E8 xx xx = CALL rel16
    if b0 == 0xE8 and start_off + 2 < len(rom):
        disp = rom[start_off+1] | (rom[start_off+2] << 8)
        if disp & 0x8000: disp -= 0x10000
        target_phys = phys(start_off) + 3 + disp
        
        if abs(target_phys - phys(0x2B3)) <= 50:
            print(f"\n[{phys(start_off):05X}] E8 → CALL [{target_phys:05X}] (CGA poll)")
            
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
                    cdec = f"{cond} {d:+d} -> [{tgt:05X}]"
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
        
        if abs(target_phys - phys(0x2B3)) <= 50:
            print(f"\n[{phys(start_off):05X}] EB → JMP [{target_phys:05X}]")


print("\n\n=== Scanning for CALL/JMP patterns that jump TO FF4A2-FF4C0 ===")
# Check the larger code block starting around FF4A2 (has MOV DS/SS etc.)
for start_off in range(max(0, len(rom)-10), min(len(rom)-3)):
    b0 = rom[start_off]
    
    # E8 xx xx = CALL rel16
    if b0 == 0xE8 and start_off + 2 < len(rom):
        disp = rom[start_off+1] | (rom[start_off+2] << 8)
        if disp & 0x8000: disp -= 0x10000
        target_phys = phys(start_off) + 3 + disp
        
        if abs(target_phys - phys(0x4A2)) <= 100 or \
           abs(target_phys - phys(0x4D0)) <= 100:
            print(f"\n[{phys(start_off):05X}] E8 → CALL [{target_phys:05X}] (disp ${disp:#06X})")
            
            t_off = target_phys - 0xFE000
            for j in range(t_off, min(t_off+20, len(rom))):
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
                    cdec = f"{cond} {d:+d} -> [{tgt:05X}]"
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
        
        if abs(target_phys - phys(0x4A2)) <= 100 or \
           abs(target_phys - phys(0x4D0)) <= 100:
            print(f"\n[{phys(start_off):05X}] EB → JMP [{target_phys:05X}]")


print("\n\n=== Scanning for CALL/JMP patterns that jump TO FF4B0-FF4C0 ===")
# Check the larger code block starting around FF4A2 (has MOV DS/SS etc.)
for start_off in range(max(0, len(rom)-10), min(len(rom)-3)):
    b0 = rom[start_off]
    
    # E8 xx xx = CALL rel16
    if b0 == 0xE8 and start_off + 2 < len(rom):
        disp = rom[start_off+1] | (rom[start_off+2] << 8)
        if disp & 0x8000: disp -= 0x10000
        target_phys = phys(start_off) + 3 + disp
        
        if abs(target_phys - phys(0x4B0)) <= 100 or \
           abs(target_phys - phys(0x4D0)) <= 100:
            print(f"\n[{phys(start_off):05X}] E8 → CALL [{target_phys:05X}] (disp ${disp:#06X})")
            
            t_off = target_phys - 0xFE000
            for j in range(t_off, min(t_off+20, len(rom))):
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
                    cdec = f"{cond} {d:+d} -> [{tgt:05X}]"
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
        
        if abs(target_phys - phys(0x4B0)) <= 100 or \
           abs(target_phys - phys(0x4D0)) <= 100:
            print(f"\n[{phys(start_off):05X}] EB → JMP [{target_phys:05X}]")

