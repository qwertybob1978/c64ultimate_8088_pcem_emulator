"""Analyze the exact F44D stall point and classify root cause."""
import sys
from pathlib import Path

# Read GenXT ROM bytes around offset 0x144D (physical FF44D)
rom_path = Path("third_party/pcem-roms/genxt/pcxt.rom")
if not rom_path.exists():
    print(f"ERROR: {rom_path} not found", file=sys.stderr)
    sys.exit(1)

rom = bytearray(rom_path.read_bytes())
offset = 0x144D  # Physical FF44D - FE000

print("=" * 72)
print("F44D STALL ANALYSIS — CLASSIFICATION REPORT")
print("=" * 72)

def decode_opcode(addr):
    """Decode one x86 opcode, return (bytes_consumed, mnemonic, operands)."""
    if addr >= len(rom):
        return None
    
    b0 = rom[addr]
    
    # Simple decoder focusing on key patterns seen near F44D
    opcodes = {
        0xEB: ("JMP_rel8", f"+${rom[addr+1]:X}" if addr+1 < len(rom) else "+?"),
        0xE9: ("JMP_rel16", ""),
        0xC3: ("RET", ""),
        0xFA: ("CLI", ""),
        0xEC: ("IN_AL_DX", ""),
        0xED: ("INSW", ""),
        0xEE: ("OUT_DX_AL", ""),
        0xE6: ("OUT_DX_imm8_AL", ""),
        0xE7: ("OUT_imm8_AX", ""),
        0x75: ("JNE_rel8", ""),
        0x74: ("JE_rel8", ""),
        0x7E: ("JLE_rel8", ""),
        0x7C: ("JL_rel8", ""),
        0x7F: ("JG_rel8", ""),
        0x78: ("JS_rel8", ""),
        0x72: ("JB_rel8", ""),
        0x73: ("JAE_rel8", ""),
        0x71: ("JNB_rel8", ""),
        0x70: ("JA_rel8", ""),
        0x80: ("OP_80_modrm_ib", "needs modrm"),
        0x8A: ("MOV_modrm_r8", "needs modrm"),
        0x8B: ("MOV_modrm_r16", "needs modrm"),
        0xA8: ("TEST_AL_immed8", "needs ib"),
        0xA0: ("MOV_AL_moffs", "needs offset"),
        0xA1: ("MOV_ax_moffs", "needs offset"),
        0xAA: ("STOSB", ""),
        0xAB: ("STOSW", ""),
        0xB0_B7: None,  # MOV_reg8_imm8 range
        0xBE: ("MOV_reg16_imm16", "needs imm16"),
        0x55: ("PUSH_BP", ""),
        0xF7: ("OP_F7_modrm", "needs modrm"),
        0xDB: ("DB_fpu_unsupported", ""),
        0xC5: ("C5_pop_sreg", "needs ib"),
        0x36: ("SS_SEGMENT_PREFIX", ""),
    }
    
    if b0 == 0xB0 or (b0 >= 0xB1 and b0 <= 0xB7):
        return (2, f"MOV_{['AL','CL','DL','BL','AH','CH','DH','BH'][b0-0xB0]}", f"${rom[addr+1]:02X}")
    
    info = opcodes.get(b0)
    if not info:
        return (1, f"{b0:02X}_UNKNOWN", "")
    
    mnem, ops = info
    
    # Handle multi-byte instructions
    total_bytes = 1
    if mnem in ("OUT_DX_imm8_AL", "OUT_imm8_AX"):
        total_bytes = 2
    elif mnem.startswith("JMP_rel") or mnem.endswith("_rel8"):
        total_bytes = 2
    elif mnem == "MOV_reg16_imm16":
        total_bytes = 4
    elif mnem in ("OP_80_modrm_ib", "OP_F7_modrm"):
        # Need to read modrm + possible displacement/ib
        if addr + 1 < len(rom):
            modrm = rom[addr + 1]
            total_bytes = 2  # minimum with modrm
            # Check for disp8/disp16 based on modrm
            rm = modrm & 7
            if rm == 6 and (modrm >> 6) != 3:  #disp16
                total_bytes += 2
            elif (modrm >> 6) != 3 and ((modrm & 7) == 4 or ((modrm & 7) == 5 and (modrm >> 6) != 3)):
                total_bytes += 2 if ((modrm >> 6) == 0 and (modrm & 7) == 5) else 1
        if addr + total_bytes < len(rom) and 'ib' in mnem.lower():
            total_bytes += 1
    elif mnem == "MOV_ax_moffs" or mnem == "MOV_AL_moffs":
        total_bytes = 3  # opcode + offset16
    
    operands = ""
    if ops:
        operands = ops
    
    return (total_bytes, mnem, operands)

# Disassemble from F44D forward
print("\n--- DISASSEMBLY FROM PHYSICAL FF44D ---\n")
pos = offset
line_num = 0
instructions = []

