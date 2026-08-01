"""Trace forward from known polling locations."""
from pathlib import Path

rom = bytearray(Path("third_party/pcem-roms/genxt/pcxt.rom").read_bytes())

def decode_simple(addr_phys, b0, next_byte=None):
    """Decode one instruction given its physical address and opcode byte."""
    if b0 == 0xBA:  # MOV DX,#imm16
        d1 = rom[next_byte]; d2 = rom[next_byte+1]
        val = d1 | (d2 << 8)
        port = val & 0xFFFF
        return f"MOV DX=#{val:#06X} (port ${port:04X})"
    elif b0 == 0xEC:  # IN AL,dx
        return "IN AL,dx"
    elif b0 == 0xEE:  # OUT dx,AL
        return "OUT dx,AL"
    elif b0 == 0xA8:  # TEST AL,#imm8
        v = rom[next_byte]
        return f"TEST AL,#${v:02X}"
    elif b0 in [0x74, 0x75]:  # JE/JNE rel8
        disp = rom[next_byte]
        if disp > 0x7F: disp -= 0x100
        target = addr_phys + 2 + disp
        cond = "JNE" if b0 == 0x75 else "JE"
        return f"{cond} {disp:+d} -> [{target:05X}]"
    elif b0 == 0xEB:  # JMP rel8
        disp = rom[next_byte]
        if disp > 0x7F: disp -= 0x100
        target = addr_phys + 2 + disp
        return f"JMP {disp:+d} -> [{target:05X}]"
    elif b0 == 0xFA:
        return "CLI"
    elif b0 == 0xFB:
        return "STI"
    elif b0 == 0x90:
        return "NOP"
    elif b0 == 0xCD and next_byte is not None:
        return f"INT #{rom[next_byte]:#04X}"
    else:
        return f"?${b0:02X}"


print("=== Tracing from FEEDB area ===")
# From trace_dx.py we found at offset 0xEDB (=FEEDB-FE000): MOV DX,#$03F4
off = 0xEDB  # ROM offset for physical address FEDBE

while off < min(0xF00, len(rom)):
    b0 = rom[off]
    
    decoded = ""
    next_off = off + 1
    
    if b0 == 0xBA and off+2 < len(rom):
        val = rom[off+1] | (rom[off+2] << 8)
        port = val & 0xFFFF
        decoded = f"MOV DX=#{val:#06X} (port ${port:04X})"
        next_off = off + 3
    elif b0 == 0xEC:
        decoded = "IN AL,dx"
        next_off = off + 1
    elif b0 == 0xEE:
        decoded = "OUT dx,AL"
        next_off = off + 1
    elif b0 == 0xA8 and off+1 < len(rom):
        v = rom[off+1]
        decoded = f"TEST AL,#${v:02X}"
        next_off = off + 2
    elif b0 in [0x74, 0x75] and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = (off + 0xFE000) + 2 + disp
        cond = "JNE" if b0 == 0x75 else "JE"
        decoded = f"{cond} {disp:+d} -> [{target:05X}]"
        next_off = off + 2
    elif b0 == 0xEB and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = (off + 0xFE000) + 2 + disp
        decoded = f"JMP {disp:+d} -> [{target:05X}]"
        next_off = off + 2
    elif b0 == 0xFA:
        decoded = "CLI"
        next_off = off + 1
    elif b0 == 0xFB:
        decoded = "STI"
        next_off = off + 1
    elif b0 == 0x90:
        decoded = "NOP"
        next_off = off + 1
    elif b0 == 0xCD and off+1 < len(rom):
        decoded = f"INT #{rom[off+1]:#04X}"
        next_off = off + 2
    
    addr = off + 0xFE000
    print(f"[{addr:05X}] {b0:02X} {' '*max(1, 35-len(decoded))}{decoded}")
    
    off = next_off


print("\n\n=== Tracing from FF44A area ===")
# Physical address FF44A has IN AL,dx at ROM offset 0x144A
off = 0x144A

while off < min(0x1460, len(rom)):
    b0 = rom[off]
    
    decoded = ""
    next_off = off + 1
    
    if b0 == 0xBA and off+2 < len(rom):
        val = rom[off+1] | (rom[off+2] << 8)
        port = val & 0xFFFF
        decoded = f"MOV DX=#{val:#06X} (port ${port:04X})"
        next_off = off + 3
    elif b0 == 0xEC:
        decoded = "IN AL,dx"
        next_off = off + 1
    elif b0 == 0xEE:
        decoded = "OUT dx,AL"
        next_off = off + 1
    elif b0 == 0xA8 and off+1 < len(rom):
        v = rom[off+1]
        decoded = f"TEST AL,#${v:02X}"
        next_off = off + 2
    elif b0 in [0x74, 0x75] and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = (off + 0xFE000) + 2 + disp
        cond = "JNE" if b0 == 0x75 else "JE"
        decoded = f"{cond} {disp:+d} -> [{target:05X}]"
        next_off = off + 2
    elif b0 == 0xEB and off+1 < len(rom):
        disp = rom[off+1]
        if disp > 0x7F: disp -= 0x100
        target = (off + 0xFE000) + 2 + disp
        decoded = f"JMP {disp:+d} -> [{target:05X}]"
        next_off = off + 2
    elif b0 == 0xFA:
        decoded = "CLI"
        next_off = off + 1
    elif b0 == 0xFB:
        decoded = "STI"
        next_off = off + 1
    elif b0 == 0x90:
        decoded = "NOP"
        next_off = off + 1
    elif b0 == 0xCD and off+1 < len(rom):
        decoded = f"INT #{rom[off+1]:#04X}"
        next_off = off + 2
    
    addr = off + 0xFE000
    print(f"[{addr:05X}] {b0:02X} {' '*max(1, 35-len(decoded))}{decoded}")
    
    off = next_off
