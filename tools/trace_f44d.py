#!/usr/bin/env python3
"""Trace around F000:F44D stall point."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = json.loads((ROOT / "config/cpu8088.json").read_text())


class RefCPU:
    def __init__(self):
        self.registers = {"AX": 0, "CX": 0, "DX": 0, "BX": 0,
                          "SP": 0, "BP": 0, "SI": 0, "DI": 0,
                          "ES": 0, "CS": 0xFFFF, "SS": 0, "DS": 0,
                          "IP": 0, "FLAGS": 0x0002}
        self.memory = bytearray(1 << 20)
        self.halted = False
        self.pending_irq = None
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

    def reset(self):
        for name in self.registers:
            if name != "CS" and name != "FLAGS":
                self.registers[name] = 0
        self.registers["CS"] = 0xFFFF
        self.registers["FLAGS"] = 0x0002
        self.halted = False
        self.pending_irq = None
        self.interrupt_shadow = 0

    def physical(self, seg, off):
        return ((seg << 4) + off) & 0xFFFFF

    def fetch_u8(self):
        addr = self.physical(self.registers["CS"], self.registers["IP"])
        val = self.memory[addr]
        self.registers["IP"] = (self.registers["IP"] + 1) & 0xFFFF
        return val

    def read_port_u8(self, port):
        # Minimal I/O model matching native io.s behavior
        port_hi = (port >> 8) & 0xFF
        port_lo = port & 0xFF
        if port == 0x3B4 or port == 0x3D4:  # CRTC index - write only usually
            return self.ports.get(port, 0xFF)
        elif port == 0x3B5 or port == 0x3D5:  # CRTC data
            return self.ports.get(port, 0xFF)
        elif port == 0x3BA or port == 0x3DA:  # Video status
            v = self.video_status_phase.get(port, 0)
            self.video_status_phase[port] ^= 1
            mask = 9 if port == 0x3DA else 0
            return (v ^ 1) | mask
        elif port == 0xF4:  # FDC main status
            return self.ports.get(port, 0xE0)  # RQM=1, DIO=0, CB=0 normally
        elif port == 0xF7:  # FDC digital input
            return self.ports.get(port, 0x00)
        elif port == 0x61:  # PPI port B
            return self.ppi_port_b
        elif port == 0x62:  # DIP switches / misc
            return 0x06  # color display switch set
        elif port == 0xB8 or port == 0xD8:  # MDA/VGA control
            return self.ports.get(port, 0xFF)
        else:
            return self.ports.get(port, 0xFF)

    def write_port_u8(self, port, value):
        self.io_events.append(("OUT", port, value))
        if port == 0x3B4 or port == 0x3D4:  # CRTC index
            self.ports[port] = value
        elif port == 0x3B5 or port == 0x3D5:  # CRTC data
            self.ports[(0x3B4 if port == 0x3B5 else 0x3D4)] = value
            self.ports[port] = value
        elif port == 0x3C0 or port == 0x3C8 or port == 0x3C9:  # Sequencer/Attribute
            self.ports[port & ~1] = value
        elif port == 0x3C4 or port == 0x3C5:  # EGA sequencer
            self.ports[port] = value
            self.ports[port & ~1] = value
        elif port == 0x3CE or port == 0x3CF:  # Graphics controller
            self.ports[port] = value
            self.ports[port & ~1] = value
        elif port in (0x3B8, 0x3D8):  # Mode control - write only
            pass
        elif port == 0x61:  # PPI port B
            self.ppi_port_b ^= (value ^ self.ppi_port_b) & 0xC0
        elif port == 0xF2:  # FDC DOR
            self.ports[0xF2] = value
        elif port == 0xF5:  # FDC data
            self.ports[0xF5] = value


def main():
    cpu = RefCPU()
    
    # Load genxt ROM
    rom_path = ROOT / "third_party" / "roms" / "genxt" / "pcxt.rom"
    if not rom_path.exists():
        print(f"No ROM at {rom_path}")
        return
    rom = rom_path.read_bytes()
    base = 0xFE000
    for i, b in enumerate(rom):
        cpu.memory[(base + i) & 0xFFFFF] = b
    
    cpu.reset()
    
    # Run and collect events near F4xx
    stall_ip = None
    stall_opcode = None
    io_events_near_stall = []
    step_count = 0
    
    for _ in range(100000):
        before_ip = cpu.registers["IP"]
        cs = cpu.registers["CS"]
        
        opcode = cpu.fetch_u8()
        physical = ((cs << 4) + before_ip) & 0xFFFFF
        
        mnemonic = cpu.opcodes.get(opcode, {}).get("mnemonic", f"UNKNOWN_{opcode:02X}")
        
        # Handle simple opcodes needed by BIOS boot path
        if opcode == 0xE6:  # OUT imm8,AL/AX
            port = cpu.fetch_u8()
            al_val = cpu.registers["AX"] & 0xFF
            ax_val = cpu.registers["AX"]
            cpu.write_port_u8(port, al_val)
            if port & 0xFF != 0:  # skip zero-port writes
                io_events_near_stall.append(("OUT", port, al_val))
            continue
        elif opcode == 0xE7:  # OUT imm8,AX
            port = cpu.fetch_u8()
            ax_val = cpu.registers["AX"]
            cpu.write_port_u8(port, ax_val & 0xFF)
            cpu.write_port_u8((port + 1) & 0xFFFF, (ax_val >> 8) & 0xFF)
            continue
        elif opcode == 0xEC:  # IN AL,DX
            dx = cpu.registers["DX"]
            val = cpu.read_port_u8(dx)
            cpu.registers["AX"] = (cpu.registers["AX"] & 0xFF00) | val
            continue
        elif opcode == 0xED:  # IN AX,DX
            dx = cpu.registers["DX"]
            lo = cpu.read_port_u8(dx)
            hi = cpu.read_port_u8((dx + 1) & 0xFFFF)
            cpu.registers["AX"] = (hi << 8) | lo
            continue
        elif opcode == 0xEB:  # JMP rel8
            disp = cpu.fetch_u8()
            if disp > 0x7F:
                disp -= 0x100
            cpu.registers["IP"] = (before_ip + disp) & 0xFFFF
            continue
        elif opcode == 0xE9:  # JMP rel16
            disp = cpu.fetch_u8() | (cpu.fetch_u8() << 8)
            if disp > 0x7FFF:
                disp -= 0x10000
            cpu.registers["IP"] = (before_ip + disp) & 0xFFFF
            continue
        elif opcode in (0x74, 0x75, 0x72, 0x73, 0x70, 0x71, 0x76, 0x77,
                        0x78, 0x79, 0x7A, 0x7B):  # JCC rel8
            zf = bool(cpu.registers["FLAGS"] & 0x40)
            cf = bool(cpu.registers["FLAGS"] & 0x01)
            sf = bool(cpu.registers["FLAGS"] & 0x08)
            of = bool(cpu.registers["FLAGS"] & 0x80)
            take = False
            cond = opcode - 0x70
            if cond == 0: take = not zf  # JE
            elif cond == 1: take = zf  # JNE
            elif cond == 2: take = not cf  # JB
            elif cond == 3: take = cf  # JAE
            elif cond == 4: take = not sf  # JN<
            elif cond == 5: take = sf  # J<
            elif cond == 6: take = not (sf ^ of)  # JNA
            elif cond == 7: take = sf ^ of  # JA
            elif cond == 8: take = not of  # JNO
            elif cond == 9: take = of  # JO
            elif cond == 10: take = not (zf or cf)  # JNB
            elif cond == 11: take = zf or cf  # JBE
            elif cond == 12: take = not zf and not cf  # JNBE
            elif cond == 13: take = zf or sf  # JS
            elif cond == 14: take = not zf and not sf  # JNS
            elif cond == 15: take = not (zf or sf ^ of)  # JNAE ... 
            disp = cpu.fetch_u8()
            if disp > 0x7F:
                disp -= 0x100
            if take:
                cpu.registers["IP"] = (before_ip + disp) & 0xFFFF
            continue
        elif opcode == 0xCD:  # INT imm8
            vec = cpu.fetch_u8()
            # Push flags, CS, IP; clear IF, TF
            cpu.registers["FLAGS"] &= ~0x0203
            # Read vector from physical address
            vaddr = ((cpu.registers["CS"] << 4) + before_ip) & 0xFFFFF  # wrong but skip for now
            # For boot path, we mainly care about INT 18h/19h
            if vec == 0x18:
                pass  # ROM BASIC entry - skip
            elif vec == 0x19:
                pass  # Bootstrap - would need full state
            else:
                pass  # Skip other interrupts for tracing
            continue
        
        # Track when we hit F4xx range
        if cs == 0xF000 and 0xF400 <= before_ip < 0xF500:
            step_count += 1
            print(f"Step {step_count}: CS={cs:04X} IP={before_ip:04X} OP={opcode:02X} MN={mnemonic}")
            
            if stall_ip is None:
                stall_ip = before_ip
                stall_opcode = opcode
            
            # Collect I/O events near stall
            io_events_near_stall.append(("STEP", cs, before_ip, opcode))
    
    print(f"\nTotal steps in F4xx range: {step_count}")
    if io_events_near_stall:
        print("\nI/O events during stall loop:")
        seen_ports = set()
        for evt in io_events_near_stall[-100:]:
            if isinstance(evt[1], int):  # OUT event
                port = evt[1]
                if port not in seen_ports:
                    seen_ports.add(port)
                    print(f"  Port {port:04X}: value {evt[2]:02X}")


if __name__ == "__main__":
    main()
