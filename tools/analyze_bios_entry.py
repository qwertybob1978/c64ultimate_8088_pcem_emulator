#!/usr/bin/env python3
from pathlib import Path

# Read BIOS ROM
rom = Path("third_party/roms/genxt/pcxt.rom").read_bytes()
print(f"ROM size: {len(rom)} bytes (0x{len(rom):X})")

# Check ROM header/entry
print(f"\nROM entry point (first 256 bytes):")
for i in range(0, min(256, len(rom)), 16):
    hex_part = " ".join(f"{rom[j]:02X}" for j in range(i, min(i+16, len(rom))))
    ascii_part = "".join(chr(rom[j]) if 32 <= rom[j] < 127 else "." for j in range(i, min(i+16, len(rom))))
    print(f"E{i:03X}  {hex_part:<48} {ascii_part}")

# Guess: What's at CPU entry F000:0000?
# CPU starts with CS:IP = F000:0000 (from BIOS config)
# But ROM is mapped at FE000 (physical = F000*16 + 0000 = F0000)
# So F000:0000 = 0xF0000 in physical addressing
# But our BIOS loads at FE000 = 0xFE000 = F000*16 + 0xE000
# So: F000:0000 in the guest actually maps to offset 0 in the ROM! YES!
# And F000:E003 maps to offset 0xE003... wait no.

# Let me recalculate:
# Seg:Off in real mode = Seg*16 + Off (physical)
# BIOS loaded at physical 0xFE000
# That means:
# - F000:0000 = 0xF0000 (not at BIOS!)
# - FE00:0000 = 0xFE000 (BIOS start)
# - F000:E000 = 0xFE000 (BIOS start!)
# - F000:E003 = 0xFE003 (offset 3 in BIOS)

# So F000:E000-FFFF is the BIOS ROM (8 KB = 0x2000)
# F000:E000 = phys 0xFE000 = offset 0
# F000:E001 = offset 1
# F000:E002 = offset 2
# F000:E003 = offset 3 ✓

print(f"\n\n=== ADDRESS MAPPING ===")
print(f"F000:E000 (BIOS start) = physical 0xFE000 = file offset 0")
print(f"F000:E003 (fault) = physical 0xFE003 = file offset 3 = 'e' from banner")
print(f"F000:FFFF = physical 0xFFFFF = file offset 0x1FFF (end of 8KB)")

print(f"\n=== CONTROL FLOW HYPOTHESIS ===")
print(f"Execution reached F000:E003, which is data (banner string)")
print(f"This means either:")
print(f"1. CPU is executing from wrong address (program counter corruption)")
print(f"2. CPU jumped/returned to data region (stack/vector corrupted)")
print(f"3. BIOS code at earlier addresses intentionally reads from E003")

print(f"\n=== CHECKING BIOS RESET VECTOR ===")
# CPU reset vector is at FFFF:0000
# In real mode, that's physical 0xFFF00
# In our setup, F000:F000 = 0xFFF00... wait no
# F000*16 + F000 = 0xF0000 + 0xF000 = 0xFF000 (close!)
# Actually FFF0:0000 = 0xFFF00 is standard
# But our config has it at F000:0000

print(f"\nLooking for code patterns near offset 0...")
for i in range(0, 64, 2):
    byte1 = rom[i]
    byte2 = rom[i+1] if i+1 < len(rom) else 0
    # Try to decode as 8088 instructions
    print(f"E{i:03X}:  {byte1:02X} {byte2:02X}", end="")
    
    # Common 8088 opcodes
    if byte1 == 0x55:
        print(" (PUSH BP)")
    elif byte1 == 0x89:
        print(" (MOV ...)")
    elif byte1 == 0xEB:
        print(" (JMP short)")
    elif byte1 == 0xE9:
        print(" (JMP far)")
    elif byte1 == 0x90:
        print(" (NOP)")
    elif byte1 == 0xC3:
        print(" (RET)")
    else:
        print()
