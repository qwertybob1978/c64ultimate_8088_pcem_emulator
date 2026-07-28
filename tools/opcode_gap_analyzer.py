#!/usr/bin/env python3
"""Analyze cpu8088.json for coverage gaps vs Intel 8088 SDM specification."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config_path = ROOT / "config" / "cpu8088.json"
data = json.loads(config_path.read_text())

# Parse defined ranges from config (values are DECIMAL strings!)
defined_ranges = set()
range_info = {}
for entry in data["opcodes"]:
    first = int(entry["first"])
    last = int(entry["last"])
    mnemonic = entry.get("mnemonic", "?")
    for b in range(first, last + 1):
        defined_ranges.add(b)
        range_info[b] = mnemonic

print("=" * 90)
print(f"DEFINED OPCODES ({len(defined_ranges)} total out of 256 possible):")
print("=" * 90)

# Group consecutive bytes by handler for display
groups = []
current_mnem = None
current_range = None
for b in sorted(range_info.keys()):
    mnem = range_info[b]
    if mnem != current_mnem:
        if current_range is not None:
            groups.append((current_range[0], current_range[-1], current_mnem))
        current_range = [b]
        current_mnem = mnem
    else:
        current_range.append(b)
if current_range is not None:
    groups.append((current_range[0], current_range[-1], current_mnem))

for start, end, mnem in groups:
    hex_start = f"${start:02X}"
    hex_end = f"${end:02X}" if end != start else ""
    print(f"  {hex_start:>7s} to {hex_end:<7s}: {mnem}")

# Now compute gaps - opcodes NOT defined in config
gaps = [b for b in range(256) if b not in defined_ranges]
print("\n" + "=" * 90)
print(f"GAPS ({len(gaps)} undefined single-byte opcodes):")
print("=" * 90)

# Intel 8088/8086 opcode map reference
INTEL_8088_MAP = {
    # Standard instructions that SHOULD be implemented but aren't in our JSON
    0x24: ("AND AL,r/m8", "AL & r/m8"),
    0x2C: ("SUB AL,r/m8", "AL -= r/m8"),
    0x34: ("XOR AL,imm8", "AL ^= imm8"),
    0x3A: ("CMP AL,r/m8", "AL - r/m8"),
    
    # CBW/CWD - CRITICAL MISSING! These caused the crash at $98
    0x98: ("CBW", "Convert Byte (AL) to Word (AX) - sign extend AL into AX"),
    0x99: ("CWD", "Convert Word (AX) to Doubleword (DX:AX) - sign extend AX into DX:AX"),
    
    # INC/DEC r/m8 single-byte forms (not via GRP4 modrm!)
    0xF6: ("INC r/m8", "Increment byte memory/register operand"),
    0xFE: ("DEC r/m8", "Decrement byte memory/register operand"),
    
    # Shift/Rotate with immediate count (only CL form exists at D0-D3?)
    0xD4: ("AAM", "ASCII adjust after multiplication"),
    0xD5: ("AAD", "ASCII adjust before addition"),
    
    # Single-byte IN/OUT variants  
    0xE4: ("IN AL,imm8", "Input from port to AL"),
    0xE5: ("OUT imm8,AL", "Output from AL to port"),
    0xEC: ("IN AL,DX", "Input from DX port to AL"),
    0xED: ("IN AX,DX", "Input from DX port to AX"),
    0xEE: ("OUT DX,AL", "Output from AL to DX port"),
    0xEF: ("OUT DX,AX", "Output from DX port to AX"),
    
    # String operations with rep prefix would need ModR/M handling
    
    # WAIT/FWAIT
    0x9B: ("WAIT", "Wait for coprocessor signal"),
}

print("\n--- GAPS THAT ARE VALID 8088 INSTRUCTIONS ---")
for gap_byte in sorted(gaps):
    intel_name = INTEL_8088_MAP.get(gap_byte)
    if intel_name:
        print(f"  ${gap_byte:02X}: {intel_name[0]:<20s} | {intel_name[1]} *** NEEDS HANDLER ***")

# Check which gaps are actually reserved/unpredictable on real 8088
RESERVED_ON_8088 = {
    # Bytes that were undefined/reserved on original 8088 but later became instructions
    0x0F: "Two-byte opcode escape - not valid on pure 8088!",
    0x38: "Undefined on 8088, used as two-byte opcode escape in 286+",
    0x3C: "CMP AL,r/m8 - defined in 80186+ but NOT on original 8088!",
    0x7E: "JLE rel8 - should be covered by Jcc range?",
    0xA0: "MOV AL,moffs8",
    0xA1: "MOV AX,moffs16", 
    0xA2: "MOV moffs8,AL",
    0xA3: "MOV moffs16,AX",
    0xC0: "GRP1 r/m8,imm8 (shift/rotate immediate)",
    0xD0: "GRP1 r/m8,1",
    0xD1: "GRP1 r/m8,CL",
    0xD2: "GRP1 r/m8,CL (byte version)",  
    0xD3: "GRP1 r/m8,CL (word version)",
    0xF0: "LOCK prefix - not a standalone instruction!",
    0xF2: "REPNE/REPNZ prefix",
    0xF3: "REP/REPE/REPZ prefix",
}

print("\n--- GAPS WITH KNOWN MEANINGS (from Intel SDM reference) ---")
all_known_gaps = set(INTEL_8088_MAP.keys()) | RESERVED_ON_8088.keys()
for gap_byte in sorted(all_known_gaps):
    if gap_byte in gaps:
        intel_info = INTEL_8088_MAP.get(gap_byte) or ("UNKNOWN", "")
        note = RESERVED_ON_8088.get(gap_byte, "")
        marker = "*** CRITICAL ***" if gap_byte == 0x98 else ""
        print(f"  ${gap_byte:02X}: {intel_info[0]:<25s} | {note}")

# Summary of what's needed for boot path
print("\n" + "=" * 90)
print("BOOT PATH REQUIREMENTS:")
print("=" * 90)
critical_missing = [0x98]  # CBW caused the crash at CS=0000 IP=7351
other_boot_needed = [0x9B, 0xE4, 0xE5, 0xEC, 0xED, 0xEE, 0xEF, 0xA0, 0xA1, 0xA2, 0xA3]

print(f"\n*** IMMEDIATELY NEEDED (caused current crash): ***")
for b in critical_missing:
    name, desc = INTEL_8088_MAP[b]
    print(f"  ${b:02X} ({name}): {desc}")

print(f"\n*** LIKELY NEEDED FOR BIOS BOOT SEQUENCE: ***")
for b in other_boot_needed:
    if b in gaps and b in INTEL_8088_MAP:
        name, desc = INTEL_8088_MAP[b]
        print(f"  ${b:02X} ({name}): {desc}")
