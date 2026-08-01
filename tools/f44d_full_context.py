"""Full disassembly of key regions."""
from pathlib import Path

rom = bytearray(Path("third_party/pcem-roms/genxt/pcxt.rom").read_bytes())

def phys(off):
    return off + 0xFE000

print("=" * 70)
print("=== REGION 1: FF2B0 - FF2C0 (CGA polling loop) ===")
off = 0x12B0  # ROM offset for physical FF2B0
end_off = min(0x12D0, len(rom))
while off < end_off:
    b0 = rom[off]
    
    decoded = ""
    next_off = off + 1
    
    if b0 == 0xBA and off+2 < len(rom):
        val = rom[off+1] | (rom[off+2] << 8)
        port = val & 0xFFFF
        decoded = f"MOV DX,#${port:04X}"
        next_off = off + 3
    elif b0 == 0xEC:
        decoded = "IN AL,dx"
    elif b0 == 0xEE:
        decoded = "OUT dx,AL"
    elif b0 == 0xB0 and off+1 < len(rom):
        v = rom[off+1]
        decoded = f"MOV AL,#${v:02X}"
        next_off = off + 2
    elif b0 == 0xA8 and off+1 < len(rom):
        v = rom[off+1]
        decoded = f"TEST AL,#${v:02X}"
        next_off = off + 2
    elif b0 in [0x74, 0x75] and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        cond = "JNE" if b0 == 0x75 else "JE"
        decoded = f"{cond} {disp:+d} -> [{phys(target):05X}] {'LOOP' if abs(disp) <= 6 else ''}"
        next_off = off + 2
    elif b0 == 0xEB and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        decoded = f"JMP {disp:+d} -> [{phys(target):05X}]"
        next_off = off + 2
    elif b0 == 0xFA:
        decoded = "CLI"
    elif b0 == 0xFB:
        decoded = "STI"
    elif b0 == 0x90:
        decoded = "NOP"
    elif b0 == 0xCD and off+1 < len(rom):
        int_num = rom[off+1]
        decoded = f"INT #{int_num:#04X}"
        next_off = off + 2
    
    addr = phys(off)
    print(f"[{addr:05X}] {b0:02X} {' '*max(1, 35-len(decoded))}{decoded}")
    
    off = next_off


print("\n" + "=" * 70)
print("=== REGION 2: FF44A - FF460 (STALL LOOP + what comes after) ===")
off = 0x144A
end_off = min(0x1465, len(rom))
while off < end_off:
    b0 = rom[off]
    
    decoded = ""
    next_off = off + 1
    
    if b0 == 0xBA and off+2 < len(rom):
        val = rom[off+1] | (rom[off+2] << 8)
        port = val & 0xFFFF
        decoded = f"MOV DX,#${port:04X}"
        next_off = off + 3
    elif b0 == 0xEC:
        decoded = "IN AL,dx"
    elif b0 == 0xEE:
        decoded = "OUT dx,AL"
    elif b0 == 0xA8 and off+1 < len(rom):
        v = rom[off+1]
        decoded = f"TEST AL,#${v:02X}"
        next_off = off + 2
    elif b0 in [0x74, 0x75] and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        cond = "JNE" if b0 == 0x75 else "JE"
        loop_marker = 'LOOP' if abs(disp) <= 6 else ''
        decoded = f"{cond} {disp:+d} -> [{phys(target):05X}] {loop_marker}"
        next_off = off + 2
    elif b0 == 0xEB and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        decoded = f"JMP {disp:+d} -> [{phys(target):05X}]"
        next_off = off + 2
    elif b0 == 0xFA:
        decoded = "CLI"
    elif b0 == 0xFB:
        decoded = "STI"
    elif b0 == 0x90:
        decoded = "NOP"
    elif b0 == 0xCD and off+1 < len(rom):
        int_num = rom[off+1]
        decoded = f"INT #{int_num:#04X}"
        next_off = off + 2
    elif b0 == 0xC3:
        decoded = "RET"
    
    addr = phys(off)
    print(f"[{addr:05X}] {b0:02X} {' '*max(1, 35-len(decoded))}{decoded}")
    
    off = next_off


