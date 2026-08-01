# Build a DOS CRT

Use `build_dos_crt.ps1` to package a DOS floppy image into the C64 x86 Magic
Desk CRT. The selected disk image is copied into cartridge banks after the
emulator payload, then staged into the REU at guest address `$200000` by the
cartridge bootstrap.

## Geometry settings

The input must be a raw disk image of exactly one of these sizes:

| Disk type | Bytes | Heads | Sectors/track | Media banks |
| --- | ---: | ---: | ---: | ---: |
| 160 KiB | 163,840 | 1 | 8 | 20 |
| 320 KiB | 327,680 | 2 | 8 | 40 |
| 360 KiB | 368,640 | 2 | 9 | 45 |

The file can have any name or extension. The script validates only the size,
not the DOS version or filesystem contents. The selected size also selects the
emulated floppy geometry: 160 KiB uses one head and eight sectors per track;
320 KiB uses two heads and eight sectors per track; 360 KiB uses two heads and
nine sectors per track. This allows different DOS
1.x images to be tested without changing the build scripts.

The settings are defined in the size `switch` in `build_crt.ps1`. The selected
values are written to the generated
`build/media_geometry.inc`, which is assembled into the FDC. A direct
`build.ps1` run uses the documented 160 KiB defaults in
`src/media_geometry.inc`; use `build_dos_crt.ps1` when a disk image is being
packaged so the settings match the media.

## Build

From the repository root, pass either a relative or absolute path:

```powershell
.\build_dos_crt.ps1 .\third_party\pcdos\Disk01.img
.\build_dos_crt.ps1 C:\path\to\dos-320k.img
```

The command rebuilds the 6502 payload, regenerates the cartridge media
descriptor, assembles the bootstrap, embeds the selected image, and validates
`build/c64x86.crt`. It also prints the selected media size and geometry. The
output CRT is ignored build output and is not committed.

The existing default command remains available:

```powershell
.\build_crt.ps1
```

It uses `third_party/svardos/svdos-360K-disk-1.img`. To select another supported image
directly, use:

```powershell
.\build_crt.ps1 -DiskImage C:\path\to\dos-160k.img
```

## Start VICE

`start_vice.ps1` rebuilds the default image and launches VICE with
`build/c64x86.crt`. To run a different image, build it first and then launch
VICE without rebuilding:

```powershell
.\build_dos_crt.ps1 C:\path\to\dos-320k.img
.\start_vice.ps1 -SkipBuild
```

VICE runs with a 16 MiB REU and warp mode. The CRT bank count includes the
payload banks plus the media banks, rounded up to 8 KiB per cartridge bank.
For example, the current payload uses four banks, so a 160 KiB image produces
24 total banks, a 320 KiB image produces 44 total banks, and a 360 KiB image
produces 49 total banks.

## Troubleshooting

- `DOS disk image must be exactly 160 KiB, 320 KiB, or 360 KiB`: the file is not a raw
  image of a supported size. Do not pass an archive or a disk image with a
  header; extract or convert it first.
- `required disk image not found`: check the path relative to the repository
  root or pass an absolute path.
- A valid CRT does not guarantee a complete DOS boot. The native CPU/device
  implementation and the particular DOS image still determine boot behavior.

Keep proprietary DOS images outside commits unless their distribution rights
explicitly permit redistribution.