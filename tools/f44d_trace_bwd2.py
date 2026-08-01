"""Trace backwards from FF44D to find DX port value origin."""
from pathlib import Path

rom_path = Path("third_party/pcem-roms/genxt/pcxt.rom")
rom = bytearray(rom_path.read_bytes())

ROM_START = 0xFE000
SEG_PREFIXES = {0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65}
ALL_PREFIXES = SEG_PREFIXES | {0xF0, 0xF2, 0xF3}

def read_byte(a):
    return rom[a] if 0 <= a < len(rom) else None

def read_word(a):
    b0 = read_byte(a); b1 = read_byte(a+1)
    return (b0 | (b1 << 8)) if b0 is not None and b1 is not None else None

def disassemble_rom(start_offset, end_offset, max_instr=None):
    """Disassemble ROM bytes from start_offset DOWN to end_offset."""
    results = []
    pos = start_offset
    
    while pos >= end_offset and pos < len(rom) and pos >= 0 and (max_instr is None or len(results) < max_instr):
        prefix_str = ""
        original_pos = pos
        
        # Collect prefixes
        while pos > 0 and rom[pos-1] in ALL_PREFIXES:
            p = rom[pos-1]
            if p == 0xF0: prefix_str += "LOCK "
            elif p == 0xF2: prefix_str += "REPNE "
            elif p == 0xF3: prefix_str += "REPE "
            elif p in SEG_PREFIXES:
                seg_map = {0x2E:"CS:", 0x36:"SS:", 0x3E:"DS:", 0x26:"ES:", 0x64:"FS:", 0x65:"GS:"}
                prefix_str += seg_map.get(p, "??:") + " "
            pos -= 1
        
        # If we consumed all bytes as prefixes with no opcode left, stop
        if pos < end_offset:
            break
            
        opcode = rom[pos]
        instr_phys_start = pos + ROM_START
        detail = ""
        mnemonic = ""
        nbytes = 1
        
        # Single-byte opcodes with optional operand
        simple = {
            0xC3: ("RET", ""), 0xFA: ("CLI", ""),
            0xEC: ("IN AL,dx", ""), 0xED: ("INSW", ""),
            0xEE: ("OUT dx,AL", ""), 0xE7: ("OUT imm8,AX", ""),
            0xA8: ("TEST AL,#$", True), 0xAA: ("STOSB", ""),
            0xAB: ("STOSW", ""), 0x90: ("NOP", ""),
            0x55: ("PUSH BP", ""),
        }
        
        jump_ops = {
            0xEB: "JMP rel8", 0xE9: "JMP rel16",
            0xE2: "LOOPCX rel8", 0xE0: "LOOPNE rel8", 0xE1: "LOOPS rel8",
            0x75: "JNE rel8", 0x74: "JE rel8", 0x7E: "JLE rel8",
            0x7C: "JL rel8", 0x7F: "JG rel8", 0x78: "JS rel8",
            0x72: "JB/JC rel8", 0x73: "JAE/JNC rel8",
            0x71: "JNB rel8", 0x70: "JA rel8",
            0x7D: "JGE rel8", 0x7B: "JP rel8", 0x7A: "JNP rel8",
            0x79: "JNS rel8", 0x77: "JA rel8", 0x76: "JBE rel8",
        }
        
        if opcode in simple:
            mnemonic = f"{prefix_str}{simple[opcode][0]}"
            needs_imm = simple[opcode][1]
            
            if needs_imm and pos+1 < len(rom):
                val = rom[pos+1]
                detail = f"${val:02X}"
                nbytes = 2
                
        elif opcode in jump_ops:
            mnem_name = jump_ops[opcode]
            mnemonic = f"{prefix_str}{mnem_name.split()[0]}"
            
            if pos + 1 >= len(rom):
                break
                
            rel_byte = rom[pos+1]
            rel_signed = rel_byte - 256 if rel_byte > 127 else rel_byte
            
            # Calculate target address (relative to next instruction)
            next_instr_phys = instr_phys_start + 2  # opcode + rel byte
            target_phys = next_instr_phys + rel_signed
            
            if rel_signed >= 0:
                detail = f"+${target_phys:X}"
            else:
                detail = f"-${abs(target_phys):X} ({'back' if target_phys < instr_phys_start else 'fwd'})"
                
            nbytes = 2
            
        elif 0xB0 <= opcode <= 0xBF:
            reg_names_8 = ['AL','CL','DL','BL','AH','CH','DH','BH']
            reg_names_16 = ['AX','CX','DX','SP','BP','SI','DI','DI']  # BF=DI, BE=CX etc.
            
            low = opcode & 7
            high = opcode >> 4
            
            if high == 0xB:  # MOV r8,#imm8
                mnemonic = f"{prefix_str}MOV {reg_names_8[low]}"
                imm = read_byte(pos+1)
                if imm is not None:
                    detail = f"#${imm:02X}"
                    nbytes = 2
                    
            elif high == 0xC or high == 0xD or high == 0xE:  # MOV r16,#imm16
                mov_regs = {0:"BX", 1:"CX", 2:"DX", 3:"SP", 5:"BP", 6:"SI", 7:"DI"}
                mnemonic = f"{prefix_str}MOV {mov_regs.get(low,'?')}"
                imm = read_word(pos+1)
                if imm is not None:
                    detail = f"#${imm:04X}"
                    nbytes = 3
                    
        elif opcode in (0x80, 0x81, 0xF6, 0xF7):
            modrm_addr = pos + 1
            if modrm_addr >= len(rom):
                mnemonic = f"{opcode:02X}_no_modrm"
                break
                
            modrm = rom[modrm_addr]
            mod = (modrm >> 6) & 3
            rg = (modrm >> 3) & 7
            rm = modrm & 7
            
            funcs8 = ['ADD','OR','ADC','SBB','AND','SUB','XOR','CMP']
            funcs16_test = ['TEST','TEST','NOT','NEG','MUL','IMUL','DIV','IDIV']
            
            size8 = "r/m8"; size16 = "r/m16"
            
            if opcode in (0x80, 0xF6):
                func = funcs8[rg] if rg < 8 else "?"
                mnemonic = f"{prefix_str}{func} {size8}"
                has_imm = True
            else:
                func = funcs16_test[rg] if rg < 8 else "?"
                mnemonic = f"{prefix_str}{func} {size16}"
                has_imm = False
                
            nbytes = 2  # opcode + modrm minimum
            
            # Decode addressing mode
            addr_mode = ""
            base_regs = ['BX+SI','BX+DI','BP+SI','BP+DI','SI','DI','BP','BX']
            
            if mod == 0 and rm == 6:
                disp = read_word(modrm_addr + 1)
                if disp is not None:
                    addr_mode = f"[{disp:04X}]"
                    nbytes += 2
            elif mod == 1:
                d = read_byte(modrm_addr + 1)
                if d is not None:
                    addr_mode = f"[{base_regs[rm]}+${d:02X}]"
                    nbytes += 1
            elif mod == 2:
                d = read_word(modrm_addr + 1)
                if d is not None:
                    addr_mode = f"[{base_regs[rm]}+${d:04X}]"
                    nbytes += 2
                    
            if has_imm and pos + nbytes < len(rom):
                imm_val = rom[pos+nbytes]
                detail = f"#${imm_val:02X} {addr_mode}".strip()
                nbytes += 1
            elif addr_mode:
                detail = addr_mode
                
        elif opcode in (0x8A, 0x8B, 0x8C, 0x8D, 0x8E):
            names = {0x8A:"MOV r8/r8", 0x8B:"MOV r16/r16", 
                     0x8C:"MOV r16/sreg", 0x8D:"LEA", 0x8E:"MOV sreg/r16"}
            mnemonic = f"{prefix_str}{names.get(opcode,'?')}"
            
            modrm_addr = pos + 1
            if modrm_addr >= len(rom):
                break
                
            modrm = rom[modrm_addr]
            mod = (modrm >> 6) & 3; rm = modrm & 7
            base_regs = ['BX+SI','BX+DI','BP+SI','BP+DI','SI','DI','BP','BX']
            
            if mod == 0 and rm == 6:
                disp = read_word(modrm_addr + 1)
                if disp is not None:
                    detail = f"[{disp:04X}]"; nbytes += 2
            elif mod == 1:
                d = read_byte(modrm_addr + 1)
                if d is not None:
                    detail = f"[{base_regs[rm]}+${d:02X}]"; nbytes += 1
            elif mod == 2:
                d = read_word(modrm_addr + 1)
                if d is not None:
                    detail = f"[{base_regs[rm]}+${d:04X}]"; nbytes += 2
                    
        else:
            mnemonic = f"{opcode:02X}_unknown"
        
        phys_addr = instr_phys_start
        full_text = mnemonic
        if detail:
            full_text += " " + detail
            
        results.append((phys_addr, full_text, nbytes))
        pos -= nbytes
        
    return results