print("\n" + "=" * 70)
print("=== REGION 3: FF43B - FF44A (backward trace from stall) ===")
off = 0x143B
end_off = min(0x144D, len(rom))
while off < end_off:
    b0 = rom[off]
    
    decoded = ""
    next_off = off + 1
    
    if b0 == 0xBA and off+2 < len(rom):
        val = rom[off+1] | (rom[off+2] << 8)
        port = val & 0xFFFF
        decoded = f"MOV DX,#${port:04X}"
        next_off = off + 3
    elif b0 == 0xEC:
        decoded = "IN AL,dx"
    elif b0 == 0xEE:
        decoded = "OUT dx,AL"
    elif b0 == 0xA8 and off+1 < len(rom):
        v = rom[off+1]
        decoded = f"TEST AL,#${v:02X}"
        next_off = off + 2
    elif b0 in [0x74, 0x75] and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        cond = "JNE" if b0 == 0x75 else "JE"
        loop_marker = 'LOOP' if abs(disp) <= 6 else ''
        decoded = f"{cond} {disp:+d} -> [{phys(target):05X}] {loop_marker}"
        next_off = off + 2
    elif b0 == 0xEB and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        decoded = f"JMP {disp:+d} -> [{phys(target):05X}]"
        next_off = off + 2
    elif b0 == 0xFA:
        decoded = "CLI"
    elif b0 == 0xFB:
        decoded = "STI"
    elif b0 == 0x90:
        decoded = "NOP"
    elif b0 == 0xCD and off+1 < len(rom):
        int_num = rom[off+1]
        decoded = f"INT #{int_num:#04X}"
        next_off = off + 2
    elif b0 == 0xC3:
        decoded = "RET"
    
    addr = phys(off)
    print(f"[{addr:05X}] {b0:02X} {' '*max(1, 35-len(decoded))}{decoded}")
    
    off = next_off


print("\n" + "=" * 70)
print("=== REGION 4: FF4F0 - FF510 (nearby MOV DX pattern from trace_dx.py) ===")
# From earlier scan we found at FF4F8: MOV DX=#$2000
off = 0x14F0
end_off = min(0x1510, len(rom))
while off < end_off:
    b0 = rom[off]
    
    decoded = ""
    next_off = off + 1
    
    if b0 == 0xBA and off+2 < len(rom):
        val = rom[off+1] | (rom[off+2] << 8)
        port = val & 0xFFFF
        decoded = f"MOV DX,#${port:04X}"
        next_off = off + 3
    elif b0 == 0xEC:
        decoded = "IN AL,dx"
    elif b0 == 0xEE:
        decoded = "OUT dx,AL"
    elif b0 == 0xA8 and off+1 < len(rom):
        v = rom[off+1]
        decoded = f"TEST AL,#${v:02X}"
        next_off = off + 2
    elif b0 in [0x74, 0x75] and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        cond = "JNE" if b0 == 0x75 else "JE"
        loop_marker = 'LOOP' if abs(disp) <= 6 else ''
        decoded = f"{cond} {disp:+d} -> [{phys(target):05X}] {loop_marker}"
        next_off = off + 2
    elif b0 == 0xEB and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = phys(off) + 2 + disp
        decoded = f"JMP {disp:+d} -> [{phys(target):05X}]"
        next_off = off + 2
    elif b0 == 0xFA:
        decoded = "CLI"
    elif b0 == 0xFB:
        decoded = "STI"
    elif b0 == 0x90:
        decoded = "NOP"
    elif b0 == 0xCD and off+1 < len(rom):
        int_num = rom[off+1]
        decoded = f"INT #{int_num:#04X}"
        next_off = off + 2
    elif b0 == 0xC3:
        decoded = "RET"
    
    addr = phys(off)
    print(f"[{addr:05X}] {b0:02X} {' '*max(1, 35-len(decoded))}{decoded}")
    
    off = next_off
