"""Debug: dump raw bytes at known instruction locations."""
from pathlib import Path

rom = bytearray(Path("third_party/pcem-roms/genxt/pcxt.rom").read_bytes())

# Known offsets based on previous disassembly
# Physical FF44D = ROM offset 0x144D
# Physical FF44F = ROM offset 0x144F  
# Physical FF450 = ROM offset 0x1450

test_offsets = [0x1440, 0x1441, 0x1442, 0x1443, 0x1444, 0x1445, 0x1446, 0x1447, 
                0x1448, 0x1449, 0x144A, 0x144B, 0x144C, 0x144D, 0x144E, 0x144F,
                0x1450, 0x1451, 0x1452, 0x1453, 0x1454]

print(f"ROM size: {len(rom)} bytes")
print()

for off in test_offsets:
    phys_addr = off + 0xFE000
    b = rom[off] if off < len(rom) else 0xFF
    print(f"[{phys_addr:05X}] ROM offset={off:#06X} byte=${b:02X}")

print("\n\nExpected patterns:")
print("  EC = IN AL,dx (should be at FF450 -> offset 0x1450)")
print("  A8 $01 = TEST AL,#$01 (should be at FF44F or nearby)")
print("  FA = CLI (should be at FF44F)")
print("  75 xx = JNE rel8 (should be at FF44D)")
