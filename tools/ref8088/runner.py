#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = ROOT / "config/cpu8088.json"
REGISTER_ORDER = ("AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI", "ES", "CS", "SS", "DS", "IP", "FLAGS")
STATUS_NAMES = {0: "ok", 1: "halted", 0xFE: "memory", 0xFF: "invalid"}


class Reference8088:
    def __init__(self, spec: dict):
        self.spec = spec
        self.flags = spec["flags"]
        self.registers = {name: 0 for name in REGISTER_ORDER}
        self.registers["FLAGS"] = self.flags["RESERVED"]
        self.memory = bytearray(1 << 20)
        self.halted = False
        self.last_cycles = 0
        self.opcodes = {}
        for entry in spec["opcodes"]:
            for opcode in range(entry["first"], entry["last"] + 1):
                self.opcodes[opcode] = entry

    def reset(self) -> None:
        for name in REGISTER_ORDER:
            self.registers[name] = 0
        self.registers["CS"] = 0xFFFF
        self.registers["FLAGS"] = self.flags["RESERVED"]
        self.halted = False
        self.last_cycles = 0

    def physical(self, segment: int, offset: int) -> int:
        return ((segment << 4) + offset) & 0xFFFFF

    def fetch_u8(self) -> int:
        address = self.physical(self.registers["CS"], self.registers["IP"])
        value = self.memory[address]
        self.registers["IP"] = (self.registers["IP"] + 1) & 0xFFFF
        return value

    def fetch_u16(self) -> int:
        low = self.fetch_u8()
        return low | (self.fetch_u8() << 8)

    def set_flag(self, name: str, enabled: bool) -> None:
        mask = self.flags[name]
        if enabled:
            self.registers["FLAGS"] |= mask
        else:
            self.registers["FLAGS"] &= ~mask
        self.registers["FLAGS"] |= self.flags["RESERVED"]

    def step(self) -> dict:
        before_ip = self.registers["IP"]
        physical = self.physical(self.registers["CS"], before_ip)
        if self.halted:
            return self.trace(before_ip, physical, None, "HLT", 1)

        opcode = self.fetch_u8()
        metadata = self.opcodes.get(opcode)
        if metadata is None:
            self.last_cycles = 0
            return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)

        handler = metadata["handler"]
        status = 0
        if handler == "nop":
            pass
        elif handler == "hlt":
            self.halted = True
            status = 1
        elif handler == "mov_r16_imm16":
            self.registers[REGISTER_ORDER[opcode - 0xB8]] = self.fetch_u16()
        elif handler == "jmp_rel8":
            displacement = self.fetch_u8()
            if displacement & 0x80:
                displacement -= 0x100
            self.registers["IP"] = (self.registers["IP"] + displacement) & 0xFFFF
        elif handler == "jmp_rel16":
            displacement = self.fetch_u16()
            if displacement & 0x8000:
                displacement -= 0x10000
            self.registers["IP"] = (self.registers["IP"] + displacement) & 0xFFFF
        elif handler in ("clear_cf", "set_cf", "clear_if", "set_if", "clear_df", "set_df"):
            action, flag = handler.split("_")
            self.set_flag(flag.upper(), action == "set")
        else:
            raise ValueError(f"reference handler is not implemented: {handler}")

        self.last_cycles = metadata["cycles"]
        return self.trace(before_ip, physical, opcode, metadata["mnemonic"], status)

    def trace(self, before_ip: int, physical: int, opcode: int | None, mnemonic: str, status: int) -> dict:
        return {
            "cs": self.registers["CS"],
            "ip": before_ip,
            "physical": physical,
            "opcode": opcode,
            "mnemonic": mnemonic,
            "status": STATUS_NAMES[status],
            "cycles": self.last_cycles,
            "after": {name: self.registers[name] for name in REGISTER_ORDER},
        }


def run_vector(spec: dict, vector: dict) -> dict:
    cpu = Reference8088(spec)
    for name, value in vector.get("initial", {}).items():
        cpu.registers[name] = value & 0xFFFF
    program = bytes.fromhex(vector["program"])
    load_address = cpu.physical(cpu.registers["CS"], cpu.registers["IP"])
    for index, value in enumerate(program):
        cpu.memory[(load_address + index) & 0xFFFFF] = value

    step_count = vector.get("maxSteps", len(vector["statuses"]))
    trace = [cpu.step() for _ in range(step_count)]
    statuses = [entry["status"] for entry in trace]
    if statuses != vector["statuses"]:
        raise AssertionError(f"{vector['name']}: statuses {statuses} != {vector['statuses']}")
    for name, value in vector["expected"].items():
        if cpu.registers[name] != value:
            raise AssertionError(
                f"{vector['name']}: {name}={cpu.registers[name]:#06x}, expected {value:#06x}"
            )
    return {"name": vector["name"], "trace": trace, "final": cpu.registers}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic 8088 JSON vectors")
    parser.add_argument("vectors", type=Path)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--json", action="store_true", help="emit machine-readable traces")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    suite = json.loads(args.vectors.read_text(encoding="utf-8"))
    results = [run_vector(spec, vector) for vector in suite["vectors"]]
    if args.json:
        json.dump({"schema": 1, "results": results}, sys.stdout, indent=2)
        print()
    else:
        for result in results:
            print(f"PASS {result['name']} ({len(result['trace'])} steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
