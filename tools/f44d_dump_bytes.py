"""Dump raw ROM bytes around FF44D stall point with inline x86 decoding."""
from pathlib import Path

rom_path = Path("third_party/pcem-roms/genxt/pcxt.rom")
rom = bytearray(rom_path.read_bytes())

def phys(addr):
    return addr - 0xFE000

# Dump from FF3C0 to FF470
START = phys(0xFF3C0)
END = phys(0xFF470)

print("=" * 90)
print(f"ROM BYTES AT PHYSICAL ADDRESSES {hex(0xFF3C0)}-{hex(0xFF46F)}")
print("=" * 90)
print()

# Print as hex rows + ASCII
for base_off in range(START, END, 16):
    phys_addr = base_off + 0xFE000
    hex_parts = []
    ascii_parts = []
    for i in range(16):
        off = base_off + i
        if off < len(rom):
            b = rom[off]
            hex_parts.append(f"{b:02X}")
            ascii_parts.append(chr(b) if 32 <= b < 127 else '.')
        else:
            hex_parts.append('  ')
            ascii_parts.append(' ')
    
    print(f"[{phys_addr:05X}] {' '.join(hex_parts[:8])}  {' '.join(hex_parts[8:])}   |{''.join(ascii_parts)}|")

print("\n\n" + "=" * 90)
print("TARGETED DECODE: Focus on IN AL,dx / OUT dx,AL / MOV DX,#imm sequences")
print("=" * 90)
print()

# Now let's find all IN (EC), OUT (EE/E4/E5), and MOV reg,#imm patterns manually
# by scanning byte-by-byte with minimal state machine

i = START
while i < min(END, len(rom)):
    b = rom[i]
    phys_addr = i + 0xFE000
    
    # Check for key instruction patterns
    if b == 0xEC:  # IN AL,dx
        print(f"[{phys_addr:05X}] EC          : IN AL,dx         <<< POLLING PORT!")
        i += 1
    elif b == 0xED:  # IN AX,dx
        print(f"[{phys_addr:05X}] ED          : IN AX,dx         <<< POLLING PORT!")
        i += 1
    elif b == 0xEE:  # OUT dx,AL
        print(f"[{phys_addr:05X}] EE          : OUT dx,AL        <<< WRITING PORT!")
        i += 1
    elif b == 0xEF:  # OUT dx,AX
        print(f"[{phys_addr:05X}] EF          : OUT dx,AX      <<< WRITING PORT!")
        i += 1
    elif b == 0xE4:  # IN AL,imm8
        port = rom[i+1] if i+1 < len(rom) else 0
        print(f"[{phys_addr:05X}] E4 {port:02X}     : IN AL,#${port:02X}  <<< IMMEDIATE PORT READ!")
        i += 2
    elif b == 0xE5:  # OUT imm8,AL
        port = rom[i+1] if i+1 < len(rom) else 0
        print(f"[{phys_addr:05X}] E5 {port:02X}     : OUT #$port:{port:02X},AL <<< IMMEDIATE PORT WRITE!")
        i += 2
    elif b == 0xBA or b == 0xBB or b == 0xB8 or b == 0xBC:
        # MOV r/m16,#imm16 where B8=AX,B9=CX,BA=DX,BB=BX,BE=SI,BF=DI,BD=BP,BE=SP... wait
        # Actually: B8+r/8 -> AX,CX,DX,BX,SP,BP,SI/DI(rare),?? 
        reg_map = {0:'AX', 1:'CX', 2:'DX', 3:'BX', 4:'SP', 5:'BP', 6:'SI', 7:'DI'}
        idx = (b & 7)
        reg_name = reg_map[idx]
        lo = rom[i+1] if i+1 < len(rom) else 0
        hi = rom[i+2] if i+2 < len(rom) else 0
        val = lo | (hi << 8)
        marker = " <<< SETTING DX!" if reg_name == 'DX' else ""
        print(f"[{phys_addr:05X}] BA/B8 etc   : MOV {reg_name},#{val:04X}{marker}")
        i += 3
    elif b == 0x8A or b == 0x8B:
        # Need MODRM - skip for now but mark
        modrm = rom[i+1] if i+1 < len(rom) else 0
        mod = (modrm >> 6) & 3
        rm = modrm & 7
        base_regs = ['BX+SI','BX+DI','BP+SI','BP+DI','SI','DI','BP','BX']
        br = base_regs[rm] if mod != 3 else f'r{rm}'
        print(f"[{phys_addr:05X}] 8A/8B       : MOV r8/r16 from [{br}]")
        i += 2
    elif b == 0xA8:  # TEST AL,#imm8
        val = rom[i+1] if i+1 < len(rom) else 0
        marker = " <<< BIT 0 CHECK" if val == 0x01 else ""
        print(f"[{phys_addr:05X}] A8 ${val:02X}     : TEST AL,#${val:02X}{marker}")
        i += 2
    elif b == 0x74 or b == 0x75 or b == 0xEB or b == 0xE2:
        disp = rom[i+1] if i+1 < len(rom) else 0
        signed_disp = disp - 256 if disp > 127 else disp
        target = phys_addr + 2 + signed_disp
        names = {0x74:"JE", 0x75:"JNE", 0xEB:"JMP", 0xE2:"LOOP CX"}
        name = names.get(b, "?")
        print(f"[{phys_addr:05X}] {b:02X} {disp:02X}      : {name} rel8 -> ${target:X}")
        i += 2
    elif b in (0xFA, 0xFB):  # CLI/SI
        names = {0xFA:'CLI', 0xFB:'STI'}
        print(f"[{phys_addr:05X}] {b:02X}          : {names[b]}")
        i += 1
    elif b == 0xC3:  # RET
        print(f"[{phys_addr:05X}] C3          : RET")
        i += 1
    elif b == 0xCA:  # RETF imm16
        val = rom[i+1] | (rom[i+2] << 8) if i+2 < len(rom) else 0
        print(f"[{phys_addr:05X}] CA ${val:04X}: RETF #{val:04X}")
        i += 3
    elif b == 0x9C:  # PUSHF
        print(f"[{phys_addr:05X}] 9C          : PUSHF")
        i += 1
    elif b == 0x9D:  # POPF
        print(f"[{phys_addr:05X}] 9D          : POPF")
        i += 1
    elif b == 0xCD and i+1 < len(rom):  # INT imm8
        n = rom[i+1]
        print(f"[{phys_addr:05X}] CD {n:02X}     : INT #{n:#04X}")
        i += 2
    elif b == 0xFF:  # Group opcode - need MODRM
        modrm = rom[i+1] if i+1 < len(rom) else 0
        reg_field = (modrm >> 3) & 7
        groups = {0:"INC/DEC", 1:"INC", 2:"CALL", 3:"CALL FAR", 
                  4:"JMP", 5:"JMP FAR", 6:"DEC"}
        name = groups.get(reg_field, "???")
        print(f"[{phys_addr:05X}] FF          : GROUP {reg_field} ({name}) r/m")
        i += 2
    elif b == 0xF7 or b == 0xFE:  # More group opcodes
        modrm = rom[i+1] if i+1 < len(rom) else 0
        reg_field = (modrm >> 3) & 7
        print(f"[{phys_addr:05X}] {b:02X}       : GROUP {reg_field} r/m")
        i += 2
    else:
        # Unknown/unhandled - just show byte
        pass
    
    # Safety check to prevent infinite loop
    if i <= phys_addr + 0xFE000:
        break

print("\n\n" + "=" * 90)
print("SUMMARY OF PORT ACCESS PATTERNS")  
print("=" * 90)
