"""Find which port is being polled by tracing BACKWARD from FF44A."""
from pathlib import Path

rom = bytearray(Path("third_party/pcem-roms/genxt/pcxt.rom").read_bytes())

def phys(off):
    return off + 0xFE000

# At FF44A we have IN AL,dx followed by TEST AL,$01 then JNE -5 back to FF44A
# This is an infinite loop waiting for BIT 0 to become SET
# We need to find what port DX contains when reaching FF44A

print("=== Scanning ROM backwards from FF44A looking for MOV DX ===")
print(f"Target: physical {phys(0x144A):05X} (ROM offset {0x144A:#06X})\n")

# Search backwards from offset 0x144A for any instruction that could load DX
for start_off in range(max(0, 0x144A - 200), 0x144A):
    b0 = rom[start_off]
    
    # BA xx xx = MOV DX,#imm16
    if b0 == 0xBA and start_off + 2 < len(rom):
        dx_val = rom[start_off+1] | (rom[start_off+2] << 8)
        addr = phys(start_off)
        
        print(f"[{addr:05X}] BA {rom[start_off+1]:02X} {rom[start_off+2]:02X}")
        print(f"         → MOV DX=#{dx_val:#06X} (port ${dx_val & 0xFFFF:#04X})")
        
        # Now verify this leads to our stall location
        # Check if there's a path from here to FF44A without another MOV DX
        
        # Also check nearby instructions after this MOV DX
        next_off = start_off + 3
        while next_off < min(start_off + 30, 0x144A, len(rom)):
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
            elif nb == 0xFA:
                decoded = "CLI"
            elif nb == 0xFB:
                decoded = "STI"
            elif nb == 0x90:
                decoded = "NOP"
            elif nb == 0xCD and next_off+1 < len(rom):
                decoded = f"INT #{rom[next_off+1]:#04X}"
                nn = next_off + 2
            elif nb == 0xBA:  # Another MOV DX - stop scanning
                break
            else:
                decoded = f"?${nb:02X}"
            
            print(f"[{phys(next_off):05X}] {nb:02X} {' '*max(1, 25-len(decoded))}{decoded}")
            next_off = nn
        
        print()

print("\n=== Also checking for PUSH/POP patterns that might preserve DX ===")
for start_off in range(max(0, 0x144A - 200), 0x144A):
    b0 = rom[start_off]
    
    # Check for PUSH DX / POP DX sequences
    if b0 == 0x54:  # PUSH DX
        addr = phys(start_off)
        print(f"[{addr:05X}] 54 → PUSH DX (saving register)")
        
        # Look ahead for matching POP DX
        for j in range(start_off+1, min(start_off+30, 0x144A)):
            if rom[j] == 0x5A:  # POP DX
                pop_addr = phys(j)
                print(f"[{pop_addr:05X}] 5A → POP DX (restoring register)")
                
                # Now check what happened between push/pop
                for k in range(start_off+1, j):
                    kb = rom[k]
                    if kb == 0xEC:
                        print(f"[{phys(k):05X}] EC → IN AL,dx (using saved DX!)")
                    elif kb == 0xEE:
                        print(f"[{phys(k):05X}] EE → OUT dx,AL (using saved DX!)")
                    elif kb == 0xA8 and k+1 < len(rom):
                        v = rom[k+1]
                        print(f"[{phys(k):05X}] A8 ${v:02X} → TEST AL,#${v:02X}")
                    elif kb in [0x74, 0x75] and k+1 < len(rom):
                        disp = rom[k+1]
                        if disp > 0x7F: disp -= 0x100
                        target = phys(k) + 2 + disp
                        cond = "JNE" if kb == 0x75 else "JE"
                        print(f"[{phys(k):05X}] {kb:02X} {cond} {disp:+d} -> [{phys(target):05X}]")
                break
    
    # BA xx xx = MOV DX,#imm16 near our target
    elif b0 == 0xBA and abs(start_off - 0x144A) < 100:
        dx_val = rom[start_off+1] | (rom[start_off+2] << 8)
        addr = phys(start_off)
        port = dx_val & 0xFFFF
        
        # Check if this is close to FF44A
        dist = 0x144A - start_off
        if dist <= 50:
            print(f"\n[PROXIMITY ALERT at {addr:05X}] Only {dist} bytes from stall!")
            print(f"         MOV DX=#{dx_val:#06X} (port ${port:04X})")
