import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_runner_module():
    path = ROOT / "tools/ref8088/runner.py"
    spec = importlib.util.spec_from_file_location("ref8088_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Cpu8088ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "config/cpu8088.json").read_text())
        cls.suite = json.loads((ROOT / "tests/vectors/cpu8088_smoke.json").read_text())
        cls.runner = load_runner_module()

    def test_generated_contracts_are_current(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_cpu8088.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_state_layout_is_contiguous_little_endian_words(self):
        image = bytearray(28)
        for index, field in enumerate(self.spec["state"], start=1):
            value = index * 0x101
            image[field["offset"]:field["offset"] + 2] = value.to_bytes(2, "little")
        for index, field in enumerate(self.spec["state"], start=1):
            actual = int.from_bytes(image[field["offset"]:field["offset"] + 2], "little")
            self.assertEqual(actual, index * 0x101)

    def test_reset_vector_resolves_to_physical_ffff0(self):
        cpu = self.runner.Reference8088(self.spec)
        cpu.reset()
        self.assertEqual(cpu.physical(cpu.registers["CS"], cpu.registers["IP"]), 0xFFFF0)
        self.assertEqual(cpu.registers["FLAGS"], self.spec["flags"]["RESERVED"])

    def test_reference_vectors(self):
        first_results = [self.runner.run_vector(self.spec, vector) for vector in self.suite["vectors"]]
        second_results = [self.runner.run_vector(self.spec, vector) for vector in self.suite["vectors"]]
        self.assertEqual(first_results, second_results)
        self.assertEqual(first_results[0]["trace"][0]["physical"], 0)
        self.assertEqual(first_results[0]["trace"][-1]["status"], "halted")

    @unittest.skipUnless((ROOT / ".cache/python/unicorn").exists(), "project-local Unicorn is not installed")
    def test_vectors_match_unicorn_x86_16(self):
        sys.path.insert(0, str(ROOT / ".cache/python"))
        path = ROOT / "tools/ref8088/unicorn_oracle.py"
        spec = importlib.util.spec_from_file_location("unicorn_oracle", path)
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        for vector in self.suite["vectors"]:
            oracle.run_unicorn(self.spec, vector)

    @unittest.skipUnless((ROOT / ".cache/python/unicorn").exists(), "project-local Unicorn is not installed")
    def test_all_8088_modrm_memory_address_forms_match_unicorn(self):
        sys.path.insert(0, str(ROOT / ".cache/python"))
        path = ROOT / "tools/ref8088/unicorn_oracle.py"
        spec = importlib.util.spec_from_file_location("unicorn_oracle_all_ea", path)
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        initial = {
            "CS": 0x3000, "IP": 0x0100, "DS": 0x1000, "SS": 0x2000,
            "BX": 0x0100, "BP": 0x0200, "SI": 0x0010, "DI": 0x0020,
        }
        bases = (
            ("BX", "SI"), ("BX", "DI"), ("BP", "SI"), ("BP", "DI"),
            ("SI",), ("DI",), ("BP",), ("BX",),
        )
        for mod in range(3):
            for rm in range(8):
                instruction = bytearray((0x8B, (mod << 6) | rm))
                bp_based = rm in (2, 3, 6)
                if mod == 0 and rm == 6:
                    offset = 0x3456
                    instruction.extend(offset.to_bytes(2, "little"))
                    bp_based = False
                else:
                    offset = sum(initial[name] for name in bases[rm]) & 0xFFFF
                    if mod == 1:
                        instruction.append(0xF8)
                        offset = (offset - 8) & 0xFFFF
                    elif mod == 2:
                        instruction.extend((0x1234).to_bytes(2, "little"))
                        offset = (offset + 0x1234) & 0xFFFF
                instruction.append(0xF4)
                segment = initial["SS" if bp_based else "DS"]
                vector = {
                    "name": f"modrm_mod{mod}_rm{rm}",
                    "initial": initial,
                    "program": instruction.hex(),
                    "memory": [{"segment": segment, "offset": offset, "bytes": "5aa5"}],
                    "statuses": ["ok", "halted"],
                    "expected": {
                        "AX": 0xA55A,
                        "IP": (initial["IP"] + len(instruction)) & 0xFFFF,
                        "FLAGS": 2,
                    },
                }
                oracle.run_unicorn(self.spec, vector)


if __name__ == "__main__":
    unittest.main()
