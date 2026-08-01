#!/usr/bin/env python3
"""Simple disassembly of BIOS code around F000:F44D stall point."""
import sys

def read_byte(data, pos):
    """Read one byte safely."""
    return data[pos] if pos < len(data) else None

def read_word(data, pos):
    """Read two bytes as little-endian word."""
    if pos + 1 >= len(data):
        return None
    return data[pos] | (data[pos+1] << 8)

def rel8(disp):
    """Convert unsigned byte to signed displacement."""
    return disp - 0x100 if disp > 0x7F else disp

def rel16(disp):
    """Convert unsigned word to signed displacement."""
    return disp - 0x10000 if disp > 0x7FFF else disp

def disassemble_rom(rom_bytes, start_offset, max_instructions=150):
    """Disassemble x86 real-mode bytes near offset start_offset."""
    
    results = []
    ip = start_offset
    
    while ip < len(rom_bytes) and len(results) < max_instructions:
        pos = ip
        opcode = rom_bytes[ip]
        ip += 1
        
        mnemonic = ""
        operands = ""
        
        # JMP rel8 (EB xx)
        if opcode == 0xEB:
            d = read_byte(rom_bytes, ip); ip += 1
            if d is None: break
            target = ((pos - start_offset) + rel8(d)) & 0xFFFF
            mnemonic = "JMP"; operands = f"F{target >> 12}:{target & 0xfff:03X}"
        
        # JMP rel16 (E9 xx xx)
        elif opcode == 0xE9:
            d = read_word(rom_bytes, ip); ip += 2
            if d is None: break
            target = ((pos - start_offset) + rel16(d)) & 0xFFFF
            mnemonic = "JMP"; operands = f"F{target >> 12}:{target & 0xfff:03X}"
        
        # Conditional jumps JCC rel8 (7x xx)
        elif 0x70 <= opcode <= 0x7F:
            cond_map = {
                0x70: "JC", 0x71: "JNC", 0x72: "JB/NAEC", 0x73: "JA/JNBE",
                0x74: "JE/JZ", 0x75: "JNE/JNZ", 0x76: "JBE/NA", 0x77: "JA/NBE",
                0x78: "JS", 0x79: "JNS", 0x7A: "JP/JPE", 0x7B: "JNP/JPO",
                0x7C: "JL/NGE", 0x7D: "JGE/NL", 0x7E: "JLE/NG", 0x7F: "JG/NE"
            }
            d = read_byte(rom_bytes, ip); ip += 1
            if d is None: break
            target = ((pos - start_offset) + rel8(d)) & 0xFFFF
            mnemonic = cond_map.get(opcode, "?") or "?"
            operands = f"F{target >> 12}:{target & 0xfff:03X}"
        
        # OUT imm8,AL (E6 xx)
        elif opcode == 0xE6:
            port = read_byte(rom_bytes, ip); ip += 1
            if port is None: break
            mnemonic = "OUT"; operands = f"{port:04X}, AL"
        
        # OUT imm8,AX (E7 xx)
        elif opcode == 0xE7:
            port = read_byte(rom_bytes, ip); ip += 1
            if port is None: break
            mnemonic = "OUTW"; operands = f"{port:04X}, AX"
        
        # IN AL,DX (EC)
        elif opcode == 0xEC:
            mnemonic = "IN_AL_DX"
        
        # IN AX,DX (ED)
        elif opcode == 0xED:
            mnemonic = "IN_AX_DX"
        
        # CLI (FA) / STI (FB)
        elif opcode == 0xFA:
            mnemonic = "CLI"
        elif opcode == 0xFB:
            mnemonic = "STI"
        
        # STOSB (AA) / STOSW (AB)
        elif opcode == 0xAA:
            mnemonic = "STOSB"
        elif opcode == 0xAB:
            mnemonic = "STOSW"
        
        # LODSW (AD)
        elif opcode == 0xAD:
            mnemonic = "LODSW"
        
        # SCASB (AE)
        elif opcode == 0xAE:
            mnemonic = "SCASB"
        
        # RET (C3) / RET imm16 (C2 xx xx)
        elif opcode == 0xC3:
            mnemonic = "RET"
        elif opcode == 0xC2:
            ret_count = read_word(rom_bytes, ip); ip += 2
            if ret_count is None: break
            mnemonic = "RETN"; operands = str(ret_count)
        
        # NOP (90)
        elif opcode == 0x90:
            mnemonic = "NOP"
        
        # PUSH reg (50-57) / POP reg (58-5F)
        elif 0x50 <= opcode <= 0x57:
            regs = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
            mnemonic = "PUSH"; operands = regs[opcode - 0x50]
        elif 0x58 <= opcode <= 0x5F:
            regs = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
            mnemonic = "POP"; operands = regs[opcode - 0x58]
        
        # MOV r/m,reg (8A) or MOV reg,r/m (8B)
        elif opcode in [0x8A, 0x8B]:
            modrm = read_byte(rom_bytes, ip); ip += 1
            if modrm is None: break
            
            mod = (modrm >> 6) & 3
            reg_field = (modrm >> 3) & 7
            rm_field = modrm & 7
            
            op_regs = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
            
            addr_map = {
                0: "[BX+Si]", 1: "[BX+Di]", 2: "[BP+Si]", 3: "[BP+Di]",
                4: "[Si]", 5: "[Di]", 6: "[disp16]", 7: "[BX]"
            }
            
            if mod == 3:
                # Register mode
                if opcode == 0x8A:  # MOV r/m,reg -> MOV dest, src
                    mnemonic = "MOV"
                    operands = f"{op_regs[reg_field]}, [{addr_map.get(rm_field,'?')}]"
                else:  # 0x8B MOV reg,r/m
                    mnemonic = "MOV"
                    operands = f"{op_regs[rm_field]}, {op_regs[reg_field]}"
            else:
                # Memory operand with displacement
                if mod == 1:
                    disp8 = read_byte(rom_bytes, ip); ip += 1
                    base_str = addr_map.get(str(rm_field), "?")
                    mem_op = f"[{base_str}+{disp8:#X}]"
                elif mod == 2:
                    disp16_val = read_word(rom_bytes, ip); ip += 2
                    base_str = addr_map.get(str(rm_field), "?")
                    mem_op = f"[{base_str}+{disp16_val:#X}]"
                else:
                    base_str = addr_map.get(str(rm_field), "?")
                    mem_op = f"[{base_str}]"
                
                mnemonic = "MOV"
                if opcode == 0x8A:  # MOV r/m,reg
                    operands = f"{mem_op}, {op_regs[reg_field]}"
                else:  # 0x8B MOV reg,r/m
                    operands = f"{op_regs[reg_field]}, {mem_op}"
        
        # MOV AL/EAX,moffs (A0-A1) or mov moffs,AL/AX (A2-A3)
        elif opcode in [0xA0, 0xA1]:
            offset_val = read_word(rom_bytes, ip); ip += 2
            mn_list = {0xA0: "MOV_AL_moff", 0xA1: "MOV_AX_moff"}
            mnemonic = mn_list[opcode]
            operands = f"F{(offset_val >> 12)}:{offset_val & 0xfff:03X}"
        
        elif opcode in [0xA2, 0xA3]:
            offset_val = read_word(rom_bytes, ip); ip += 2
            mn_list = {0xA2: "MOV_moff_AL", 0xA3: "MOV_moff_AX"}
            mnemonic = mn_list[opcode]
            operands = f"F{(offset_val >> 12)}:{offset_val & 0xfff:03X}"
        
        # ADD AL,immediate (04 xx) / OR AX,immediate (0D xx xx)
        elif opcode == 0x04:
            imm = read_byte(rom_bytes, ip); ip += 1
            if imm is None: break
            mnemonic = "ADD_AL_im"; operands = f"{imm:#X}"
        
        elif opcode == 0x0D:
            val = read_word(rom_bytes, ip); ip += 2
            if val is None: break
            mnemonic = "OR_AX_imm"; operands = f"{val:#X}"
        
        # TEST AX,mword (A9 xx xx)
        elif opcode == 0xA9:
            val = read_word(rom_bytes, ip); ip += 2
            if val is None: break
            mnemonic = "TEST_AX_imm"; operands = f"{val:#X}"
        
        # INT imm8 (CD xx)
        elif opcode == 0xCD:
            vec = read_byte(rom_bytes, ip); ip += 1
            if vec is None: break
            mnemonic = "INT"; operands = f"{vec:#X}h"
        
        # PUSH CS (0x0E) / POP CS (0x1F)
        elif opcode == 0x0E:
            mnemonic = "PUSH_CS"
        elif opcode == 0x1F:
            mnemonic = "POP_CS"
        
        # MOV segReg,r/m (8C) / MOV r/m,segReg (8E) - simplified
        elif opcode == 0x8C:
            modrm = read_byte(rom_bytes, ip); ip += 1
            mnemonic = "MOV_seg_r/m" if modrm is not None else "??"
        elif opcode == 0x8E:
            modrm = read_byte(rom_bytes, ip); ip += 1
            mnemonic = "MOV_reg_seg" if modrm is not None else "??"
        
        # ROL/ROR/etc with immediate (C0/C1 + group)
        elif opcode in [0xC0, 0xC1]:
            modrm = read_byte(rom_bytes, ip); ip += 1
            imm = read_byte(rom_bytes, ip); ip += 1
            mnemonic = "SHIFTCMD_imm8"
        
        # Default fallback for unknown opcodes
        else:
            mnemonic = f"?{opcode:02X}?"
    
    return results


def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else "third_party/pcem-roms/genxt/pcxt.rom"
    
    try:
        with open(rom_path, 'rb') as f:
            rom = bytearray(f.read())
    except FileNotFoundError:
        print(f"No ROM at {rom_path}")
        return
    
    # Physical F000:F44D -> offset 0xFF44D in ROM space -> 0x144D within genxt ROM file
    start_offset = 0x144D - 0x100  # Start a bit before for context
    
    lines = disassemble_rom(rom, start_offset, max_instructions=120)
    
    print("\n=== DISASSEMBLY OF BIOS CODE AROUND F000:F44D ===\n")
    for line in lines[:120]:
        print(line)


if __name__ == "__main__":
    main()
