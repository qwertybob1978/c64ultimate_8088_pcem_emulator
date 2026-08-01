#!/usr/bin/env python3
"""Debug disassembly around F000:F44D."""
import sys

def main():
    with open("third_party/pcem-roms/genxt/pcxt.rom", 'rb') as f:
        rom = bytearray(f.read())
    
    print(f"ROM size: {len(rom)} bytes")
    
    # Physical F000:F44D -> offset 0xFF44D in full address space -> 0x144D within genxt ROM
    start_offset = 0x144D - 0x100  # Start before for context
    
    print(f"Starting at ROM offset {start_offset:#X} ({start_offset})")
    print(f"Bytes available from start: {len(rom) - start_offset}")
    
    ip = start_offset
    count = 0
    
    while ip < len(rom) and count < 50:
        try:
            opcode = rom[ip]
        except IndexError:
            print(f"\nIndexError at ip={ip:#X}")
            break
        
        mnemonic = "?"
        extra_bytes = 0
        
        if opcode == 0xEB:  # JMP rel8
            mnemonic = "JMP_rel8"; extra_bytes = 1
        elif opcode == 0xE9:  # JMP rel16
            mnemonic = "JMP_rel16"; extra_bytes = 2
        elif 0x70 <= opcode <= 0x7F:  # JCC rel8
            mnemonic = "JCC_rel8"; extra_bytes = 1
        elif opcode == 0xE6:  # OUT imm8,AL
            mnemonic = "OUT_AL"; extra_bytes = 1
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
        elif opcode == 0xC3:  # RET
            mnemonic = "RET"
        elif opcode == 0xC2:  # RET imm16
            mnemonic = "RET_imm16"; extra_bytes = 2
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
            mnemonic = "INT"; extra_bytes = 1
        
        next_ip = ip + 1 + extra_bytes
        
        print(f"[{ip - start_offset:03X}] F{(ip >> 4):04X}:{(ip & 0xF):03X} OP={opcode:02X} {mnemonic}")
        
        ip = next_ip
        count += 1


if __name__ == "__main__":
    main()
