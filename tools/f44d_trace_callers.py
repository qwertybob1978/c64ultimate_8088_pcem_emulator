"""Trace FORWARD from FF43B to see full control flow."""
from pathlib import Path

rom = bytearray(Path("third_party/pcem-roms/genxt/pcxt.rom").read_bytes())

def phys(off):
    return off + 0xFE000

print("=" * 70)
print("=== Tracing FORWARD from FF43B (JNE -5 pattern start) ===")
off = 0x143B
end_off = min(0x14C0, len(rom))

while off < end_off:
    b0 = rom[off]
    
    decoded = ""
    next_off = off + 1
    
    if b0 == 0xBA and off+2 < len(rom):
        val = rom[off+1] | (rom[off+2] << 8)
        port = val & 0xFFFF
        decoded = f"MOV DX,#${port:04X}"
        next_off = off + 3
    elif b0 == 0xEC:
        decoded = "IN AL,dx"
    elif b0 == 0xEE:
        decoded = "OUT dx,AL"
    elif b0 == 0xA8 and off+1 < len(rom):
        v = rom[off+1]
        decoded = f"TEST AL,#${v:02X}"
        next_off = off + 2
    elif b0 in [0x74, 0x75] and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        cond = "JNE" if b0 == 0x75 else "JE"
        loop_marker = ' <-- LOOP' if abs(disp) <= 6 else ''
        decoded = f"{cond} {disp:+d} -> [{phys(target):05X}]{loop_marker}"
        next_off = off + 2
    elif b0 == 0xEB and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        decoded = f"JMP {disp:+d} -> [{phys(target):05X}]"
        next_off = off + 2
    elif b0 == 0xE9 and off+2 < len(rom):  # JMP ax,imm16
        imm = rom[off+1] | (rom[off+2] << 8)
        decoded = f"JMP #{imm:#06X}"
        next_off = off + 3
    elif b0 == 0xFA:
        decoded = "CLI"
    elif b0 == 0xFB:
        decoded = "STI"
    elif b0 == 0x90:
        decoded = "NOP"
    elif b0 == 0xCD and off+1 < len(rom):
        int_num = rom[off+1]
        decoded = f"INT #{int_num:#04X}"
        next_off = off + 2
    elif b0 == 0xC3:
        decoded = "RET"
    
    addr = phys(off)
    print(f"[{addr:05X}] {b0:02X} {' '*max(1, 35-len(decoded))}{decoded}")
    
    off = next_off


print("\n\n=== Scanning ROM for CALL/JMP targets that jump TO FF43B-FF45C ===")
# Find all jumps/calls/rets in the BIOS that could lead to our stall region
for start_off in range(max(0, 0xFE00), min(len(rom)-3, 0xFFFE)):
    b0 = rom[start_off]
    
    # E8 xx xx = CALL rel16
    if b0 == 0xE8 and start_off + 2 < len(rom):
        disp = rom[start_off+1] | (rom[start_off+2] << 8)
        if disp & 0x8000: disp -= 0x10000
        target_phys = phys(start_off) + 3 + disp
        
        # Check if this call lands near our polling loops
        if 0x143B <= target_phys - 0xFE000 <= 0x1460 or \
           0x2B3 <= target_phys - 0xFE000 <= 0x2D0:
            print(f"[{phys(start_off):05X}] E8 → CALL [{target_phys:05X}] (displacement ${disp:#06X})")
            
            # Show context around target
            t_off = target_phys - 0xFE000
            for j in range(t_off, min(t_off+10, len(rom))):
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
                elif cb == 0xEB and j+1 < len(rom):
                    d = rom[j+1]
                    if d > 0x7F: d -= 0x100
                    tgt = phys(j) + 2 + d
                    cdec = f"JMP {d:+d} -> [{tgt:05X}]"
                    cn = j + 2
                elif cb == 0xFA:
                    cdec = "CLI"
                elif cb == 0xFB:
                    cdec = "STI"
                
                if cdec:
                    print(f"         [${phys(j):05X}] {cb:02X} {' '*max(1, 30-len(cdec))}{cdec}")
    
    # EB xx / E9 xx = JMP rel16/rel8
    elif b0 == 0xEB and start_off + 1 < len(rom):
        disp = rom[start_off+1]
        if disp > 0x7F: disp -= 0x100
        target_phys = phys(start_off) + 2 + disp
        
        if 0x143B <= target_phys - 0xFE000 <= 0x1460 or \
           0x2B3 <= target_phys - 0xFE000 <= 0x2D0:
            print(f"[{phys(start_off):05X}] EB → JMP [{target_phys:05X}]")

print("\n\n=== Scanning for RET instructions that return TO FF43B-FF45C ===")
# Also check what happens when we hit the RET at FF444
for start_off in range(max(0, 0xFE00), min(len(rom)-1, 0xFFFE)):
    b0 = rom[start_off]
    
    if b0 == 0xC3:  # RET
        addr = phys(start_off)
        
        # Check nearby for MOV DX patterns before this RET
        for prev_off in range(max(0, start_off-20), start_off):
            pb = rom[prev_off]
            
            if pb == 0xBA and prev_off+2 < len(rom):
                dx_val = rom[prev_off+1] | (rom[prev_off+2] << 8)
                port = dx_val & 0xFFFF
                dist = start_off - prev_off
                print(f"[{addr:05X}] C3 RET ← preceded by MOV DX=#{dx_val:#06X} ({dist} bytes prior)")

