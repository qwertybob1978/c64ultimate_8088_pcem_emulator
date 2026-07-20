AS := ca65
LD := ld65
BUILD_DIR := build
TARGET := $(BUILD_DIR)/c64x86-hwtest.prg
SOURCES := src/boot/hwtest.s src/host/turbo.s src/memory/reu.s \
	src/memory/page_cache.s src/cpu8088/state.s src/cpu8088/address.s \
	src/cpu8088/modrm.s src/cpu8088/stack.s src/memory/guest_memory.s \
	src/cpu8088/step.s src/video/cga.s
OBJECTS := $(patsubst src/%.s,$(BUILD_DIR)/%.o,$(SOURCES))

.PHONY: all clean test rom-image crt

all: $(TARGET)

$(TARGET): $(OBJECTS) cfg/c64x86.cfg
	python tools/generate_cpu8088.py --check
	$(LD) -C cfg/c64x86.cfg -m $(BUILD_DIR)/c64x86-hwtest.map \
		-Ln $(BUILD_DIR)/c64x86-hwtest.lbl -o $@ $(OBJECTS)

$(BUILD_DIR)/%.o: src/%.s
	@mkdir -p $(dir $@)
	$(AS) -I src -g -o $@ $<

test:
	python -m unittest discover -s tests -v

rom-image:
	python tools/build_guest_image.py --profile genxt

crt: $(TARGET)
	python tools/generate_cartridge_include.py
	$(AS) -I src -I $(BUILD_DIR) -g -o $(BUILD_DIR)/cartridge-bootstrap.o \
		src/cartridge/bootstrap.s
	$(LD) -C cfg/cartridge_bootstrap.cfg -o $(BUILD_DIR)/cartridge-bootstrap.bin \
		$(BUILD_DIR)/cartridge-bootstrap.o
	python tools/build_crt.py
	python tools/build_crt.py --check $(BUILD_DIR)/c64x86.crt

clean:
	rm -rf $(BUILD_DIR)
