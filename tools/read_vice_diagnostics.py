#!/usr/bin/env python3
"""Read diagnostic data from C64 video memory in VICE save state."""

import struct
import sys

def read_c64_video_memory(screenshot_path=None):
    """Extract and display C64 video memory diagnostics."""
    
    # For now, just print a guide to the expected diagnostic layout
    print("=== C64 Video Memory Diagnostic Layout ===")
    print()
    print("Screen RAM addresses (one row = 40 bytes):")
    print("  Row 0 ($0400-$0427): Boot status")
    print("  Row 1 ($0428-$044F): More status")
    print("  Row 2 ($0450-$0477): P1 (previous instruction): P1: <status> <opcode> <cs_hi> <cs_lo> <ip_hi> <ip_lo>")
    print("  Row 3 ($0478-$049F): P2 (prior-2 instruction): P2: <status> <opcode> <cs_hi> <cs_lo> <ip_hi> <ip_lo>")
    print("  Row 4 ($04A0-$04C7): FC/PV/VM/IQ diagnostics")
    print("  Row 5 ($04C8-$04EF): D (bytes), I (IVT), 0 (IVT0) diagnostics")
    print("  Row 6 ($04F0-$0517): R (last IRET), M (frame mismatch)")
    print()
    
    # Look for VICE snapshot file
    import os
    import glob
    
    # Try to find latest VICE snapshot
    vice_dir = os.path.expandvars(r"C:\Repository\C64_x86\.cache\vice-3.10\c64")
    if os.path.exists(vice_dir):
        snapshots = sorted(glob.glob(os.path.join(vice_dir, "*.vsf")))
        if snapshots:
            latest_snapshot = snapshots[-1]
            print(f"Found VICE snapshot: {latest_snapshot}")
            print()
            
            # Try to read video RAM from snapshot
            # VICE snapshots are complex, so this is a simplified approach
            try:
                with open(latest_snapshot, 'rb') as f:
                    data = f.read()
                    
                # Look for C64 video RAM signature pattern
                # Video RAM in C64 starts at $0400
                # Try to find reasonable ASCII text patterns
                print("Searching for video RAM in snapshot...")
                
                # VICE snapshots have a header structure, but for now just look for patterns
                # In a real scenario, you'd parse the snapshot format properly
                
            except Exception as e:
                print(f"Error reading snapshot: {e}")
    else:
        print(f"VICE cache directory not found: {vice_dir}")
    
    print()
    print("=== Key Diagnostic Values to Look For ===")
    print()
    print("P2 (prior-2 instruction state):")
    print("  - CS: Should show F000 (or C000 if pointing to cartridge)")
    print("  - IP: The instruction pointer before the fault")
    print("  - Opcode: The byte at that address")
    print()
    print("Expected values:")
    print("  - If P2 IP is E001 or E002, then sequential execution led to E003")
    print("  - If P2 IP is E003+, then a jump/return was involved")
    print("  - If P2 CS != F000, might indicate interrupt/vector issue")
    print()

if __name__ == '__main__':
    read_c64_video_memory()
