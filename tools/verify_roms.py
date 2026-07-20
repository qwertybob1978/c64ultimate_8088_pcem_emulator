#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "roms.json"
DEFAULT_ROM_ROOT = ROOT / "third_party" / "pcem-roms"


def verify(manifest_path: Path, rom_root: Path, profile: str | None) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profiles = manifest["profiles"]
    selected = {profile: profiles[profile]} if profile else profiles
    failures = 0

    for profile_name, details in selected.items():
        for entry in details["files"]:
            path = rom_root / entry["path"]
            if not path.is_file():
                print(f"MISSING {profile_name}: {entry['path']}")
                failures += 1
                continue
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if len(data) != entry["size"] or digest != entry["sha256"]:
                print(f"INVALID {profile_name}: {entry['path']}")
                failures += 1
                continue
            print(
                f"OK {profile_name}: {entry['path']} -> "
                f"{entry['guest_address']} ({len(data)} bytes)"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local PCem ROM inputs")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rom-root", type=Path, default=DEFAULT_ROM_ROOT)
    parser.add_argument("--profile", choices=("genxt", "ibmxt", "ibmpc"))
    args = parser.parse_args()
    return 1 if verify(args.manifest, args.rom_root, args.profile) else 0


if __name__ == "__main__":
    raise SystemExit(main())

