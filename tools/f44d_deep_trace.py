"""Deep trace backward from FF44A looking for how DX gets initialized."""
from pathlib import Path

rom = bytearray(Path("third_party/roms/genxt/pcxt.rom").read_bytes())

def phys(off):
    return off + 0xFE000

print("=== Scanning ROM backwards from FF44A (offset 0x144A) ===")
print(f"Looking in range [{phys(0x144A - 500):05X} .. {phys(0x144A)}]\n")

# Search for ALL possible ways DX could be set before reaching FF44A
for start_off in range(max(0, 0x144A - 500), 0x144A):
    b0 = rom[start_off]
    
    # BA xx xx = MOV DX,#imm16
    if b0 == 0xBA and start_off + 2 < len(rom):
        dx_val = rom[start_off+1] | (rom[start_off+2] << 8)
        addr = phys(start_off)
        
        dist_from_target = 0x144A - start_off
        
        print(f"[{addr:05X}] BA {rom[start_off+1]:02X} {rom[start_off+2]:02X}")
        print(f"         → MOV DX=#{dx_val:#06X} (port ${dx_val & 0xFFFF:#04X}) [distance={dist_from_target} bytes]")
        
        # Trace forward briefly to see what happens after this MOV DX
        next_off = start_off + 3
        while next_off < min(start_off + 40, 0x144A, len(rom)):
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
                decoded = f"{cond} {disp:+d} -> [{phys(target):05X}]"
                nn = next_off + 2
            elif nb == 0xEB and next_off+1 < len(rom):
                disp = rom[next_off+1]
                if disp > 0x7F: disp -= 0x100
                target = phys(next_off) + 2 + disp
                decoded = f"JMP {disp:+d} -> [{phys(target):05X}]"
                nn = next_off + 2
            elif nb == 0xE8 or nb == 0xFF:  # CALL patterns
                decoded = "CALL"
                nn = next_off + 1
            elif nb == 0xFA:
                decoded = "CLI"
            elif nb == 0xFB:
                decoded = "STI"
            elif nb == 0x90:
                decoded = "NOP"
            elif nb == 0xCD and next_off+1 < len(rom):
                int_num = rom[next_off+1]
                decoded = f"INT #{int_num:#04X}"
                nn = next_off + 2
            elif nb == 0xBA:  # Another MOV DX - stop scanning this chain
                break
            else:
                pass  # Skip unknowns for brevity
            
            print(f"[{phys(next_off):05X}] {nb:02X} {' '*max(1, 30-len(decoded))}{decoded}")
            next_off = nn
        
        print()

print("\n=== Also checking for CALL instructions near FF44A ===")
# Check if there's a CALL that might load DX internally
for start_off in range(max(0, 0x144A - 50), min(0x144A, len(rom))):
    b0 = rom[start_off]
    
    # E8 xx xx = CALL rel16 (near call with displacement)
    if b0 == 0xE8 and start_off + 2 < len(rom):
        disp = rom[start_off+1] | (rom[start_off+2] << 8)
        if disp & 0x8000: disp -= 0x10000  # sign extend
        target = phys(start_off) + 3 + disp
        print(f"[{phys(start_off):05X}] E8 → CALL to [{target:05X}] (displacement ${disp:#06X})")
        
        # Now trace forward from the CALL target looking for MOV DX
        call_target_offset = target - 0xFE000
        for j in range(call_target_offset, min(call_target_offset + 30, len(rom))):
            cb = rom[j]
            
            cdec = ""
            cn = j + 1
            
            if cb == 0xBA and j+2 < len(rom):
                dx_val = rom[j+1] | (rom[j+2] << 8)
                cdec = f"MOV DX=#{dx_val:#06X} (port ${dx_val & 0xFFFF:#04X})"
                cn = j + 3
            elif cb == 0xEC:
                cdec = "IN AL,dx"
            elif cb == 0xEE:
                cdec = "OUT dx,AL"
            elif cb == 0xA8 and j+1 < len(rom):
                v = rom[j+1]
                cdec = f"TEST AL,#${v:02X}"
                cn = j + 2
            else:
                pass
            
            if cdec:
                print(f"         [${phys(j):05X}] {cb:02X} {' '*max(1, 30-len(cdec))}{cdec}")
            
            j = cn

print("\n=== Checking for OUT $imm8,AL patterns near FF44A ===")
# Maybe BIOS uses OUT immediate port instead of IN AL,dx?
for start_off in range(max(0, 0x144A - 100), 0x144A):
    b0 = rom[start_off]
    
    # E6 xx = OUT imm8,AL  
    if b0 == 0xE6 and start_off + 1 < len(rom):
        port = rom[start_off+1]
        addr = phys(start_off)
        dist_from_target = 0x144A - start_off
        
        print(f"[{addr:05X}] E6 ${port:02X} → OUT #{port:#04X},AL [distance={dist_from_target} bytes]")
