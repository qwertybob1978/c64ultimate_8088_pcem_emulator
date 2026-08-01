"""Trace backwards from FF44D to find where DX port value originates."""
from pathlib import Path

rom_path = Path("third_party/pcem-roms/genxt/pcxt.rom")
rom = bytearray(rom_path.read_bytes())

def read_byte(addr):
    return rom[addr] if addr < len(rom) else None

def read_word(addr):
    b0 = read_byte(addr)
    b1 = read_byte(addr+1)
    if b0 is None or b1 is None:
        return None
    return b0 | (b1 << 8)

# Full x86 decoder with proper prefix handling
SEGMENT_PREFIXES = {0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65}
LOCK_PREFIX = 0xF0
REPNE_PREFIX = 0xF2
REPE_PREFIX = 0xF3

PREFIX_BYTES = SEGMENT_PREFIXES | {LOCK_PREFIX, REPNE_PREFIX, REPE_PREFIX}

ROM_START_PHYS = 0xFE000  # GenXT BIOS ROM starts here
ROM_END_PHYS = 0xFFFFF     # End of 128KB ROM at FFFFF

def phys_to_offset(phys):
    return phys - ROM_START_PHYS

def disassemble_range(start_phys, end_phys, max_instructions=None):
    """Disassemble from start_phys down to end_phys (backwards)."""
    instructions = []
    
    # Convert physical addresses to ROM offsets
    pos = phys_to_offset(start_phys)
    target_end = phys_to_offset(end_phys)
    
    while pos >= target_end and (max_instructions is None or len(instructions) < max_instructions):
        bytes_consumed = 0
        prefix_str = ""
        
        # Handle prefixes
        while pos > 0 and rom[pos-1] in PREFIX_BYTES:
            p = rom[pos-1]
            if p == LOCK_PREFIX:
                prefix_str += "LOCK "
            elif p == REPNE_PREFIX:
                prefix_str += "REPNE "
            elif p == REPE_PREFIX:
                prefix_str += "REPE "
            elif p in SEGMENT_PREFIXES:
                seg_map = {0x2E:"CS:", 0x36:"SS:", 0x3E:"DS:", 0x26:"ES:", 0x64:"FS:", 0x65:"GS:"}
                prefix_str += seg_map.get(p, "??:") + " "
            pos -= 1
        
        # Safety check for bounds
        if pos < target_end or pos >= len(rom):
            break
            
        opcode = rom[pos]
        instr_start = pos
        detail = ""
        mnemonic = ""
        
        # Single-byte opcodes
        single_ops = {
            0xC3: ("RET", ""),
            0xFA: ("CLI", ""),
            0xEC: ("IN AL,dx", ""),
            0xED: ("INSW", ""),
            0xEE: ("OUT dx,AL", ""),
            0xE7: ("OUT imm8,AX", ""),
            0xEB: ("JMP rel8", "+$"),
            0xE9: ("JMP rel16", "+$"),
            0xE2: ("LOOPCX rel8", "+$"),
            0xE0: ("LOOPNE rel8", "+$"),
            0xE1: ("LOOPS rel8", "+$"),
            
            0x75: ("JNE rel8", "+$"),
            0x74: ("JE rel8", "+$"),
            0x7E: ("JLE rel8", "+$"),
            0x7C: ("JL rel8", "+$"),
            0x7F: ("JG rel8", "+$"),
            0x78: ("JS rel8", "+$"),
            0x72: ("JB rel8", "+$"),
            0x73: ("JAE rel8", "+$"),
            0x71: ("JNB rel8", "+$"),
            0x70: ("JA rel8", "+$"),
            0x7D: ("JGE rel8", "+$"),
            0x7B: ("JP rel8", "+$"),
            0x7A: ("JNP rel8", "+$"),
            0x79: ("JNS rel8", "+$"),
            0x77: ("JA rel8", "+$"),
            0x76: ("JBE rel8", "+$"),
            0x72: ("JC rel8", "+$"),
            0x73: ("JNC rel8", "+$"),
            
            0xA8: ("TEST AL,#$", None),
            0xAA: ("STOSB", ""),
            0xAB: ("STOSW", ""),
            0x55: ("PUSH BP", ""),
            0x90: ("NOP", ""),
        }
        
        if opcode in single_ops:
            mnemonic, prefix = single_ops[opcode]
            detail = ""
            
            if prefix is not None and pos + 1 < len(rom):
                rel_byte = rom[pos+1]
                if rel_byte > 127:
                    rel_signed = rel_byte - 256
                else:
                    rel_signed = rel_byte
                
                target = (pos + 2) + rel_signed
                if rel_signed >= 0:
                    detail = f"+${target:X}"
                else:
                    detail = f"-${abs(target):X}"
                
                bytes_consumed = 2
            else:
                bytes_consumed = 1
        
        elif opcode == 0xB4 or (0xB0 <= opcode <= 0xB7):
            reg_names = ['AL', 'CL', 'DL', 'BL', 'AH', 'CH', 'DH', 'BH']
            idx = opcode - 0xB0
            mnemonic = f"MOV {reg_names[idx]}"
            imm_val = read_byte(pos+1)
            if imm_val is not None:
                detail = f"#${imm_val:02X}"
                bytes_consumed = 2
            else:
                bytes_consumed = 1
                
        elif opcode == 0xBE or (0xBA & 0xE0 == 0xB8):
            # MOV reg16,#imm16 for BX,CX,DX,BP,SI,DI,DS,SS
            mov_regs = {0:"BX", 1:"CX", 2:"DX", 3:"SP", 5:"BP", 6:"SI", 7:"DI"}
            low_bits = opcode & 7
            if low_bits in mov_regs:
                mnemonic = f"MOV {mov_regs[low_bits]}"
                imm_val = read_word(pos+1)
                if imm_val is not None:
                    detail = f"#${imm_val:04X}"
                    bytes_consumed = 3
                else:
                    bytes_consumed = 1
            
        elif opcode in (0x80, 0x81, 0xF6, 0xF7):
            # Group opcodes with MODRM
            modrm_addr = pos + 1
            if modrm_addr < len(rom):
                modrm = rom[modrm_addr]
                mod = (modrm >> 6) & 3
                reg_field = (modrm >> 3) & 7
                rm = modrm & 7
                
                group_funcs_8 = ['ADD','OR','ADC','SBB','AND','SUB','XOR','CMP']
                group_funcs_16 = ['TEST','TEST','NOT','NEG','MUL','IMUL','DIV','IDIV']
                
                size_str = "r/m8" if opcode in (0x80, 0xF6) else "r/m16"
                
                if opcode in (0x80, 0x81):
                    func_name = group_funcs_8[reg_field] if reg_field < 8 else "?"
                else:
                    func_name = group_funcs_16[reg_field] if reg_field < 8 else "?"
                    
                mnemonic = f"{func_name} {size_str}"
                bytes_consumed = 2  # minimum: opcode + modrm
                
                # Decode displacement
                disp_str = ""
                if mod == 0 and rm == 6:
                    disp = read_word(modrm_addr + 1)
                    if disp is not None:
                        disp_str = f"[{disp:04X}]"
                        bytes_consumed += 2
                elif mod == 1:
                    disp = read_byte(modrm_addr + 1)
                    if disp is not None:
                        disp_str = f"[${disp:02X}]"
                        bytes_consumed += 1
                elif mod == 2:
                    disp = read_word(modrm_addr + 1)
                    if disp is not None:
                        disp_str = f"[${disp:04X}]"
                        bytes_consumed += 2
                        
                # Immediate operand?
                ib_needed = opcode in (0x80, 0xF6) or (opcode == 0x81 and False)
                iw_needed = opcode == 0x81
                
                if ib_needed and pos + bytes_consumed < len(rom):
                    imm_val = rom[pos + bytes_consumed]
                    detail = f"#${imm_val:02X}{disp_str}"
                    bytes_consumed += 1
                elif iw_needed and pos + bytes_consumed + 1 < len(rom):
                    imm_val = read_word(pos + bytes_consumed)
                    if imm_val is not None:
                        detail = f"#${imm_val:04X}{disp_str}"
                        bytes_consumed += 2
                    
        elif opcode in (0x8A, 0x8B, 0x8C, 0x8D, 0x8E):
            # MOV variants with MODRM  
            mov_names = {0x8A:"MOV r8/r8", 0x8B:"MOV r16/r16", 
                       0x8C:"MOV r16/sreg", 0x8D:"LEA", 0x8E:"MOV sreg/r16"}
            
            modrm_addr = pos + 1
            if modrm_addr < len(rom):
                modrm = rom[modrm_addr]
                mod = (modrm >> 6) & 3
                reg_field = (modrm >> 3) & 7
                rm = modrm & 7
                
                mnemonic = mov_names.get(opcode, "?")
                bytes_consumed = 2
                
                base_regs_16 = ['BX+SI','BX+DI','BP+SI','BP+DI','SI','DI','BP','BX']
                
                if mod == 0 and rm == 6:
                    disp = read_word(modrm_addr + 1)
                    if disp is not None:
                        detail = f"[{disp:04X}]"
                        bytes_consumed += 2
                elif mod == 1:
                    disp = read_byte(modrm_addr + 1)
                    if disp is not None:
                        detail = f"[{base_regs_16[rm]}+${disp:02X}]"
                        bytes_consumed += 1
                elif mod == 2:
                    disp = read_word(modrm_addr + 1)
                    if disp is not None:
                        detail = f"[{base_regs_16[rm]}+${disp:04X}]"
                        bytes_consumed += 2
                        
        else:
            mnemonic = f"{opcode:02X}_unknown"
            bytes_consumed = 1
        
        phys_addr = instr_start + 0xFE000
        full_text = prefix_str + mnemonic
        if detail:
            full_text += " " + detail
            
        instructions.append((phys_addr, full_text, bytes_consumed))
        
        pos -= bytes_consumed
    
    return instructions

