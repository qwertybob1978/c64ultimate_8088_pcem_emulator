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
        self.pending_irq = None
        self.pending_nmi = False
        self.interrupt_shadow = 0
        self.video_status_phase = {0x3BA: 0, 0x3DA: 0}
        self.ppi_port_b = 0
        self.keyboard_data = 0
        self.last_interrupt_return_ip = None
        self.ports = {}
        self.io_events = []
        self.segment_override = None
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
        self.pending_irq = None
        self.pending_nmi = False
        self.interrupt_shadow = 0
        self.video_status_phase = {0x3BA: 0, 0x3DA: 0}
        self.ppi_port_b = 0
        self.keyboard_data = 0

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

    def read_port_u8(self, port: int) -> int:
        port &= 0xFFFF
        if port == 0x60 and port not in self.ports:
            value = self.keyboard_data
        elif port == 0x61 and port not in self.ports:
            value = self.ppi_port_b
        elif port == 0x62 and port not in self.ports:
            value = 0x06 if self.ppi_port_b & 0x08 else 0x0D
        elif port == 0x3DA and port not in self.ports:
            value = 0x09 if self.video_status_phase[port] else 0x00
            self.video_status_phase[port] ^= 1
        else:
            value = self.ports.get(port, 0xFF)
        self.io_events.append({"direction": "in", "port": port, "value": value})
        return value

    def write_port_u8(self, port: int, value: int) -> None:
        port &= 0xFFFF
        value &= 0xFF
        self.ports[port] = value
        if port == 0x61:
            self.ppi_port_b = value
        self.io_events.append({"direction": "out", "port": port, "value": value})

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
        segment_name = self.segment_override or ("SS" if bp_based else "DS")
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

    def interrupt(self, vector: int) -> None:
        self.last_interrupt_return_ip = self.registers["IP"]
        self.push_u16(self.registers["FLAGS"] | 0xF000)
        self.push_u16(self.registers["CS"])
        self.push_u16(self.registers["IP"])
        self.set_flag("IF", False)
        self.set_flag("TF", False)
        table_offset = (vector & 0xFF) * 4
        self.registers["IP"] = self.read_memory(0, table_offset, 16)
        self.registers["CS"] = self.read_memory(0, table_offset + 2, 16)

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
        self.io_events = []
        self.last_interrupt_return_ip = None
        if self.pending_nmi:
            self.pending_nmi = False
            self.halted = False
            self.interrupt(2)
            self.last_cycles = 50
            return self.trace(before_ip, physical, None, "NMI", 0)
        shadowed = self.interrupt_shadow > 0
        if shadowed:
            self.interrupt_shadow -= 1
        if (
            self.pending_irq is not None
            and not shadowed
            and self.registers["FLAGS"] & self.flags["IF"]
        ):
            vector = self.pending_irq
            self.pending_irq = None
            self.halted = False
            self.interrupt(vector)
            self.last_cycles = 50
            return self.trace(before_ip, physical, None, "IRQ", 0)
        if self.halted:
            return self.trace(before_ip, physical, None, "HLT", 1)

        opcode = self.fetch_u8()
        segment_override = None
        self.segment_override = None
        repeat = None
        while opcode in (0x26, 0x2E, 0x36, 0x3E, 0xF0, 0xF2, 0xF3):
            if opcode in (0x26, 0x2E, 0x36, 0x3E):
                segment_override = {0x26: "ES", 0x2E: "CS", 0x36: "SS", 0x3E: "DS"}[opcode]
                self.segment_override = segment_override
            elif opcode in (0xF2, 0xF3):
                repeat = opcode
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
        elif handler == "xchg_accumulator":
            index = opcode & 7
            accumulator = self.registers["AX"]
            self.registers["AX"] = self.get_register(index, 16)
            self.set_register(index, 16, accumulator)
        elif handler == "cwd":
            self.registers["DX"] = 0xFFFF if self.registers["AX"] & 0x8000 else 0
        elif handler == "wait":
            pass
        elif handler == "aam":
            base = self.fetch_u8()
            if base == 0:
                self.last_cycles = 0
                return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)
            al = self.get_register(0, 8)
            self.set_register(4, 8, al // base)
            self.set_register(0, 8, al % base)
            self.update_result_flags(self.get_register(0, 8), 8)
        elif handler == "aad":
            base = self.fetch_u8()
            value = (self.get_register(4, 8) * base + self.get_register(0, 8)) & 0xFF
            self.set_register(0, 8, value)
            self.set_register(4, 8, 0)
            self.update_result_flags(value, 8)
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
        elif handler == "group4":
            operand, extension = self.decode_modrm(8)
            if extension not in (0, 1):
                self.last_cycles = 0
                return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)
            carry = bool(self.registers["FLAGS"] & self.flags["CF"])
            operation = "add" if extension == 0 else "sub"
            result = self.alu(operation, self.read_operand(operand), 1, 8)
            self.write_operand(operand, result)
            self.set_flag("CF", carry)
            cycles = 3 if operand["kind"] == "register" else 15
        elif handler == "group5":
            operand, extension = self.decode_modrm(16)
            if extension not in (2, 4):
                self.last_cycles = 0
                return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)
            target = self.read_operand(operand)
            if extension == 2:
                self.push_u16(self.registers["IP"])
                cycles = 16 if operand["kind"] == "register" else 21
            else:
                cycles = 11 if operand["kind"] == "register" else 18
            self.registers["IP"] = target
        elif handler == "push_reg16":
            self.push_u16(self.get_register(opcode & 7, 16))
        elif handler == "pop_reg16":
            self.set_register(opcode & 7, 16, self.pop_u16())
        elif handler == "segment_stack":
            segment_name = ("ES", "CS", "SS", "DS")[(opcode & 0x18) >> 3]
            if opcode & 1:
                self.registers[segment_name] = self.pop_u16()
                if segment_name == "SS":
                    self.interrupt_shadow = 1
            else:
                self.push_u16(self.registers[segment_name])
        elif handler == "pushf":
            self.push_u16(self.registers["FLAGS"] | 0xF000)
        elif handler == "popf":
            self.registers["FLAGS"] = (self.pop_u16() & 0x0FFF) | self.flags["RESERVED"]
        elif handler == "sahf":
            status_mask = self.flags["SF"] | self.flags["ZF"] | self.flags["AF"] | self.flags["PF"] | self.flags["CF"]
            ah = self.get_register(4, 8)
            self.registers["FLAGS"] = (self.registers["FLAGS"] & ~status_mask) | (ah & status_mask)
            self.registers["FLAGS"] |= self.flags["RESERVED"]
        elif handler == "lahf":
            self.set_register(4, 8, self.registers["FLAGS"] & 0xFF)
        elif handler == "mov_modrm":
            width = 16 if opcode & 1 else 8
            rm_operand, reg_index = self.decode_modrm(width)
            reg_operand = {"kind": "register", "index": reg_index, "width": width}
            destination, source = (reg_operand, rm_operand) if opcode & 2 else (rm_operand, reg_operand)
            self.write_operand(destination, self.read_operand(source))
        elif handler == "xchg_modrm":
            width = 16 if opcode & 1 else 8
            rm_operand, reg_index = self.decode_modrm(width)
            reg_operand = {"kind": "register", "index": reg_index, "width": width}
            rm_value = self.read_operand(rm_operand)
            reg_value = self.read_operand(reg_operand)
            self.write_operand(rm_operand, reg_value)
            self.write_operand(reg_operand, rm_value)
            cycles = 4 if rm_operand["kind"] == "register" else 17
        elif handler == "mov_segment":
            rm_operand, segment_index = self.decode_modrm(16)
            if segment_index > 3 or (opcode == 0x8E and segment_index == 1):
                self.last_cycles = 0
                return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)
            segment_name = ("ES", "CS", "SS", "DS")[segment_index]
            if opcode == 0x8C:
                self.write_operand(rm_operand, self.registers[segment_name])
            else:
                self.registers[segment_name] = self.read_operand(rm_operand)
                if segment_name == "SS":
                    self.interrupt_shadow = 1
        elif handler == "mov_rm_imm":
            width = 16 if opcode & 1 else 8
            destination, extension = self.decode_modrm(width)
            if extension != 0:
                self.last_cycles = 0
                return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)
            immediate = self.fetch_u16() if width == 16 else self.fetch_u8()
            self.write_operand(destination, immediate)
        elif handler == "load_far_pointer":
            source, register_index = self.decode_modrm(16)
            if source["kind"] != "memory":
                self.last_cycles = 0
                return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)
            target_offset = self.read_operand(source)
            target_segment = self.read_memory(
                source["segment"], (source["offset"] + 2) & 0xFFFF, 16
            )
            self.set_register(register_index, 16, target_offset)
            self.registers["ES" if opcode == 0xC4 else "DS"] = target_segment
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
        elif handler in ("movs", "cmps", "stos", "lods", "scas"):
            width = 16 if opcode & 1 else 8
            delta = width // 8
            if self.registers["FLAGS"] & self.flags["DF"]:
                delta = -delta
            iterations = self.registers["CX"] if repeat is not None else 1
            cycles = 0 if iterations == 0 else metadata["cycles"] * iterations
            for _ in range(iterations):
                source_segment = self.registers[segment_override or "DS"]
                if handler in ("movs", "cmps", "lods"):
                    source = self.read_memory(source_segment, self.registers["SI"], width)
                if handler in ("movs", "cmps", "stos", "scas"):
                    destination = self.read_memory(self.registers["ES"], self.registers["DI"], width)
                if handler == "movs":
                    self.write_memory(self.registers["ES"], self.registers["DI"], width, source)
                elif handler == "cmps":
                    self.alu("cmp", source, destination, width)
                elif handler == "stos":
                    self.write_memory(self.registers["ES"], self.registers["DI"], width, self.get_register(0, width))
                elif handler == "lods":
                    self.set_register(0, width, source)
                elif handler == "scas":
                    self.alu("cmp", self.get_register(0, width), destination, width)

                if handler in ("movs", "cmps", "lods"):
                    self.registers["SI"] = (self.registers["SI"] + delta) & 0xFFFF
                if handler in ("movs", "cmps", "stos", "scas"):
                    self.registers["DI"] = (self.registers["DI"] + delta) & 0xFFFF
                if repeat is not None:
                    self.registers["CX"] = (self.registers["CX"] - 1) & 0xFFFF
                    if handler in ("cmps", "scas"):
                        zf = bool(self.registers["FLAGS"] & self.flags["ZF"])
                        if (repeat == 0xF3 and not zf) or (repeat == 0xF2 and zf):
                            break
        elif handler in ("alu_modrm", "test_modrm"):
            width = 16 if opcode & 1 else 8
            rm_operand, reg_index = self.decode_modrm(width)
            reg_operand = {"kind": "register", "index": reg_index, "width": width}
            destination, source = (reg_operand, rm_operand) if opcode & 2 else (rm_operand, reg_operand)
            result = self.alu(metadata["operation"], self.read_operand(destination), self.read_operand(source), width)
            if metadata["operation"] != "cmp" and handler != "test_modrm":
                self.write_operand(destination, result)
        elif handler == "alu_rm_imm":
            width = 16 if opcode & 1 else 8
            destination, extension = self.decode_modrm(width)
            operation = ("add", "or", "adc", "sbb", "and", "sub", "xor", "cmp")[extension]
            if opcode == 0x83:
                immediate = self.fetch_u8()
                if immediate & 0x80:
                    immediate |= 0xFF00
            else:
                immediate = self.fetch_u16() if width == 16 else self.fetch_u8()
            result = self.alu(operation, self.read_operand(destination), immediate, width)
            if operation != "cmp":
                self.write_operand(destination, result)
        elif handler in ("alu_acc_imm8", "alu_acc_imm16", "test_acc_imm8", "test_acc_imm16"):
            width = 16 if handler.endswith("16") else 8
            destination = {"kind": "register", "index": 0, "width": width}
            immediate = self.fetch_u16() if width == 16 else self.fetch_u8()
            result = self.alu(metadata["operation"], self.read_operand(destination), immediate, width)
            if metadata["operation"] != "cmp" and not handler.startswith("test_"):
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
        elif handler == "loop_rel8":
            displacement = self.fetch_u8()
            if displacement & 0x80:
                displacement -= 0x100
            if opcode == 0xE3:
                taken = self.registers["CX"] == 0
            else:
                self.registers["CX"] = (self.registers["CX"] - 1) & 0xFFFF
                nonzero = self.registers["CX"] != 0
                zero_flag = bool(self.registers["FLAGS"] & self.flags["ZF"])
                taken = nonzero and (
                    opcode == 0xE2
                    or (opcode == 0xE1 and zero_flag)
                    or (opcode == 0xE0 and not zero_flag)
                )
            if taken:
                self.registers["IP"] = (self.registers["IP"] + displacement) & 0xFFFF
                cycles = 18
        elif handler == "call_rel16":
            displacement = self.fetch_u16()
            if displacement & 0x8000:
                displacement -= 0x10000
            self.push_u16(self.registers["IP"])
            self.registers["IP"] = (self.registers["IP"] + displacement) & 0xFFFF
        elif handler == "call_far":
            target_ip = self.fetch_u16()
            target_cs = self.fetch_u16()
            self.push_u16(self.registers["CS"])
            self.push_u16(self.registers["IP"])
            self.registers["IP"] = target_ip
            self.registers["CS"] = target_cs
        elif handler == "jmp_far":
            target_ip = self.fetch_u16()
            target_cs = self.fetch_u16()
            self.registers["IP"] = target_ip
            self.registers["CS"] = target_cs
        elif handler in ("in_imm", "in_dx"):
            width = 16 if opcode & 1 else 8
            port = self.fetch_u8() if handler == "in_imm" else self.registers["DX"]
            value = self.read_port_u8(port)
            if width == 16:
                value |= self.read_port_u8((port + 1) & 0xFFFF) << 8
            self.set_register(0, width, value)
        elif handler in ("out_imm", "out_dx"):
            width = 16 if opcode & 1 else 8
            port = self.fetch_u8() if handler == "out_imm" else self.registers["DX"]
            value = self.get_register(0, width)
            self.write_port_u8(port, value)
            if width == 16:
                self.write_port_u8((port + 1) & 0xFFFF, value >> 8)
        elif handler in ("ret_near", "ret_near_imm"):
            stack_adjust = self.fetch_u16() if handler == "ret_near_imm" else 0
            self.registers["IP"] = self.pop_u16()
            self.registers["SP"] = (self.registers["SP"] + stack_adjust) & 0xFFFF
        elif handler in ("ret_far", "ret_far_imm"):
            stack_adjust = self.fetch_u16() if handler == "ret_far_imm" else 0
            self.registers["IP"] = self.pop_u16()
            self.registers["CS"] = self.pop_u16()
            self.registers["SP"] = (self.registers["SP"] + stack_adjust) & 0xFFFF
        elif handler == "int3":
            self.interrupt(3)
        elif handler == "int_imm8":
            self.interrupt(self.fetch_u8())
        elif handler == "into":
            if self.registers["FLAGS"] & self.flags["OF"]:
                self.interrupt(4)
                cycles = 73
        elif handler == "iret":
            self.registers["IP"] = self.pop_u16()
            self.registers["CS"] = self.pop_u16()
            self.registers["FLAGS"] = (self.pop_u16() & 0x0FFF) | self.flags["RESERVED"]
        elif handler == "group3":
            width = 16 if opcode & 1 else 8
            operand, extension = self.decode_modrm(width)
            operand_value = self.read_operand(operand)
            if extension == 0:
                immediate = self.fetch_u16() if width == 16 else self.fetch_u8()
                self.alu("and", operand_value, immediate, width)
                cycles = 5 if operand["kind"] == "register" else 11
            elif extension == 2:
                self.write_operand(operand, ~operand_value & ((1 << width) - 1))
                cycles = 3 if operand["kind"] == "register" else 16
            elif extension in (4, 5):
                signed = extension == 5
                accumulator = self.registers["AX"] & ((1 << width) - 1)
                multiplier = operand_value
                if signed:
                    sign = 1 << (width - 1)
                    accumulator = accumulator - (sign << 1) if accumulator & sign else accumulator
                    multiplier = multiplier - (sign << 1) if multiplier & sign else multiplier
                product = accumulator * multiplier
                full_mask = (1 << (width * 2)) - 1
                encoded = product & full_mask
                if width == 8:
                    self.registers["AX"] = encoded
                else:
                    self.registers["AX"] = encoded & 0xFFFF
                    self.registers["DX"] = encoded >> 16
                upper = encoded >> width
                lower = encoded & ((1 << width) - 1)
                if signed:
                    expected_upper = ((1 << width) - 1) if lower & (1 << (width - 1)) else 0
                    overflow = upper != expected_upper
                else:
                    overflow = upper != 0
                self.set_flag("CF", overflow)
                self.set_flag("OF", overflow)
                self.set_flag("AF", False)
                self.update_result_flags(lower, width)
                cycles = 70 if width == 8 else 118
            elif extension not in (6, 7):
                self.last_cycles = 0
                return self.trace(before_ip, physical, opcode, "INVALID", 0xFF)
            else:
                divisor_raw = operand_value
                signed = extension == 7
                if width == 8:
                    dividend_raw = self.registers["AX"]
                    quotient_bits = 8
                else:
                    dividend_raw = (self.registers["DX"] << 16) | self.registers["AX"]
                    quotient_bits = 16
                if signed:
                    dividend_sign = 1 << (width * 2 - 1)
                    divisor_sign = 1 << (width - 1)
                    dividend = dividend_raw - (dividend_sign << 1) if dividend_raw & dividend_sign else dividend_raw
                    divisor = divisor_raw - (divisor_sign << 1) if divisor_raw & divisor_sign else divisor_raw
                else:
                    dividend = dividend_raw
                    divisor = divisor_raw
                divide_error = divisor == 0
                if not divide_error:
                    magnitude = abs(dividend) // abs(divisor)
                    quotient = -magnitude if (dividend < 0) != (divisor < 0) else magnitude
                    remainder = dividend - quotient * divisor
                    if signed:
                        minimum = -(1 << (quotient_bits - 1))
                        maximum = (1 << (quotient_bits - 1)) - 1
                    else:
                        minimum = 0
                        maximum = (1 << quotient_bits) - 1
                    divide_error = not minimum <= quotient <= maximum
                if divide_error:
                    self.interrupt(0)
                elif width == 8:
                    self.registers["AX"] = ((remainder & 0xFF) << 8) | (quotient & 0xFF)
                else:
                    self.registers["AX"] = quotient & 0xFFFF
                    self.registers["DX"] = remainder & 0xFFFF
                cycles = 80 if width == 8 else 144
        elif handler == "shift":
            width = 16 if opcode & 1 else 8
            destination, extension = self.decode_modrm(width)
            value = self.read_operand(destination)
            mask = (1 << width) - 1
            count = 1 if opcode < 0xD2 else self.get_register(1, 8)
            if count:
                initial = value
                carry = bool(self.registers["FLAGS"] & self.flags["CF"])
                for _ in range(count):
                    if extension == 0:
                        carry = bool(value & (1 << (width - 1)))
                        value = ((value << 1) | int(carry)) & mask
                    elif extension == 1:
                        carry = bool(value & 1)
                        value = (value >> 1) | (int(carry) << (width - 1))
                    elif extension == 2:
                        input_carry = carry
                        carry = bool(value & (1 << (width - 1)))
                        value = ((value << 1) | int(input_carry)) & mask
                    elif extension == 3:
                        input_carry = carry
                        carry = bool(value & 1)
                        value = (value >> 1) | (int(input_carry) << (width - 1))
                    elif extension in (4, 6):
                        carry = bool(value & (1 << (width - 1)))
                        value = (value << 1) & mask
                    else:
                        carry = bool(value & 1)
                        sign = value & (1 << (width - 1))
                        value >>= 1
                        if extension == 7:
                            value |= sign
                if extension in (0, 2):
                    overflow = bool(value & (1 << (width - 1))) != carry
                elif extension in (1, 3):
                    overflow = bool(value & (1 << (width - 1))) != bool(value & (1 << (width - 2)))
                elif extension in (4, 6):
                    first_result = (initial << 1) & mask
                    overflow = bool(first_result & (1 << (width - 1))) != bool(initial & (1 << (width - 1)))
                elif extension == 5:
                    overflow = bool(initial & (1 << (width - 1)))
                else:
                    overflow = False
                if count != 1:
                    overflow = False
                self.set_flag("CF", carry)
                self.set_flag("OF", overflow)
                if extension >= 4:
                    self.set_flag("AF", False)
                    self.update_result_flags(value, width)
                self.write_operand(destination, value)
            cycles = metadata["cycles"] if opcode < 0xD2 else 8 + 4 * count
        elif handler == "daa":
            original = self.get_register(0, 8)
            adjusted = original
            old_cf = bool(self.registers["FLAGS"] & self.flags["CF"])
            low_adjust = (original & 0x0F) > 9 or bool(self.registers["FLAGS"] & self.flags["AF"])
            if low_adjust:
                adjusted = (adjusted + 0x06) & 0xFF
            high_adjust = original > 0x99 or old_cf
            if high_adjust:
                adjusted = (adjusted + 0x60) & 0xFF
            self.set_register(0, 8, adjusted)
            self.set_flag("AF", low_adjust)
            self.set_flag("CF", high_adjust)
            self.set_flag("OF", False)
            self.update_result_flags(adjusted, 8)
        elif handler == "complement_cf":
            self.set_flag("CF", not bool(self.registers["FLAGS"] & self.flags["CF"]))
        elif handler in ("clear_cf", "set_cf", "clear_if", "set_if", "clear_df", "set_df"):
            action, flag = handler.split("_")
            self.set_flag(flag.upper(), action == "set")
            if handler == "set_if":
                self.interrupt_shadow = 1
        else:
            raise ValueError(f"reference handler is not implemented: {handler}")

        self.last_cycles = cycles
        return self.trace(before_ip, physical, opcode, metadata["mnemonic"], status)

    def trace(self, before_ip: int, physical: int, opcode: int | None, mnemonic: str, status: int) -> dict:
        result = {
            "cs": self.registers["CS"],
            "ip": before_ip,
            "physical": physical,
            "opcode": opcode,
            "mnemonic": mnemonic,
            "status": STATUS_NAMES[status],
            "cycles": self.last_cycles,
            "writes": list(self.memory_writes),
            "io": list(self.io_events),
            "after": {name: self.registers[name] for name in REGISTER_ORDER},
        }
        if self.last_interrupt_return_ip is not None:
            result["interruptReturnIP"] = self.last_interrupt_return_ip
        return result


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
    if "pendingIrq" in vector:
        cpu.pending_irq = vector["pendingIrq"] & 0xFF
    if vector.get("pendingNmi"):
        cpu.pending_nmi = True
    for entry in vector.get("ports", []):
        cpu.ports[entry["port"] & 0xFFFF] = entry["value"] & 0xFF

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
    if "expectedIo" in vector:
        actual_io = [event for entry in trace for event in entry["io"]]
        if actual_io != vector["expectedIo"]:
            raise AssertionError(f"{vector['name']}: I/O {actual_io} != {vector['expectedIo']}")
    for entry in vector.get("expectedPorts", []):
        actual = cpu.ports.get(entry["port"] & 0xFFFF, 0xFF)
        if actual != entry["value"]:
            raise AssertionError(
                f"{vector['name']}: port {entry['port']:#06x}={actual:#04x}, expected {entry['value']:#04x}"
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
