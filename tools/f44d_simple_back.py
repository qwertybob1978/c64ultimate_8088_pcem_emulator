"""Simple backward trace from FF44D."""
from pathlib import Path

rom_path = Path("third_party/roms/genxt/pcxt.rom")
rom = bytearray(rom_path.read_bytes())

ROM_OFFSET = lambda phys: phys - 0xFE000

# Disassemble backwards from physical FF450 back ~128 bytes
START_PHYS = 0xFF450
END_PHYS = START_PHYS - 128

def decode_one(addr):
    """Decode one x86 instruction at ROM offset addr. Returns (nbytes, mnem, detail)."""
    if addr < 0 or addr >= len(rom):
        return (1, "?", "")
    
    b0 = rom[addr]
    
    # Prefixes
    seg_map = {0x2E:"CS:", 0x36:"SS:", 0x3E:"DS:", 0x26:"ES:"}
    prefix = ""
    while addr > 0 and rom[addr-1] in ({0xF0,0xF2,0xF3}|set(seg_map.keys())):
        p = rom[addr-1]
        if p == 0xF0: prefix += "LOCK "
        elif p == 0xF2: prefix += "REPNE "  
        elif p == 0xF3: prefix += "REPE "
        else: prefix += seg_map.get(p, f"{p:02X}: ")
        addr -= 1
    
    opcode = rom[addr]
    
    # Single byte ops
    if opcode == 0xC3: return (1, "RET", "")
    if opcode == 0xFA: return (1, "CLI", "")
    if opcode == 0xEC: return (1, "IN AL,dx", "")
    if opcode == 0xEE: return (1, "OUT dx,AL", "")
    if opcode == 0xAA: return (1, "STOSB", "")
    if opcode == 0xAB: return (1, "STOSW", "")
    if opcode == 0xA8: 
        v = rom[addr+1] if addr+1 < len(rom) else 0
        return (2, "TEST AL,#$", f"${v:02X}")
    if opcode == 0x90: return (1, "NOP", "")
    if opcode == 0x55: return (1, "PUSH BP", "")
    
    # Jumps with rel8
    jump_ops = {0xEB:"JMP", 0xE2:"LOOPCX", 0xE0:"LOOPNE", 0xE1:"LOOPS",
                0x75:"JNE", 0x74:"JE", 0x7E:"JLE", 0x7C:"JL", 0x7F:"JG",
                0x78:"JS", 0x72:"JB/JC", 0x73:"JAE/JNC", 0x71:"JNB",
                0x70:"JA", 0x7D:"JGE", 0x7B:"JP", 0x7A:"JNP", 0x79:"JNS"}
    
    if opcode in jump_ops and addr + 1 < len(rom):
        mnem = jump_ops[opcode]
        rel = rom[addr+1]
        signed_rel = rel - 256 if rel > 127 else rel
        target = (addr + 2) + signed_rel
        detail = f"+${target:X}"
        return (2, f"{prefix}{mnem} rel8", detail)
    
    # MOV reg8,#imm8 (B0-B7)
    if 0xB0 <= opcode <= 0xB7:
        regs = ['AL','CL','DL','BL','AH','CH','DH','BH']
        idx = opcode & 7
        imm = rom[addr+1] if addr+1 < len(rom) else 0
        return (2, f"MOV {regs[idx]},#$", f"${imm:02X}")
    
    # MOV reg16,#imm16 (B8-BF)  
    if 0xB8 <= opcode <= 0xBF:
        regs = ['BX','CX','DX','SP','BP','SI','DI','??']
        idx = opcode & 7
        lo = rom[addr+1] if addr+1 < len(rom) else 0
        hi = rom[addr+2] if addr+2 < len(rom) else 0
        imm = lo | (hi << 8)
        return (3, f"MOV {regs[idx]},#$", f"${imm:04X}")
    
    # OUT DX,AL variants with immediate port
    if opcode == 0xE6 and addr + 1 < len(rom):
        port = rom[addr+1]
        return (2, "OUT dx,#$", f"$port={port:02X}")
    
    # Group opcodes (80, F6, F7) with MODRM
    if opcode in (0x80, 0xF6, 0xF7) and addr + 1 < len(rom):
        modrm = rom[addr+1]
        mod = (modrm >> 6) & 3
        rg = (modrm >> 3) & 7
        rm = modrm & 7
        
        funcs8 = ['ADD','OR','ADC','SBB','AND','SUB','XOR','CMP']
        funcs16 = ['TEST','TEST','NOT','NEG','MUL','IMUL','DIV','IDIV']
        
        size_str = 'r/m8' if opcode != 0xF7 else 'r/m16'
        func_name = funcs8[rg] if opcode in (0x80, 0xF6) else funcs16[rg]
        
        detail_parts = []
        nbytes = 2
        
        base_regs = ['BX+SI','BX+DI','BP+SI','BP+DI','SI','DI','BP','BX']
        
        if mod == 0 and rm == 6:
            d = rom[addr+2] | (rom[addr+3]<<8) if addr+3 < len(rom) else 0
            detail_parts.append(f"[{d:04X}]")
            nbytes += 2
        elif mod == 1:
            d = rom[addr+2] if addr+2 < len(rom) else 0
            detail_parts.append(f"[{base_regs[rm]}+${d:02X}]")
            nbytes += 1
        elif mod == 2:
            d = rom[addr+2] | (rom[addr+3]<<8) if addr+3 < len(rom) else 0
            detail_parts.append(f"[{base_regs[rm]}+${d:04X}]")
            nbytes += 2
            
        if opcode in (0x80, 0xF6) and addr+nbytes < len(rom):
            imm_val = rom[addr+nbytes]
            detail_parts.insert(0, f"#{imm_val:02X}")
            nbytes += 1
            
        return (nbytes, f"{func_name} {size_str}", " ".join(detail_parts))
    
    # MOV r/m,r8 / MOV r8,r/m (8A) etc.
    if opcode in (0x8A, 0x8B, 0x8C, 0x8D, 0x8E) and addr + 1 < len(rom):
        names = {0x8A:"MOV r8/r8", 0x8B:"MOV r16/r16", 
                 0x8C:"MOV sreg/r16", 0x8D:"LEA", 0x8E:"MOV r16/sreg"}
        mnem = names.get(opcode, "?")
        
        modrm = rom[addr+1]
        mod = (modrm >> 6) & 3; rm = modrm & 7
        base_regs = ['BX+SI','BX+DI','BP+SI','BP+DI','SI','DI','BP','BX']
        
        detail_parts = []
        nbytes = 2
        
        if mod == 0 and rm == 6:
            d = rom[addr+2] | (rom[addr+3]<<8) if addr+3 < len(rom) else 0
            detail_parts.append(f"[{d:04X}]"); nbytes += 2
        elif mod == 1:
            d = rom[addr+2] if addr+2 < len(rom) else 0
            detail_parts.append(f"[{base_regs[rm]}+${d:02X}]"); nbytes += 1
        elif mod == 2:
            d = rom[addr+2] | (rom[addr+3]<<8) if addr+3 < len(rom) else 0
            detail_parts.append(f"[{base_regs[rm]}+${d:04X}]"); nbytes += 2
            
        return (nbytes, mnem, " ".join(detail_parts))
    
    # Unknown - just show raw bytes
    return (1, f"{opcode:02X}_UNK", "")

