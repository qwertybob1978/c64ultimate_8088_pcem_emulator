#!/usr/bin/env python3
"""Parse build/fault-dump.bin using VICE label file."""
from pathlib import Path
import re

WORKSPACE = Path(__file__).resolve().parent.parent
DUMP = WORKSPACE / "build" / "fault-dump.bin"
LABELS = WORKSPACE / "build" / "c64x86-hwtest.lbl"
DUMP_START = 0x0400

def parse_labels(path):
    labels = {}
    for line in path.read_text().splitlines():
        m = re.match(r'al\s+([0-9A-Fa-f]+)\s+\.(\S+)', line)
        if m:
            labels[m.group(2)] = int(m.group(1), 16)
    return labels

def read(addr, n):
    off = addr - DUMP_START
    if off < 0 or off + n > len(dump):
        return None
    return dump[off:off+n]

def u8(addr):
    b = read(addr, 1)
    return b[0] if b else None

def u16(addr):
    b = read(addr, 2)
    return b[0] | (b[1] << 8) if b else None

def u32(addr):
    b = read(addr, 4)
    return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24) if b else None

def cs_ip(cs_addr, ip_addr):
    cs = u16(cs_addr)
    ip = u16(ip_addr)
    if cs is None or ip is None:
        return "???"
    return f"{cs:04X}:{ip:04X}"

labels = parse_labels(LABELS)
dump = DUMP.read_bytes()

print(f"Dump size: {len(dump)} bytes (covers ${DUMP_START:04X}-${DUMP_START+len(dump)-1:04X})")
print()

status = u8(labels['boot_failure_status'])
print(f"boot_failure_status = ${status:02X} ({status})")
print(f"Fault IP            = {cs_ip(labels['boot_fault_cs'], labels['boot_fault_ip'])}")
print(f"Fault SS:SP         = {cs_ip(labels['boot_fault_ss'], labels['boot_fault_sp'])}")
fb = read(labels['boot_fault_bytes'], 4)
print(f"Fault bytes         = {' '.join(f'{b:02X}' for b in fb)}")
sb = read(labels['boot_stack_bytes'], 4)
print(f"Stack bytes         = {' '.join(f'{b:02X}' for b in sb)}")
print()
print(f"Prev  CS:IP         = {cs_ip(labels['boot_prev_cs'], labels['boot_prev_ip'])}")
print(f"Prev  opcode/status = ${u8(labels['boot_prev_opcode']):02X} / ${u8(labels['boot_prev_status']):02X}")
pb = read(labels['boot_prev_bytes'], 4)
print(f"Prev  bytes         = {' '.join(f'{b:02X}' for b in pb)}")
print()
print(f"Prev2 CS:IP         = {cs_ip(labels['boot_prev2_cs'], labels['boot_prev2_ip'])}")
print(f"Prev2 opcode/status = ${u8(labels['boot_prev2_opcode']):02X} / ${u8(labels['boot_prev2_status']):02X}")
p2b = read(labels['boot_prev2_bytes'], 4)
print(f"Prev2 bytes         = {' '.join(f'{b:02X}' for b in p2b)}")
print()
print(f"Reset CS:IP         = {cs_ip(labels['boot_reset_cs'], labels['boot_reset_ip'])}")
rb = read(labels['boot_reset_bytes'], 5)
print(f"Reset bytes         = {' '.join(f'{b:02X}' for b in rb)}")
print()
print(f"Last opcode         = ${u8(labels['cpu8088_last_opcode']):02X}")
ft = read(labels['cpu8088_last_far_target'], 4)
# far_target layout is IP low, IP high, CS low, CS high? The code writes +3 first then +0 last, but memory order is little-endian as stored.
# We stored 4 bytes: cpu8088_last_far_target+0 .. +3. The display writes +3 (high CS), +2 (low CS), +1 (high IP), +0 (low IP).
print(f"Last far target     = CS {ft[3]:02X}{ft[2]:02X} IP {ft[1]:02X}{ft[0]:02X}")
nt = read(labels['cpu8088_last_near_target'], 2)
print(f"Last near target    = ${nt[1]:02X}{nt[0]:02X}")
ds = read(labels['cpu8088_last_direct_source'], 2)
dt = read(labels['cpu8088_last_direct_target'], 2)
print(f"Last direct source  = ${ds[1]:02X}{ds[0]:02X}")
print(f"Last direct target  = ${dt[1]:02X}{dt[0]:02X}")
print()
print(f"Interrupt stage     = ${u8(labels['cpu8088_interrupt_stage']):02X}")
print(f"Stack stage         = ${u8(labels['cpu8088_stack_stage']):02X}")
sph = labels.get('stack_fail_phys')
if sph:
    sp = read(sph, 3)
    print(f"stack_fail_phys     = ${sp[2]:02X}{sp[1]:02X}{sp[0]:02X}")
print(f"interrupt_vector    = ${u8(labels['interrupt_vector']):02X}")
ivt0 = read(labels['boot_fault_ivt0'], 4)
print(f"IVT[00h]            = {' '.join(f'{b:02X}' for b in ivt0)}")
ivt = read(labels['boot_fault_ivt'], 4)
print(f"IVT[09h]            = {' '.join(f'{b:02X}' for b in ivt)}")
ivt10 = read(labels['boot_fault_ivt0'] + 0x40, 4)
print(f"IVT[10h]            = {' '.join(f'{b:02X}' for b in ivt10)}")
print(f"pic_vector_base     = ${u8(labels['pic_vector_base']):02X}")
print(f"pic_mask            = ${u8(labels['pic_mask']):02X}")
print(f"cpu8088_irq_vector  = ${u8(labels['cpu8088_irq_vector']):02X}")
print()
print(f"interrupt_last_iret_stage = ${u8(labels['interrupt_last_iret_stage']):02X}")
print(f"interrupt_last_iret = {cs_ip(labels['interrupt_last_iret_cs'], labels['interrupt_last_iret_ip'])}")
print(f"interrupt_frame_mismatch = ${u8(labels['interrupt_frame_mismatch']):02X}")
print()
print(f"fdc_last_command    = ${u8(labels['fdc_last_command']):02X}")
print(f"fdc_dma_failures    = ${u8(labels['fdc_dma_failures']):02X}")
print(f"fdc_dor_writes      = ${u8(labels['fdc_dor_writes']):02X}")
print(f"pic_irq6_requests   = ${u8(labels['pic_irq6_requests']):02X}")
print(f"pic_irq6_deliveries = ${u8(labels['pic_irq6_deliveries']):02X}")
print(f"cpu8088_irq6_serviced = ${u8(labels['cpu8088_irq6_serviced']):02X}")
