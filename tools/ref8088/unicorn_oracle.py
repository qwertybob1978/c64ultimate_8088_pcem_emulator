#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".cache/python"))

from unicorn import Uc, UC_ARCH_X86, UC_HOOK_INTR, UC_MODE_16
from unicorn.x86_const import (
    UC_X86_REG_AX, UC_X86_REG_BP, UC_X86_REG_BX, UC_X86_REG_CS,
    UC_X86_REG_CX, UC_X86_REG_DI, UC_X86_REG_DS, UC_X86_REG_DX,
    UC_X86_REG_EFLAGS, UC_X86_REG_ES, UC_X86_REG_IP, UC_X86_REG_SI,
    UC_X86_REG_SP, UC_X86_REG_SS,
)

try:
    from .runner import REGISTER_ORDER, Reference8088, run_vector
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runner import REGISTER_ORDER, Reference8088, run_vector


REGISTER_IDS = {
    "AX": UC_X86_REG_AX, "CX": UC_X86_REG_CX, "DX": UC_X86_REG_DX,
    "BX": UC_X86_REG_BX, "SP": UC_X86_REG_SP, "BP": UC_X86_REG_BP,
    "SI": UC_X86_REG_SI, "DI": UC_X86_REG_DI, "ES": UC_X86_REG_ES,
    "CS": UC_X86_REG_CS, "SS": UC_X86_REG_SS, "DS": UC_X86_REG_DS,
    "IP": UC_X86_REG_IP, "FLAGS": UC_X86_REG_EFLAGS,
}


def run_unicorn(spec: dict, vector: dict) -> dict:
    expected = run_vector(spec, vector)
    address_cpu = Reference8088(spec)
    oracle = Uc(UC_ARCH_X86, UC_MODE_16)
    oracle.mem_map(0, 2 << 20)

    initial = {name: 0 for name in REGISTER_ORDER}
    initial["FLAGS"] = spec["flags"]["RESERVED"]
    initial.update(vector.get("initial", {}))
    for name, value in initial.items():
        oracle.reg_write(REGISTER_IDS[name], value)

    load_address = address_cpu.physical(initial["CS"], initial["IP"])
    oracle.mem_write(load_address, bytes.fromhex(vector["program"]))
    for block in vector.get("memory", []):
        address = address_cpu.physical(block["segment"], block["offset"])
        oracle.mem_write(address, bytes.fromhex(block["bytes"]))

    def write_word(segment: int, offset: int, value: int) -> None:
        oracle.mem_write(address_cpu.physical(segment, offset), bytes((value & 0xFF,)))
        oracle.mem_write(address_cpu.physical(segment, (offset + 1) & 0xFFFF), bytes(((value >> 8) & 0xFF,)))

    def software_interrupt(uc: Uc, number: int, _user_data: object) -> None:
        ss = uc.reg_read(UC_X86_REG_SS) & 0xFFFF
        sp = uc.reg_read(UC_X86_REG_SP) & 0xFFFF
        flags = uc.reg_read(UC_X86_REG_EFLAGS) & 0xFFFF
        cs = uc.reg_read(UC_X86_REG_CS) & 0xFFFF
        ip = uc.reg_read(UC_X86_REG_IP) & 0xFFFF
        for value in (flags | 0xF000, cs, ip):
            sp = (sp - 2) & 0xFFFF
            write_word(ss, sp, value)
        uc.reg_write(UC_X86_REG_SP, sp)
        uc.reg_write(UC_X86_REG_EFLAGS, flags & ~(spec["flags"]["IF"] | spec["flags"]["TF"]))
        vector_address = (number & 0xFF) * 4
        entry = bytes(uc.mem_read(vector_address, 4))
        uc.reg_write(UC_X86_REG_IP, int.from_bytes(entry[:2], "little"))
        uc.reg_write(UC_X86_REG_CS, int.from_bytes(entry[2:], "little"))

    oracle.hook_add(UC_HOOK_INTR, software_interrupt)

    flag_mask = sum(spec["flags"][name] for name in ("CF", "PF", "AF", "ZF", "SF", "TF", "IF", "DF", "OF"))
    for index, reference_trace in enumerate(expected["trace"]):
        cs = oracle.reg_read(UC_X86_REG_CS)
        ip = oracle.reg_read(UC_X86_REG_IP)
        begin = address_cpu.physical(cs, ip)
        prefix_bytes = bytes(oracle.mem_read(begin, 8))
        has_repeat = False
        for byte in prefix_bytes:
            if byte in (0xF2, 0xF3):
                has_repeat = True
            if byte not in (0x26, 0x2E, 0x36, 0x3E, 0xF0, 0xF2, 0xF3):
                break
        while True:
            current_cs = oracle.reg_read(UC_X86_REG_CS)
            current_ip = oracle.reg_read(UC_X86_REG_IP)
            current = address_cpu.physical(current_cs, current_ip)
            oracle.emu_start(current, 2 << 20, count=1)
            repeat_complete = (
                oracle.reg_read(UC_X86_REG_CX) == reference_trace["after"]["CX"]
                and oracle.reg_read(UC_X86_REG_IP) == reference_trace["after"]["IP"]
            )
            if not has_repeat or repeat_complete:
                break
        for name in REGISTER_ORDER:
            actual = oracle.reg_read(REGISTER_IDS[name]) & 0xFFFF
            wanted = reference_trace["after"][name]
            if name == "FLAGS":
                actual &= flag_mask
                wanted &= flag_mask
            if actual != wanted:
                raise AssertionError(
                    f"{vector['name']} step {index}: Unicorn {name}={actual:#06x}, reference={wanted:#06x}"
                )

    for block in vector.get("expectedMemory", []):
        expected_bytes = bytes.fromhex(block["bytes"])
        address = address_cpu.physical(block["segment"], block["offset"])
        actual = bytes(oracle.mem_read(address, len(expected_bytes)))
        if actual != expected_bytes:
            raise AssertionError(
                f"{vector['name']}: Unicorn memory {actual.hex()} != {expected_bytes.hex()}"
            )
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description="Differentially test reference vectors with Unicorn")
    parser.add_argument("vectors", type=Path)
    parser.add_argument("--spec", type=Path, default=ROOT / "config/cpu8088.json")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    suite = json.loads(args.vectors.read_text(encoding="utf-8"))
    for vector in suite["vectors"]:
        run_unicorn(spec, vector)
        print(f"MATCH {vector['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
