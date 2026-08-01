import pathlib
import re
import unittest
import json
import hashlib
import importlib.util
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_guest_image_module():
    path = ROOT / "tools/build_guest_image.py"
    spec = importlib.util.spec_from_file_location("build_guest_image", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_crt_module():
    path = ROOT / "tools/build_crt.py"
    spec = importlib.util.spec_from_file_location("build_crt", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_dos_media_module():
    path = ROOT / "tools/validate_dos_media.py"
    spec = importlib.util.spec_from_file_location("validate_dos_media", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_hex_constant(source: str, name: str) -> int:
    match = re.search(rf"^{name}\s*=\s*\$([0-9A-Fa-f]+)", source, re.MULTILINE)
    if not match:
        raise AssertionError(f"missing assembly constant: {name}")
    return int(match.group(1), 16)


class Phase0Contracts(unittest.TestCase):
    def test_genxt_runtime_patch_bypasses_only_fdc_reset_status_check(self):
        rom = (ROOT / "third_party/pcem-roms/genxt/pcxt.rom").read_bytes()
        self.assertEqual(rom[0x0D08:0x0D0A], bytes((0x3C, 0xC0)))
        self.assertEqual(rom[0x1980], 0x51)
        self.assertEqual(rom[0x0507:0x050B], bytes((0xCD, 0x19, 0x07, 0x26)))
        self.assertEqual(rom[0x06A0:0x06BC], bytes((0xFF,)) * 28)

        source = (ROOT / "src/memory/guest_init.s").read_text()
        self.assertRegex(
            source,
            r"lda\s+#\$EB\s+sta\s+guest_genxt_bios\+\$0D08\s+"
            r"lda\s+#\$09\s+sta\s+guest_genxt_bios\+\$0D09",
        )
        self.assertRegex(
            source,
            r"lda\s+#\$C3\s+sta\s+guest_genxt_bios\+\$1980",
        )
        self.assertRegex(source, r"lda\s+#\$FA\s+sta\s+guest_genxt_bios\+\$0507")
        self.assertRegex(source, r"lda\s+#\$E9\s+sta\s+guest_genxt_bios\+\$0508")
        self.assertRegex(source, r"lda\s+#\$95\s+sta\s+guest_genxt_bios\+\$0509")
        self.assertRegex(source, r"lda\s+#\$01\s+sta\s+guest_genxt_bios\+\$050A")
        self.assertIn("sta guest_genxt_bios+$06A0,x", source)
        self.assertIn("$B8,$A5,$FE,$A3,$20,$00", source)
        self.assertIn("$B8,$59,$EC,$A3,$4C,$00", source)
        self.assertIn("$B8,$00,$F0,$A3", source)
        self.assertIn("$22,$00,$A3,$4E,$00", source)
        self.assertIn("$E9,$36,$00", source)

    def test_boot_autokey_answers_genxt_continue_prompt_with_y(self):
        source = (ROOT / "src/boot/hwtest.s").read_text()
        self.assertIn("cmp #$F9", source)
        self.assertIn("cmp #$80", source)
        self.assertIn("cmp #$A3", source)
        self.assertRegex(
            source,
            r"lda\s+#\$15\s+; XT set-1 Y make code\s+jsr\s+io_keyboard_push\s+"
            r"lda\s+#\$95\s+; XT set-1 Y break code",
        )

    def test_genxt_speaker_entry_installs_verified_vectors_before_cpu_step(self):
        source = (ROOT / "src/boot/hwtest.s").read_text()
        self.assertIn("jsr install_genxt_boot_ivt", source)
        self.assertIn("ldx boot_genxt_ivt_index", source)
        self.assertIn("inc boot_genxt_ivt_index", source)
        self.assertRegex(
            source,
            r"cmp\s+#\$80\s+bne\s+@done\s+"
            r"lda\s+cpu8088_state\+CPU_IP\+1\s+cmp\s+#\$F9",
        )
        self.assertIn(".word $FEA5,$E987,$FF23,$FF23,$FF23,$FF23,$EF57,$FF23", source)
        self.assertIn(".word $F065,$F84D,$F841,$EC59", source)
        self.assertIn(".word $FF23,$E6F2,$FE6E,$FF53,$FF53,$F0A4,$EFC7,$0000", source)

    def test_genxt_bad_default_interrupt_target_uses_verified_offsets(self):
        source = (ROOT / "src/cpu8088/interrupts.s").read_text()
        self.assertRegex(
            source,
            r"lda\s+interrupt_ip\+1\s+cmp\s+#\$E0\s+bne\s+@install_vector",
        )
        self.assertRegex(
            source,
            r"lda\s+interrupt_vector\s+cmp\s+#\$08\s+bcc\s+@install_vector\s+"
            r"cmp\s+#\$20\s+bcs\s+@install_vector",
        )
        self.assertIn(".word $F065,$F84D,$F841,$EC59", source)

    @classmethod
    def setUpClass(cls):
        cls.hardware = (ROOT / "src/host/hardware.inc").read_text()

    def test_turbo_register_and_maximum_index(self):
        self.assertEqual(parse_hex_constant(self.hardware, "U64_TURBO_CONTROL"), 0xD031)
        control = parse_hex_constant(self.hardware, "U64_TURBO_MAX")
        self.assertEqual(control & 0x0F, 15)
        self.assertTrue(control & 0x80)

    def test_reu_register_block(self):
        registers = [
            "REU_STATUS", "REU_COMMAND", "REU_C64_ADDR_LO",
            "REU_C64_ADDR_HI", "REU_REU_ADDR_LO", "REU_REU_ADDR_MI",
            "REU_REU_ADDR_HI", "REU_LENGTH_LO", "REU_LENGTH_HI",
            "REU_IRQ_MASK", "REU_ADDR_CONTROL",
        ]
        values = [parse_hex_constant(self.hardware, name) for name in registers]
        self.assertEqual(values, list(range(0xDF00, 0xDF0B)))

    def test_immediate_reu_transfer_commands(self):
        self.assertEqual(parse_hex_constant(self.hardware, "REU_CMD_TO_REU"), 0x90)
        self.assertEqual(parse_hex_constant(self.hardware, "REU_CMD_FROM_REU"), 0x91)

    def test_pcem_reference_is_pinned_to_clone(self):
        lock = (ROOT / "references/pcem.commit").read_text()
        expected = re.search(r"^commit=([0-9a-f]{40})$", lock, re.MULTILINE)
        self.assertIsNotNone(expected)

        head = ROOT / "third_party/pcem/.git/refs/heads/dev"
        if head.exists():
            self.assertEqual(head.read_text().strip(), expected.group(1))

    def test_rom_manifest_matches_local_inputs(self):
        manifest = json.loads((ROOT / "config/roms.json").read_text())
        rom_root = ROOT / "third_party/pcem-roms"
        for profile in manifest["profiles"].values():
            for entry in profile["files"]:
                path = rom_root / entry["path"]
                if not path.exists():
                    continue
                data = path.read_bytes()
                self.assertEqual(len(data), entry["size"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])

    def test_8088_segmented_address_examples(self):
        physical = lambda segment, offset: ((segment << 4) + offset) & 0xFFFFF
        self.assertEqual(physical(0xFFFF, 0x0000), 0xFFFF0)
        self.assertEqual(physical(0xFFFF, 0x0010), 0x00000)
        self.assertEqual(physical(0x1234, 0x5678), 0x179B8)

    @unittest.skipUnless(
        (ROOT / "third_party/pcem-roms/genxt/pcxt.rom").exists(),
        "local PCem ROM checkout not present",
    )
    def test_genxt_guest_image_maps_reset_vector_rom(self):
        module = load_guest_image_module()
        image = module.build_image(
            ROOT / "config/roms.json",
            ROOT / "third_party/pcem-roms",
            "genxt",
        )
        rom = (ROOT / "third_party/pcem-roms/genxt/pcxt.rom").read_bytes()
        self.assertEqual(len(image), 0x100000)
        self.assertEqual(image[0xFE000:0x100000], rom)
        self.assertEqual(image[0xFFFF0:0x100000], rom[-16:])
        self.assertEqual(image[0x00000:0xA0000], bytes(0xA0000))

    def test_magic_desk_crt_structure(self):
        module = load_crt_module()
        with tempfile.TemporaryDirectory() as directory:
            temporary = pathlib.Path(directory)
            bootstrap = temporary / "bootstrap.bin"
            payload = temporary / "payload.prg"
            output = temporary / "test.crt"
            header = bytearray([0x00, 0x80, 0x00, 0x80])
            header.extend(module.AUTOSTART_SIGNATURE)
            header.extend(bytes(0x100 - len(header)))
            bootstrap.write_bytes(header)
            payload.write_bytes(b"\x01\x08\x60")
            module.build(bootstrap, payload, output)
            details = module.validate(output)
            self.assertEqual(details["type"], 19)
            self.assertEqual(details["banks"], 4)
            self.assertEqual(details["size"], 0x40 + 4 * (0x10 + 0x2000))

    def test_magic_desk_payload_crosses_bank_boundary(self):
        module = load_crt_module()
        with tempfile.TemporaryDirectory() as directory:
            temporary = pathlib.Path(directory)
            bootstrap = temporary / "bootstrap.bin"
            payload = temporary / "payload.prg"
            output = temporary / "test.crt"
            header = bytearray([0x00, 0x80, 0x00, 0x80])
            header.extend(module.AUTOSTART_SIGNATURE)
            header.extend(bytes(0x100 - len(header)))
            bootstrap.write_bytes(header)
            payload_bytes = bytes(index & 0xFF for index in range(0x2100))
            payload.write_bytes(b"\x01\x08" + payload_bytes)
            module.build(bootstrap, payload, output)

            image = output.read_bytes()
            bank_zero = 0x40 + 0x10
            bank_one = bank_zero + module.BANK_SIZE + 0x10
            first_size = module.BANK_SIZE - module.BOOTSTRAP_SIZE
            self.assertEqual(
                image[bank_zero + module.BOOTSTRAP_SIZE:bank_zero + module.BANK_SIZE],
                payload_bytes[:first_size],
            )
            self.assertEqual(
                image[bank_one:bank_one + len(payload_bytes) - first_size],
                payload_bytes[first_size:],
            )

    def test_dos_boot_media_manifest_describes_360k_geometry(self):
        manifest = json.loads((ROOT / "config/dos_media.json").read_text())
        boot = manifest["disks"]["boot"]
        self.assertEqual(boot["size"], 360 * 1024)
        self.assertEqual(boot["bytesPerSector"], 512)
        self.assertEqual(boot["totalSectors"], 720)
        self.assertEqual(boot["sectorsPerTrack"], 9)
        self.assertEqual(boot["heads"], 2)
        self.assertIn("never commit", manifest["distribution"].lower())

    def test_local_dos_boot_media_when_present(self):
        candidates = list((ROOT / ".cache/media/msdos330").rglob("DISK01.IMG"))
        if not candidates:
            self.skipTest("user-supplied DOS media not present")
        details = load_dos_media_module().validate(candidates[0])
        self.assertEqual(details["size"], 368640)

    def test_cga_crtc_cursor_registers_are_shadowed(self):
        source = (ROOT / "src/video/cga.s").read_text()
        self.assertIn("cga_mono_cursor_start", source)
        self.assertIn("cga_color_cursor_start", source)
        self.assertIn("cga_mono_cursor_pos", source)
        self.assertIn("cga_color_cursor_pos", source)
        self.assertRegex(source, r"cpx\s+#\$0A\s+beq\s+@cursor_start")
        self.assertRegex(source, r"cpx\s+#\$0F\s+beq\s+@cursor_pos_lo")
        self.assertRegex(source, r"cpx\s+#\$0A\s+beq\s+@ccursor_start")
        self.assertRegex(source, r"cpx\s+#\$0F\s+beq\s+@ccursor_pos_lo")

    def test_cga_render_picks_the_denser_text_half(self):
        source = (ROOT / "src/video/cga.s").read_text()
        render = source.split("cga_render_text_40:", 1)[1].split(
            "cga_test_render:", 1
        )[0]
        self.assertIn("cga_row_left_count", render)
        self.assertIn("cga_row_right_count", render)
        self.assertIn("cga_row_base", render)
        self.assertRegex(render, r"lda\s+cga_row_right_count\s+cmp\s+cga_row_left_count")
        self.assertRegex(render, r"lda\s+#\$50")

    def test_cga_render_uses_crtc_start_address(self):
        source = (ROOT / "src/video/cga.s").read_text()
        render = source.split("cga_render_text_40:", 1)[1].split(
            "cga_test_render:", 1
        )[0]
        helper = source.split("cga_apply_color_start_address:", 1)[1].split(
            "cga_ascii_to_screen:", 1
        )[0]
        self.assertIn("jsr cga_apply_color_start_address", render)
        self.assertRegex(helper, r"lda\s+cga_color_crtc_regs\+\$0C")
        self.assertRegex(helper, r"lda\s+cga_color_crtc_regs\+\$0D")
        self.assertRegex(helper, r"adc\s+cga_text_start_offset")
        self.assertRegex(helper, r"adc\s+cga_text_start_offset\+1")

    def test_xt_high_page_io_routes_cga_register_ports(self):
        source = (ROOT / "src/bus/io.s").read_text()
        read_dispatch = source.split("@high_page_03:", 1)[1].split("@video_status_03:", 1)[0]
        write_dispatch = source.split("@write_high_page_03:", 1)[1].split("@write_fdc_dor:", 1)[0]
        for port, target in (
            ("#$B4", "@cga_mono_crtc_index"),
            ("#$B5", "@cga_mono_crtc_data"),
            ("#$B8", "@cga_mono_mode_control"),
            ("#$B9", "@cga_mono_color_select"),
            ("#$D4", "@cga_color_crtc_index"),
            ("#$D5", "@cga_color_crtc_data"),
            ("#$D8", "@cga_color_mode_control"),
            ("#$D9", "@cga_color_select"),
        ):
            self.assertRegex(
                read_dispatch,
                rf"cmp\s+{re.escape(port)}\s+(?:beq|long_beq)\s+{re.escape(target)}",
            )
            self.assertRegex(
                write_dispatch,
                rf"cpx\s+{re.escape(port)}\s+(?:beq|long_beq)\s+@write_{re.escape(target[1:])}",
            )

    def test_xt_color_status_port_toggles_display_and_retrace_bits(self):
        source = (ROOT / "src/bus/io.s").read_text()
        read_dispatch = source.split("@high_page_03:", 1)[1].split(
            "@video_status_03:", 1
        )[0]
        status_handler = source.split("@video_status_03:", 1)[1].split(
            "@fdc_density_config:", 1
        )[0]
        status_handler += source.split("@toggle_video_status:", 1)[1].split(
            "@keyboard_data:", 1
        )[0]
        self.assertRegex(read_dispatch, r"cmp\s+#\$DA\s+beq\s+@video_status_03")
        self.assertIn("lda io_video_status,x", status_handler)
        self.assertIn("eor #$01", status_handler)
        self.assertIn("lda #$09", status_handler)

    def test_xt_high_page_io_preserves_fdc_routes(self):
        source = (ROOT / "src/bus/io.s").read_text()
        read_dispatch = source.split("@high_page_03:", 1)[1].split(
            "@video_status_03:", 1
        )[0]
        write_dispatch = source.split("@write_high_page_03:", 1)[1].split(
            "@write_fdc_dor:", 1
        )[0]
        for port, target in (
            ("#$F3", "@fdc_density_config"),
            ("#$F4", "@fdc_main_status"),
            ("#$F5", "@fdc_data"),
            ("#$F7", "@fdc_digital_input"),
        ):
            self.assertRegex(
                read_dispatch,
                rf"cmp\s+{re.escape(port)}\s+(?:beq|long_beq)\s+{re.escape(target)}",
            )
        for port, target in (
            ("#$F2", "@write_fdc_dor"),
            ("#$F5", "@write_fdc_data"),
        ):
            self.assertRegex(
                write_dispatch,
                rf"cpx\s+{re.escape(port)}\s+(?:beq|long_beq)\s+{re.escape(target)}",
            )

    def test_boot_guest_injects_real_y_make_break_pair(self):
        source = (ROOT / "src/boot/hwtest.s").read_text()
        boot = source.split("boot_guest:", 1)[1].split("display_fdc_runtime:", 1)[0]
        self.assertRegex(boot, r"lda\s+#\$15[\s\S]*jsr\s+io_keyboard_push[\s\S]*lda\s+#\$95[\s\S]*jsr\s+io_keyboard_push[\s\S]*jsr\s+io_keyboard_service[\s\S]*jsr\s+io_keyboard_service[\s\S]*jsr\s+io_keyboard_service")
    def test_boot_guest_resets_xt_keyboard_before_autokey(self):
        source = (ROOT / "src/boot/hwtest.s").read_text()
        boot = source.split("boot_guest:", 1)[1].split("display_fdc_runtime:", 1)[0]
        self.assertIn("jsr io_keyboard_reset", boot)
        self.assertRegex(boot, r"jsr\s+cpu8088_reset[\s\S]*jsr\s+io_keyboard_reset")
    def test_xt_keyboard_queue_symbols_are_exported_for_diagnostics(self):
        source = (ROOT / "src/bus/io.s").read_text()
        for sym in (
            ".export io_keyboard_pa",
            ".export io_keyboard_key_waiting",
            ".export io_keyboard_wantirq",
            ".export io_keyboard_count",
        ):
            self.assertIn(sym, source)
    def test_xt_keyboard_reset_is_exported_for_boot_use(self):
        source = (ROOT / "src/bus/io.s").read_text()
        self.assertIn(".export io_keyboard_reset", source)
    def test_xt_keyboard_reset_initializes_bda_keyboard_buffer(self):
        source = (ROOT / "src/bus/io.s").read_text()
        reset = source.split("io_keyboard_reset:", 1)[1].split("io_fdc_data_writes:", 1)[0]
        self.assertRegex(reset, r"lda\s+#\$00[\s\S]*sta\s+io_keyboard_head[\s\S]*sta\s+io_keyboard_tail")
        self.assertRegex(reset, r"lda\s+#<\$041A[\s\S]*lda\s+#\$1E[\s\S]*jsr\s+cpu8088_mem_write_u8[\s\S]*lda\s+#<\$041C[\s\S]*lda\s+#\$20[\s\S]*jsr\s+cpu8088_mem_write_u8")
        self.assertRegex(reset, r"lda\s+#<\$041F[\s\S]*lda\s+#\$00[\s\S]*jsr\s+cpu8088_mem_write_u8")
    def test_xt_keyboard_queue_and_reset_are_modeled(self):
        source = (ROOT / "src/bus/io.s").read_text()
        self.assertIn("io_keyboard_queue", source)
        self.assertIn("io_keyboard_head", source)
        self.assertIn("io_keyboard_tail", source)
        self.assertIn("io_keyboard_count", source)
        self.assertIn("io_keyboard_pa", source)
        self.assertIn("io_keyboard_wantirq", source)
        self.assertIn("io_keyboard_shift_full", source)
        self.assertRegex(source, r"@keyboard_data:[\s\S]*lda\s+io_keyboard_pa[\s\S]*rts")
        self.assertRegex(source, r"io_keyboard_service:[\s\S]*lda\s+io_keyboard_wantirq[\s\S]*sta\s+io_keyboard_pa[\s\S]*jsr\s+pic_request_irq[\s\S]*lda\s+io_keyboard_count[\s\S]*lda\s+io_keyboard_queue,y[\s\S]*sta\s+io_keyboard_key_waiting[\s\S]*sta\s+io_keyboard_wantirq")
        self.assertRegex(source, r"@write_ppi_port_b:[\s\S]*and\s+#\$80[\s\S]*jsr\s+io_keyboard_service")
        self.assertRegex(source, r"io_keyboard_push:[\s\S]*sta\s+io_keyboard_queue,y[\s\S]*inc\s+io_keyboard_count")
        self.assertRegex(source, r"io_keyboard_reset:[\s\S]*lda\s+#\$AA[\s\S]*sta\s+io_keyboard_pa")
    def test_host_keyboard_poll_services_keyboard_then_emits_make_and_break(self):
        source = (ROOT / "src/host/keyboard.s").read_text()
        poll = source.split("host_keyboard_poll:", 1)[1].split(
            "host_keyboard_translate:", 1
        )[0]
        self.assertRegex(poll, r"jsr\s+io_keyboard_service[\s\S]*jsr\s+io_keyboard_push[\s\S]*ora\s+#\$80[\s\S]*jsr\s+io_keyboard_push")
        self.assertRegex(poll, r"jsr\s+pic_request_irq")

    def test_dma_flushes_cpu_cache_before_direct_transfer(self):
        source = (ROOT / "src/devices/dma.s").read_text()
        self.assertIn(".import cpu8088_mem_cache_flush", source)
        save = source.index("sta dma_source_addr+2")
        flush = source.index("jsr cpu8088_mem_cache_flush")
        transfer = source.index("jsr reu_copy_from_reu")
        self.assertLess(save, flush)
        self.assertLess(flush, transfer)

    def test_fdc_read_id_consumes_drive_head_parameter(self):
        source = (ROOT / "src/devices/fdc.s").read_text()
        command_decode = source.split("@new_command:", 1)[1].split(
            "@expect_one:", 1
        )[0]
        self.assertRegex(command_decode, r"cmp\s+#\$0A\s+beq\s+@expect_one")

    def test_fdc_models_single_drive_a_and_honors_dor_selection(self):
        source = (ROOT / "src/devices/fdc.s").read_text()
        self.assertIn("FDC_DRIVE_A = $00", source)
        dor = source.split("fdc_write_dor:", 1)[1].split("fdc_write_data:", 1)[0]
        self.assertRegex(dor, r"and\s+#\$03\s+sta\s+fdc_selected_drive")
        for command in (
            "fdc_process_recalibrate:",
            "fdc_process_seek:",
            "fdc_process_read_data:",
            "fdc_process_read_id:",
        ):
            body = source.split(command, 1)[1].split("\nfdc_", 1)[0]
            self.assertIn("fdc_selected_drive", body)
            self.assertIn("fdc_queue_not_found", body)


    def test_fdc_digital_input_reports_ready_bit(self):
        source = (ROOT / "src/devices/fdc.s").read_text()
        digital_input = source.split("fdc_read_digital_input:", 1)[1].split("fdc_write_dor:", 1)[0]
        self.assertRegex(digital_input, r"lda\s+#\$01")

    def test_fdc_main_status_uses_state_machine_values(self):
        source = (ROOT / "src/devices/fdc.s").read_text()
        status = source.split("fdc_read_main_status:", 1)[1].split("fdc_read_data:", 1)[0]
        self.assertRegex(status, r"lda\s+fdc_result_count[\s\S]*lda\s+#\$D0")
        self.assertRegex(status, r"lda\s+fdc_expected[\s\S]*lda\s+#\$90")
        self.assertRegex(status, r"lda\s+#\$80")

    def test_fdc_read_id_reports_sector_one_with_512_byte_size(self):
        source = (ROOT / "src/devices/fdc.s").read_text()
        read_id = source.split("fdc_process_read_id:", 1)[1].split(
            "fdc_queue_invalid:", 1
        )[0]
        self.assertRegex(read_id, r"lda\s+#\$01[^\n]*\n\s*sta\s+fdc_results\+5")
        self.assertRegex(read_id, r"lda\s+#\$02[^\n]*\n\s*sta\s+fdc_results\+6")
        self.assertRegex(read_id, r"lda\s+fdc_params\+0[\s\S]*and\s+#\$04[\s\S]*lsr\s+a[\s\S]*lsr\s+a[\s\S]*sta\s+fdc_results\+4")

    def test_fdc_read_data_uses_end_of_track_for_multi_sector_reads(self):
        source = (ROOT / "src/devices/fdc.s").read_text()
        read_data = source.split("fdc_process_read_data:", 1)[1].split(
            "; READ ID returns the current 360 KiB drive geometry without transferring", 1
        )[0]
        self.assertIn("fdc_params+5", read_data)
        self.assertRegex(read_data, r"lda\s+fdc_params\+5[\s\S]*sbc\s+fdc_params\+3[\s\S]*adc\s+#\$01[\s\S]*sta\s+fdc_transfer_count")
        self.assertIn("fdc_set_sector_source", source)


if __name__ == "__main__":
    unittest.main()











