#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = ROOT / "config/cpu8088.json"
REGISTER_ORDER = ("AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI", "ES", "CS", "SS", "DS", "IP", "FLAGS")
STATUS_NAMES = {0: "ok", 1: "halted", 0xFE: "memory", 0xFF: "invalid"}
WORD_REGISTERS = ("AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI")
BYTE_REGISTERS = (
    ("AX", 0), ("CX", 0), ("DX", 0), ("BX", 0),
    ("AX", 8), ("CX", 8), ("DX", 8), ("BX", 8),
)


class Reference8088:
    def __init__(self, spec: dict):
        self.spec = spec
        self.flags = spec["flags"]
        self.registers = {name: 0 for name in REGISTER_ORDER}
        self.registers["FLAGS"] = self.flags["RESERVED"]
        self.memory = bytearray(1 << 20)
        self.halted = False
        self.last_cycles = 0
        self.memory_writes = []
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

    def get_register(self, index: int, width: int) -> int:
        if width == 16:
            return self.registers[WORD_REGISTERS[index]]
        name, shift = BYTE_REGISTERS[index]
        return (self.registers[name] >> shift) & 0xFF

    def set_register(self, index: int, width: int, value: int) -> None:
        if width == 16:
            self.registers[WORD_REGISTERS[index]] = value & 0xFFFF
            return
        name, shift = BYTE_REGISTERS[index]
        mask = 0xFF << shift
        self.registers[name] = (self.registers[name] & ~mask) | ((value & 0xFF) << shift)

    def read_memory(self, segment: int, offset: int, width: int) -> int:
        low = self.memory[self.physical(segment, offset)]
        if width == 8:
            return low
        high = self.memory[self.physical(segment, (offset + 1) & 0xFFFF)]
        return low | (high << 8)

    def write_memory(self, segment: int, offset: int, width: int, value: int) -> None:
        address = self.physical(segment, offset)
        self.memory[address] = value & 0xFF
        self.memory_writes.append({"physical": address, "value": value & 0xFF})
        if width == 16:
            address = self.physical(segment, (offset + 1) & 0xFFFF)
            self.memory[address] = (value >> 8) & 0xFF
            self.memory_writes.append({"physical": address, "value": (value >> 8) & 0xFF})

    def decode_modrm(self, width: int) -> tuple[dict, int]:
        value = self.fetch_u8()
        mod = value >> 6
        reg = (value >> 3) & 7
        rm = value & 7
        if mod == 3:
            return {"kind": "register", "index": rm, "width": width}, reg

        bases = (
            ("BX", "SI"), ("BX", "DI"), ("BP", "SI"), ("BP", "DI"),
            ("SI",), ("DI",), ("BP",), ("BX",),
        )
        bp_based = rm in (2, 3, 6)
        if mod == 0 and rm == 6:
            offset = self.fetch_u16()
            bp_based = False
        else:
            offset = sum(self.registers[name] for name in bases[rm]) & 0xFFFF
            if mod == 1:
                displacement = self.fetch_u8()
                if displacement & 0x80:
                    displacement -= 0x100
                offset = (offset + displacement) & 0xFFFF
            elif mod == 2:
                offset = (offset + self.fetch_u16()) & 0xFFFF
        segment_name = "SS" if bp_based else "DS"
        return {
            "kind": "memory",
            "segment": self.registers[segment_name],
            "segmentName": segment_name,
            "offset": offset,
            "width": width,
        }, reg

    def read_operand(self, operand: dict) -> int:
        if operand["kind"] == "register":
            return self.get_register(operand["index"], operand["width"])
        return self.read_memory(operand["segment"], operand["offset"], operand["width"])

    def write_operand(self, operand: dict, value: int) -> None:
        if operand["kind"] == "register":
            self.set_register(operand["index"], operand["width"], value)
        else:
            self.write_memory(operand["segment"], operand["offset"], operand["width"], value)

    @staticmethod
    def even_parity(value: int) -> bool:
        return (value & 0xFF).bit_count() % 2 == 0

    def update_result_flags(self, result: int, width: int) -> None:
        mask = (1 << width) - 1
        sign = 1 << (width - 1)
        self.set_flag("PF", self.even_parity(result))
        self.set_flag("ZF", (result & mask) == 0)
        self.set_flag("SF", bool(result & sign))

    def alu(self, operation: str, left: int, right: int, width: int) -> int:
        mask = (1 << width) - 1
        sign = 1 << (width - 1)
        carry_in = 1 if self.registers["FLAGS"] & self.flags["CF"] else 0
        if operation in ("add", "adc"):
            carry = carry_in if operation == "adc" else 0
            full = left + right + carry
            result = full & mask
            self.set_flag("CF", full > mask)
            self.set_flag("AF", ((left & 0xF) + (right & 0xF) + carry) > 0xF)
            self.set_flag("OF", bool((~(left ^ right) & (left ^ result) & sign)))
        elif operation in ("sub", "sbb", "cmp"):
            borrow = carry_in if operation == "sbb" else 0
            result = (left - right - borrow) & mask
            self.set_flag("CF", left < right + borrow)
            self.set_flag("AF", (left & 0xF) < ((right & 0xF) + borrow))
            self.set_flag("OF", bool(((left ^ right) & (left ^ result) & sign)))
        elif operation == "and":
            result = left & right
            self.set_flag("CF", False)
            self.set_flag("OF", False)
            self.set_flag("AF", False)
        elif operation == "or":
            result = left | right
            self.set_flag("CF", False)
            self.set_flag("OF", False)
            self.set_flag("AF", False)
        elif operation == "xor":
            result = left ^ right
            self.set_flag("CF", False)
            self.set_flag("OF", False)
            self.set_flag("AF", False)
        else:
            raise ValueError(f"unknown ALU operation: {operation}")
        self.update_result_flags(result, width)
        return result

    def push_u16(self, value: int) -> None:
        self.registers["SP"] = (self.registers["SP"] - 2) & 0xFFFF
        self.write_memory(self.registers["SS"], self.registers["SP"], 16, value)

    def pop_u16(self) -> int:
        value = self.read_memory(self.registers["SS"], self.registers["SP"], 16)
        self.registers["SP"] = (self.registers["SP"] + 2) & 0xFFFF
        return value

    def condition(self, code: int) -> bool:
        flags = self.registers["FLAGS"]
        cf = bool(flags & self.flags["CF"])
        pf = bool(flags & self.flags["PF"])
        zf = bool(flags & self.flags["ZF"])
        sf = bool(flags & self.flags["SF"])
        of = bool(flags & self.flags["OF"])
        conditions = (
            of, not of, cf, not cf, zf, not zf, cf or zf, not cf and not zf,
            sf, not sf, pf, not pf, sf != of, sf == of, zf or sf != of, not zf and sf == of,
        )
        return conditions[code]

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
        self.memory_writes = []
        if self.halted:
            return self.trace(before_ip, physical, None, "HLT", 1)

        opcode = self.fetch_u8()
        metadata = self.opcodes.get(opcode)
        if metadata is None:
            self.last_cycles = 0
            return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)

        handler = metadata["handler"]
        status = 0
        cycles = metadata["cycles"]
        if handler == "nop":
            pass
        elif handler == "hlt":
            self.halted = True
            status = 1
        elif handler == "mov_r8_imm8":
            self.set_register(opcode - 0xB0, 8, self.fetch_u8())
        elif handler == "mov_r16_imm16":
            self.set_register(opcode - 0xB8, 16, self.fetch_u16())
        elif handler in ("inc_reg16", "dec_reg16"):
            index = opcode & 7
            carry = bool(self.registers["FLAGS"] & self.flags["CF"])
            operation = "add" if handler == "inc_reg16" else "sub"
            self.set_register(index, 16, self.alu(operation, self.get_register(index, 16), 1, 16))
            self.set_flag("CF", carry)
        elif handler == "push_reg16":
            self.push_u16(self.get_register(opcode & 7, 16))
        elif handler == "pop_reg16":
            self.set_register(opcode & 7, 16, self.pop_u16())
        elif handler == "mov_modrm":
            width = 16 if opcode & 1 else 8
            rm_operand, reg_index = self.decode_modrm(width)
            reg_operand = {"kind": "register", "index": reg_index, "width": width}
            destination, source = (reg_operand, rm_operand) if opcode & 2 else (rm_operand, reg_operand)
            self.write_operand(destination, self.read_operand(source))
        elif handler == "mov_rm_imm":
            width = 16 if opcode & 1 else 8
            destination, extension = self.decode_modrm(width)
            if extension != 0:
                self.last_cycles = 0
                return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)
            immediate = self.fetch_u16() if width == 16 else self.fetch_u8()
            self.write_operand(destination, immediate)
        elif handler == "mov_moffs":
            width = 16 if opcode & 1 else 8
            memory_operand = {
                "kind": "memory",
                "segment": self.registers["DS"],
                "segmentName": "DS",
                "offset": self.fetch_u16(),
                "width": width,
            }
            accumulator = {"kind": "register", "index": 0, "width": width}
            destination, source = (memory_operand, accumulator) if opcode & 2 else (accumulator, memory_operand)
            self.write_operand(destination, self.read_operand(source))
        elif handler == "alu_modrm":
            width = 16 if opcode & 1 else 8
            rm_operand, reg_index = self.decode_modrm(width)
            reg_operand = {"kind": "register", "index": reg_index, "width": width}
            destination, source = (reg_operand, rm_operand) if opcode & 2 else (rm_operand, reg_operand)
            result = self.alu(metadata["operation"], self.read_operand(destination), self.read_operand(source), width)
            if metadata["operation"] != "cmp":
                self.write_operand(destination, result)
        elif handler in ("alu_acc_imm8", "alu_acc_imm16"):
            width = 16 if handler.endswith("16") else 8
            destination = {"kind": "register", "index": 0, "width": width}
            immediate = self.fetch_u16() if width == 16 else self.fetch_u8()
            result = self.alu(metadata["operation"], self.read_operand(destination), immediate, width)
            if metadata["operation"] != "cmp":
                self.write_operand(destination, result)
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
        elif handler == "jcc_rel8":
            displacement = self.fetch_u8()
            if displacement & 0x80:
                displacement -= 0x100
            if self.condition(opcode & 0x0F):
                self.registers["IP"] = (self.registers["IP"] + displacement) & 0xFFFF
                cycles = 16
        elif handler == "call_rel16":
            displacement = self.fetch_u16()
            if displacement & 0x8000:
                displacement -= 0x10000
            self.push_u16(self.registers["IP"])
            self.registers["IP"] = (self.registers["IP"] + displacement) & 0xFFFF
        elif handler in ("ret_near", "ret_near_imm"):
            stack_adjust = self.fetch_u16() if handler == "ret_near_imm" else 0
            self.registers["IP"] = self.pop_u16()
            self.registers["SP"] = (self.registers["SP"] + stack_adjust) & 0xFFFF
        elif handler in ("clear_cf", "set_cf", "clear_if", "set_if", "clear_df", "set_df"):
            action, flag = handler.split("_")
            self.set_flag(flag.upper(), action == "set")
        else:
            raise ValueError(f"reference handler is not implemented: {handler}")

        self.last_cycles = cycles
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
            "writes": list(self.memory_writes),
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
    for block in vector.get("memory", []):
        data = bytes.fromhex(block["bytes"])
        for index, value in enumerate(data):
            address = cpu.physical(block["segment"], (block["offset"] + index) & 0xFFFF)
            cpu.memory[address] = value

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
    for block in vector.get("expectedMemory", []):
        actual = bytes(
            cpu.memory[cpu.physical(block["segment"], (block["offset"] + index) & 0xFFFF)]
            for index in range(len(bytes.fromhex(block["bytes"])))
        )
        expected = bytes.fromhex(block["bytes"])
        if actual != expected:
            raise AssertionError(f"{vector['name']}: memory {actual.hex()} != {expected.hex()}")
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
