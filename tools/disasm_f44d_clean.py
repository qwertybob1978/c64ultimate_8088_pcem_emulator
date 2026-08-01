#!/usr/bin/env python3
"""Clean disassembly of BIOS code around F000:F44D stall point."""
import sys

def disassemble_rom(rom_bytes, start_offset, max_instructions=150):
    """Disassemble x86 real-mode bytes near offset start_offset."""
    
    results = []
    ip = start_offset
    count = 0
    
    while ip < len(rom_bytes) and count < max_instructions:
        pos = ip
        opcode = rom_bytes[ip]
        ip += 1
        
        mnemonic = ""
        operands = ""
        
        # JMP rel8 (EB xx)
        if opcode == 0xEB:
            disp = rom_bytes[ip]; ip += 1
            target = ((pos - start_offset) + (disp - 0x100 if disp > 0x7F else disp)) & 0xFFFF
            mnemonic = "JMP"; operands = f"F{target >> 12}:{target & 0xfff:03X}"
        
        # JMP rel16 (E9 xx xx)
        elif opcode == 0xE9:
            lo = rom_bytes[ip]; hi = rom_bytes[ip+1]; ip += 2
            disp = lo | (hi << 8)
            target = ((pos - start_offset) + (disp - 0x10000 if disp > 0x7FFF else disp)) & 0xFFFF
            mnemonic = "JMP"; operands = f"F{target >> 12}:{target & 0xfff:03X}"
        
        # Conditional jumps JCC rel8 (7x xx)
        elif 0x70 <= opcode <= 0x7F:
            cond_map = {
                0x70: "JC", 0x71: "JNC", 0x72: "JB", 0x73: "JAEC",
                0x74: "JEZ", 0x75: "JNE", 0x76: "JBE", 0x77: "JA",
                0x78: "JS", 0x79: "JNS", 0x7A: "JP", 0x7B: "JNP",
                0x7C: "JL", 0x7D: "JGE", 0x7E: "JLE", 0x7F: "JG"
            }
            disp = rom_bytes[ip]; ip += 1
            target = ((pos - start_offset) + (disp - 0x100 if disp > 0x7F else disp)) & 0xFFFF
            mnemonic = cond_map.get(opcode, "?") or "?"
            operands = f"F{target >> 12}:{target & 0xfff:03X}"
        
        # OUT imm8,AL (E6 xx)
        elif opcode == 0xE6:
            port = rom_bytes[ip]; ip += 1
            mnemonic = "OUT"; operands = f"{port:04X}, AL"
        
        # OUT imm8,AX (E7 xx)
        elif opcode == 0xE7:
            port = rom_bytes[ip]; ip += 1
            mnemonic = "OUTW"; operands = f"{port:04X}, AX"
        
        # IN AL,DX (EC)
        elif opcode == 0xEC:
            mnemonic = "IN_AL_DX"
        
        # IN AX,DX (ED)
        elif opcode == 0xED:
            mnemonic = "IN_AX_DX"
        
        # CLI (FA)
        elif opcode == 0xFA:
            mnemonic = "CLI"
        
        # STI (FB)
        elif opcode == 0xFB:
            mnemonic = "STI"
        
        # STOSB (AA)
        elif opcode == 0xAA:
            mnemonic = "STOSB"
        
        # STOSW (AB)
        elif opcode == 0xAB:
            mnemonic = "STOSW"
        
        # LODSW (AD)
        elif opcode == 0xAD:
            mnemonic = "LODSW"
        
        # SCASB (AE)
        elif opcode == 0xAE:
            mnemonic = "SCASB"
        
        # RET (C3)
        elif opcode == 0xC3:
            mnemonic = "RET"
        
        # RET imm16 (C2 xx xx)
        elif opcode == 0xC2:
            lo = rom_bytes[ip]; hi = rom_bytes[ip+1]; ip += 2
            ret_count = lo | (hi << 8)
            mnemonic = "RETN"; operands = str(ret_count)
        
        # NOP / XCHG AX,AX (90)
        elif opcode == 0x90:
            mnemonic = "NOP"
        
        # INC/DEC/PUSH/POP register (40-5F range handled separately below)
        
        # PUSH reg (50-57)
        elif 0x50 <= opcode <= 0x57:
            regs = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
            mnemonic = "PUSH"; operands = regs[opcode - 0x50]
        
        # POP reg (58-5F)
        elif 0x58 <= opcode <= 0x5F:
            regs = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
            mnemonic = "POP"; operands = regs[opcode - 0x58]
        
        # MOV r/m,reg (8A) or MOV reg,r/m (8B)
        elif opcode in [0x8A, 0x8B]:
            modrm = rom_bytes[ip]; ip += 1
            mod = (modrm >> 6) & 3
            reg_field = (modrm >> 3) & 7
            rm_field = modrm & 7
            
            is_mov_rm_reg = (opcode == 0x8A)
            
            if mod == 3:
                # Register to/from register
                mn_list = {False: "MOV_r_m", True: "MOV_m_r"}
                mnemonic = mn_list.get(is_mov_rm_reg, "?")
                op_regs = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
                if is_mov_rm_reg:
                    operands = f"{op_regs[reg_field]}, [{['BX+SI','BX+DI','BP+SI','BP+DI','SI','DI','disp16','BX'][rm_field]}]"
                else:
                    operands = f"{op_regs[rm_field]}, {op_regs[reg_field]}"
            else:
                # Memory operand with displacement
                addr_map = {0: "[BX+SI]", 1: "[BX+DI]", 2: "[BP+SI]", 3: "[BP+DI]",
                           4: "[SI]", 5: "[DI]", 6: "[disp16]", 7: "[BX]"}
                
                if mod == 1:
                    disp8 = rom_bytes[ip]; ip += 1
                    base_str = addr_map.get(str(rm_field), "?")
                    operands = f"[{base_str}+{disp8:#X}]"
                elif mod == 2:
                    lo = rom_bytes[ip]; hi = rom_bytes[ip+1]; ip += 2
                    disp16 = lo | (hi << 8)
                    base_str = addr_map.get(str(rm_field), "?")
                    operands = f"[{base_str}+{disp16:#X}]"
                else:
                    base_str = addr_map.get(str(rm_field), "?")
                    operands = f"[{base_str}]"
                
                op_regs = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
                if is_mov_rm_reg:
                    mnemonic = "MOV"
                    operands += f", {op_regs[reg_field]}"
                else:
                    mnemonic = "MOV"
                    operands = f"{op_regs[reg_field]}, {operands}"
        
        # MOV AL/EAX,moffs (A0-A1) or mov moffs,AL/AX (A2-A3)
        elif opcode in [0xA0, 0xA1]:
            lo = rom_bytes[ip]; hi = rom_bytes[ip+1]; ip += 2
            offset_val = lo | (hi << 8)
            mn_list = {0xA0: "MOV_AL_moff", 0xA1: "MOV_AX_moff"}
            mnemonic = mn_list[opcode]
            operands = f"F{(offset_val >> 12)}:{offset_val & 0xfff:03X}"
        
        elif opcode in [0xA2, 0xA3]:
            lo = rom_bytes.ip; hi = rom_bytes[ip+1]; ip += 2
            offset_val = lo | (hi << 8)
            mn_list = {0xA2: "MOV_moff_AL", 0xA3: "MOV_moff_AX"}
            mnemonic = mn_list[opcode]
            operands = f"F{(offset_val >> 12)}:{offset_val & 0xfff:03X}"
        
        # MOV AH,imm8 (B4 xx) / MOV reg,immediate (B0-B7)
        elif opcode >= 0xB0 and opcode <= 0xBF:
            imm = rom_bytes[ip]; ip += 1
            
            if opcode < 0xBC:
                # B0-BF: MOV r/m, immediate
                reg_names = ["AL", "CL", "DL", "BL", "AH", "CH", "DH", "BH"]
                mnemonic = "MOV"; operands = f"{reg_names[(opcode-0xB0)&7]}, {imm:#X}"
            else:
                # BC-BF: MOV AX/SI/DI/BP, imm16
                reg_map = {"BC": "AX", "BD": "SI", "BE": "DI", "BF": "BP"}
                key = hex(opcode)[2:]
                reg_name = reg_map.get(key, "?")
                lo = rom_bytes[ip]; hi = rom_bytes[ip+1]; ip += 2
                imm16 = lo | (hi << 8)
                mnemonic = "MOV"; operands = f"{reg_name}, {imm16:#X}"
        
        # MOV segReg,r/m (8C) - complex skip for now
        elif opcode == 0x8C:
            modrm = rom_bytes[ip]; ip += 1
            mnemonic = "MOV_seg_r/m"
        
        # MOV r/m,segReg (8E)
        elif opcode == 0x8E:
            modrm = rom_bytes[ip]; ip += 1
            mnemonic = "MOV_reg_seg"
        
        # ROL/ROR/ADC/etc with imm8 (D0-D1 + C0-C7 group)
        elif opcode in [0xC0, 0xC1]:
            modrm = rom_bytes[ip]; ip += 1
            imm = rom_bytes[ip]; ip += 1
            mnemonic = "SHIFTCMD_imm8"
        
        # INT imm8 (CD xx)
        elif opcode == 0xCD:
            vec = rom_bytes[ip]; ip += 1
            mnemonic = "INT"; operands = f"{vec:#X}h"
        
        # PUSH CS (0x0E)
        elif opcode == 0x0E:
            mnemonic = "PUSH_CS"
        
        # POP CS (0x1F)
        elif opcode == 0x1F:
            mnemonic = "POP_CS"
        
        # AND/OR/XOR/TEST etc with immediate (80-83 groups handled partially)
        elif opcode >= 0x80 and opcode <= 0x83:
            modrm = rom_bytes.ip; ip += 1
            mnemonic = "OP_80xx_group"
        
        # ADD AL,immediate (04 xx)
        elif opcode == 0x04:
            imm = rom_bytes[ip]; ip += 1
            mnemonic = "ADD_AL_im"; operands = f"{imm:#X}"
        
        # CMP byte at memory with immedate (80 / cmp moffs, imm)
        elif opcode == 0x80:
            modrm = rom_bytes[ip]; ip += 1
            if (modrm >> 3) & 7 == 7:  # CMP r/m, imm8
                disp_off = rom_bytes[ip] if ((modrm >> 6) & 3) == 1 else \
                          (rom_bytes[ip+1] | (rom_bytes[ip+2] << 8)) if ((modrm >> 6) & 3) == 2 else 0
                if ((modrm >> 6) & 3) != 3:
                    ip += max(0, disp_off - 1) if isinstance(disp_off, int) and disp_off > 0 else 0
                imm_val = rom_bytes[ip]; ip += 1
                mnemonic = "CMP_m_imm8"
            else:
                mnemonic = "OP_80_modrm"
        
        # TEST AX,mword (A9 xx xx) or OR AX,mword (0D xx xx)
        elif opcode in [0xA9]:
            lo = rom_bytes[ip]; hi = rom_bytes[ip+1]; ip += 2
            val = lo | (hi << 8)
            mnemonic = "TEST_AX_imm"; operands = f"{val:#X}"
        
        # OR reg,immediate (0D xx xx for OR AX,imm but that's actually different encoding)
        elif opcode == 0x0D:
            lo = rom_bytes[ip]; hi = rom_bytes[ip+1]; ip += 2
            val = lo | (hi << 8)
            mnemonic = "OR_AX_imm"; operands = f"{val:#X}"
        
        # AND AL,immediate (F6 /group 4 + immediate)
        elif opcode == 0xF6:
            modrm = rom_bytes[ip]; ip += 1
            group = (modrm >> 3) & 7
            if group == 0:  # TEST r/m, imm8
                pass
            elif group == 5:  # NOT/NEG/... 
                pass
        
        # Default fallback
        else:
            mnemonic = f"?{opcode:02X}?"
    
    return results


def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else "third_party/roms/genxt/pcxt.rom"
    
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
