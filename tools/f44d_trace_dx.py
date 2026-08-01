"""Trace backward from FF44A to find MOV DX,#imm or similar."""
from pathlib import Path

rom = bytearray(Path("third_party/pcem-roms/genxt/pcxt.rom").read_bytes())

def phys(off):
    return off + 0xFE000

# Scan ROM backwards from offset 0x144A (physical FF44A) looking for:
# B2 xx = MOV DL,#imm
# BA xx xx = MOV DX,#imm16  
# BB xx xx = MOV BX,#imm16
# BE xx xx = MOV SI,#imm16
# BF xx xx = MOV DI,#imm16
# BA xx xx = MOV DX,#imm16 (2-byte immediate follows little-endian)
# Also look for OUT imm8,AL ($EE) which sets AL then uses DX

print("=== Scanning ROM FE000-FEFFF for MOV reg,#imm patterns ===")
print(f"Target location: physical {phys(0x144A):05X} (offset {0x144A:#06X})\n")

# Search entire first 32K of ROM (FE000 to FEFFF would be offsets 0x0000-0xFFFF but ROM is only 8KB)
# Actually ROM is 8KB total (FE000-FFFFF), so we scan offsets 0x0000-0x1FFF
for start_off in range(0, min(len(rom)-3, 0x2000)):
    b0 = rom[start_off]
    
    # Check for common patterns that set up DX before IN AL,dx
    
    # BA xx xx = MOV DX,#imm16 (little-endian)
    if b0 == 0xBA and start_off + 2 < len(rom):
        dx_val = rom[start_off+1] | (rom[start_off+2] << 8)
        print(f"[{phys(start_off):05X}] BA {rom[start_off+1]:02X} {rom[start_off+2]:02X} → MOV DX=#{dx_val:#06X}")
        
        # Now check if there's an EC (IN AL,dx) shortly after this MOV DX
        for j in range(start_off+3, min(start_off+20, len(rom))):
            if rom[j] == 0xEC:  # IN AL,dx
                print(f"           → followed by IN AL,dx at [{phys(j):05X}]")
                break
    
    # B2 xx = MOV DL,#imm8
    elif b0 == 0xB2 and start_off + 1 < len(rom):
        dl_val = rom[start_off+1]
        print(f"[{phys(start_off):05X}] B2 {dl_val:02X} → MOV DL=#{dl_val:#04X}")
        
        # Check nearby for IN AL,dx
        for j in range(start_off+2, min(start_off+20, len(rom))):
            if rom[j] == 0xEC:
                print(f"          → followed by IN AL,dx at [{phys(j):05X}]")
                break
    
    # EE = OUT AL,imm8 (uses AL which might have been loaded earlier)
    elif b0 == 0xEE:
        pass  # Skip - not directly relevant
    
    # Look for port writes too (OUT ports $F4/$F7 etc.)
    elif b0 == 0xE6 and start_off + 1 < len(rom):
        port = rom[start_off+1]
        if port >= 0xF0:
            print(f"[{phys(start_off):05X}] E6 {port:02X} → OUT #{port:#04X},AL")

print("\n=== Scanning near FF44A backward ===")
# Also scan a window around our target going backwards
for off in range(max(0, 0x144A-100), 0x144A):
    b0 = rom[off]
    
    # Any instruction that could set up registers before polling loop
    patterns = []
    
    # PUSH/POP operations on common regs
    if b0 == 0x52: patterns.append("PUSH BX")
    elif b0 == 0x53: patterns.append("PUSH CX")  
    elif b0 == 0x54: patterns.append("PUSH DX")
    elif b0 == 0x55: patterns.append("PUSH SI")
    elif b0 == 0x56: patterns.append("PUSH DI")
    elif b0 == 0x5A: patterns.append("POP DX")
    elif b0 == 0x5E: patterns.append("POP SI")
    elif b0 == 0x5F: patterns.append("POP DI")
    
    # INC/DEC DX
    elif b0 == 0xFE and off+1 < len(rom) and (rom[off+1] & 0xC0) == 0xD0:
        reg = (rom[off+1]) >> 3 & 7
        if reg == 2:  # DX
            patterns.append(f"INC DX")
    elif b0 == 0xFF and off+1 < len(rom) and (rom[off+1] & 0xC0) == 0xD0:
        reg = (rom[off+1]) >> 3 & 7
        if reg == 2:  # DX
            patterns.append(f"DEC DX")
    
    # MOV AL,#imm8 followed by OUT dx,AL or IN AL,dx pattern
    if b0 == 0xB0 and off+1 < len(rom):
        al_val = rom[off+1]
        patterns.append(f"MOV AL=#{al_val:#04X}")
        
        # Check for OUT dx,AL shortly after
        for j in range(off+2, min(off+10, len(rom))):
            if rom[j] == 0xEE:  # OUT dx,AL
                print(f"[{phys(off):05X}] B0 {al_val:02X} → MOV AL=#{al_val:#04X}, then OUT dx,AL at [{phys(j):05X}]")
                break
    
    if patterns:
        addr = phys(off)
        print(f"[{addr:05X}] {b0:02X} {' '.join(patterns)}")
