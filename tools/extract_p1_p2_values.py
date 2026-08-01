#!/usr/bin/env python3
"""Extract P1/P2 diagnostic byte values from compiled binary."""
from pathlib import Path

# Load compiled cartridge
prg = Path("build/c64x86-hwtest.prg").read_bytes()

# PRG format: 2-byte load address, then code
# Usual C64 cartridge load address is $0801 for BASIC area
# But our program might have different load address

load_addr_lo = prg[0]
load_addr_hi = prg[1]
load_addr = (load_addr_hi << 8) | load_addr_lo
print(f"PRG load address: 0x{load_addr:04X}")

# Symbol table shows:
#   boot_prev2_bytes: 0x73B1
#   boot_prev_bytes: 0x73BB

boot_prev2_offset = 0x73B1 - load_addr
boot_prev_offset = 0x73BB - load_addr

print(f"boot_prev2_bytes offset in PRG: 0x{boot_prev2_offset:04X}")
print(f"boot_prev_bytes offset in PRG: 0x{boot_prev_offset:04X}")

if boot_prev2_offset + 2 < len(prg) and boot_prev2_offset >= 0:
    boot_prev2_b0 = prg[2 + boot_prev2_offset]
    boot_prev2_b1 = prg[2 + boot_prev2_offset + 1]
    boot_prev2_b2 = prg[2 + boot_prev2_offset + 2]
    boot_prev2_b3 = prg[2 + boot_prev2_offset + 3]
    print(f"\nboot_prev2_bytes at 0x{0x73B1:04X}:")
    print(f"  [0] = 0x{boot_prev2_b0:02X}")
    print(f"  [1] = 0x{boot_prev2_b1:02X}")
    print(f"  [2] = 0x{boot_prev2_b2:02X}")
    print(f"  [3] = 0x{boot_prev2_b3:02X}")
else:
    print(f"\nboot_prev2_bytes: offset out of range (file size: {len(prg)})")

if boot_prev_offset + 2 < len(prg) and boot_prev_offset >= 0:
    boot_prev_b0 = prg[2 + boot_prev_offset]
    boot_prev_b1 = prg[2 + boot_prev_offset + 1]
    boot_prev_b2 = prg[2 + boot_prev_offset + 2]
    boot_prev_b3 = prg[2 + boot_prev_offset + 3]
    print(f"\nboot_prev_bytes at 0x{0x73BB:04X}:")
    print(f"  [0] = 0x{boot_prev_b0:02X}")
    print(f"  [1] = 0x{boot_prev_b1:02X}")
    print(f"  [2] = 0x{boot_prev_b2:02X}")
    print(f"  [3] = 0x{boot_prev_b3:02X}")
else:
    print(f"\nboot_prev_bytes: offset out of range (file size: {len(prg)})")

# Try CRT too - it's a cartridge that contains the PRG code
print(f"\n\nTrying CRT cartridge...")
crt = Path("build/c64x86.crt").read_bytes()
print(f"CRT size: {len(crt)} bytes")

# Look for the pattern in CRT - might be copied multiple times across banks
# CRT format is complex; for now let's search for known boot_prev2_bytes pattern
# Look for a location containing the JMP instruction bytes we expect

# P1/P2 should contain recent instruction bytes
# Common 8088 instruction opcodes to search for:
# 90 = NOP, EA = JMP, 55 = PUSH, C3 = RET, 89/8B = MOV, etc.

# Let's search around where we expect BIOS banner data
banner_sig = b"Generic Turbo"
for i in range(len(crt) - len(banner_sig)):
    if crt[i:i+len(banner_sig)] == banner_sig:
        print(f"\nFound 'Generic Turbo' at CRT offset 0x{i:04X}")
        # Look nearby for diagnostic variables (BSS region)
        # They might be stored just before or after banner in cartridge ROM
