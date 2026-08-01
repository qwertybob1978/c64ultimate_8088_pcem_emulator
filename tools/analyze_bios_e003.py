#!/usr/bin/env python3
from pathlib import Path

# Read BIOS ROM
rom = Path("third_party/pcem-roms/genxt/pcxt.rom").read_bytes()
print(f"ROM size: {len(rom)} bytes (0x{len(rom):X})")

# F000:E003 = physical FE000 + E003 = FE003
# But ROM is loaded at FE000, so offset in ROM is E003
offset = 0xE003
print(f"\nOffset in ROM: 0x{offset:04X} (decimal {offset})")
print(f"File exists: {rom is not None}")

if offset + 100 <= len(rom):
    # Show context around E003
    print(f"\nBytes at E003 region (64 bytes before and 64 after):")
    start = max(0, offset - 64)
    end = min(len(rom), offset + 64)
    
    for i in range(start, end, 16):
        hex_part = " ".join(f"{rom[j]:02X}" if j < len(rom) else "  " for j in range(i, min(i+16, len(rom))))
        ascii_part = "".join(chr(rom[j]) if 32 <= rom[j] < 127 else "." for j in range(i, min(i+16, len(rom))))
        marker = " <--" if i <= offset < i+16 else ""
        print(f"E{i:03X}  {hex_part:<48} {ascii_part}{marker}")
else:
    print(f"Offset out of range")

# Now let's look for the banner string "ener" (65 6E 65 72)
print(f"\n\nSearching for banner string (65 6E 65 72 = 'ener')...")
needle = bytes([0x65, 0x6E, 0x65, 0x72])
pos = rom.find(needle)
if pos >= 0:
    print(f"Found at file offset: 0x{pos:04X}")
    print(f"In logical address: F000:E{pos:03X}")
    
    print(f"\nContext around banner (offset 0x{pos:04X}):")
    for i in range(max(0, pos-32), min(len(rom), pos+48), 16):
        hex_part = " ".join(f"{rom[j]:02X}" if j < len(rom) else "  " for j in range(i, min(i+16, len(rom))))
        ascii_part = "".join(chr(rom[j]) if 32 <= rom[j] < 127 else "." for j in range(i, min(i+16, len(rom))))
        marker = " <-- BANNER" if i <= pos < i+16 else ""
        print(f"E{i:03X}  {hex_part:<48} {ascii_part}{marker}")
else:
    print("Banner not found!")

# Look for any references or context clues
print(f"\n\nLooking for full bannerstring pattern...")
# Common banner patterns
patterns = [
    ("Generic", bytes([0x47, 0x65, 0x6E, 0x65, 0x72, 0x69, 0x63])),  # "Generic"
    ("XT", bytes([0x58, 0x54])),  # "XT"
]

for name, pattern in patterns:
    pos = rom.find(pattern)
    if pos >= 0:
        print(f"\n'{name}' at offset 0x{pos:04X}:")
        for i in range(max(0, pos-16), min(len(rom), pos+32)):
            c = rom[i]
            print(f"  0x{i:04X}: {c:02X} {repr(chr(c)) if 32 <= c < 127 else '.'}")
