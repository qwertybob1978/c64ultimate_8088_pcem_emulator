"""Minimal x86 decoder focused on finding I/O port polling loops."""
from pathlib import Path

rom = bytearray(Path("third_party/roms/genxt/pcxt.rom").read_bytes())

def phys(off):
    return off + 0xFE000

# Scan from FF3C0 to FF470 looking for specific patterns
START = phys(0xFF3C0) - 0xFE000
END = phys(0xFF470) - 0xFE000

results = []

i = START
while i < END and i < len(rom):
    b = rom[i]
    
    if b == 0xEC:  # IN AL,dx
        addr = phys(i)
        results.append(f"[{addr:05X}] EC          : IN AL,dx")
        i += 1
    
    elif b == 0xED:  # IN AX,dx
        addr = phys(i)
        results.append(f"[{addr:05X}] ED          : IN AX,dx")
        i += 1
        
    elif b == 0xEE:  # OUT dx,AL
        addr = phys(i)
        results.append(f"[{addr:05X}] EE          : OUT dx,AL")
        i += 1
        
    elif b == 0xEF:  # OUT dx,AX
        addr = phys(i)
        results.append(f"[{addr:05X}] EF          : OUT dx,AX")
        i += 1
        
    elif b == 0xE4:  # IN AL,#imm8
        port = rom[i+1] if i+1 < len(rom) else 0
        addr = phys(i)
        results.append(f"[{addr:05X}] E4 ${port:02X}     : IN AL,#${port:02X}")
        i += 2
        
    elif b == 0xE5:  # OUT #imm8,AL
        port = rom[i+1] if i+1 < len(rom) else 0
        addr = phys(i)
        results.append(f"[{addr:05X}] E5 ${port:02X}     : OUT #$port:{port:02X},AL")
        i += 2
        
    elif 0xB8 <= b <= 0xBF:  # MOV r/m16,#imm16
        reg_map = {0:'AX', 1:'CX', 2:'DX', 3:'BX', 4:'SP', 5:'BP', 6:'SI', 7:'DI'}
        idx = (b & 7)
        reg_name = reg_map[idx]
        lo = rom[i+1] if i+1 < len(rom) else 0
        hi = rom[i+2] if i+2 < len(rom) else 0
        val = lo | (hi << 8)
        marker = " <<< SETTING DX!" if reg_name == 'DX' else ""
        addr = phys(i)
        results.append(f"[{addr:05X}] B8-BF       : MOV {reg_name},#{val:04X}{marker}")
        i += 3
        
    elif b == 0xA8:  # TEST AL,#imm8
        val = rom[i+1] if i+1 < len(rom) else 0
        addr = phys(i)
        tag = " BIT0_CHECK" if val == 0x01 else ""
        results.append(f"[{addr:05X}] A8 ${val:02X}     : TEST AL,#${val:02X}{tag}")
        i += 2
    
    elif b in (0xFA,):  # CLI
        addr = phys(i)
        results.append(f"[{addr:05X}] FA          : CLI")
        i += 1
        
    elif b == 0xFB:  # STI
        addr = phys(i)
        results.append(f"[{addr:05X}] FB          : STI")
        i += 1
        
    elif b == 0xC3:  # RET
        addr = phys(i)
        results.append(f"[{addr:05X}] C3          : RET")
        i += 1
        
    elif b == 0xEB or b == 0xE2 or b == 0xE0 or b == 0xE1:
        disp = rom[i+1] if i+1 < len(rom) else 0
        signed_disp = disp - 256 if disp > 127 else disp
        target_addr = phys(i + 2) + signed_disp
        names = {0xEB:"JMP", 0xE2:"LOOP CX", 0xE0:"LOOPNE", 0xE1:"LOOPS"}
        name = names.get(b, "?")
        addr = phys(i)
        results.append(f"[{addr:05X}] {b:02X} {disp:02X}      : {name} -> ${target_addr:X}")
        i += 2
        
    elif 0x70 <= b <= 0x7F:  # Conditional jumps
        jump_names = {
            0x70:"JO", 0x71:"JNO", 0x72:"JB/JC", 0x73:"JAE/JNC",
            0x74:"JE/JZ", 0x75:"JNE/JNZ", 0x76:"JBE", 0x77:"JA",
            0x78:"JS", 0x79:"JNS", 0x7A:"JP", 0x7B:"JNP",
            0x7C:"JL", 0x7D:"JGE", 0x7E:"JLE", 0x7F:"JG"
        }
        name = jump_names.get(b, "??")
        disp = rom[i+1] if i+1 < len(rom) else 0
        signed_disp = disp - 256 if disp > 127 else disp
        target_addr = phys(i + 2) + signed_disp
        addr = phys(i)
        results.append(f"[{addr:05X}] {b:02X} {disp:02X}      : {name} rel8 -> ${target_addr:X}")
        i += 2
    
    else:
        i += 1

# Print all findings
for r in results:
    print(r)

print("\n\n=== POLLING LOOP ANALYSIS ===\n")

# Find sequences of IN AL,dx followed by TEST AL,#$01
in_positions = [r for r in results if "IN AL,dx" in r and "," not in r.split(":")[1]]
test_01_positions = [r for r in results if "TEST AL,#$01 BIT0_CHECK" in r]

if in_positions or test_01_positions:
    print("Found I/O polling patterns:")
    for r in results:
        if any(kw in r for kw in ["IN AL,dx", "TEST AL,#$01 BIT0_CHECK"]):
            print(f"  >>> {r}")
else:
    print("No IN/OUT or TEST AL,$01 found in this range.")
    
print("\n=== MOV DX PATTERNS ===\n")
mov_dx = [r for r in results if "MOV DX," in r]
if mov_dx:
    for r in mov_dx:
        print(f"  >>> {r}")
else:
    print("No explicit MOV DX found — port value set elsewhere (earlier code).")
