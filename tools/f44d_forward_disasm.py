"""Forward disassembly of GenXT BIOS ROM around FF44D stall point.
Comprehensive x86 decoder targeting the exact busy-wait loops.
Focuses on finding WHERE DX register gets loaded with port numbers."""

from pathlib import Path

rom_path = Path("third_party/roms/genxt/pcxt.rom")
rom = bytearray(rom_path.read_bytes())

def phys_to_rom(addr):
    """Convert physical address to ROM file offset."""
    return addr - 0xFE000

def rom_offset(offset):
    """Return bytes at ROM offset."""
    if 0 <= offset < len(rom):
        return rom[offset]
    return 0

# Segment prefix map
SEG_PREFIXES = {0x2E: "CS:", 0x36: "SS:", 0x3E: "DS:", 0x26: "ES:", 0x3E: "FS:", 0x36: "GS:"}
REP_PREFIXES = {0xF3: "REPE/REPZ", 0xF2: "REPNE/REPNZ"}
LOCK_PREFIX = 0xF0

REGS8 = ['AL','CL','DL','BL','AH','CH','DH','BH']
REGS16 = ['AX','CX','DX','BX','SP','BP','SI','DI']

def disassemble(start_phys, end_phys):
    """Disassemble from start_phys to end_phys forward."""
    start_off = phys_to_rom(start_phys)
    end_off = phys_to_rom(end_phys)
    
    pos = start_off
    instructions = []
    
    while pos < end_off and pos >= 0 and pos < len(rom):
        orig_pos = pos
        prefixes = ""
        
        # Handle prefixes (but not opcode escape)
        while True:
            b = rom[pos]
            if b in SEG_PREFIXES or b == LOCK_PREFIX or b in REP_PREFIXES:
                pfx_name = SEG_PREFIXES.get(b, REP_PREFIXES.get(b, "LOCK"))
                if pfx_name:
                    prefixes += pfx_name + " "
                pos += 1
            elif b == 0x66:  # Operand size override
                prefixes += "OPSIZE "
                pos += 1
            else:
                break
        
        if pos >= len(rom):
            break
            
        opcode = rom[pos]
        mnem_parts = [prefixes.strip()]
        detail_parts = []
        nbytes = 1
        
        def read_byte():
            nonlocal pos
            val = rom[pos] if pos < len(rom) else 0
            pos += 1
            return val
        
        def read_word():
            lo = read_byte()
            hi = read_byte()
            return lo | (hi << 8)
        
        def modrm_detail(mod, rm, reg_field, base_regs=None):
            parts = []
            if mod == 0:
                if rm == 6:
                    disp = read_word()
                    parts.append(f"[{disp:04X}]")
                else:
                    brs = {'BX+SI':'[BX+SI]', 'BX+DI':'[BX+DI]', 
                           'BP+SI':'[BP+SI]', 'BP+DI':'[BP+DI]',
                           'SI':'[SI]', 'DI':'[DI]', 'BP':'[BP]', 'BX':'[BX]'}
                    parts.append(brs.get(rm, f'[{rm}]'))
            elif mod == 1:
                disp = read_byte()
                brs = {0:'BX+SI', 1:'BX+DI', 2:'BP+SI', 3:'BP+DI',
                       4:'SI', 5:'DI', 6:'BP', 7:'BX'}
                base = brs.get(rm, '?')
                parts.append(f"[{base}+${disp:02X}]")
            elif mod == 2:
                disp = read_word()
                brs = {0:'BX+SI', 1:'BX+DI', 2:'BP+SI', 3:'BP+DI',
                       4:'SI', 5:'DI', 6:'BP', 7:'BX'}
                base = brs.get(rm, '?')
                parts.append(f"[{base}+${disp:04X}]")
            return parts
        
        # --- Decode opcodes ---
        
        # Single-byte ops with no operands
        single_ops = {
            0x90: "NOP", 0xC3: "RET", 0xCB: "RETF",
            0xFA: "CLI", 0xF4: "HLT", 0xCF: "IRET",
            0x9C: "PUSHF", 0x9D: "POPF", 0x07: "POP ES",
            0x17: "POP CS", 0x1F: "POP DS", 0x27: "DAA",
            0x2F: "DAS", 0x37: "AAA", 0x3F: "AAS",
            0xD4: "AAM", 0xD5: "AAD", 0xEC: "IN AL,dx",
            0xed: "IN AX,dx", 0xee: "OUT dx,AL", 0xef: "OUT dx,AX",
            0x8F: "POP ???", 0xCC: "INT 3", 0xCD: "INT imm8",
            0xD6: "SALC", 0xE3: "JCXZ rel8", 0xEA: "JMP FAR ptr",
            0x98: "CBW", 0x99: "CWDE/CWD", 0x9B: "WAIT/FNWAIT",
            0xFE: None, 0xF7: None, 0xFF: None,  # Group opcodes - need MODRM
        }
        
        if opcode in (0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7):
            idx = opcode & 7
            reg = REGS8[idx]
            val = read_byte()
            mnem_parts.append(f"MOV {reg},#{val:02X}")
            nbytes = 2
            
        elif opcode == 0xBE or opcode == 0xBF:
            # MOV DX/SI/DI/BP,BL/BL/etc immediate - actually B8-BF are MOV r16,#imm16
            pass  # handled below
        
        elif 0xB8 <= opcode <= 0xBF:
            idx = opcode & 7
            reg = REGS16[idx]
            val = read_word()
            mnem_parts.append(f"MOV {reg},#{val:04X}")
            nbytes = 3
            
        elif opcode == 0x68:  # PUSH imm16
            val = read_word()
            mnem_parts.append(f"PUSH #{val:04X}")
            nbytes = 3
            
        elif opcode == 0x6A:  # PUSH imm8 sign-extended
            val = read_byte()
            if val > 127:
                val -= 256
            mnem_parts.append(f"PUSH #{val:+d}")
            nbytes = 2
            
        elif opcode == 0xEB:  # JMP rel8
            disp = read_byte()
            signed_disp = disp - 256 if disp > 127 else disp
            target = pos + signed_disp
            mnem_parts.append(f"JNE/JMP rel8 +${target:X}")
            nbytes = 2
            
        elif 0x70 <= opcode <= 0x7F:  # Conditional jumps
            jump_names = {
                0x70:"JO", 0x71:"JNO", 0x72:"JB/JC/JNAE", 0x73:"JAE/JNB/JNC",
                0x74:"JE/JZ", 0x75:"JNE/JNZ", 0x76:"JBE/JNA", 0x77:"JA/JNBE",
                0x78:"JS", 0x79:"JNS", 0x7A:"JP/JPE", 0x7B:"JNP/JPO",
                0x7C:"JL/JNGE", 0x7D:"JGE/JNL", 0x7E:"JLE/JNG", 0x7F:"JG/JNLE"
            }
            name = jump_names.get(opcode, "J??")
            disp = read_byte()
            signed_disp = disp - 256 if disp > 127 else disp
            target = pos + signed_disp
            mnem_parts.append(f"{name} rel8 +${target:X}")
            nbytes = 2
            
        elif opcode == 0xE2:  # LOOPCX rel8
            disp = read_byte()
            signed_disp = disp - 256 if disp > 127 else disp
            target = pos + signed_disp
            mnem_parts.append(f"LOOP CX rel8 +${target:X}")
            nbytes = 2
            
        elif opcode == 0xE0:  # LOOPNE rel8
            disp = read_byte()
            signed_disp = disp - 256 if disp > 127 else disp
            target = pos + signed_disp
            mnem_parts.append(f"LOOPNE rel8 +${target:X}")
            nbytes = 2
            
        elif opcode == 0xE1:  # LOOPS rel8
            disp = read_byte()
            signed_disp = disp - 256 if disp > 127 else disp
            target = pos + signed_disp
            mnem_parts.append(f"LOOPS rel8 +${target:X}")
            nbytes = 2
        
        elif opcode in (0x80, 0x82):  # Group 1 with imm8
            modb = read_byte()
            mod = (modb >> 6) & 3
            reg_field = (modb >> 3) & 7
            rm = modb & 7
            funcs = ['ADD','OR','ADC','SBB','AND','SUB','XOR','CMP']
            func_name = funcs[reg_field]
            
            brs = {0:'BX+SI', 1:'BX+DI', 2:'BP+SI', 3:'BP+DI',
                   4:'SI', 5:'DI', 6:'BP', 7:'BX'}
            
            detail_parts.extend(modrm_detail(mod, rm, reg_field))
            val = read_byte()
            detail_parts.insert(0, f"#{val:02X}")
            mnem_parts.append(f"{func_name} r/m8")
            nbytes += 1 + len(detail_parts) - 1  # already counted bytes above
            
        elif opcode == 0xF6:  # Group 3/4 with imm8 possible
            modb = read_byte()
            mod = (modb >> 6) & 3
            reg_field = (modb >> 3) & 7
            rm = modb & 7
            
            test_funcs = ['TEST','NOT','NEG','MUL','IMUL','DIV','IDIV']
            if reg_field <= 1:
                func_name = "TEST"
                val = read_byte()
                detail_parts.insert(0, f"#{val:02X}")
            else:
                func_name = test_funcs.get(reg_field-2, '???')
            
            detail_parts.extend(modrm_detail(mod, rm, reg_field))
            mnem_parts.append(f"{func_name} r/m8")
            
        elif opcode == 0xA8:  # TEST AL,#imm8
            val = read_byte()
            mnem_parts.append(f"TEST AL,#${val:02X}")
            nbytes = 2
            
        elif opcode == 0xAC:  # LODSB
            mnem_parts.append("LODSB")
            
        elif opcode == 0xAD:  # LODSW
            mnem_parts.append("LODSW")
            
        elif opcode == 0xAE:  # SCASB
            mnem_parts.append("SCASB")
            
        elif opcode == 0xAF:  # SCASW
            mnem_parts.append("SCASW")
        
        elif opcode == 0xAA:  # STOSB
            mnem_parts.append("STOSB")
            
        elif opcode == 0xAB:  # STOSW
            mnem_parts.append("STOSW")
            
        elif opcode == 0x9A:  # CALL FAR ptr
            seg = read_word()
            off = read_word()
            mnem_parts.append(f"CALL FAR ${seg}:{off:04X}")
            nbytes = 5
            
        elif opcode == 0xC2:  # RET imm16
            val = read_word()
            mnem_parts.append(f"RET #{val:04X}")
            nbytes = 3
            
        elif opcode in (0xC4, 0xC5):  # LES/LDS
            mnem_parts.append("LES/LDS (needs MODRM)")
            modb = read_byte()
            pos += 2  # skip past any displacement/immediate
            nbytes = 3 + len(detail_parts) - 1
            
        elif opcode == 0xCA:  # RETF imm16
            val = read_word()
            mnem_parts.append(f"RETF #{val:04X}")
            nbytes = 3
            
        elif opcode == 0xCC:  # INT 3 — handled by single_ops above
            pass
            
        elif opcode == 0xCD:  # INT imm8
            n = read_byte()
            mnem_parts.append(f"INT #{n:#04X}")
            nbytes = 2
            
        elif opcode == 0xD7:  # XLAT
            mnem_parts.append("XLAT")
            
        elif opcode == 0xE4 or opcode == 0xE5:  # IN/OUT with immediate port
            if opcode == 0xE4:
                reg_idx = ((rom[pos] >> 0) & 7) if False else 0  # will be set below
                pass
            port = read_byte()
            if opcode == 0xE4:
                mnem_parts.append(f"IN AL,#${port:02X}")
            else:
                mnem_parts.append(f"OUT #$port:{port:02X},AL")
            nbytes = 2
            
        elif opcode == 0xEB:  # JMP short
            disp = read_byte()
            signed_disp = disp - 256 if disp > 127 else disp
            target = pos + signed_disp
            mnem_parts.append(f"JMP rel8 +${target:X}")
            nbytes = 2
            
        elif opcode == 0xF2:  # REPNE prefix alone? unlikely but handle
            pass  # should have been caught by prefix loop
        
        elif opcode == 0x9B:  # WAIT/FNWAIT
            mnem_parts.append("WAIT")
        
        elif opcode == 0xFE:  # Group 0 (unary ops on r/m8)
            modb = read_byte()
            mod = (modb >> 6) & 3
            rm = modb & 7
            detail_parts.extend(modrm_detail(mod, rm, 0))
            mnem_parts.append("INC/DEC r/m8 (group 0)")
            
        elif opcode in (0xFF,):  # Group 5/6/7 etc.
            modb = read_byte()
            mod = (modb >> 6) & 3
            reg_field = (modb >> 3) & 7
            rm = modb & 7
            groups = {0:"PUSH", 1:"INC", 2:"CALL", 3:"CALL FAR", 
                      4:"JMP", 5:"JMP FAR", 6:"DEC"}
            name = groups.get(reg_field, "???")
            detail_parts.extend(modrm_detail(mod, rm, reg_field))
            mnem_parts.append(f"{name} r/m16")
            
        elif opcode in single_ops and single_ops[opcode]:
            mnem_parts.append(single_ops[opcode])
            
        elif opcode == 0x0E or opcode == 0x16 or opcode == 0x1E or opcode == 0x06:
            seg_names = {0x06:"PUSH ES", 0x0E:"PUSH CS", 0x16:"PUSH DS", 0x1E:"PUSH SS"}
            mnem_parts.append(seg_names.get(opcode, f"PUSH segment"))
            
        elif opcode == 0x0F:  # Two-byte opcode escape
            mb = read_byte()
            # Common two-byte opcodes
            if mb == 0xB6:
                mnem_parts.append("MOVZX r8,r/m8")
                modb = read_byte()
                pos += 1
            elif mb == 0xB7:
                mnem_parts.append("MOVZX r16,r/m16")
                modb = read_byte()
                pos += 1
            else:
                mnem_parts.append(f"2BYTE_OP ${mb:02X}")
                modb = read_byte()
                pos += 1
            nbytes += 1
            
        else:
            mnem_parts.append(f"${opcode:02X}_UNK")
        
        # Build instruction string
        instr_str = " ".join(mnem_parts)
        det_str = " ".join(detail_parts)
        
        phys_addr = orig_pos + 0xFE000
        
        # Mark interesting instructions
        marker = ""
        if "IN AL,dx" in instr_str:
            marker = " <<< IN PORT!"
        elif "OUT" in instr_str.upper():
            marker = " <<< OUT PORT!"
        elif "DX," in instr_str or ",DX" in instr_str or "MOV DX" in instr_str:
            marker = " <<< SETTING DX!"
        elif "TEST AL,#$01" in instr_str:
            marker = " <<< TEST BIT 0 CHECK"
        elif "LOOP CX" in instr_str:
            marker = " <<< LOOP COUNTER"
        
        line = f"[{phys_addr:05X}] {instr_str}"
        if det_str:
            line += f" ({det_str})"
        print(line + marker)
        
        instructions.append((phys_addr, instr_str, det_str))
    
    return instructions

print("=" * 80)
print("FORWARD DISASSEMBLY OF GENXT BIOS POST AREA (FF3D0 - FF460)")
print("=" * 80)
print()

instructions = disassemble(0xFF3D0, 0xFF460)

# Analyze patterns
print("\n" + "=" * 80)
print("ANALYSIS: POLLING LOOPS IDENTIFIED")
print("=" * 80)

in_instrs = [i for i in instructions if "IN AL" in i[1] and "dx" in i[1].lower()]
test_al_01 = [i for i in instructions if "TEST AL,#$01" in i[1]]
mov_dx = [i for i in instructions if "MOV DX" in i[1]]

print(f"\nIN AL,dx found at:")
for addr, mnem, _ in in_instrs:
    print(f"  {addr}: {mnem}")

print(f"\nTEST AL,$01 found at:")  
for addr, mnem, _ in test_al_01:
    print(f"  {addr}: {mnem}")

if mov_dx:
    print(f"\nMOV DX found at:")
    for addr, mnem, _ in mov_dx:
        print(f"  {addr}: {mnem}")
else:
    print("\nNo explicit MOV DX found — port value likely set by earlier code.")
    print("Need to trace back further or check register state setup.")
