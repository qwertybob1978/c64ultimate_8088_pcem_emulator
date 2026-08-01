#!/usr/bin/env python3
"""Disassembly of BIOS code around F000:F44D stall point."""
import sys

def main():
    with open("third_party/pcem-roms/genxt/pcxt.rom", 'rb') as f:
        rom = bytearray(f.read())
    
    print(f"ROM size: {len(rom)} bytes")
    print(f"BIOS ROM starts at physical FE000")
    
    # Physical F000:F44D = (F000<<4)+F44D = F0000+F44D = FF44D
    # ROM offset = FF44D - FE000 = 0x144D
    target_phys = 0xFF44D
    start_off = target_phys - 0xFE000
    
    print(f"\nTarget physical addr: {target_phys:#07X}")
    print(f"Starting disassembly at ROM offset {start_off:#05X} ({start_off})")
    print()
    
    ip = max(0, start_off - 0x20)  # Start a bit before for context
    count = 0
    
    while ip < len(rom) and count < 100:
        try:
            opcode = rom[ip]
        except IndexError:
            break
        
        mnemonic = "?"
        extra_bytes = 0
        
        if opcode == 0xEB:  # JMP rel8
            mnemonic = "JMP_rel8"; extra_bytes = 1
        elif opcode == 0xE9:  # JMP rel16
            mnemonic = "JMP_rel16"; extra_bytes = 2
        elif 0x70 <= opcode <= 0x7F:  # JCC rel8
            cond_map = {
                0x70:"JC",0x71:"JNC",0x72:"JB",0x73:"JAEC",
                0x74:"JEZ",0x75:"JNE",0x76:"JBE",0x77:"JA",
                0x78:"JS",0x79:"JNS",0x7A:"JP",0x7B:"JNP",
                0x7C:"JL",0x7D:"JGE",0x7E:"JLE",0x7F:"JG"
            }
            mnemonic = cond_map.get(opcode,"?"); extra_bytes = 1
        elif opcode == 0xE6:  # OUT imm8,AL
            mnemonic = "OUT_AL_imm8"; extra_bytes = 1
        elif opcode == 0xE7:  # OUT imm8,AX
            mnemonic = "OUT_AX_imm8"; extra_bytes = 1
        elif opcode == 0xEC:  # IN AL,DX
            mnemonic = "IN_AL_DX"
        elif opcode == 0xED:  # IN AX,DX
            mnemonic = "IN_AX_DX"
        elif opcode == 0xFA:  # CLI
            mnemonic = "CLI"
        elif opcode == 0xFB:  # STI
            mnemonic = "STI"
        elif opcode == 0xAA:  # STOSB
            mnemonic = "STOSB"
        elif opcode == 0xAB:  # STOSW
            mnemonic = "STOSW"
        elif opcode == 0xAD:  # LODSW
            mnemonic = "LODSW"
        elif opcode == 0xAE:  # SCASB
            mnemonic = "SCASB"
        elif opcode == 0xC3:  # RET
            mnemonic = "RET"
        elif opcode == 0xC2:  # RET imm16
            mnemonic = "RETN_imm16"; extra_bytes = 2
        elif opcode == 0x90:  # NOP
            mnemonic = "NOP"
        elif 0x50 <= opcode <= 0x57:  # PUSH reg
            regs = ["AX","CX","DX","BX","SP","BP","SI","DI"]
            mnemonic = f"PUSH_{regs[opcode-0x50]}"
        elif 0x58 <= opcode <= 0x5F:  # POP reg
            regs = ["AX","CX","DX","BX","SP","BP","SI","DI"]
            mnemonic = f"POP_{regs[opcode-0x58]}"
        elif opcode in [0x8A, 0x8B]:  # MOV r/m,reg / MOV reg,r/m
            mnemonic = "MOV_modrm"; extra_bytes = 1
        elif opcode in [0xA0, 0xA1, 0xA2, 0xA3]:  # MOV moffs
            mnemonic = "MOV_moffs"; extra_bytes = 2
        elif opcode >= 0xB0 and opcode <= 0xBF:  # MOV reg,imm
            if opcode < 0xBC:
                mnemonic = "MOV_reg8_imm8"; extra_bytes = 1
            else:
                mnemonic = "MOV_reg16_imm16"; extra_bytes = 2
        elif opcode == 0xCD:  # INT imm8
            mnemonic = "INT_imm8"; extra_bytes = 1
        
        offset_from_start = ip - start_off
        phys_addr = 0xFE000 + ip
        seg_ip = (phys_addr >> 4) & 0xFFFFF
        segment = phys_addr >> 4
        instruction_offset = phys_addr & 0xF
        
        marker = " <-- F44D" if abs(offset_from_start) <= 2 else ""
        
        print(f"[+{offset_from_start:+04X}] {phys_addr:#07X} OP={opcode:02X} {mnemonic}{marker}")
        
        ip += 1 + extra_bytes
        count += 1


if __name__ == "__main__":
    main()
