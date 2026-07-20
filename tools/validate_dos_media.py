#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config/dos_media.json"


def validate(image_path: Path, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, int | str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest["disks"]["boot"]
    image = image_path.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if len(image) != expected["size"]:
        raise ValueError(f"unexpected disk size: {len(image)}")
    if digest.lower() != expected["sha256"].lower():
        raise ValueError(f"unexpected disk SHA-256: {digest}")
    if image[510:512] != b"\x55\xaa":
        raise ValueError("disk lacks the 55AA boot signature")

    geometry = {
        "bytesPerSector": int.from_bytes(image[11:13], "little"),
        "totalSectors": int.from_bytes(image[19:21], "little"),
        "sectorsPerTrack": int.from_bytes(image[24:26], "little"),
        "heads": int.from_bytes(image[26:28], "little"),
    }
    for name, value in geometry.items():
        if value != expected[name]:
            raise ValueError(f"unexpected BPB {name}: {value}")
    return {"sha256": digest, "size": len(image), **geometry}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the user-supplied DOS boot disk")
    parser.add_argument("image", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    details = validate(args.image, args.manifest)
    print(
        f"Valid 360 KiB DOS boot disk: {args.image} "
        f"({details['totalSectors']} sectors, sha256={details['sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
