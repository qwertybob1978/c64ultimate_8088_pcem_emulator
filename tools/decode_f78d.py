#!/usr/bin/env python3
"""Decode instruction stream at physical address where CS:F000 IP:F78D maps."""
import sys
from pathlib import Path

data = Path(r"build/guest-genxt.reu").read_bytes()

# Physical addr for CS=F000 IP=F78D = 0xF000*16 + 0xF78D = 0xFF78D
phys_start = 0xFF780
print("=== Bytes at physical 0xFF780 ===")
for i in range(0x40):
    if (i % 16 == 0) and i > 0:
        print()
    elif (i % 16 == 0):
        print(f"{phys_start+i:05X}: ", end="")
    b = data[phys_start + i]
    print(f"{b:02X} ", end="")
print("\n")

print("=== Proper x86 decode with ModR/M support ===")
pos = phys_start
while pos < min(phys_start + 0x40, len(data)):
    addr = pos
    op = data[pos]
    pos += 1

    # OUT DX,AL / IN AL,DY family - no ModR.M needed for these specific ops
    if op == 0xEE:
        modrm = data[pos]; pos += 1
        reg_f = (modrm >> 3) & 7
        rm_f = modrm & 7
        print(f"@{addr:05X}: EE {modrm:02X}   OUT DX,AL  [Mod={modrm>>6:#b} Reg={reg_f} Rm={rm_f}]")
    elif op == 0xEC or op == 0xED:
        mnem = "IN AL,DY" if op == 0xEC else "IN AX,DY"
        modrm = data[pos]; pos += 1
        print(f"@{addr:05X}: {op:02X} {modrm:02X}     {mnem}")
    elif op == 0xEF:
        modrm = data[pos]; pos += 1
        print(f"@{addr:05X}: EF {modrm:02X}       OUT DY,AX")

    # RET/RET imm16
    elif op == 0xC3:
        print(f"@{addr-1:05X}: C3             RET")
    elif op == 0xC2:
        imm = int.from_bytes(bytes([data[pos], data[pos+1]]), "little"); pos += 2
        print(f"@{addr-1:05X}: C2 {imm:04X}      RET imm16")

    # PUSH/POP single regs
    elif op >= 0x50 and op <= 0x5F:
        rnames = ["PUSH AX", "PUSH CX", "PUSH DX", "PUSH BX",
                   "PUSH SP", "PUSH BP", "PUSH SI", "PUSH DI"]
        pnames = ["POP AX", "POP CX", "POP DX", "POP BX",
                  "POP SP", "POP BP", "POP SI", "POP DI"]
        idx = op - 0x50
        label = pnames[idx] if pos > phys_start + 8 else rnames[idx]
        print(f"@{addr-1:05X}: {op:02X}           {label}")

    # INC/DEC/PUSH/POP register inc/decs
    elif op >= 0x40 and op <= 0x4F:
        rd = op - 0x40
        ops = ["INC", "DEC", "PUSH", "POP", "INC", "DEC", "INC", "DEC"]
        regs = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
        print(f"@{addr-1:05X}: {op:02X}         {ops[rd//2]} {regs[rd%8]}")

    # MOV reg, imm8 (B0-B7) or MOV reg, imm16 (B8-BF for word regs)
    elif op in (0xB0, 0xB1, 0xB2, 0xB3):
        rname = ["AL", "CL", "DL", "BL"][op - 0xB0]
        val = data[pos]; pos += 1
        print(f"@{addr-1:05X}: {op:02X} {val:02X}     MOV {rname},#{val:#04X}")
    elif op in (0xB4, 0xB5, 0xB6, 0xB7):
        rname = ["AH", "CH", "DH", "BH"][op - 0xB4]
        val = data[pos]; pos += 1
        print(f"@{addr-1:05X}: {op:02X} {val:02X}     MOV {rname},#{val:#04X}")
    elif op in (0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF):
        rname = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"][op - 0xB8]
        val = int.from_bytes(bytes([data[pos], data[pos+1]]), "little"); pos += 2
        print(f"@{addr-1:05X}: {op:02X} ?? ??      MOV {rname},{val:#06X}")

    # LDS / LES
    elif op == 0xC5:
        modrm = data[pos]; pos += 1
        print(f"@{addr-1:05X}: C5 {modrm:02X}       LDS r/m,mem32")
    elif op == 0xC4:
        modrm = data[pos]; pos += 1
        print(f"@{addr-1:05X}: C4 {modrm:02X}       LES r/m,mem32")

    # XCHG AX,r/m and similar single-byte forms
    elif op >= 0x90 and op <= 0x97:
        xchg_reg = ["CX", "DX", "BX", "", "BP", "SI", "DI"][op - 0x91]
        if not xchg_reg:
            print(f"@{addr-1:05X}: {op:02X}           XCHG AX,SP")
        else:
            print(f"@{addr-1:05X}: {op:02X}           XCHG AX,{xchg_reg}")

    # Group 1/2/3/4 with ModR.M byte
    elif op in (0xFE, 0xF6, 0xF7):
        grp_name = "GRP6" if op == 0xFE else ("GRP3/4 byte" if op == 0xF6 else "GRP3/4 word")
        modrm = data[pos]; pos += 1
        grp = (modrm >> 3) & 7
        print(f"@{addr-1:05X}: {op:02X} {modrm:02X}   {grp_name}[{grp}]")

    # CALL rel16
    elif op == 0xE8:
        val = int.from_bytes(bytes([data[pos], data[pos+1]]), "little"); pos += 2
        target = addr + val
        print(f"@{addr-2:05X}: E8 ?? ??         CALL rel16 -> @{target:05X}")

    # JMP rel16
    elif op == 0xE9:
        val = int.from_bytes(bytes([data[pos], data[pos+1]]), "little"); pos += 2
        target = addr + val
        print(f"@{addr-2:05X}: E9 ?? ??         JMP rel16 -> @{target:05X}")

    # FAR JMP/CALL
    elif op == 0xEA:
        iip = int.from_bytes(bytes([data[pos], data[pos+1]]), "little"); ipos = pos + 2
        cs = int.from_bytes(bytes([data[ipos], data[ipos+1]]), "little"); ipos += 2
        print(f"@{addr-2:05X}: EA ??? ???       JMP FAR {cs}:{iip:04X}")
    elif op == 0x9A:
        iip = int.from_bytes(bytes([data[pos], data[pos+1]]), "little"); ipos = pos + 2
        cs = int.from_bytes(bytes([data[ipos], data[ipos+1]]), "little"); ipos += 2
        print(f"@{addr-2:05X}: 9A ??? ???       CALL FAR {cs}:{iip:04X}")

    # Short jumps
    elif op == 0xEB:
        disp = data[pos]; pos += 1
        target = addr + (disp if disp < 128 else disp - 256)
        print(f"@{addr-1:05X}: EB {disp:02X}      JMP short @{target:05X}")
    elif op in (0x74,):
        disp = data[pos]; pos += 1
        target = addr + (disp if disp < 128 else disp - 256)
        print(f"@{addr-1:05X}: 74 {disp:02X}      JE/JZ short @{target:05X}")
    elif op in (0x75,):
        disp = data[pos]; pos += 1
        target = addr + (disp if disp < 128 else disp - 256)
        print(f"@{addr-1:05X}: 75 {disp:02X}      JNE/JNZ short @{target:05X}")
    elif op in (0xE0,):
        disp = data[pos]; pos += 1
        tgt = addr + 2 + (disp if disp < 128 else disp - 256)
        print(f"@{addr-1:05X}: E0 {disp:02X}      LOOPNE short @{tgt:05X}")
    elif op in (0xE1,):
        disp = data[pos]; pos += 1
        tgt = addr + 2 + (disp if disp < 128 else disp - 256)
        print(f"@{addr-1:05X}: E1 {disp:02X}      LOOPE short @{tgt:05X}")
    elif op in (0xE2,):
        disp = data[pos]; pos += 1
        tgt = addr + 2 + (disp if disp < 128 else disp - 256)
        print(f"@{addr-1:05X}: E2 {disp:02X}      LOOP short @{tgt:05X}")
    elif op in (0xE3,):
        disp = data[pos]; pos += 1
        tgt = addr + 2 + (disp if disp < 128 else disp - 256)
        print(f"@{addr-1:05X}: E3 {disp:02X}      JCXZ short @{tgt:05X}")

    # Special instructions
    elif op == 0xCC:
        print(f"@{addr-1:05X}: CC             INT 3")
    elif op == 0xCD:
        vec = data[pos]; pos += 1
        print(f"@{addr-1:05X}: CD {vec:02X}       INT #{vec:#04X}")
    elif op == 0xFA:
        print(f"@{addr-1:05X}: FA             CLI")
    elif op == 0xFB:
        print(f"@{addr-1:05X}: FB             STI")
    elif op == 0xFC:
        print(f"@{addr-1:05X}: FC             CLC")
    elif op == 0xFD:
        print(f"@{addr-1:05X}: FD             STD")
    elif op == 0xF9:
        print(f"@{addr-1:05X}: F9             STC")
    elif op == 0xF4:
        print(f"@{addr-1:05X}: F4             HLT")
    elif op == 0xF5:
        print(f"@{addr-1:05X}: F5             CMC")
    elif op >= 0xF0 and op <= 0xF3:
        prefixes = ["LOCK", "INT1", "REPNE", "REP"]
        print(f"@{addr-1:05X}: {op:02X}         PREFIX ({prefixes[op-0xF0]})")

    # ADD/SUB/etc with ModR.M byte for simple cases
    elif op in (0x00, 0x01, 0x02, 0x03, 0x08, 0x09, 0x0A, 0x0B,
                0x10, 0x11, 0x12, 0x13, 0x18, 0x19, 0x1A, 0x1B,
                0x20, 0x21, 0x22, 0x23, 0x28, 0x29, 0x2A, 0x2B,
                0x30, 0x31, 0x32, 0x33, 0x38, 0x39, 0x3A, 0x3B):
        modrm = data[pos]; pos += 1
        mnem_map = {
            0x00: "ADD", 0x08: "OR", 0x10: "ADC", 0x18: "SBB",
            0x20: "AND", 0x28: "SUB", 0x30: "XOR", 0x38: "CMP"
        }
        base_idx = ((op - 0x00) // 8) * 8 if op < 0x40 else 0
        group = [0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38][base_idx >> 3]
        mnemonic = mnem_map.get(group, f"OP{op:#x}")
        print(f"@{addr-1:05X}: {op:02X} {modrm:02X}   {mnemonic} r/m,r")

    # MOV forms
    elif op == 0x8A:
        modrm = data[pos]; pos += 1
        print(f"@{addr-1:05X}: 8A {modrm:02X}     MOV AL,r/m")
    elif op == 0x8B:
        modrm = data[pos]; pos += 1
        print(f"@{addr-1:05X}: 8B {modrm:02X}     MOV r16,r/m")
    elif op in (0x86, 0x87):
        xchg_type = "BYTE" if op == 0x86 else "WORD"
        modrm = data[pos]; pos += 1
        reg_f = (modrm >> 3) & 7
        rm_f = modrm & 7
        regs = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
        print(f"@{addr-1:05X}: {op:02X} {modrm:02X}   XCHG {regs[reg_f]},r/m{xchg_type}")

    # General Group 1/2 with ModR.M byte for other ops
    elif op >= 0x80 and op <= 0x8F:
        modrm = data[pos]; pos += 1
        reg_field = (modrm >> 3) & 7
        rm_field = modrm & 7
        print(f"@{addr-1:05X}: {op:02X} {modrm:02X}   MODR/M [{(modrm>>6)&0b11},{reg_field},{rm_field}]")

    # ADD r/m,r immediate variants
    elif op in (0xC0, 0xC1):
        grp_name = "GRP2 imm8" if op == 0xC0 else "GRP2 imm16"
        modrm = data[pos]; pos += 1
        print(f"@{addr-1:05X}: {op:02X} ?? {modrm:02X}   {grp_name}")

    # Unknown opcode
    else:
        print(f"@{addr-1:05X}: {op:02X}           ?unknown?")


print("\n\n=== Summary of OUT DX,AL accesses ===")
# Re-scan just for OUT instructions
pos = phys_start
while pos < min(phys_start + 0x40, len(data)):
    addr = pos; op = data[pos]; pos += 1
    if op == 0xEE or op == 0xEF:
        modrm = data[pos]; pos += 1
        print(f"  @{addr:05X}: {'OUT DY,AX' if op==0xEF else 'OUT DX,AL'} [ModR.M={modrm:#04X}]")
    elif op in (0xEC, 0xED):
        modrm = data[pos]; pos += 1
        mnem = "IN AL,DY" if op == 0xEC else "IN AX,DY"
        print(f"  @{addr:05X}: {mnem} [ModR.M={modrm:#04X}]")
