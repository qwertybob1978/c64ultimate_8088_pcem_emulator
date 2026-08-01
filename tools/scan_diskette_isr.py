data = open('third_party/pcem-roms/genxt/pcxt.rom', 'rb').read()
BASE = 0xE000

def show(name, p):
    i = 0
    while True:
        j = data.find(p, i)
        if j < 0:
            break
        print(f'{name}: F000:{BASE+j:04X}  {data[j:j+7].hex()}')
        i = j + 1

# or byte [0x3e], 0x80  (set operation-complete bit)
show('or  [0x3e],80', b'\x80\x0e\x3e\x00\x80')
show('or  es:[0x3e],80', b'\x26\x80\x0e\x3e\x00\x80')
# mov byte [0x3e], imm
show('mov [0x3e],imm', b'\xc6\x06\x3e\x00')
# EOI to PIC: mov al,0x20 ; out 0x20,al  -> B0 20 E6 20
show('mov al,20;out 20', b'\xb0\x20\xe6\x20')
# IVT[0E] setup writes to 0000:0038 (offset) -> stores to [0x38]
show('mov [0x38],ax', b'\xa3\x38\x00')
show('mov [0x3a],ax', b'\xa3\x3a\x00')
