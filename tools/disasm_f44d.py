#!/usr/bin/env python3
"""Disassemble the BIOS code around F000:F44D stall point."""
import sys

def disasm_8088(rom_bytes, start_offset):
    """Simple x86 disassembler for real-mode code near F44D."""
    
    # Common patterns found in PC BIOS boot path
    results = []
    ip = start_offset
    
    while ip < len(rom_bytes) and ip < start_offset + 300:
        pos = ip
        opcode = rom_bytes[ip]
        
        def read_byte():
            nonlocal ip
            val = rom_bytes[ip]
            ip += 1
            return val
        
        def read_word():
            lo = read_byte()
            hi = read_byte()
            return lo | (hi << 8)
        
        def rel8_disp(val):
            if val > 0x7F:
                val -= 0x100
            return val
        
        def rel16_disp(val):
            if val > 0x7FFF:
                val -= 0x10000
            return val
        
        mnemonic = ""
        operands = ""
        size = 1
        
        if opcode == 0xEB:  # JMP rel8
            disp = read_byte()
            target = ((pos - start_offset) + rel8_disp(disp)) & 0xFFFF
            mnemonic = "JMP"
            operands = f"F{target >> 12}:{target & 0xFFF:03X}"
        elif opcode == 0xE9:  # JMP rel16
            disp = read_word()
            target = ((pos - start_offset) + rel16_disp(disp)) & 0xFFFF
            mnemonic = "JMP"
            operands = f"F{target >> 12}:{target & 0xFFF:03X}"
        elif opcode == 0x75:  # JNE rel8
            disp = read_byte()
            target = ((pos - start_offset) + rel8_disp(disp)) & 0xFFFF
            mnemonic = "JNZ/JNE"
            operands = f"F{target >> 12}:{target & 0xFFF:03X}"
        elif opcode == 0x74:  # JE rel8
            disp = read_byte()
            target = ((pos - start_offset) + rel8_disp(disp)) & 0xFFFF
            mnemonic = "JE/Z"
            operands = f"F{target >> 12}:{target & 0xFFF:03X}"
        elif opcode == 0x72:  # JB rel8
            disp = read_byte()
            target = ((pos - start_offset) + rel8_disp(disp)) & 0xFFFF
            mnemonic = "JB/NAE"
            operands = f"F{target >> 12}:{target & 0xFFF:03X}"
        elif opcode == 0x73:  # JAE rel8
            disp = read_byte()
            target = ((pos - start_offset) + rel8_disp(disp)) & 0xFFFF
            mnemonic = "JA/E"
            operands = f"F{target >> 12}:{target & 0xFFF:03X}"
        elif opcode == 0x77:  # JA rel8
            disp = read_byte()
            target = ((pos - start_offset) + rel8_disp(disp)) & 0xFFFF
            mnemonic = "JA/NBE"
            operands = f"F{target >> 12}:{target & 0xFFF:03X}"
        elif opcode == 0x76:  # JBE rel8
            disp = read_byte()
            target = ((pos - start_offset) + rel8_disp(disp)) & 0xFFFF
            mnemonic = "JBE/NA"
            operands = f"F{target >> 12}:{target & 0xFFF:03X}"
        elif opcode == 0xE6:  # OUT imm8,AL
            port = read_byte()
            mnemonic = "OUT"
            operands = f"{port:04X},AL"
        elif opcode == 0xE7:  # OUT imm8,AX
            port = read_byte()
            mnemonic = "OUTW"
            operands = f"{port:04X},AX"
        elif opcode == 0xEC:  # IN AL,DX
            mnemonic = "IN"
            operands = "AL,DX"
        elif opcode == 0xED:  # IN AX,DX
            mnemonic = "INW"
            operands = "AX,DX"
        elif opcode == 0xFA:  # CLI
            mnemonic = "CLI"
            operands = ""
        elif opcode == 0xFB:  # STI
            mnemonic = "STI"
            operands = ""
        elif opcode == 0xAA:  # STOSB
            mnemonic = "STOSB"
            operands = "[ES:DI],AL"
        elif opcode == 0xAB:  # STOSW
            mnemonic = "STOSW"
            operands = "[ES:DI],AX"
        elif opcode == 0xAD:  # LODSW
            mnemonic = "LODSW"
            operands = "AX,[DS:SI]"
        elif opcode == 0xAE:  # SCASB
            mnemonic = "SCASB"
            operands = "AL,[ES:DI]"
        elif opcode == 0xAF:  # SCASW
            mnemonic = "SCASW"
            operands = "AX,[ES:DI]"
        elif opcode == 0xC3:  # RET
            mnemonic = "RET"
            operands = ""
        elif opcode == 0xC2:  # RET imm16
            imm = read_word()
            mnemonic = "RET"
            operands = str(imm)
        elif opcode == 0x90:  # NOP (and XCHG AX,EAX which is same as NOP in 8088)
            mnemonic = "NOP"
            operands = ""
        elif opcode == 0x40:  # INC AX
            mnemonic = "INC"
            operands = "AX"
        elif opcode == 0x47:  # INC DI
            mnemonic = "INC"
            operands = "DI"
        elif opcode == 0x4E:  # DEC SI
            mnemonic = "DEC"
            operands = "SI"
        elif opcode == 0x50 + i for i in range(8):  # PUSH register
            reg = [f"PUSH {r}" for r in ["AX","CX","DX","BX","SP","BP","SI","DI"]]
            mnemonic = reg[opcode - 0x50]
            operands = ""
        elif opcode == 0x58 + i for i in range(8):  # POP register
            reg = [f"POP {r}" for r in ["AX","CX","DX","BX","SP","BP","SI","DI"]]
            mnemonic = reg[opcode - 0x58]
            operands = ""
        elif opcode == 0x8A:  # MOV r/m,reg (modrm follows)
            modrm = read_byte()
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            
            if mod == 3 and rm != 7 or mod < 3:
                # Complex addressing mode - skip detailed decode
                mnemonic = f"MOV_{['r/m','r/m+disp8','r/m+disp16','reg'][(mod)]}"
                operands = "?"
            else:
                mnemonic = "MOV"
                operands = "?"
            
            size += 1
        elif opcode == 0x8B:  # MOV reg,r/m
            modrm = read_byte()
            mod = (modrm >> 6) & 3
            dest_reg = (modrm >> 3) & 7
            src_rm = modrm & 7
            
            regs = ["AX","CX","DX","BX","SP","BP","SI","DI"]
            mnemonic = "MOV"
            
            if mod == 3:
                operands = f"{regs[src_rm]},{regs[dest_reg]}"
            elif mod == 0:
                if src_rm == 6:
                    disp16 = read_word()
                    operands = f"[{regs[dest_reg]}+{disp16:#X}]"
                else:
                    operands = f"[{regs[src_rm]}],{regs[dest_reg]}"
            elif mod == 1:
                disp8 = read_byte()
                operands = f"[{regs[src_rm]}+{disp8}],{regs[dest_reg]}"
            else:  # mod == 2
                disp16 = read_word()
                operands = f"[{regs[src_rm]}+{disp16:#X}],{regs[dest_reg]}"
            
            size += 1
        elif opcode == 0x8C:  # MOV r/m,segReg
            modrm = read_byte()
            mod = (modrm >> 6) & 3
            seg_reg_idx = modrm & 7
            seg_regs = ["ES","CS","SS","DS","ES","ES","ES","ES"]
            
            if mod == 3:
                mnemonic = "MOV"
                operands = f"{seg_regs[seg_reg_idx]},r/m"
            else:
                mnemonic = "MOV"
                operands = f"{seg_regs[seg_reg_idx]},[{...}]"
            
            size += 1
        elif opcode == 0x8E:  # MOV segReg,r/m
            modrm = read_byte()
            mod = (modrm >> 6) & 3
            seg_reg_idx = (modrm >> 3) & 7
            rm = modrm & 7
            seg_regs = ["ES","CS","SS","DS","ES","ES","ES","ES"]
            
            mnemonic = "MOV"
            if mod == 3:
                operands = f"{seg_regs[seg_reg_idx]},r/m"
            else:
                operands = f"{seg_regs[seg_reg_idx]},memory"
            
            size += 1
        elif opcode == 0xC0 or opcode == 0xC1:  # ROL/ROR/ADD/etc imm8/rm
            modrm = read_byte()
            imm = read_byte()
            mnemonic = "SHIFTCMD_imm8"
            operands = f"{imm},r/m"
            size += 1
        elif opcode >= 0xA0 and opcode <= 0xA3:  # MOV AL/EAX,moffs / mov moffs,AL/EAX
            addr = read_word()
            mnemonic = {0xA0: "MOV_AL", 0xA1: "MOV_AX", 
                       0xA2: "MOV_AL_m", 0xA3: "MOV_AX_m"}[opcode]
            operands = f"F{addr >> 12}:{addr & 0xFFF:03X}"
        elif opcode == 0xB4:  # MOV AH,imm8
            imm = read_byte()
            mnemonic = "MOV"
            operands = f"AH,{imm:#X}"
        elif opcode == 0xBA:  # MOV DX/SB/DB/CB/DI/BP/BX/CX,imm16
            imm = read_word()
            reg_list = ["DX","SB","DB","CB","DI","BP","BX","CX"]
            mnemonic = "MOV"
            operands = f"{reg_list[(rom_bytes[ip-1])>>5? No wait - let me recalculate]}"
        
        results.append(f"  F{(pos-start_offset):03X}: {mnemonic:20s} {operands}")
    
    return results


