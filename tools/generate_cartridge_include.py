#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_labels(path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    pattern = re.compile(r"^al\s+([0-9A-Fa-f]{6})\s+\.(\S+)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            labels[match.group(2)] = int(match.group(1), 16)
    return labels


def generate(prg: Path, labels_path: Path, output: Path) -> None:
    raw = prg.read_bytes()
    if len(raw) < 3:
        raise ValueError("payload PRG is too short")
    load_address = int.from_bytes(raw[:2], "little")
    payload_size = len(raw) - 2
    labels = parse_labels(labels_path)
    required = ("start", "__BSS_RUN__", "__BSS_SIZE__")
    missing = [name for name in required if name not in labels]
    if missing:
        raise ValueError(f"missing linker labels: {', '.join(missing)}")

    # Bank zero reserves its first 256 bytes for the bootstrap. Multi-bank
    # payload copying will be added when the internal-RAM image exceeds 7936 B.
    if payload_size > 0x1F00:
        raise ValueError("payload exceeds the current single-bank cartridge loader")

    values = {
        "PAYLOAD_ROM_ADDRESS": 0x8100,
        "PAYLOAD_LOAD_ADDRESS": load_address,
        "PAYLOAD_SIZE": payload_size,
        "PAYLOAD_ENTRY": labels["start"],
        "PAYLOAD_BSS_START": labels["__BSS_RUN__"],
        "PAYLOAD_BSS_SIZE": labels["__BSS_SIZE__"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(f"{name} = ${value:04X}" for name, value in values.items()) + "\n",
        encoding="ascii",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate cartridge payload constants")
    parser.add_argument("--prg", type=Path, default=ROOT / "build/c64x86-hwtest.prg")
    parser.add_argument("--labels", type=Path, default=ROOT / "build/c64x86-hwtest.lbl")
    parser.add_argument("--output", type=Path, default=ROOT / "build/cartridge_payload.inc")
    args = parser.parse_args()
    generate(args.prg, args.labels, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

