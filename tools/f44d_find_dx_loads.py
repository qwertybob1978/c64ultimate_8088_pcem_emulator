"""Find ALL MOV DX instructions in ROM and trace forward."""
from pathlib import Path

rom = bytearray(Path("third_party/pcem-roms/genxt/pcxt.rom").read_bytes())

def phys(off):
    return off + 0xFE000

print("=" * 70)
print("=== Finding all MOV DX,#imm sequences near our stall region ===")
print(f"Scanning range: [{phys(max(0, 0x143B - 200)):05X} .. {phys(min(len(rom), 0x143B + 200))}]\n")

# Search backwards from offset 0x143B for any MOV DX patterns
for start_off in range(max(0, 0x143B - 200), min(0x143B, len(rom)-2)):
    b0 = rom[start_off]
    
    # BA xx xx = MOV DX,#imm16
    if b0 == 0xBA and start_off + 2 < len(rom):
        dx_val = rom[start_off+1] | (rom[start_off+2] << 8)
        addr = phys(start_off)
        
        dist_from_target = abs(addr - phys(0x143B))
        
        print(f"[{addr:05X}] BA {rom[start_off+1]:02X} {rom[start_off+2]:02X}")
        print(f"         → MOV DX=#{dx_val:#06X} [port ${dx_val & 0xFFFF:#04X}] ({dist_from_target} bytes from target)")
        
        # Trace forward briefly showing what happens after this MOV DX
        next_off = start_off + 3
        while next_off < min(start_off + 30, len(rom)):
            nb = rom[next_off]
            
            decoded = ""
            nn = next_off + 1
            
            if nb == 0xEC:
                decoded = "IN AL,dx"
            elif nb == 0xEE:
                decoded = "OUT dx,AL"
            elif nb == 0xA8 and next_off+1 < len(rom):
                v = rom[next_off+1]
                decoded = f"TEST AL,#${v:02X}"
                nn = next_off + 2
            elif nb in [0x74, 0x75] and next_off+1 < len(rom):
                disp = rom[next_off+1]
                if disp > 0x7F: disp -= 0x100
                target = phys(next_off) + 2 + disp
                cond = "JNE" if nb == 0x75 else "JE"
                loop_marker = ' <-- LOOP' if abs(disp) <= 6 else ''
                decoded = f"{cond} {disp:+d} -> [{phys(target):05X}]{loop_marker}"
                nn = next_off + 2
            elif nb == 0xEB and next_off+1 < len(rom):
                disp = rom[next_off+1]
                if disp > 0x7F: disp -= 0x100
                target = phys(next_off) + 2 + disp
                decoded = f"JMP {disp:+d} -> [{phys(target):05X}]"
                nn = next_off + 2
            elif nb == 0xFA:
                decoded = "CLI"
            elif nb == 0xFB:
                decoded = "STI"
            elif nb == 0xC3:
                decoded = "RET"
            elif nb == 0xBA:  # Another MOV DX - stop scanning this chain
                break
            else:
                pass  # Skip unknowns for brevity
            
            print(f"[{phys(next_off):05X}] {nb:02X} {' '*max(1, 30-len(decoded))}{decoded}")
            next_off = nn
        
        print()

print("\n\n=== Also checking nearby CALL/JMP patterns ===")
# Check if there's a CALL that might load DX internally before jumping to our region
for start_off in range(max(0, 0x143B - 200), min(0x143B, len(rom)-2)):
    b0 = rom[start_off]
    
    # E8 xx xx = CALL rel16 (near call with displacement)
    if b0 == 0xE8 and start_off + 2 < len(rom):
        disp = rom[start_off+1] | (rom[start_off+2] << 8)
        if disp & 0x8000: disp -= 0x10000  # sign extend
        target_phys = phys(start_off) + 3 + disp
        
        dist_from_target = abs(target_phys - phys(0x143B))
        
        if dist_from_target < 100:
            print(f"\n[{phys(start_off):05X}] E8 → CALL [{target_phys:05X}] (displacement ${disp:#06X}) [dist={dist_from_target}]")
            
            # Now trace forward from the CALL target looking for MOV DX
            call_target_offset = target_phys - 0xFE000
            for j in range(call_target_offset, min(call_target_offset + 30, len(rom))):
                cb = rom[j]
                
                cdec = ""
                cn = j + 1
                
                if cb == 0xBA and j+2 < len(rom):
                    dx_val = rom[j+1] | (rom[j+2] << 8)
                    port = dx_val & 0xFFFF
                    cdec = f"MOV DX=#{dx_val:#06X} (port ${port:04X})"
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
                    marker = ' <<< TARGET REGION' if abs(phys(j) - target_phys) <= 10 else ''
                    print(f"[{phys(j):05X}] {cb:02X} {' '*max(1, 30-len(cdec))}{cdec}{marker}")
