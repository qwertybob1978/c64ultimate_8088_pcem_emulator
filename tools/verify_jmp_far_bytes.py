#!/usr/bin/env python3
"""Verify JMP FAR operand byte order in CPU emulator."""

# JMP FAR (0xEA) format in x86/8088 real mode:
# Opcode: EA
# Operand: 4 bytes = [IP_low, IP_high, CS_low, CS_high]
# 
# Little-endian: lower address holds lower value bits
# So memory layout at instruction address:
#   +0: 0xEA (opcode)
#   +1: IP_low
#   +2: IP_high  
#   +3: CS_low
#   +4: CS_high

# At FFFF:0000 (physical 0xFFFF0 = ROM offset 0x1FF0):
rom_bytes = [0xEA, 0x5B, 0xE0, 0x00, 0xF0]

opcode = rom_bytes[0]
ip_low = rom_bytes[1]
ip_high = rom_bytes[2]
cs_low = rom_bytes[3]
cs_high = rom_bytes[4]

print(f"Instruction bytes at FFFF:0000:")
print(f"  Opcode: 0x{opcode:02X}")
print(f"  IP: 0x{ip_low:02X} 0x{ip_high:02X} = 0x{ip_high:02X}{ip_low:02X}")
print(f"  CS: 0x{cs_low:02X} 0x{cs_high:02X} = 0x{cs_high:02X}{cs_low:02X}")

# Little-endian 16-bit interpretation:
ip_target = (ip_high << 8) | ip_low
cs_target = (cs_high << 8) | cs_low

print(f"\nAfter JMP FAR execution:")
print(f"  CS:IP should be 0x{cs_target:04X}:0x{ip_target:04X}")

# Check against hwtest.s code in step.s:
print(f"\nCPU emulator (@install_far_target) does:")
print(f"  CPU_IP = far_target[0] (low byte)")
print(f"  CPU_IP+1 = far_target[1] (high byte)")
print(f"  CPU_CS = far_target[2] (low byte)")  
print(f"  CPU_CS+1 = far_target[3] (high byte)")

print(f"\nWith operand bytes 5B E0 00 F0:")
print(f"  far_target[0] = 0x5B → CPU_IP = 0x5B")
print(f"  far_target[1] = 0xE0 → CPU_IP+1 = 0xE0")
print(f"  far_target[2] = 0x00 → CPU_CS = 0x00")
print(f"  far_target[3] = 0xF0 → CPU_CS+1 = 0xF0")

print(f"\nResulting in: IP = 0xE05B, CS = 0xF000")
print(f"But diagnostic shows fault at: CS = 0xF000, IP = 0xE003")
print(f"\nDifference: E05B - E003 = 0x{0xE05B - 0xE003:04X} = {0xE05B - 0xE003} bytes")

# Check what's at E05B in the ROM
import sys
from pathlib import Path
rom = Path("third_party/roms/genxt/pcxt.rom").read_bytes()
e05b_offset = 0x5B
if e05b_offset < len(rom):
    print(f"\nBytes at E05B (offset 0x{e05b_offset:04X}) in ROM:")
    for i in range(e05b_offset, min(e05b_offset + 16, len(rom))):
        print(f"  E{i:03X}: 0x{rom[i]:02X}")
