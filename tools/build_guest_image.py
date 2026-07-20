#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUEST_SIZE = 1024 * 1024
CONVENTIONAL_RAM_END = 0xA0000
CGA_TEXT_START = 0xB8000
CGA_TEXT_END = 0xBC000


def parse_address(value: str) -> int:
    address = int(value, 0)
    if not 0 <= address < GUEST_SIZE:
        raise ValueError(f"guest address outside 20-bit space: {value}")
    return address


def build_image(manifest_path: Path, rom_root: Path, profile_name: str) -> bytearray:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = manifest["profiles"][profile_name]

    # Unpopulated PC address space reads high. Installed conventional RAM and
    # the initial CGA text buffer begin cleared for deterministic diagnostics.
    image = bytearray([0xFF]) * GUEST_SIZE
    image[:CONVENTIONAL_RAM_END] = bytes(CONVENTIONAL_RAM_END)
    image[CGA_TEXT_START:CGA_TEXT_END] = bytes(CGA_TEXT_END - CGA_TEXT_START)

    occupied: list[tuple[int, int, str]] = []
    for entry in profile["files"]:
        path = rom_root / entry["path"]
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != entry["size"] or digest != entry["sha256"]:
            raise ValueError(f"ROM verification failed: {entry['path']}")

        start = parse_address(entry["guest_address"])
        end = start + len(data)
        if end > GUEST_SIZE:
            raise ValueError(f"ROM crosses 20-bit boundary: {entry['path']}")
        for other_start, other_end, other_path in occupied:
            if start < other_end and other_start < end:
                raise ValueError(f"ROM overlap: {entry['path']} and {other_path}")
        occupied.append((start, end, entry["path"]))
        image[start:end] = data

    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a raw 1 MiB 8088 memory image")
    parser.add_argument("--manifest", type=Path, default=ROOT / "config/roms.json")
    parser.add_argument("--rom-root", type=Path, default=ROOT / "third_party/pcem-roms")
    parser.add_argument("--profile", choices=("genxt", "ibmxt", "ibmpc"), default="genxt")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    output = args.output or ROOT / "build" / f"guest-{args.profile}.reu"
    image = build_image(args.manifest, args.rom_root, args.profile)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)
    digest = hashlib.sha256(image).hexdigest()
    print(f"Wrote {output} ({len(image)} bytes, sha256={digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

