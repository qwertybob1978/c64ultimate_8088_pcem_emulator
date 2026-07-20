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


if __name__ == "__main__":
    unittest.main()