# Disassemble backwards from START_PHYS to END_PHYS
print("=" * 80)
print("BACKWARD TRACE FROM FF450 (~128 bytes)")  
print("=" * 80)
print()

start_off = ROM_OFFSET(START_PHYS)
end_off = ROM_OFFSET(END_PHYS)

pos = start_off
instructions = []

while pos >= end_off and pos >= 0 and pos < len(rom):
    nb, mnem, det = decode_one(pos)
    phys = pos + 0xFE000
    
    marker = ""
    if phys == 0xFF450: marker = " <-- IN AL,dx (STALL)"
    elif phys == 0xFF44F: marker = " <-- CLI"
    elif phys == 0xFF44D: marker = " <-- JNE @retry"
    elif "MOV DX,#$" in mnem or ("DX" in mnem and "#$" in det): 
        marker = " <<< MOV DX port setup!"
    elif "OUT dx" in mnem.lower():
        marker = " <<< OUT instruction"
    elif "MOV CX,#$" in mnem or "CX" in mnem and "#$" in det:
        marker = " <<< MOV CX"
        
    line = f"  {phys:05X} OP={rom[pos]:02X} {mnem}"
    if det:
        line += f" {det}"
    print(line + marker)
    
    instructions.append((phys, mnem, det, nb))
    pos -= nb

# Summary of interesting patterns
print("\n" + "=" * 80)
print("SUMMARY OF KEY PATTERNS")
print("=" * 80)

mov_dx = [i for i in instructions if "MOV DX" in i[1]]
out_instrs = [i for i in instructions if "OUT" in i[1].upper()]
in_instrs = [i for i in instructions if "IN " in i[1]]

if mov_dx:
    print(f"\nMOV DX found ({len(mov_dx)}):")
    for addr, mnem, det, _ in mov_dx:
        print(f"  {addr:05X}: {mnem} {det}")
else:
    print("\nNo explicit 'MOV DX' found. Port value may come from:")
    print("  - Register preserved across function calls")
    print("  - Stack pop operation")
    print("  - Earlier code outside our trace window")

if out_instrs:
    print(f"\nOUT instructions ({len(out_instrs)}):")
    for addr, mnem, det, _ in out_instrs:
        print(f"  {addr:05X}: {mnem} {det}")
