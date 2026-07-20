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


if __name__ == "__main__":
    unittest.main()
