#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BANK_SIZE = 0x2000
BOOTSTRAP_SIZE = 0x200
CARTRIDGE_BANKS = 4
MEDIA_REU_ADDR = 0x200000


def required_banks(payload_size: int) -> int:
    first_bank_capacity = BANK_SIZE - BOOTSTRAP_SIZE
    remaining = max(0, payload_size - first_bank_capacity)
    extra_banks = (remaining + BANK_SIZE - 1) // BANK_SIZE
    return max(CARTRIDGE_BANKS, 1 + extra_banks)


def parse_labels(path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    pattern = re.compile(r"^al\s+([0-9A-Fa-f]{6})\s+\.(\S+)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            labels[match.group(2)] = int(match.group(1), 16)
    return labels


def generate(prg: Path, labels_path: Path, output: Path, media: Path | None = None) -> None:
    raw = prg.read_bytes()
    if len(raw) < 3:
        raise ValueError("payload PRG is too short")
    load_address = int.from_bytes(raw[:2], "little")
    payload_size = len(raw) - 2
    payload_banks = required_banks(payload_size)
    media_size = media.stat().st_size if media is not None and media.exists() else 0
    labels = parse_labels(labels_path)
    required = ("start", "__BSS_RUN__", "__BSS_SIZE__")
    missing = [name for name in required if name not in labels]
    if missing:
        raise ValueError(f"missing linker labels: {', '.join(missing)}")

    # Bank zero reserves its first bootstrap window for the cartridge loader. The
    # RAM-resident
    # loader continues at $8000 in each following Magic Desk bank.
    values = {
        "PAYLOAD_ROM_ADDRESS": 0x8000 + BOOTSTRAP_SIZE,
        "PAYLOAD_LOAD_ADDRESS": load_address,
        "PAYLOAD_SIZE": payload_size,
        "PAYLOAD_BANKS": payload_banks,
        "PAYLOAD_ENTRY": labels["start"],
        "PAYLOAD_BSS_START": labels["__BSS_RUN__"],
        "PAYLOAD_BSS_SIZE": labels["__BSS_SIZE__"],
        "MEDIA_PRESENT": 1 if media_size else 0,
        "MEDIA_ROM_BANK": payload_banks,
        "MEDIA_ROM_ADDRESS": 0x8000,
        "MEDIA_SIZE_LO": media_size & 0xFF,
        "MEDIA_SIZE_HI": (media_size >> 8) & 0xFF,
        "MEDIA_SIZE_BANK": (media_size >> 16) & 0xFF,
        "MEDIA_REU_ADDR_LO": MEDIA_REU_ADDR & 0xFF,
        "MEDIA_REU_ADDR_MI": (MEDIA_REU_ADDR >> 8) & 0xFF,
        "MEDIA_REU_ADDR_HI": (MEDIA_REU_ADDR >> 16) & 0xFF,
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
    parser.add_argument("--media", type=Path)
    args = parser.parse_args()
    generate(args.prg, args.labels, args.output, args.media)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
