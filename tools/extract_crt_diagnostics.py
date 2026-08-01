#!/usr/bin/env python3
"""Extract diagnostic data from CRT cartridge file."""

import struct
import sys
from pathlib import Path

def parse_crt_file(crt_path):
    """Parse CRT file and extract cartridge RAM diagnostic values."""
    
    if not Path(crt_path).exists():
        print(f"ERROR: CRT file not found: {crt_path}")
        return
    
    with open(crt_path, 'rb') as f:
        # Read C64 CRT header
        sig = f.read(16)  # "C64 CARTRIDGE   "
        header_length = struct.unpack('>I', f.read(4))[0]
        version = struct.unpack('>H', f.read(2))[0]
        hw_type = struct.unpack('>H', f.read(2))[0]
        exrom = struct.unpack('>B', f.read(1))[0]
        game = struct.unpack('>B', f.read(1))[0]
        
        # Skip rest of header to position 64
        f.seek(64)
        
        print("=== C64 CRT File Analysis ===")
        print(f"Hardware Type: {hw_type} (Magic Desk = 19)")
        print(f"EXROM: {exrom}, GAME: {game}")
        print()
        
        # Parse CHIP packages
        chips = []
        offset = 64
        chip_num = 0
        
        while offset < Path(crt_path).stat().st_size:
            f.seek(offset)
            chip_header = f.read(16)
            
            if len(chip_header) < 16 or chip_header[:4] != b'CHIP':
                break
            
            chip_size = struct.unpack('>I', chip_header[4:8])[0]
            chip_type = struct.unpack('>H', chip_header[8:10])[0]
            chip_bank = struct.unpack('>H', chip_header[10:12])[0]
            chip_addr = struct.unpack('>H', chip_header[12:14])[0]
            
            chip_data_offset = offset + 16
            chips.append({
                'num': chip_num,
                'type': chip_type,
                'bank': chip_bank,
                'addr': chip_addr,
                'size': chip_size,
                'data_offset': chip_data_offset,
                'offset': offset,
            })
            
            type_name = "RAM" if chip_type == 0 else f"ROM" if chip_type == 1 else f"?"
            print(f"CHIP {chip_num}: bank={chip_bank:3d} type={chip_type:2d} ({type_name:3s}) "
                  f"addr=${chip_addr:04X} size={chip_size:6d} bytes")
            
            offset += 16 + chip_size
            chip_num += 1
        
        print()
        print("=== Looking for boot_prev2_* diagnostic values ===")
        print()
        
        # The hwtest code and diagnostic BSS data should be in one of the ROM banks
        # Look for the boot_prev2_* variables which should contain diagnostic state
        
        # boot_fault_cs should be F000 (last known fault location)
        # boot_prev2_cs should also be F000
        # boot_fault_bytes should be "ener" (0x65 0x6E 0x65 0x72)
        
        found_diagnostics = False
        
        for chip in chips:
            print(f"Chip {chip['num']}: bank={chip['bank']}, type={chip['type']}, size={chip['size']}")
            
            f.seek(chip['data_offset'])
            data = f.read(min(1024, chip['size']))  # Read up to 1KB
            
            # Look for F000 pattern (boot_fault_cs or boot_prev2_cs)
            for i in range(len(data) - 3):
                if data[i:i+2] == b'\x00\xf0':  # F000 in little-endian
                    # Found a potential F000 reference
                    print(f"  Found F0 00 at offset ${i:04X}")
                    
                    # Check surrounding context
                    start = max(0, i - 16)
                    end = min(len(data), i + 32)
                    context = data[start:end]
                    context_hex = ' '.join(f'{b:02X}' for b in context)
                    context_ascii = ''.join(chr(b) if 32 <= b < 127 else '.' for b in context)
                    print(f"    {context_hex}")
                    print(f"    {context_ascii}")
                    found_diagnostics = True
            
            # Look for "ener" pattern (boot_fault_bytes)
            if b'ener' in data:
                idx = data.find(b'ener')
                print(f"  Found 'ener' at offset ${idx:04X}")
                start = max(0, idx - 8)
                end = min(len(data), idx + 16)
                context = data[start:end]
                context_hex = ' '.join(f'{b:02X}' for b in context)
                print(f"    {context_hex}")
                found_diagnostics = True
        
        if not found_diagnostics:
            print("Could not locate diagnostic patterns in cartridge.")
            print()
            print("The hwtest code with boot_prev2_* variables may be stored with")
            print("different memory organization or the cartridge file may contain")
            print("a different code version than expected.")

if __name__ == '__main__':
    crt_path = r"C:\Repository\C64_x86\build\c64x86.crt"
    parse_crt_file(crt_path)

