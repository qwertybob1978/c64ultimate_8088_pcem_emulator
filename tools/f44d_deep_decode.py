"""Deep decode of x86 code around FF44D with full MODRM/displacement handling."""
from pathlib import Path

rom_path = Path("third_party/pcem-roms/genxt/pcxt.rom")
rom = bytearray(rom_path.read_bytes())
offset = 0x144D  # Physical FF44D - FE000

def read_byte(addr):
    if addr >= len(rom):
        return None
    return rom[addr]

def read_word(addr):
    b0 = read_byte(addr)
    b1 = read_byte(addr + 1)
    if b0 is None or b1 is None:
        return None
    return b0 | (b1 << 8)

# Full x86 opcode decoder with MODRM support
def decode_full(addr):
    """Decode one complete x86 instruction starting at addr.
    Returns (bytes_consumed, mnemonic, detail_str).
    """
    if addr >= len(rom):
        return None
    
    b0 = rom[addr]
    
    # Single-byte opcodes we care about near F44D
    simple_ops = {
        0xEB: ("JMP", "rel8"),
        0xE9: ("JMP", "rel16"),
        0xC3: ("RET", ""),
        0xFA: ("CLI", ""),
        0xEC: ("IN AL,dx", ""),
        0xED: ("INSW", ""),
        0xEE: ("OUT dx,AL", ""),
        0xE7: ("OUT imm8,AX", ""),
        0x75: ("JNE", "rel8"),
        0x74: ("JE", "rel8"),
        0x7E: ("JLE", "rel8"),
        0x7C: ("JL", "rel8"),
        0x7F: ("JG", "rel8"),
        0x78: ("JS", "rel8"),
        0x72: ("JB", "rel8"),
        0x73: ("JAE", "rel8"),
        0x71: ("JNB", "rel8"),
        0x70: ("JA", "rel8"),
        0xA8: ("TEST AL", "imm8"),
        0xA0: ("MOV AL", "moffs"),
        0xA1: ("MOV ax", "moffs"),
        0xAA: ("STOSB", ""),
        0xAB: ("STOSW", ""),
        0x55: ("PUSH BP", ""),
        0xF0: ("LOCK prefix", ""),
        0xF2: ("REPNE/REPE prefix", ""),
        0xF3: ("REP prefix", ""),
        0x2E: ("CS segment override", ""),
        0x36: ("SS segment override", ""),
        0x3E: ("DS segment override", ""),
        0x26: ("ES segment override", ""),
        0x64: ("FS segment override", ""),
        0x65: ("GS segment override", ""),
    }
    
    if b0 in (0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7):
        reg_names = ['AL', 'CL', 'DL', 'BL', 'AH', 'CH', 'DH', 'BH']
        idx = b0 - 0xB0
        return (2, f"MOV {reg_names[idx]}", f"#${rom[addr+1]:02X}")
    
    info = simple_ops.get(b0)
    if not info:
        # Could be a group opcode or needs MODRM parsing
        pass
    
    mnem, detail = info if info else (f"{b0:02X}*", "")
    
    total_bytes = 1
    
    if detail == "rel8":
        rel = rom[addr + 1]
        if rel > 127:
            rel -= 256
        target = addr + 2 + rel
        return (2, mnem, f"+${target:X}" if target >= 0 else f"-${abs(target):X}")
    
    elif detail == "#$XX" or detail.startswith("#"):
        return (2, mnem, detail)
        
    elif detail == "imm8":
        val = read_byte(addr + 1)
        return (2, mnem, f"${val:02X}" if val is not None else "?")
        
    elif detail == "moffs":
        lo = read_word(addr + 1)
        hi = read_word(addr + 3)
        seg_prefix = ""
        if addr > 0 and rom[addr-1] in (0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65):
            seg_map = {0x2E:"CS:", 0x36:"SS:", 0x3E:"DS:", 0x26:"ES:", 0x64:"FS:", 0x65:"GS:"}
            seg_prefix = seg_map.get(rom[addr-1], "")
        offset_val = lo | (hi << 8) if lo is not None else 0
        return (3, mnem, f"[{seg_prefix}{offset_val:04X}]")
        
    elif detail == "rel16":
        disp = read_word(addr + 1)
        if disp is None:
            return (3, mnem, "?")
        target = addr + 3 + disp
        return (3, mnem, f"+${target:X}")
    
    elif b0 in (0x80, 0x81, 0x82, 0x83, 0xC0, 0xC1, 0xD0, 0xD1, 0xD2, 0xD3, 
                0xF6, 0xF7):
        # Group opcodes with MODRM byte
        modrm_addr = addr + 1
        if modrm_addr >= len(rom):
            return (1, mnem, "??incomplete??" )
        modrm = rom[modrm_addr]
        mod = (modrm >> 6) & 3
        reg_or_opcode = (modrm >> 3) & 7
        rm = modrm & 7
        
        # Determine register name for the group function
        group_funcs_8bit = ['ADD', 'OR', 'ADC', 'SBB', 'AND', 'SUB', 'XOR', 'CMP']
        group_funcs_16bit = ['ADD', 'OR', 'ADC', 'SBB', 'AND', 'SUB', 'XOR', 'TEST']
        
        func_idx = reg_or_opcode
        if b0 in (0x80, 0x82):
            size_byte = '8'
            func_name = group_funcs_8bit[func_idx] if func_idx < 8 else "?"
        elif b0 in (0x81, 0x83, 0xC0, 0xC1, 0xD0, 0xD1, 0xD2, 0xD3):
            size_byte = '16'  
            func_name = group_funcs_16bit[func_idx] if func_idx < 8 else "?"
        elif b0 in (0xF6, 0xF7):
            func_names_f = ['TEST', 'MOV (cast)', 'NOT', 'NEG', 'MUL', 'IMUL', 'DIV', 'IDIV']
            func_name = func_names_f[func_idx] if func_idx < 8 else "?"
            size_byte = '8' if b0 == 0xF6 else '16'
        else:
            size_byte = '?'
            func_name = "?"
            
        total_bytes = 2  # opcode + modrm minimum
        
        # Decode displacement and immediate based on MODRM
        disp_str = ""
        imm_val = None
        
        if mod == 0:
            if rm == 6:
                # Disp16 only
                disp = read_word(modrm_addr + 1)
                if disp is not None:
                    disp_str = f"[{disp:04X}]"
                    total_bytes += 2
            else:
                # [BX+SI], [BX+DI], [BP+SI], [BP+DI], [SI], [DP]
                base_regs = {0:"BX+SI", 1:"BX+DI", 2:"BP+SI", 3:"BP+DI", 
                           4:"SI", 5:"DI", 6:"BP", 7:"BX"}
                disp_str = f"[{base_regs.get(rm, '?')}]"
                
        elif mod == 1:
            # 8-bit displacement
            disp = read_byte(modrm_addr + 1)
            if disp is not None:
                disp_str = f"[{disp:02X}]"
                total_bytes += 1
                
        elif mod == 2:
            # 16-bit displacement
            disp = read_word(modrm_addr + 1)
            if disp is not None:
                disp_str = f"[{disp:04X}]"
                total_bytes += 2
        
        # Check for immediate operand after displacement
        ib_needed = False
        iw_needed = False
        
        if b0 == 0x81 or b0 == 0xC1 or b0 == 0xE9:
            iw_needed = True
        elif b0 in (0x80, 0x82, 0x83, 0xC0, 0xD0, 0xF6):
            ib_needed = True  
        elif b0 in (0x81, 0xC1):
            iw_needed = True
            
        if ib_needed and addr + total_bytes + 1 <= len(rom):
            imm_val = rom[addr + total_bytes]
            return (total_bytes + 1, f"{func_name} r/m{size_byte}", f"#{imm_val:02X}{disp_str}")
        elif iw_needed and addr + total_bytes + 2 <= len(rom):
            imm_val = read_word(addr + total_bytes)
            return (total_bytes + 2, f"{func_name} r/m{size_byte}", f"#{imm_val:04X}{disp_str}")
            
        return (total_bytes, f"{func_name} r/m{size_byte}", disp_str)
    
    elif b0 in (0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F):
        # MOV variants with MODRM
        mov_funcs = {0x8A: "MOV r8/r8", 0x8B: "MOV r16/r16", 
                    0x8C: "MOV r16/sreg", 0x8D: "LEA",
                    0x8E: "MOV sreg/r16", 0x8F: "POP r16"}
        
        modrm_addr = addr + 1
        if modrm_addr >= len(rom):
            return (1, "?", "")
        modrm = rom[modrm_addr]
        
        func_name = mov_funcs.get(b0, "?")
        total_bytes = 2
        
        # Decode addressing mode
        mod = (modrm >> 6) & 3
        rm = modrm & 7
        
        base_regs_16 = {0:"BX+SI", 1:"BX+DI", 2:"BP+SI", 3:"BP+DI",
                       4:"SI", 5:"DI", 6:"BP", 7:"BX"}
        
        if mod == 0 and rm == 6:
            disp = read_word(modrm_addr + 1)
            if disp is not None:
                seg_prefix = ""
                if addr > 0 and rom[addr-1] in (0x2E, 0x36, 0x3E, 0x26):
                    seg_map = {0x2E:"CS:", 0x36:"SS:", 0x3E:"DS:", 0x26:"ES:"}
                    seg_prefix = seg_map.get(rom[addr-1], "")
                return (4, func_name, f"[{seg_prefix}{disp:04X}]")
            else:
                return (3, func_name, "[??]")
        elif mod == 1:
            disp = read_byte(modrm_addr + 1)
            if disp is not None:
                return (3, func_name, f"[{base_regs_16.get(rm,'?')}+${disp:02X}]")
        elif mod == 2:
            disp = read_word(modrm_addr + 1)
            if disp is not None:
                return (4, func_name, f"[{base_regs_16.get(rm,'?')}+${disp:04X}]")
                
        return (total_bytes, func_name, f"r/m={modrm:02X}")
    
    elif b0 == 0xEC:  # IN AL,dx - already handled but add detail
        pass
    
    return (total_bytes, mnem, "")

