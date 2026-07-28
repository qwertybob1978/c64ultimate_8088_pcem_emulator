#!/usr/bin/env python3
"""Decode BIOS ROM bytes around physical address FF78D."""
from pathlib import Path

# Read the guest image
data = Path(r'C:\Repository\C64_x86\build\guest-genxt.reu').read_bytes()

# Physical address FF78D -> file offset FF78D - FE000 = 178D
start_offset = 0x1780
end_offset = start_offset + 256

print(f"Decoding BIOS ROM from file offset {start_offset:#06X} ({end_offset-start_offset} bytes)")
print(f"This corresponds to physical addresses {(0xFE000+start_offset):#07X}-{(0xFE000+end_offset):#07X}\n")

pos = start_offset
while pos < min(end_offset, len(data)):
    phys_addr = 0xFE000 + pos
    
    # Print every 16 bytes with decoded instruction info
    if (pos % 16 == 0):
        print(f"\n@{phys_addr:05X}: ", end='')
    
    b = data[pos]
    print(f"{b:02X} ", end='')
    pos += 1

print("\n\n=== Full x86 opcode decode ===")
pos = start_offset
while pos < min(end_offset, len(data)):
    addr = 0xFE000 + pos
    opcode = data[pos]
    pos += 1
    
    mnemonics = {
        0x00: "ADD r/m,r", 0x01: "ADD r/m,r", 0x02: "ADD r,m/r", 0x03: "ADD r,r/m",
        0x04: "AL,imm8", 0x05: "AX,imm16",
        0x06: "PUSH ES", 0x07: "POP ES",
        0x08: "OR r/m,r", 0x09: "OR r/m,r", 0x0A: "OR r,m/r", 0x0B: "OR r,r/m",
        0x0C: "AL,imm8", 0x0D: "AX,imm16",
        0x0E: "PUSH CS",
        0x10: "ADC r/m,r", 0x11: "ADC r/m,r", 0x12: "ADC r,m/r", 0x13: "ADC r,r/m",
        0x14: "AL,imm8", 0x15: "AX,imm16",
        0x16: "PUSH SS", 0x17: "POP SS",
        0x18: "SBB r/m,r", 0x19: "SBB r/m,r", 0x1A: "SBB r,m/r", 0x1B: "SBB r,r/m",
        0x1C: "AL,imm8", 0x1D: "AX,imm16",
        0x1E: "PUSH DS",
        0x20: "AND r/m,r", 0x21: "AND r/m,r", 0x22: "AND r,m/r", 0x23: "AND r,r/m",
        0x24: "AL,imm8", 0x25: "AX,imm16",
        0x27: "DAA",
        0x28: "SUB r/m,r", 0x29: "SUB r/m,r", 0x2A: "SUB r,m/r", 0x2B: "SUB r,r/m",
        0x2C: "AL,imm8", 0x2D: "AX,imm16",
        0x2F: "DAS",
        0x30: "XOR r/m,r", 0x31: "XOR r/m,r", 0x32: "XOR r,m/r", 0x33: "XOR r,r/m",
        0x34: "AL,imm8", 0x35: "AX,imm16",
        0x37: "AAA", 0x39: "CMP r/m,r", 0x3B: "CMP r,r/m", 0x3C: "AL,imm8", 0x3D: "AX,imm16",
        0x3F: "NEG AX",
        0x40: "INC AX", 0x41: "INC CX", 0x42: "INC DX", 0x43: "INC BX",
        0x44: "INC SP", 0x45: "INC BP", 0x46: "INC SI", 0x47: "INC DI",
        0x48: "DEC AX", 0x49: "DEC CX", 0x4A: "DEC DX", 0x4B: "DEC BX",
        0x4C: "DEC SP", 0x4D: "DEC BP", 0x4E: "DEC SI", 0x4F: "DEC DI",
        0x50: "PUSH AX", 0x51: "PUSH CX", 0x52: "PUSH DX", 0x53: "PUSH BX",
        0x54: "PUSH SP", 0x55: "PUSH BP", 0x56: "PUSH SI", 0x57: "PUSH DI",
        0x58: "POP AX", 0x59: "POP CX", 0x5A: "POP DX", 0x5B: "POP BX",
        0x5C: "POP SP", 0x5D: "POP BP", 0x5E: "POP SI", 0x5F: "POP DI",
        0x60: "PUSHA", 0x61: "POPA",
        0x62: "BOUND r,r/m",
        0x68: "PUSH imm16", 0x6A: "PUSH imm8", 0x6B: "IMUL r,i/s",
        0x6C: "IN AL,dx/imm8", 0x6D: "INSW dx,es:[di]",
        0x6E: "OUTS dx,[esi]/imm8", 0x6F: "OUTSW dx,[esi]/movsw",
        0x70: "JO rel8", 0x71: "JNO rel8", 0x72: "JB/JAE rel8", 0x73: "JNB/JB rel8",
        0x74: "JE/JNE rel8", 0x75: "JNE rel8", 0x76: "JBE/JA rel8", 0x77: "JA/JBE rel8",
        0x78: "JS/JNS rel8", 0x79: "JPE/JPO rel8",
        0x7A: "JCXZ/JNZ rel8", 0x7B: "JMP rel8 (conditional)",
        0x7C: "JL/JGE rel8", 0x7D: "JLE/JG rel8",
        0x80: "GRP1 imm8", 0x81: "GRP1 imm16", 0x82: "GRP1 imm8", 0x83: "GRP1 imm8s",
        0x84: "TEST r/m,r", 0x85: "TEST r,m/r",
        0x86: "XCHG r/m,r", 0x87: "XCHG r,r/m",
        0x88: "MOV r/m,r", 0x89: "MOV r,r/m", 0x8A: "MOV r,r/m", 0x8B: "MOV r,r/m",
        0x8C: "MOV r/m,sreg", 0x8D: "LEA r,m", 0x8E: "MOV sreg,r/m", 0x8F: "POP r/m",
        0x90: "NOP", 0x91: "XCHG AX,CX", 0x92: "XCHG AX,DX", 0x93: "XCHG AX,BX",
        0x94: "XCHG AX,SP", 0x95: "XCHG AX,BP", 0x96: "XCHG AX,SI", 0x97: "XCHG AX,DI",
        0x98: "CBW", 0x99: "CWDE",
        0x9A: "CALL FAR ptr cs:ip",
        0x9B: "WAIT", 0x9C: "PUSHF", 0x9D: "POPF",
        0x9E: "SAHF", 0x9F: "LAHF",
        0xA0: "AL,[bp+si]", 0xA1: "AX,[seg:off]", 0xA2: "[seg:off],AL", 0xA3: "[seg:off],AX",
        0xA4: "MOVS [di],[si]", 0xA5: "MOVSW/CMPSW",
        0xA6: "CMPS [di]/[si]", 0xA7: "CMPSW/[di]/[si]",
        0xA8: "TEST AL,imm8", 0xA9: "TEST AX,imm16",
        0xAA: "STOS AL,[di]", 0xAB: "STOS AX,[di]",
        0xAC: "LODS AL,[si]", 0xAD: "LODS AX,[si]",
        0xAE: "SCAS AL,[di]", 0xAF: "SCAS AX,[di]",
        0xB0: "MOV AL,imm8", 0xB1: "MOV CL,imm8", 0xB2: "MOV DL,imm8", 0xB3: "MOV BL,imm8",
        0xB4: "MOV AH,imm8", 0xB5: "MOV CH,imm8", 0xB6: "MOV DH,imm8", 0xB7: "MOV BH,imm8",
        0xB8: "MOV r16,imm16", 0xBA: "MOV r/m16,imm16",
        0xBC: "MOV SP,imm16", 0xBD: "MOV BP,imm16", 0xBE: "MOV SI,imm16", 0xBF: "MOV DI,imm16",
        0xC0: "GRP2 imm8", 0xC1: "GRP2 imm8",
        0xC2: "RET imm16", 0xC3: "RET",
        0xC4: "LES r,r/m", 0xC5: "LDS r,r/m",
        0xC6: "MOV r/m8,imm8", 0xC7: "MOV r/m16,imm16",
        0xC8: "ENTER imm16,imm8", 0xC9: "LEAVE",
        0xCA: "RETF imm16", 0xCB: "RETF", 0xCC: "INT3", 0xCD: "INT imm8",
        0xCE: "INTO", 0xCF: "IRET",
        0xD0: "GRP2", 0xD1: "GRP2", 0xD2: "GRP2", 0xD3: "GRP2",
        0xD4: "AAM imm8", 0xD5: "AAD imm8",
        0xD6: "SALC",
        0xD7: "DAA/DAS/XLAT",
        0xD8: "FPU", 0xD9: "FPU", 0xDA: "FPU", 0xDB: "FPU", 0xDC: "FPU", 0xDD: "FPU", 0xDE: "FPU", 0xDF: "FPU",
        0xE0: "LOOPNE rel8", 0xE1: "LOOPE rel8", 0xE2: "LOOP rel8",
        0xE3: "JCXZ rel8",
        0xE4: "IN AL,imm8", 0xE5: "IN AX,imm8", 0xE6: "OUT imm8,AL", 0xE7: "OUT imm8,AX",
        0xE8: "CALL rel16", 0xE9: "JMP rel16", 0xEA: "JMP FAR ptr cs:ip",
        0xEB: "JMP rel8",
        0xEC: "IN AL,dx", 0xED: "IN AX,dx", 0xEE: "OUT dx,AL", 0xEF: "OUT dx,AX",
        0xF0: "LOCK", 0xF1: "INT1 (ICE)", 0xF2: "REPNE", 0xF3: "REP",
        0xF4: "HLT", 0xF5: "CMC",
        0xF6: "GRP3/4 imm8", 0xF7: "GRP3/4 imm16",
        0xF8: "CLC", 0xF9: "STC", 0xFA: "CLI", 0xFB: "STI",
        0xFC: "CLD", 0xFD: "STD",
    }
    
    mnemonic = mnemonics.get(opcode, f"UNKNOWN ${opcode:02X}")
    
    # Skip over operands for display purposes
    if opcode in (0x04, 0x0C, 0x14, 0x1C, 0x24, 0x2C, 0x34, 0x3C):
        pos += 1  # imm8
    elif opcode in (0x05, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D):
        pos += 2  # imm16
    elif opcode in (0x6A, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7B, 0x7C, 0x7D, 0xA8, 0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xC0, 0xC1, 0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE6, 0xD4, 0xD5, 0xF6, 0xF7):
        pass  # Complex operand handling - just show current byte
    elif opcode == 0xEB:
        pos += 1  # rel8
    elif opcode in (0xE8, 0xE9):
        pos += 2  # rel16 or abs16
    
    print(f"@{addr:05X}: {opcode:02X} -> {mnemonic}")
