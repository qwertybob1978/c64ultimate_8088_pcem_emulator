#!/usr/bin/env python3
"""Extract P1/P2 byte diagnostic variables from compiled cartridge."""
from pathlib import Path

# CRT is compiled cartridge. Boot diagnostics are in bank 0 or 1.
# hwtest.s has BSS for:
#   boot_prev2_bytes[4] at some offset
#   boot_prev_bytes[4] at some offset
# 
# Since we don't have symbol table easily accessible, we need to find them
# by pattern matching in the compiled binary.

crt = Path("build/c64x86.crt").read_bytes()
print(f"CRT size: {len(crt)} bytes")

# CRT format: 16-byte header, then 8 KB per bank
# Header: 'CTRRIP63', version, hardware type, number of chips
#         Then chip packets (type + size + data)

# Magic Desk format typically stores ROM in first chip packet
# Let's look for the 0xAA55 or JMP signature

# Actually, easier approach: look for the banner string which we know is at E003
# If we find it, we can search nearby for diagnostic variables

# The banner "ener" is the sequence 65 6E 65 72
banner_sig = bytes([0x65, 0x6E, 0x65, 0x72])

positions = []
for i in range(len(crt) - 4):
    if crt[i:i+4] == banner_sig:
        positions.append(i)

print(f"\nFound 'ener' signature at {len(positions)} position(s):")
for pos in positions:
    # Show context around it
    start = max(0, pos - 32)
    end = min(len(crt), pos + 32)
    context = crt[start:end]
    
    print(f"\nOffset 0x{pos:04X}:")
    for i, b in enumerate(context):
        if i % 16 == 0:
            print(f"  {start+i:04X}: ", end="")
        print(f"{b:02X} ", end="")
        if (i + 1) % 16 == 0:
            print()

# Now look for likely diagnostic variable locations
# boot_prev_bytes should contain recent instruction bytes
# boot_prev2_bytes should contain instruction bytes from 2 steps prior

# Strategy: scan for sequences of data bytes that might represent instructions
# Common patterns: JMP (EA), MOV (B8, 89, 8B), NOP (90), RET (C3), etc.

print("\n\nSearching for diagnostic variable clusters...")

# Look for clusters of plausible instruction bytes
# Pattern: 4 bytes that could be instruction opcodes
instruction_opcodes = {
    0x90: "NOP", 0xC3: "RET", 0xC9: "LEAVE", 
    0xEA: "JMP", 0xE9: "JMP",
    0x89: "MOV", 0x8B: "MOV", 0xB8: "MOV", 0xB9: "MOV",
    0xAA: "STOSB", 0xAC: "LODSB",
    0x50: "PUSH", 0x58: "POP",
    0x20: " ", 0x47: "G", 0x65: "e", 0x6E: "n",  # banner chars
    0x04: "ADD",
}

print("\nLikely diagnostic locations (4-byte sequences with opcode-like values):")
for i in range(0, len(crt) - 4, 1):
    b = crt[i:i+4]
    # Check if at least 2-3 bytes are plausible instruction bytes
    opcode_count = sum(1 for byte in b if byte in instruction_opcodes or byte == 0x00 or byte == 0xFF)
    if opcode_count >= 2:
        print(f"  0x{i:04X}: {' '.join(f'{x:02X}' for x in b)}")
        if i > 100000:  # Limit output
            print("  ... (truncated)")
            break