# Disassemble from F44D forward with full decoding
print("=" * 80)
print("DEEP DECODE OF BIOS CODE AROUND PHYSICAL FF44D (F000:F44D)")
print("=" * 80)
print()

pos = offset
line_num = 0
instructions = []

while pos < min(offset + 150, len(rom)) and line_num < 50:
    decoded = decode_full(pos)
    if not decoded:
        break
        
    bytes_consumed, mnem, detail = decoded
    phys_addr = 0xFE000 + pos
    rel_offset = pos - offset
    
    prefix = f"[+{rel_offset:+05X}]"
    instr_text = f"{prefix} {phys_addr:05X} OP={rom[pos]:02X}"
    if detail:
        instr_text += f"  {mnem:<20s} {detail}"
    else:
        instr_text += f"  {mnem}"
        
    instructions.append((phys_addr, mnem, detail, rel_offset, bytes_consumed))
    print(instr_text)
    
    pos += bytes_consumed
    line_num += 1

# Now analyze the control flow patterns more carefully
print("\n" + "=" * 80)  
print("CONTROL FLOW ANALYSIS — POLLING LOOPS & HARDWARE STATE CHECKS")
print("=" * 80)

for i, (addr, mnem, detail, rel_off, nbytes) in enumerate(instructions):
    if "IN_AL_DX" in mnem or ("IN AL" in mnem):
        print(f"\n--- Hardware poll sequence starting at offset +{rel_off:04X} ({addr:05X}) ---")
        print(f"  Instruction: {mnem} {detail}")
        
        # Look ahead for TEST/compare/jump pattern
        j = i + 1
        while j < min(i + 6, len(instructions)):
            _, m, d, ro, nb = instructions[j]
            marker = ""
            if j == i + 1:
                marker = " <-- immediate next"
            elif j == i + 2:
                marker = " <-- two steps later"
                
            print(f"  [{j-i}] +{ro:04X}: {m:<20s} {d}{marker}")
            
            if any(x in m for x in ["JE", "JNE", "JB", "JAE", "JS", "JNS"]):
                print(f"      ^ Conditional branch detected!")
                break
                
            j += 1