# Disassemble backwards from FF450 to ~FF3C0 (~160 bytes of context)
print("=" * 80)
print("BACKWARD TRACE FROM PHYSICAL FF44D/FF450")
print("=" * 80)
print("\nGoal: Find where DX register gets loaded with I/O port value\n")

start_off = 0x1450 - ROM_START  # Physical FF450 -> ROM offset 0x1450
end_off = start_off - 200       # Go back ~200 bytes

instructions = disassemble_rom(start_off, end_off, max_instr=60)

print(f"{'Physical':>10} | {'Instruction'}")
print("-" * 80)

for addr, text, nbytes in reversed(instructions):
    marker = ""
    
    # Mark key instructions near stall point
    if addr == 0xFF450:
        marker = " <-- IN AL,dx (STALL LOOP ENTRY)"
    elif addr == 0xFF44F:
        marker = " <-- CLI"
    elif addr == 0xFF44D:
        marker = " <-- JNE @retry"
    elif "MOV DX,#$" in text or "MOV CX,#$" in text or "MOV BX,#$" in text:
        marker = " <<< MOV reg,#imm"
    elif "OUT dx" in text.lower():
        marker = " <<< OUT dx,AL"
        
    print(f" {addr:05X}     | {text:<45s}{marker}")

# Now search specifically for patterns that load DX with a port address
print("\n" + "=" * 80)
print("SEARCHING FOR PORT ADDRESS SETUP PATTERNS")  
print("=" * 80)

port_patterns = ["DX", "CX", "BX"]
for pat in port_patterns:
    matches = [(a,t,n) for a,t,n in reversed(instructions) if f"MOV {pat}" in t]
    if matches:
        print(f"\nMOV {pat},#imm found:")
        for addr, text, _ in matches[:5]:
            print(f"  {addr:05X}: {text}")

# Also look for any OUT sequences before the stall
print("\n" + "=" * 80)
print("ALL OUTPUT SEQUENCES BEFORE STALL")
print("=" * 80)

out_seqs = [(a,t,n) for a,t,n in reversed(instructions) 
           if 'OUT' in t and 'STOS' not in t]
if out_seqs:
    for addr, text, _ in out_seqs:
        print(f"  {addr:05X}: {text}")
else:
    print("  No explicit OUT instructions found in trace window.")
    print("  The I/O port value must come from register state set earlier.")
