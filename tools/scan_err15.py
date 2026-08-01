data = open('third_party/pcem-roms/genxt/pcxt.rom', 'rb').read()
BASE = 0xE000

def show(name, p):
    i = 0
    while True:
        j = data.find(p, i)
        if j < 0:
            break
        print(f'{name}: F000:{BASE+j:04X}  bytes={data[j:j+6].hex()}')
        i = j + 1

# direct segment-override writes to offset 0x15
show('mov [0x15],al',            b'\xA2\x15\x00')
show('mov es:[0x15],al',         b'\x26\xA2\x15\x00')
show('mov byte [0x15],imm',      b'\xC6\x06\x15\x00')
show('mov byte es:[0x15],imm',   b'\x26\xC6\x06\x15\x00')

for op, mn in [(0x08, 'or'), (0x09, 'or'), (0x00, 'add'), (0x01, 'add'),
               (0x20, 'and'), (0x21, 'and'), (0x30, 'xor'), (0x88, 'mov'),
               (0x89, 'mov'), (0x0a, 'or r'), (0x0b, 'or r')]:
    show(f'{mn} [0x15]', bytes([op, 0x06, 0x15, 0x00]))
    show(f'{mn} es:[0x15]', bytes([0x26, op, 0x06, 0x15, 0x00]))
