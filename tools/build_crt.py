#!/usr/bin/env python3
import argparse
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRT_SIGNATURE = b"C64 CARTRIDGE   "
CRT_HEADER_SIZE = 0x40
CRT_VERSION = 0x0100
MAGIC_DESK_TYPE = 19
BANK_SIZE = 0x2000
MINIMUM_BANKS = 4
BOOTSTRAP_SIZE = 0x100
AUTOSTART_SIGNATURE = bytes((0xC3, 0xC2, 0xCD, 0x38, 0x30))


def make_header(name: str) -> bytes:
    encoded_name = name.encode("ascii")[:32].ljust(32, b"\0")
    return (
        CRT_SIGNATURE
        + struct.pack(">IHHBB6x", CRT_HEADER_SIZE, CRT_VERSION, MAGIC_DESK_TYPE, 0, 1)
        + encoded_name
    )


def make_chip(bank: int, data: bytes) -> bytes:
    if len(data) != BANK_SIZE:
        raise ValueError("Magic Desk CHIP data must be exactly 8 KiB")
    return b"CHIP" + struct.pack(">IHHHH", 0x2010, 0, bank, 0x8000, BANK_SIZE) + data


def required_banks(payload_size: int) -> int:
    if payload_size < 0:
        raise ValueError("payload size must be non-negative")
    first_bank_capacity = BANK_SIZE - BOOTSTRAP_SIZE
    remaining = max(0, payload_size - first_bank_capacity)
    extra_banks = (remaining + BANK_SIZE - 1) // BANK_SIZE
    return max(MINIMUM_BANKS, 1 + extra_banks)


def build(bootstrap_path: Path, payload_path: Path, output: Path) -> None:
    bootstrap = bootstrap_path.read_bytes()
    raw_payload = payload_path.read_bytes()
    if len(bootstrap) != BOOTSTRAP_SIZE:
        raise ValueError("bootstrap must be exactly 256 bytes")
    if len(raw_payload) < 3:
        raise ValueError("payload PRG is too short")
    payload = raw_payload[2:]
    bank_count = required_banks(len(payload))
    banks = [bytearray([0xFF]) * BANK_SIZE for _ in range(bank_count)]
    banks[0][:BOOTSTRAP_SIZE] = bootstrap
    payload_offset = 0
    first_size = min(len(payload), BANK_SIZE - BOOTSTRAP_SIZE)
    banks[0][BOOTSTRAP_SIZE:BOOTSTRAP_SIZE + first_size] = payload[:first_size]
    payload_offset = first_size
    for bank in banks[1:]:
        chunk = payload[payload_offset:payload_offset + BANK_SIZE]
        bank[:len(chunk)] = chunk
        payload_offset += len(chunk)
    image = make_header("C64 x86 8088")
    for bank_number, bank in enumerate(banks):
        image += make_chip(bank_number, bytes(bank))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)


def validate(path: Path) -> dict[str, int | str]:
    data = path.read_bytes()
    if len(data) < CRT_HEADER_SIZE or data[:16] != CRT_SIGNATURE:
        raise ValueError("invalid CRT signature")
    header_size, version, cart_type, exrom, game = struct.unpack(">IHHBB", data[16:26])
    if (header_size, version, cart_type, exrom, game) != (
        CRT_HEADER_SIZE, CRT_VERSION, MAGIC_DESK_TYPE, 0, 1
    ):
        raise ValueError("unexpected Magic Desk CRT header")

    offset = header_size
    banks: list[int] = []
    while offset < len(data):
        if data[offset:offset + 4] != b"CHIP" or offset + 16 > len(data):
            raise ValueError(f"invalid CHIP packet at offset {offset:#x}")
        packet_length, chip_type, bank, address, size = struct.unpack(
            ">IHHHH", data[offset + 4:offset + 16]
        )
        if packet_length != 16 + size or chip_type != 0:
            raise ValueError("invalid CHIP packet length or type")
        if address != 0x8000 or size != BANK_SIZE:
            raise ValueError("invalid Magic Desk bank mapping")
        if offset + packet_length > len(data):
            raise ValueError("truncated CHIP packet")
        banks.append(bank)
        offset += packet_length

    if offset != len(data) or len(banks) < MINIMUM_BANKS or banks != list(range(len(banks))):
        raise ValueError("missing, duplicate, or unordered Magic Desk banks")
    if data[0x50 + 4:0x50 + 9] != AUTOSTART_SIGNATURE:
        # Bank zero begins after 64-byte CRT + 16-byte CHIP headers. Its first
        # four bytes are the cold/warm vectors, followed by the signature.
        raise ValueError("bank zero lacks C64 autostart signature")
    return {"type": cart_type, "banks": len(banks), "size": len(data)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or validate C64 x86 CRT")
    parser.add_argument("--bootstrap", type=Path, default=ROOT / "build/cartridge-bootstrap.bin")
    parser.add_argument("--payload", type=Path, default=ROOT / "build/c64x86-hwtest.prg")
    parser.add_argument("--output", type=Path, default=ROOT / "build/c64x86.crt")
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    if args.check:
        details = validate(args.check)
        print(
            f"Valid Magic Desk CRT: {args.check} "
            f"({details['banks']} banks, {details['size']} bytes)"
        )
    else:
        build(args.bootstrap, args.payload, args.output)
        details = validate(args.output)
        print(
            f"Built {args.output} "
            f"({details['banks']} banks, {details['size']} bytes)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