# Disassemble backwards from just before FF44D to find DX setup
print("=" * 80)
print("BACKWARD TRACE FROM PHYSICAL FF44D")
print("=" * 80)
print("\nSearching for where DX register gets loaded with I/O port value...")
print("(Looking for MOV DX,#imm or similar patterns)\n")

instructions = disassemble_range(0xFF450, 0xFF3C0, max_instructions=80)

for addr, text, nbytes in reversed(instructions):
    marker = ""
    if addr == 0xFF44F:
        marker = " <-- CLI at F44F"
    elif addr == 0xFF450:
        marker = " <-- IN AL,dx at F450 (STALL LOOP)"
    
    print(f"  {addr:05X}: {text:<35s} ({nbytes} byte){marker}")

# Also look for OUT dx,AL sequences that might set up the port
print("\n" + "=" * 80)  
print("SEARCHING FOR OUT dx,AL SEQUENCES (port setup)")
print("=" * 80)

out_sequences = []
for i, (addr, text, _) in enumerate(reversed(instructions)):
    if "OUT dx" in text.lower():
        # Show context around this OUT
        start_idx = max(0, len(instructions)-i-5)
        end_idx = min(len(instructions), len(instructions)-i+2)
        
        print(f"\n--- OUT sequence near {addr:05X} ---")
        for j in range(start_idx, end_idx):
            a, t, n = instructions[j]
            marker = " <<< THIS IS THE OUT" if a == addr else ""
            print(f"  {a:05X}: {t}{marker}")
