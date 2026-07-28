#!/usr/bin/env python3
"""Analyze cpu8088.json for coverage gaps vs Intel 8088 SDM single-byte opcodes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config_path = ROOT / "config" / "cpu8088.json"
data = json.loads(config_path.read_text())

# Parse defined ranges from config
defined_ranges = []
for entry in data["opcodes"]:
    first = int(entry["first"])
    last = int(entry["last"])
    if first > last:
        raise ValueError(f"Invalid range: {entry}")
    defined_ranges.append((first, last, entry.get("mnemonic", "?")))

# Sort by first byte
defined_ranges.sort(key=lambda x: x[0])

print("=" * 80)
print("DEFINED OPCODE RANGES (sorted):")
print("=" * 80)
for first, last, mnemonic in defined_ranges:
    print(f"  ${first:02X}-$${last:02X} ({first:3d}-{last:3d}): {mnemonic}")

# Intel 8088 single-byte opcode map (standard instructions only)
# Format: (start_decimal, end_decimal, intel_mnemonic, notes)
intel_single_byte = [
    # ADD family
    (0, 3, "ADD r/m,r8/r16", ""),
    (4, 4, "ADD AL/AX,imm8/imm16", ""),
    
    # Segment pushes/pops  
    (6, 7, "PUSH ES / POP ES", ""),
    (14, 15, "PUSH CS / POP CS", "INVALID on real 8088 - reserved!"),
    (16, 17, "PUSH SS / POP SS", ""),
    (18, 19, "PUSH DS / POP DS", ""),
    
    # OR family
    (8, 11, "OR r/m,r8/r16", ""),
    (12, 12, "OR AL,imm8", ""),
    (13, 13, "OR AX,imm16", ""),
    
    # ADC family
    (20, 23, "ADC r/m,r8/r16", ""),  # Note: decimal 20-23 = hex $14-$17
    
    # SBB family
    (24, 27, "SBB r/m,r8/r16", ""),  # decimal 24-27 = hex $18-$1B
    
    # AND family
    (32, 35, "AND r/m,r8/r16", ""),  # decimal 32-35 = hex $20-$23
    
    # DAA
    (39, 39, "DAA", ""),  # decimal 39 = hex $27
    
    # SUB family
    (40, 43, "SUB r/m,r8/r16", ""),  # decimal 40-43 = hex $28-$2B
    
    # XOR family
    (48, 51, "XOR r/m,r8/r16", ""),  # decimal 48-51 = hex $30-$33
    
    # CMP family
    (56, 59, "CMP r/m,r8/r16", ""),  # decimal 56-59 = hex $38-$3B
    
    # INC/DEC r16
    (64, 71, "INC r16", ""),  # decimal 64-71 = hex $40-$47
    (72, 79, "DEC r16", ""),  # decimal 72-79 = hex $48-$4F
    
    # PUSH/POP r16
    (80, 87, "PUSH r16", ""),  # decimal 80-87 = hex $50-$57
    (88, 95, "POP r16", ""),   # decimal 88-95 = hex $58-$5F
    
    # CBW - THE CRITICAL MISSING OPCODE!
    (152, 152, "CBW", "*** MISSING *** Convert Byte to Word"),
    
    # CWD - another critical missing opcode
    (159, 159, "CWD", "*** MISSING *** Convert Word to Doubleword"),
    
    # Jcc rel8
    (112, 127, "Jcc rel8", ""),  # decimal 112-127 = hex $70-$7F
    
    # GRP1 immediate
    (128, 131, "GRP1 imm8", ""),  # decimal 128-131 = hex $80-$83
    
    # TEST modrm
    (132, 133, "TEST r/m,reg / TEST reg,r/m", ""),  # decimal 132-133 = hex $84-$85
    
    # XCHG
    (134, 135, "XCHG r16,r/m16 / XCHG r/m16,r16", ""),  # decimal 134-135 = hex $86-$87
    
    # MOV modrm
    (136, 139, "MOV r/m,r8/r16 etc.", ""),  # decimal 136-139 = hex $88-$8B
    
    # MOV segment registers
    (140, 140, "MOV Sreg,r/m16", ""),  # decimal 140 = hex $8C
    (142, 142, "MOV r/m16,Sreg", ""),  # decimal 142 = hex $8E
    
    # NOP
    (144, 144, "NOP", ""),  # decimal 144 = hex $90
    
    # INT3
    (204, 204, "INT 3", ""),  # decimal 204 = hex $CC
    
    # INT imm8
    (205, 205, "INT imm8", ""),  # decimal 205 = hex $CD
    
    # INTO
    (206, 206, "INTO", ""),  # decimal 206 = hex $CE
    
    # IRET
    (207, 207, "IRET", ""),  # decimal 207 = hex $CF
    
    # Shift/Rotate family
    (208, 211, "ROL/ROR/RCL/RCR r/m,cl/1", ""),  # decimal 208-211 = hex $D0-$D3
    
    # INC/DEC r/m8 (single-byte forms)
    (244, 244, "INC/DEC r/m8 single-byte", ""),  # decimal 244-247 = hex $F4-$F7 - WAIT need to verify
    
    # LOOP/JCXZ
    (224, 227, "LOOPNZ/LOOPE/JCXZ rel8", ""),  # decimal 224-227 = hex $E0-$E3
    
    # CALL/JMP rel16/rel8
    (232, 232, "CALL rel16", ""),  # decimal 232 = hex $E8
    (233, 233, "JMP rel16", ""),   # decimal 233 = hex $E9
    (234, 234, "JMP ptr16:16", ""),  # decimal 234 = hex $EA
    (235, 235, "JMP rel8", ""),     # decimal 235 = hex $EB
    
    # IN/OUT families
    (228, 229, "IN acc,imm8 / OUT imm8,acc", ""),  # decimal 228-229 = hex $E4-$E5
    (230, 231, "IN DX,acc / OUT DX,acc", ""),       # decimal 230-231 = hex $E6-$E7... wait that's wrong
    
    # HLT
    (246, 246, "HLT", ""),  # decimal 246 = hex $F6? No wait...
    
    # More control instructions
    (247, 247, "CMC", ""),  # decimal 247 = hex $F7? 
    (248, 249, "GRP3 modrm", ""),  # decimal 248-249 = hex $F8-$F9? 
    
    # CLC/STC/CLI/STI/CLD/STD
    (250, 250, "CLC", ""),  # decimal 250 = hex $FA
    (251, 251, "STC", ""),  # decimal 251 = hex $FB
    (252, 252, "CLI", ""),  # decimal 252 = hex $FC
    (253, 253, "STI", ""),  # decimal 253 = hex $FD
    (254, 254, "CLD", ""),  # decimal 254 = hex $FE
    (255, 255, "STD", ""),  # decimal 255 = hex $FF
    
    # GRP4/GRP5 - need to check exact ranges
]

# Actually let me just compute gaps directly from defined_ranges
print("\n" + "=" * 80)
print("GAP ANALYSIS:")
print("=" * 80)

gaps = []
for i in range(len(defined_ranges) - 1):
    current_end = defined_ranges[i][1]
    next_start = defined_ranges[i+1][0]
    if next_start > current_end + 1:
        gap_start = current_end + 1
        gap_end = next_start - 1
        for byte_val in range(gap_start, gap_end + 1):
            intel_name = lookup_intel(byte_val)
            gaps.append((byte_val, intel_name))

def lookup_intel(opcode_dec):
    """Look up Intel SDM meaning of a single-byte opcode."""
    intel_map = {
        0x20: "AND r/m8,r8",  # Wait no - these are already covered at $20-$23 as AND family
        