def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else "third_party/roms/genxt/pcxt.rom"
    try:
        with open(rom_path, 'rb') as f:
            rom = bytearray(f.read())
    except FileNotFoundError:
        print(f"No ROM at {rom_path}")
        return
    
    # Disassemble from offset of F44D (physical FF44D -> ROM offset 0x144D)
    start_off = 0x144D - 0x100  # Start a bit before for context
    
    ip = start_off
    lines = []
    
    while ip < min(start_off + 200, len(rom)):
        pos = ip
        opcode = rom[ip]
        
        def rd():
            nonlocal ip
            v = rom[ip]; ip += 1; return v
        
        mn = ""
        op = ""
        
        if opcode == 0xEB:  # JMP rel8
            d = rd(); t = ((pos-start_off)+((d-0x100)if d>0x7F else d))&0xFFFF
            mn="JMP"; op=f"F{t>>12}:{t&0xfff:03X}"
        elif opcode == 0xE9:  # JMP rel16
            d=rd()|(rd()<<8); t=((pos-start_off)+(d-0x10000 if d>0x7FFF else d))&0xFFFF
            mn="JMP"; op=f"F{t>>12}:{t&0xfff:03X}"
        elif opcode in [0x75,0x74,0x72,0x73,0x76,0x77]:  # JCC rel8
            cond_map={0x75:"JNZ",0x74:"JE",0x72:"JB",0x73:"JAEC",0x76:"JBE",0x77:"JA"}
            d=rd(); t=((pos-start_off)+((d-0x100)if d>0x7F else d))&0xFFFF
            mn=cond_map.get(opcode,"J?"); op=f"F{t>>12}:{t&0xfff:03X}"
        elif opcode==0xEC: mn="IN_AL_DX"; op=""
        elif opcode==0xED: mn="IN_AX_DX"; op=""
        elif opcode==0xFA: mn="CLI"
        elif opcode==0xFB: mn="STI"
        elif opcode==0xAA: mn="STOSB"
        elif opcode==0xAB: mn="STOSW"
        elif opcode==0xAD: mn="LODSW"
        elif opcode==0xAE: mn="SCASB"
        elif opcode==0xC3: mn="RET"
        elif opcode==0xC2: imm=rd()|(rd()<<8); mn="RET"; op=str(imm)
        elif opcode==0x90: mn="NOP"
        elif opcode>=0x40 and opcode<=0x47: reg=["AX","CX","DX","BX","SP","BP","SI"][opcode-0x40]; mn="INC"; op=reg
        elif opcode==0x4E: mn="DEC"; op="SI"
        elif opcode>=0x50 and opcode<=0x57: reg=["AX","CX","DX","BX","SP","BP","SI","DI"][opcode-0x50]; mn="PUSH"; op=reg
        elif opcode>=0x58 and opcode<=0x5F: reg=["AX","CX","DX","BX","SP","BP","SI","DI"][opcode-0x58]; mn="POP"; op=reg
        elif opcode==0xE6: port=rd(); mn="OUT"; op=f"{port:04X},AL"
        elif opcode==0xE7: port=rd(); mn="OUTW"; op=f"{port:04X},AX"
        elif opcode==0x8A:  # MOV r/m,reg
            modrm=rd(); mod=(modrm>>6)&3; rm=modrm&7; reg=(modrm>>3)&7
            regs=["AX","CX","DX","BX","SP","BP","SI","DI"]
            if mod==3: mn="MOV"; op=f"{regs[reg]},{regs[rm]}"
            else: 
                disp_off = rd() if mod==1 else (rd()|(rd()<<8)) if mod==2 else 0
                base_reg = ["BX+SI","BCX","BDX","BBX","BSI","BPP","BXDI","DDI"][rm]
                mn="MOV"; op=f"[{base_reg}+disp],{regs[reg]}"
        elif opcode==0x8B:  # MOV reg,r/m
            modrm=rd(); mod=(modrm>>6)&3; dest=(modrm>>3)&7; src=modrm&7
            regs=["AX","CX","DX","BX","SP","BP","SI","DI"]
            if mod==3: mn="MOV"; op=f"{regs[src]},{regs[dest]}"
            else:
                disp_off = rd() if mod==1 else (rd()|(rd()<<8)) if mod==2 else 0
                addr_str = {"0":"[BX+SI]","1":"[BX+DI]","2":"[BP+SI]","3":"[BP+DI]",
                           "4":"[SI]","5":"[DI]","6":"[BP]","7":"[BX]"}.get(str(src),"?")
                mn="MOV"; op=f"{regs[dest]},{addr_str}"
        elif opcode in [0xA0,0xA1]:  # MOV AL/AX,moffs
            off=rd()|(rd()<<8); mn={"A0":"MOV_AL_moff","A1":"MOV_AX_moff"}[f"{opcode:X}".lower()]
            op=f"F{off>>12}:{off&0xfff:03X}"
        elif opcode in [0xA2,0xA3]:  # MOV moffs,AL/AX
            off=rd()|(rd()<<8); mn={"A2":"MOV_moff_AL","A3":"MOV_moff_AX"}[f"{opcode:X}".lower()]
            op=f"F{off>>12}:{off&0xfff:03X}"
        elif opcode==0xB4: imm=rd(); mn="MOV_AH_imm"; op=f"AH,{imm:#X}"
        elif opcode==0xBA:  # This is actually a prefix or different encoding - skip for now
            pass
        elif opcode>=0xC0 and opcode<=0xFF: 
            modrm=rd()
            mod=(modrm>>6)&3; rm=modrm&7; reg=(modrm>>3)&7
            regs=["AX","CX","DX","BX","SP","BP","SI","DI"]
            if mod==3:
                # Register mode operations
                high_bits=(opcode>>4)&0xF
                low_bits=opcode&0x7
                if high_bits==0xC:  # MOV r/m,immediate
                    imm_size = 1 if ((opcode>>3)&1)==0 else 2
                    imm_val = rd() if imm_size==1 else (rd()|(rd()<<8))
                    mn=f"MOV_{regs[reg]}_imm"
                    op=f"{regs[reg]},{imm_val:#X}"
                elif high_bits==0xD:  # INC/DEC/PUSH/POP/etc
                    if reg<=3: mn={0:"INC",1:"PUSH",2:"POP",3:"ADD"}[reg]; op=regs[(opcode>>3)&7]
                    else: mn="???"
            else:
                disp_off = rd() if mod==1 else (rd()|(rd()<<8)) if mod==2 else 0
                addr_map = {0:"[BX+SI]",1:"[BX+DI]",2:"[BP+SI]",3:"[BP+DI]",
                           4:"[SI]",5:"[DI]",6:"[disp16]",7:"[BX]"}
                addr_str = addr_map.get(str(rm),"?")
                mn=f"OP_C0_plus_F{hex(opcode)}"
                op=f"{addr_str},..."
        
        lines.append(f"[{(pos-start_off):03X}] F{(pos-start_offset)&0xFFFFF>>12}:{(pos-start_offset)&0xFFF:03X}: {mn:25s} {op}")
        ip += 1
    
    print("\n=== DISASSEMBLY OF BIOS CODE AROUND F000:F44D ===\n")
    for line in lines[:100]:  # First 100 instructions
        print(line)


if __name__ == "__main__":
    main()
