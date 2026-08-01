#!/usr/bin/env python3
"""Dump C64 boot diagnostic memory to understand state."""

import struct

# C64 cartridge memory layout
# Diagnostic data starts in the cartridge RAM section

def analyze_diagnostic_memory():
    """Analyze boot diagnostic memory from cartridge."""
    
    # The diagnostic data is stored in cartridge memory
    # These are the symbol addresses from hwtest.s
    diag_symbols = {
        'boot_failure_status': 'Failure status',
        'boot_fault_cs': 'Fault CS',
        'boot_fault_ip': 'Fault IP',
        'boot_fault_ss': 'Fault SS',
        'boot_fault_sp': 'Fault SP',
        'boot_fault_bytes': 'Fault bytes (4)',
        'boot_fault_ivt': 'IVT[9] (4)',
        'boot_fault_ivt0': 'IVT[0] (4)',
        'boot_prev_cs': 'P1 CS',
        'boot_prev_ip': 'P1 IP',
        'boot_prev_opcode': 'P1 opcode',
        'boot_prev_status': 'P1 status',
        'boot_prev2_cs': 'P2 CS',
        'boot_prev2_ip': 'P2 IP',
        'boot_prev2_opcode': 'P2 opcode',
        'boot_prev2_status': 'P2 status',
    }
    
    print("=== Boot Diagnostic Memory Locations ===")
    print()
    print("These values are stored in the CRT cartridge memory:")
    print()
    
    # The cartridge file contains the diagnostic data
    # We need to find the correct offset in the CRT file
    
    crt_path = r"C:\Repository\C64_x86\build\c64x86.crt"
    
    try:
        with open(crt_path, 'rb') as f:
            # Read CRT header
            header = f.read(0x40)
            if header[:4] != b'CART':
                print("ERROR: Not a valid CRT file")
                return
            
            # CRT header is 64 bytes, followed by chip packages
            print(f"CRT file size: {len(header)} bytes header")
            
            # Read chip packages
            chips = []
            offset = 0x40
            f.seek(offset)
            
            while True:
                chip_header = f.read(16)
                if len(chip_header) < 16:
                    break
                    
                if chip_header[:4] != b'CHIP':
                    break
                
                chip_size = struct.unpack('>I', chip_header[4:8])[0]
                chip_type = struct.unpack('>H', chip_header[8:10])[0]
                chip_bank = struct.unpack('>H', chip_header[10:12])[0]
                chip_addr = struct.unpack('>H', chip_header[12:14])[0]
                
                chips.append({
                    'type': chip_type,
                    'bank': chip_bank,
                    'addr': chip_addr,
                    'size': chip_size,
                    'data_offset': offset + 16,
                })
                
                print(f"CHIP bank={chip_bank} type={chip_type} addr=${chip_addr:04X} size={chip_size}")
                
                offset += 16 + chip_size
                f.seek(offset)
            
            print()
            print("Diagnostic data should be in one of these chips")
            print("(typically in the cartridge RAM bank)")
            
    except FileNotFoundError:
        print(f"CRT file not found: {crt_path}")
    except Exception as e:
        print(f"Error reading CRT: {e}")
    
    print()
    print("To extract diagnostic data:")
    print("1. Run VICE with the CRT")
    print("2. Use VICE built-in memory inspector to view $0400-$0530 (video RAM)")
    print("3. Or use the monitor: 'm 0400 0530' to dump memory")
    print()

if __name__ == '__main__':
    analyze_diagnostic_memory()
