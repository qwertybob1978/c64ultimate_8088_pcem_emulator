# Older IBM 5150 ROM trial

The supplied file is stored at `third_party/pcem-roms/ibmpc/BIOS_IBM5150_27OCT82_1501476_U33.BIN`.
It is an 8 KiB U33 device image.  The 27-Oct-1982 IBM 5150 firmware is a multi-device
set, so U33 alone is not a complete BIOS image; the companion U34 device is required
to form a bootable ROM set.  The manifest profile `ibmpc_1982_u33` records the source
URL and intentionally marks this image `reference-only-incomplete`.

The active implementation therefore remains on the verified PCem Generic XT ROM
(`genxt/pcxt.rom`).  To trial a complete older IBM set later, obtain the matching U34
image, concatenate/map the pair according to the IBM 5150 address layout, add a ROM
profile in `config/roms.json`, and make the guest BIOS loader select that profile.