# Check what ports might be accessed based on DX values from OUT instructions
print("\n" + "=" * 80)
print("PORT ACCESS PATTERN SUMMARY")
print("=" * 80)

out_instructions = [(i, inst) for i, inst in enumerate(instructions) 
                   if 'OUT' in inst[1]]
in_instructions = [(i, inst) for i, inst in enumerate(instructions) 
                  if 'IN' in inst[1]]

if out_instructions:
    print("\nOUT instructions found:")
    for idx, (_, mnem, detail, rel_off, _) in out_instructions[:10]:
        print(f"  Offset +{rel_off:04X}: {mnem} {detail}")
else:
    print("\nNo explicit OUT instructions in this range.")
    print("DX port value must come from earlier code outside our window.")

if in_instructions:
    print(f"\nFound {len(in_instructions)} IN instruction(s)")
    
print("\n" + "=" * 80)
print("CLASSIFICATION HYPOTHESIS")  
print("=" * 80)
print("""
Based on the disassembly showing:
  FF44D: JNE (conditional jump back to retry)
  FF44F: CLI (disable interrupts)
  FF450: IN AL,dx (read hardware status)
  FF451-FF452: TEST AL,$?? (check specific bit)
  FF453: JE/JE (branch based on test result)

The BIOS is waiting for a SPECIFIC BIT to become SET in an I/O register.
Common patterns at POST time:
  1. FDC Main Status ($F4) — wait for data ready (bit 7) or command done
  2. PIC Interrupt Controller ($20/$21) — check IRQ pending/clear
  3. PIT Channel 0/1/2 ($40-$42) — timer tick/status
  4. DMA Controller ($00-$0F) — channel status/page registers
  5. Keyboard/PPI ($60/$61) — key pressed or shift state
  
Given that we previously fixed F065 by adding port $3F3 density config,
and this stall occurs during early POST before disk access, most likely:
  → Waiting for FDC readiness after DOR write (port $F2)
  → Or checking interrupt controller state after STI/CLI sequence
""")
print("=" * 80)
