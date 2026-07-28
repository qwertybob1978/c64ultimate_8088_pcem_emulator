#!/usr/bin/env python3
"""Dump RAM contents around actual crash region."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = ROOT / "build" / "guest-genxt.reu"
raw = data.read_bytes()

print(f"REU size: {len(raw):,d} bytes\n")

# Crash reported as CS=0000 IP=7351 -> physical = 0*16 + 0x7351 = 0x7351
crash_phys = 0x7351
boot_start = 0x7C00

print("=== CRASH ADDRESS: phys 0x7351 (CS=0000:IP=7351) ===")
for addr in range(crash_phys - 0x20, min(crash_phys + 0x20, len(raw)), 16):
    hex_str = ' '.join(f'{b:02X}' for b in raw[addr:min(addr+16, len(raw))])
    ascii_str = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in raw[addr:min(addr+16, len(raw))])
    print(f"{addr:04X}: {hex_str:<48s} |{ascii_str}|")

print("\n=== BOOT SECTOR REGION: phys 0x7C00-0x7FFF ===")
for addr in range(boot_start, min(boot_start + 0x100, len(raw)), 16):
    chunk_size = min(16, len(raw) - addr)
    hex_str = ' '.join(f'{b:02X}' for b in raw[addr:addr+chunk_size])
    ascii_str = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in raw[addr:addr+chunk_size])
    marker = ""
    # Check if this line has any non-zero bytes
    if any(b != 0 for b in raw[addr:addr+chunk_size]):
        marker = " <-- NON-ZERO!"
    print(f"{addr:04X}: {hex_str:<48s} |{ascii_str}|{marker}")

print("\n=== CONVENTIONAL RAM CHECK: 0x0000-0x01FF (INT VECTORS) ===")
for addr in range(0x0000, 0x0200, 16):
    hex_str = ' '.join(f'{b:02X}' for b in raw[addr:min(addr+16, len(raw))])
    ascii_str = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in raw[addr:min(addr+16, len(raw))])
    print(f"{addr:04X}: {hex_str:<48s} |{ascii_str}|")

# Count non-zero regions below A0000
print("\n=== MEMORY MAP: Non-zero regions below 0xA0000 ===")
in_region = False
region_start = 0
prev_byte = None
for i in range(min(len(raw), 0xA0000)):
    byte_val = raw[i]
    is_zero = (byte_val == 0)
    
    if not is_zero and not in_region:
        in_region = True
        region_start = i
    elif is_zero and in_region:
        in_region = False
        if (i - region_start) >= 8:  # Only show regions >= 8 bytes
            print(f"  0x{region_start:05X}-0x{i-1:05X} ({i-region_start:3d} bytes)")

if in_region:
    print(f"  0x{region_start:05X}-0x9FFFF ({0xA0000-region_start:3d} bytes)")
