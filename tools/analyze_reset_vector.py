#!/usr/bin/env python3
from pathlib import Path

rom = Path("third_party/roms/genxt/pcxt.rom").read_bytes()

# FFFF:0000 = physical 0xFFFF0
# But ROM is 8KB loaded at physical 0xFE000-0xFFFFF (0xFE000 + 0x2000 - 1 = 0xFFFF)
# So offset in ROM: 0xFFFF0 - 0xFE000 = 0x1FF0

print(f"ROM size: 0x{len(rom):X} bytes")
print(f"BIOS @ physical 0xFE000")
print(f"FFFF:0000 @ physical 0xFFFF0")
print(f"Offset in ROM: 0xFFFF0 - 0xFE000 = 0x{0xFFFF0 - 0xFE000:X}")

reset_offset = 0xFFFF0 - 0xFE000
print(f"\nBytes at CPU reset entry (FFFF:0000, offset 0x{reset_offset:X}):")
for i in range(max(0, reset_offset - 16), min(len(rom), reset_offset + 32)):
    print(f"E{i:03X}: {rom[i]:02X}")

# Also check F000:E000
print(f"\n\nBytes at F000:E000 (BIOS nominal start, offset 0x0000):")
for i in range(0, min(len(rom), 64)):
    print(f"E{i:03X}: {rom[i]:02X}")
    
# Check if there's a jump/call at start
print(f"\n\nInterpreting as 8088 code at offset 0x{reset_offset:X}:")
if reset_offset + 5 < len(rom):
    for i in range(reset_offset, reset_offset + 5):
        print(f"  {rom[i]:02X}", end="")
    print()
    
    # Check for common entry instructions
    b0 = rom[reset_offset]
    b1 = rom[reset_offset + 1] if reset_offset + 1 < len(rom) else 0
    b2 = rom[reset_offset + 2] if reset_offset + 2 < len(rom) else 0
    b3 = rom[reset_offset + 3] if reset_offset + 3 < len(rom) else 0
    b4 = rom[reset_offset + 4] if reset_offset + 4 < len(rom) else 0
    
    # Check for EA 50 00 F0 (JMP FAR F000:0050)
    if b0 == 0xEA:
        ip_lo, ip_hi, cs_lo, cs_hi = b1, b2, b3, b4
        far_ip = (ip_hi << 8) | ip_lo
        far_cs = (cs_hi << 8) | cs_lo
        print(f"  -> Detected: JMP FAR {far_cs:04X}:{far_ip:04X}")
    elif b0 == 0x55:
        print(f"  -> Detected: PUSH BP")
    elif b0 == 0xE9:
        offset = (b2 << 8) | b1
        print(f"  -> Detected: JMP short 0x{offset:04X}")
    else:
        print(f"  -> First byte 0x{b0:02X} (not standard entry)")