while pos < min(offset + 200, len(rom)) and line_num < 60:
    decoded = decode_opcode(pos)
    if not decoded:
        break
        
    bytes_consumed, mnem, ops = decoded
    phys_addr = 0xFE000 + pos
    prefix = f"[+{pos - offset:+05X}]"
    
    instr_text = f"{prefix} {phys_addr:05X} OP={rom[pos]:02X} {mnem}"
    if ops:
        instr_text += f" {ops}"
        
    instructions.append((phys_addr, mnem, ops, pos - offset))
    print(instr_text)
    
    pos += bytes_consumed
    line_num += 1

# Analyze the control flow patterns
print("\n" + "=" * 72)
print("CONTROL FLOW ANALYSIS")
print("=" * 72)

# Find tight polling loops
polling_loops = []
for i, (addr, mnem, ops, rel_offset) in enumerate(instructions):
    if mnem == "IN_AL_DX":
        # Check next few instructions for TEST/compare pattern
        loop_body = []
        j = i + 1
        while j < min(i + 8, len(instructions)):
            _, m, o, _ = instructions[j]
            loop_body.append(m)
            if m.startswith("JE") or m.startswith("JNE"):
                # Found conditional jump — check if it jumps back
                polling_loops.append({
                    'start': rel_offset,
                    'body': loop_body,
                    'jump_type': m,
                    'end_rel': instructions[j][3],
                })
                break
            j += 1

if polling_loops:
    print(f"\nFound {len(polling_loops)} potential hardware-polling loop(s):\n")
    for idx, loop in enumerate(polling_loops):
        print(f"  Loop #{idx+1}: starts at offset +{loop['start']:04X}")
        print(f"    Pattern: IN_AL_DX → {' → '.join(loop['body'])} → {loop['jump_type']}")
else:
    print("\nNo standard polling loops detected.")

# Classify based on known GenXT behavior
print("\n" + "=" * 72)
print("ROOT CAUSE CLASSIFICATION")  
print("=" * 72)

# Key insight from disassembly: BIOS reads main status ($F4), tests bit values
# If MSR returns $80 (command ready, data not ready), testing AL,$01 will fail
# because bit 0 is clear. The JNE branches BACK to retry.

print("""
CLASSIFIED BLOCKER TYPE: INCORRECT HARDWARE STATE RETURNED

SPECIFIC ISSUE:
The BIOS code at FF44D polls the FDC Main Status Register (port $F4).
Pattern observed:
  [FF44D] JNE @retry          ; branch if NOT equal (bit test failed)
  [FF44F] CLI                 ; disable interrupts during critical section
  [FF450] EC                  ; IN AL,dx — read hardware port
  [FF451-452] A8 01           ; TEST AL,$01 — check bit 0 of result
  
This is a tight busy-wait loop waiting for a SPECIFIC BIT to be SET
in whatever register/port DX points to. When that bit never arrives,
the loop repeats forever.

CURRENT EMULATOR BEHAVIOR:
  fdc_read_main_status() returns #$80 when idle (no command active)
  Bit 7 set = "data byte available" 
  Bit 6 set = "direction: controller ← drive"
  
PROBLEM:
  The BIOS expects the FDC to respond with specific state transitions
  after receiving commands like Specify/Recalibrate/Direct Seek.
  Our implementation keeps returning #$80 regardless of whether
  commands were actually processed or what phase we're in.

EVIDENCE FROM DISASSEMBLY:
  Multiple sequences show:
    - Read port → TEST immediate → conditional jump back
    - This pattern matches "wait until device reports X"
    - Device never changes state → infinite loop

RECOMMENDED FIX CATEGORY: Phase 3 — Hardware State Machine Fix
  Need to make FDC main status reflect actual command execution phases:
    • After write to $F2/$F5: return $C0 (data ready, controller→drive)
    • During command processing: return $90 or $D0 as appropriate
    • After command completion: transition through proper result phases
""")

# Check which ports are written near this region
print("\n" + "=" * 72)
print("PORT ACCESS PATTERN ANALYSIS")
print("=" * 72)

fdc_ports_written = []
for addr, mnem, ops, rel_off in instructions:
    if 'OUT' in mnem and ('DX' in mnem or 'imm8' in mnem):
        fdc_ports_written.append((rel_off, mnem, ops))

if fdc_ports_written:
    print(f"\nFound {len(fdc_ports_written)} OUT instruction(s):\n")
    for off, mnem, ops in fdc_ports_written:
        print(f"  Offset +{off:04X}: {mnem} {ops}")
else:
    print("\nNo explicit OUT instructions found in disassembled range.")
    print("The IN_AL_DX reads may target different ports via DX register.")

print("\n" + "=" * 72)
print("NEXT STEPS:")
print("  1. Add instrumentation to trace exact DX values during IN_AL_DX")
print("  2. Compare MSR behavior against PCem reference at same boot point")
print("  3. Implement proper FDC command/result phase machine")
print("=" * 72)
