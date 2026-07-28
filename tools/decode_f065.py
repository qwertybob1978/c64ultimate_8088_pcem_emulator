#!/usr/bin/env python3
"""Decode exact bytes around F065 in the Generic XT BIOS."""
import json
from pathlib import Path


def main():
    # Load opcode metadata
    spec = json.loads(Path('config/cpu8088.json').read_text())
    
    # Build opcode lookup
    opcodes = {}
    for entry in spec['opcodes']:
        for opc in range(entry['first'], entry['last'] + 1):
            opcodes[opc] = entry
    
    # Read ROM data from REU image
    reu_data = Path('build/guest-genxt.reu').read_bytes()
    
    # Calculate physical address of CS:F000 IP:F065
    phys = ((0xF000 << 4) + 0xF065) & 0xFFFFF
    print(f"Physical address for CS=F000h IP=F065h: {phys:#07X}")
    print(f"ROM region: FE000h - FFFFFh")
    print(f"In ROM bounds? {0xFE000 <= phys < 0x100000}\n")
    
    # Decode bytes starting at F065
    print("=== Bytes around F065 (offsets -8 to +32) ===")
    print(f"{'Offset':>6} {'Phys Addr':>10} {'Byte':>6} {'Mnemonic':<20} {'Details'}")
    print("-" * 80)
    
    for offset in range(-8, 33):
        p = (phys + offset) & 0xFFFFF
        byte_val = reu_data[p] if p < len(reu_data) else 0xFF
        
        entry = opcodes.get(byte_val)
        mnemonic = entry['mnemonic'][:18].ljust(18) if entry else '???'
        
        marker = " <-- START" if offset == 0 else ""
        print(f"{offset:+6d} {p:#07X} ${byte_val:02X}   {mnemonic:<20}{marker}")
    
    # Now decode a few instructions manually starting at F065
    print("\n\n=== Instruction decode starting at F065 ===")
    pos = phys
    for i in range(20):
        byte_val = reu_data[pos]
        entry = opcodes.get(byte_val)
        
        if not entry:
            mne = '???'
            details = ''
        elif entry['handler'] in ('nop', 'hlt'):
            mne = entry['mnemonic']
            details = '(no operands)'
        elif entry['handler'].startswith(('mov_r8_imm8', 'mov_r16_imm16')):
            imm_byte = reu_data[(pos+1) & 0xFFFFF]
            imm_word = reu_data[(pos+1) & 0xFFFFF] | (reu_data[(pos+2) & 0xFFFFF] << 8)
            reg_num = byte_val - (0xB0 if 'r8' in entry['handler'] else 0xB8)
            reg_names_8 = ['AL','CL','DL','BL','AH','CH','DH','BH']
            reg_names_16 = ['AX','CX','DX','BX','SP','BP','SI','DI']
            width = '8' if 'r8' in entry['handler'] else '16'
            mne = f'MOV R{width}:{reg_names_8[reg_num] if width=="8" else reg_names_16[reg_num]},imm${imm_word:X}'
            details = f'(length={entry["length"]})'
        elif entry['handler'] == 'set_if':
            mne = 'STI'
            details = '(enable interrupts)'
        elif entry['handler'] == 'clear_df':
            mne = 'CLD'
            details = '(clear direction flag)'
        elif entry['handler'] == 'push_reg16':
            reg_idx = byte_val & 7
            reg_names = ['AX','CX','DX','BX','SP','BP','SI','DI']
            mne = f'PUSH {reg_names[reg_idx]}'
            details = ''
        elif entry['handler'] == 'pop_reg16':
            reg_idx = byte_val & 7
            reg_names = ['AX','CX','DX','BX','SP','BP','SI','DI']
            mne = f'POP {reg_names[reg_idx]}'
            details = ''
        elif entry['handler'] == 'segment_stack':
            seg_names = ['ES','CS','SS','DS']
            idx = (byte_val >> 3) & 3
            mne = f'MOV {seg_names[idx]},mem16'
            details = ''
        elif entry['handler'] == 'grp1_immediate':
            # Need ModR/M to decode properly, just show raw
            modrm = reu_data[(pos+1) & 0xFFFFF]
            mne = f'GRP1_imm ${byte_val:02X} [ModR/M=${modrm:02X}]'
            details = '(needs full decoder)'
        elif entry['handler'].startswith('int'):
            vec = reu_data[(pos+1) & 0xFFFFF]
            mne = f'INT ${vec:#x}'
            details = f'(vector {vec})'
        else:
            mne = entry['mnemonic'][:15].ljust(15)
            details = f'[handler={entry["handler"]}]'
        
        print(f"[{i:2d}] @{((0xF000<<4)+phys-pos):04X}:$(pos-phys){byte_val:02X}   {mne:<30}{details}")
        
        pos += entry.get('length', 1) if entry else 1
        
        # Stop if we hit a clear return or jump away
        if i > 15 and offset > 20:
            break


if __name__ == '__main__':
    raise SystemExit(main())
