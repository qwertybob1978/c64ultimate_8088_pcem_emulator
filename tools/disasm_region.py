#!/usr/bin/env python3
"""Ad-hoc 16-bit disassembler for the genxt BIOS ROM (segment F000)."""
import sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_16

ROM = open("third_party/pcem-roms/genxt/pcxt.rom", "rb").read()
BASE = 0xE000  # ROM byte 0 maps to F000:E000


def dis(start, end):
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    off = start - BASE
    for i in md.disasm(ROM[off:end - BASE], start):
        print("%04X: %-18s %s %s" % (
            i.address, " ".join("%02X" % b for b in i.bytes), i.mnemonic, i.op_str))


if __name__ == "__main__":
    a = int(sys.argv[1], 16)
    b = int(sys.argv[2], 16)
    dis(a, b)
