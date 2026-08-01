#!/usr/bin/env python3
"""Scan pcxt.rom for direct jumps/calls whose target is F000:E000."""
from pathlib import Path

ROM = Path(__file__).resolve().parent.parent / "third_party/roms/genxt/pcxt.rom"
rom = ROM.read_bytes()
BASE_SEG = 0xF000
BASE_PHYS = 0xFE000

def phys_to_seg_ip(phys):
    return (phys >> 4) & 0xF000, phys & 0xFFFF  # actually segment base

def decode_jmp(ip):
    """Given an IP in F000 segment, return list of (next_ip, target_ip, kind, bytes)."""
    results = []
    for addr in range(ip, len(rom)):
        op = rom[addr]
        if op == 0xEB and addr + 1 < len(rom):  # JMP rel8
            disp = rom[addr + 1]
            target = (addr + 2 + (disp if disp < 128 else disp - 256)) & 0xFFFF
            results.append((addr, target, "JMP8", rom[addr:addr + 2]))
        elif op in (0xE8, 0xE9) and addr + 2 < len(rom):  # CALL/JMP rel16
            disp = rom[addr + 1] | (rom[addr + 2] << 8)
            if disp >= 0x8000:
                disp -= 0x10000
            target = (addr + 3 + disp) & 0xFFFF
            kind = "CALL" if op == 0xE8 else "JMP16"
            results.append((addr, target, kind, rom[addr:addr + 3]))
        elif 0x70 <= op <= 0x7F and addr + 1 < len(rom):  # JCC rel8
            disp = rom[addr + 1]
            if disp >= 0x80:
                disp -= 0x100
            target = (addr + 2 + disp) & 0xFFFF
            results.append((addr, target, f"J{op:02X}", rom[addr:addr + 2]))
    return results

# Target IP in F000 segment: E000 corresponds to ROM offset 0x0000
# (since F000:E000 physical = FE000, ROM offset 0)
target_ip = 0xE000

for addr in range(len(rom)):
    op = rom[addr]
    if op == 0xEB and addr + 1 < len(rom):
        disp = rom[addr + 1]
        if disp >= 0x80:
            disp -= 0x100
        tgt = (addr + 2 + disp) & 0xFFFF
        if tgt == target_ip:
            print(f"F000:{addr:04X}  EB {rom[addr+1]:02X}      JMP SHORT F000:{tgt:04X}")
    elif op in (0xE8, 0xE9) and addr + 2 < len(rom):
        disp = rom[addr + 1] | (rom[addr + 2] << 8)
        if disp >= 0x8000:
            disp -= 0x10000
        tgt = (addr + 3 + disp) & 0xFFFF
        if tgt == target_ip:
            kind = "CALL" if op == 0xE8 else "JMP"
            print(f"F000:{addr:04X}  {op:02X} {rom[addr+1]:02X} {rom[addr+2]:02X}  {kind} NEAR F000:{tgt:04X}")
    elif 0x70 <= op <= 0x7F and addr + 1 < len(rom):
        disp = rom[addr + 1]
        if disp >= 0x80:
            disp -= 0x100
        tgt = (addr + 2 + disp) & 0xFFFF
        if tgt == target_ip:
            print(f"F000:{addr:04X}  {op:02X} {rom[addr+1]:02X}     JCC F000:{tgt:04X}")
