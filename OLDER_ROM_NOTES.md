# Older IBM 5150 ROM trial

The [Minus Zero Degrees BIOS archive](https://minuszerodegrees.net/bios/bios.htm)
lists four IBM 5150 BIOS revisions. Its 27-Oct-1982 download is the complete 8 KiB
U33 BIOS image; the separately listed U29-U32 Cassette BASIC ROMs are optional for
disk boot.

The downloaded U33 file is byte-for-byte identical (SHA-256
`3700c345f3dcb76039986429ade9ff0cffbc2f0cae535b987b95a5de8aa0094f`) to the
already pinned `third_party/pcem-roms/ibmpc/pc102782.bin`. The existing `ibmpc`
manifest profile therefore already represents this candidate, and no duplicate
profile or release asset is needed.

The active implementation remains on the verified PCem Generic XT ROM
(`genxt/pcxt.rom`) because the IBM 5150 firmware also requires IBM-PC-specific PPI
switch behavior, while the Generic XT route has already reached the disk boot path.

## Minus Zero Degrees IBM XT archive

The same page lists the 11/08/82 IBM 5160 (XT) revision as a split U18/U19 set.
That option requires the 64 KiB mapping already described by the `ibmxt` profile,
so it is not a simpler substitute for the current 8 KiB Generic XT BIOS.
