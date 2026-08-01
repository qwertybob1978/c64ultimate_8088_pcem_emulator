# C64 x86: Intel 8088 Simulator for the Commodore 64 Ultimate

## 1. Project goal

Build an IBM PC/XT-class simulator that runs as a native 6510 program on a
Commodore 64 Ultimate (C64U), using:

- the C64U turbo CPU mode (up to 64 MHz on C64 Ultimate/Ultimate 64 Elite-II;
  up to 48 MHz on an original Ultimate 64);
- a 16 MiB REU as the backing store for the 8088's 1 MiB physical address
  space, disk images, and optional debug data;
- VIC-II video, the C64 keyboard, and optionally a joystick as the host user
  interface;
- selected IBM PC/XT hardware designs and implementation ideas from
  [PCem](https://github.com/sarah-walker-pcem/pcem/).

The primary executable and release artifact must be a C64 cartridge image with
the `.crt` extension. A `.prg` may remain available for diagnostics and
developer tests, but is not the final user-facing executable.

The first useful release should boot an XT-compatible BIOS and a DOS-compatible
floppy image, provide readable text output, accept keyboard input, and run
ordinary real-mode software. Exact IBM PC bus timing, copy-protection support,
and demo-grade cycle accuracy are not first-release goals.

Active acceptance target: boot `third_party/svardos/svdos-360K-disk-1.img` with
the Generic XT BIOS to a usable DOS prompt in the packaged CRT/VICE path,
then exercise keyboard input and a read-only DOS command before expanding the
scope of the floppy workload.

## 2. Feasibility statement

This is technically plausible as a **functional** simulator, but real-time
4.77 MHz 8088 performance must not be assumed. A 64 MHz 6510 provides only
about 13.4 host cycles per guest clock before display, REU, and device costs.
An interpreted 8088 instruction normally needs many host instructions.

The project therefore needs an early benchmark gate. Success for the first
release means useful interactive performance and correct software execution,
not necessarily 100% of original XT speed. Optimizations should favor:

1. compact 6502 assembly in the CPU hot path;
2. direct-page/zero-page storage for frequently used guest state;
3. cached guest memory pages in C64 internal RAM;
4. large, infrequent REU DMA transfers rather than byte-at-a-time REU access;
5. coarse device scheduling where software compatibility permits it;
6. dirty-region video updates rather than continuous full-screen conversion.

If the feasibility prototype cannot reach at least a usable fraction of XT
speed, retain the accurate interpreter as a reference core and investigate a
block translator as a later, explicitly separate experiment.

## 3. Target machine and scope

### 3.1 Initial guest profile

Emulate one fixed, deliberately small configuration:

| Component | Initial target |
|---|---|
| CPU | Intel 8088, real mode, architecturally correct instructions and flags |
| Clock model | Nominal 4.772728 MHz; instruction/event timing approximate first |
| Address space | 20-bit, 1 MiB, including 20-bit segment wrap |
| RAM | 640 KiB conventional RAM |
| Firmware | Generic XT-compatible BIOS, configurable ROM mapping |
| Interrupts | One Intel 8259A-compatible PIC |
| Timer | Intel 8253-compatible PIT, channels needed by BIOS/DOS |
| System I/O | XT-style PPI behavior needed for keyboard, switches, and speaker |
| Keyboard | XT keyboard scan-code set 1 |
| Display | CGA subset: text first, then 320x200 graphics |
| Storage | One 360 KiB 5.25-inch floppy image, read/write |
| Sound | PC speaker, initially simple on/off or low-rate edge playback |
| Optional later storage | XT-IDE-compatible controller and hard-disk image |
| Nice-to-have feasibility | Real Commodore 1571 access for MS-DOS-format boot disks |

Do not begin with EGA/VGA, 8087, EMS, serial/parallel devices, networking,
mouse support, protected mode, 80286 instructions, or cycle-exact CGA effects.
The physical Commodore 1571 study is explicitly non-blocking and must not delay
the standard 360 KiB image boot path.

### 3.2 Host requirements

- Commodore 64 Ultimate, Ultimate 64 Elite-II, or original Ultimate 64.
- Current stable firmware with turbo control and a configured 16 MiB REU.
- Turbo control set to **U64 Turbo Registers** or **Turbo Enable Bit** so the
  program can control `$D031`/`$D030`.
- Badline timing disabled while executing internal-memory hot paths if testing
  proves that this is stable for the selected display mode.
- USB storage or network-accessible storage for the program, firmware, and
  disk images.
- A development PC with `ca65`/`ld65` (cc65), Python 3 for generators and test
  tooling, Git, and a desktop PCem build for differential testing.
- VICE with REU enabled for functional automation. VICE is not a substitute
  for final turbo and REU performance tests on actual C64U hardware.
  The repository pins the official Windows VICE 3.10 build in
  `config/vice.json`; `tools/test_vice.ps1` runs `x64sc` from clean defaults,
  attaches the `.crt`, enables a 16384 KiB REU, and verifies the diagnostic's
  green completion border. The absent C64U turbo register is expected in VICE.

### 3.3 Cartridge executable requirements

- Produce a valid `.crt` image recognized by the C64U file browser and VICE.
- Autostart into a small cartridge bootstrap without requiring a BASIC `RUN`
  command.
- Keep BIOS ROMs, disk images, and other non-redistributable guest assets out
  of the `.crt`; load them separately into REU according to the manifest.
- Copy the emulator's hot code, zero-page setup, mutable tables, and required
  runtime data from cartridge ROM into internal C64 RAM before enabling turbo.
- Avoid executing the interpreter directly from cartridge ROM during normal
  operation because cartridge-bus accesses run through the slower external-bus
  path under turbo.
- Use CRT hardware type 19 (Magic Desk) initially: 8 KiB ROM banks at
  `$8000-$9FFF`, bank selection through `$DE00`, and bit 7 of `$DE00` to disable
  GAME/EXROM after relocation. Its I/O register does not overlap the REU at
  `$DF00`. Phase 0 must verify cartridge emulation, bank switching,
  autostart, cartridge disable/unmap, and simultaneous 16 MiB REU access on the
  supported C64U firmware matrix.
- Preserve a minimal recovery/menu path for reset and clean disk-image export
  even after the main cartridge mapping has been disabled.

## 4. ROM, disk, and asset requirements

No proprietary ROM or operating-system image should be committed to this
repository or included in a release. The loader should verify user-supplied
assets from a manifest containing path, load address, size, and SHA-256.

### 4.1 ROM acquisition for development

Get the PCem-compatible development ROM sets from
[BaRRaKudaRain/PCem-ROMs](https://github.com/BaRRaKudaRain/PCem-ROMs):

```sh
git clone https://github.com/BaRRaKudaRain/PCem-ROMs.git third_party/pcem-roms
python tools/verify_roms.py
```

Pin the checkout to the revision recorded in `references/pcem-roms.commit` and
keep the checkout ignored by Git. At the time this source was added, the ROM
repository did not provide a license file covering the collected binaries.
Treat it as an acquisition source only: developers and users remain responsible
for determining whether they may possess and use each ROM in their jurisdiction.
Do not copy these ROMs into commits, source archives, or release packages.

The initial manifest selects `genxt/pcxt.rom`. The `ibmxt` and `ibmpc` sets are
alternate compatibility profiles. ROM filenames, sizes, mappings, and hashes
must come from `config/roms.json`, not hard-coded assumptions in the emulator.

For older-firmware experiments, the [Minus Zero Degrees IBM BIOS archive](https://minuszerodegrees.net/bios/bios.htm)
confirms that its 27-Oct-1982 IBM 5150 U33 image is an 8 KiB BIOS. It is identical
to the pinned `ibmpc/pc102782.bin`; optional Cassette BASIC is not required for
disk boot. Keep Generic XT as the active profile unless IBM-PC-specific PPI switch
emulation proves cheaper than continuing the already-working Generic XT boot path.

| Asset | Required? | Mapping/use | Distribution policy |
|---|---:|---|---|
| Generic XT BIOS (`genxt/pcxt.rom`, 8 KiB) | Yes for the recommended profile | `$FE000-$FFFFF`, confirmed against pinned PCem | Acquire from the PCem-ROMs checkout for local development, or build an open-source [pcxtbios](https://github.com/virtualxt/pcxtbios) alternative; never bundle without verified redistribution rights |
| IBM XT ROMs `ibmxt/5000027.u19` and `ibmxt/1501512.u18` | Alternative only | `$F0000-$F7FFF` and `$F8000-$FFFFF`, confirmed against pinned PCem | Available in the PCem-ROMs checkout for local development; never redistribute without permission |
| IBM PC ROM `ibmpc/pc102782.bin` | Alternative only | `$FE000-$FFFFF`, confirmed against pinned PCem | Available in the PCem-ROMs checkout for local development; never redistribute without permission |
| IBM BASIC ROMs `basicc11.f6`, `.f8`, `.fa`, `.fc` | No | BASIC fallback for the IBM PC profile | Omit from the minimal XT profile; user supplied if supported later |
| CGA/MDA option ROM | No | PCem lists none for basic CGA/MDA | Not applicable |
| Display font | Yes | Host-side text renderer | Use an original/openly licensed 4x8 or 8x8 font, or generate one; document its license rather than copying an unknown IBM font |
| 360 KiB raw floppy image | Yes to boot DOS | 40 tracks, 2 heads, 9 sectors, 512 bytes/sector | Empty/test images may be generated; users supply proprietary DOS images |
| DOS-compatible boot media | Yes for end-to-end demo | Floppy image | Prefer redistributable 8086-compatible software such as an appropriately licensed FreeDOS build; validate actual 8088 compatibility |
| XT-IDE Universal BIOS | Later | Option ROM, normally in the adapter-ROM region | Build from its source and retain license notices |
| Hard-disk image | Later | Raw fixed-disk image | Generate blank/test images; do not bundle proprietary software |

The recommended release configuration is a generic XT BIOS plus generated test
floppies. IBM ROM compatibility is a user-selectable validation profile, not a
release dependency.

## 5. Licensing and PCem use

PCem is GPL-2.0 licensed. Pin the reference source to a reviewed revision rather
than following a moving branch; the revision inspected while drafting this plan
was `d674c4088e04a5fdc74e452c4d5284fa8920726d` on the `dev` branch.

Before implementation, choose and document one of these policies:

- **Recommended:** license this project under GPL-2.0-compatible terms and port
  selected PCem logic with attribution, copyright notices, and clear provenance.
- Use PCem only as behavioral documentation and independently implement every
  component. This requires disciplined provenance notes and does not remove the
  need to respect other specifications and firmware licenses.

Keep a `docs/provenance.md` ledger for every adapted table, algorithm, test
vector, font, firmware build, and tool. Do not assume a ROM file found online is
redistributable.

## 6. Architecture

```text
 C64 keyboard/joystick                       VIC-II / HDMI output
          |                                           ^
          v                                           |
 +-------------------- C64 internal RAM ---------------------------+
 | UI + scheduler | 8088 hot core | device state | page/video cache|
 +-------------------------+------------------+---------------------+
                           | batched DMA      |
                           v                  v
 +---------------------------- 16 MiB REU --------------------------+
 | 1 MiB guest physical memory | floppy/HDD data | trace/snapshots  |
 +-----------------------------+-----------------+------------------+
                           ^
                           | boot/save through Ultimate DOS/UCI
                           v
                    USB/network filesystem
```

### 6.1 Modules

Use assembly for the emulator core and narrow hardware abstraction interfaces
for everything else:

```text
src/
  boot/       startup, C64 banking, turbo detection/control
  cpu8088/    registers, decoder, effective addresses, ALU, strings, interrupts
  memory/     20-bit mapping, REU DMA, cache, dirty pages, ROM protection
  bus/        port I/O dispatch and guest-cycle accounting
  devices/    PIC, PIT, PPI/keyboard, CGA, floppy controller, speaker
  host/       VIC renderer, C64 input, UCI/files, diagnostics
  monitor/    debugger, trace, breakpoints, memory/register display
tools/        ROM manifest, image builders, generated opcode tables, test tools
tests/        CPU vectors, device tests, boot traces, disk fixtures
```

Generate repetitive opcode metadata on the development PC, then assemble the
result into read-only tables. Avoid a large C runtime in the target binary.

### 6.2 Guest memory and REU layout

Reserve REU addresses by constants generated from one memory-map file:

| REU range | Purpose |
|---|---|
| `$000000-$0FFFFF` | Complete 8088 physical address space |
| `$100000-$1FFFFF` | Page-cache backing, snapshots, or scratch |
| `$200000-$27FFFF` | Up to one 512 KiB floppy image and metadata |
| `$280000-$EFFFFF` | Future hard disk, trace ring, second floppy, test data |
| `$F00000-$FFFFFF` | Reserved for tooling and future expansion |

All ranges except the 1 MiB guest space are provisional and should be generated,
not embedded throughout the code.

The memory subsystem must:

- translate `segment << 4 + offset` with 20-bit wrap;
- enforce RAM, video RAM, option-ROM, and BIOS-ROM regions;
- cache a measured number of 256-byte or 1 KiB guest pages in internal RAM;
- pin the current instruction page and stack page where practical;
- write back dirty pages before eviction and on shutdown/snapshot;
- provide explicit slow paths for reads crossing a page boundary;
- copy ROMs and disk images directly into REU at startup using Ultimate DOS/UCI
  when available, rather than streaming them through the 6510 byte by byte;
- benchmark REU transfer setup and transfer sizes on each supported board.

Never execute a REU DMA transfer from or to a C64 range containing the active
stack, DMA routine, IRQ handler, or live display metadata.

### 6.3 8088 execution core

Implement a table-driven interpreter with specialized assembly handlers:

- all documented 8088 opcodes and prefixes (`LOCK`, segment overrides,
  `REP`/`REPE`/`REPNE`);
- 8- and 16-bit ModR/M decoding and the 8088 effective-address forms;
- correct arithmetic flags, including auxiliary carry and defined/undefined
  behavior required by known software;
- interrupts, NMI, `INT`, `IRET`, single-step trap, `HLT`, and interrupt shadow
  behavior around `STI` and segment-register loads;
- string instructions with interruptible repetition;
- divide faults and other 8088-specific edge cases;
- optional approximate cycle counts per instruction and memory access.

Use PCem's `src/cpu/808x.c` as the primary implementation cross-reference, but
validate behavior against independent CPU vectors and, where possible, a second
emulator. Do not bring over PCem's dynamic recompiler or later-x86 framework.

### 6.4 Timing and scheduling

Maintain a 32-bit or fixed-point guest clock accumulator. Each instruction
returns an estimated number of 8088 clocks. Advance PIT, PIC delivery, floppy,
keyboard, speaker, and video events from that common time base.

Provide two modes:

- **Compatible:** better instruction/device timing, suitable for software that
  depends on delays.
- **Fast:** coarser peripheral batching and optional idle-loop acceleration.

The host raster interrupt should only request work. It must not mutate guest
device state concurrently with an instruction handler. Perform scheduled work
at explicit safe points in the main loop.

### 6.5 Video

Deliver video in this order:

1. BIOS teletype debug console for first boot diagnostics.
2. CGA 40x25 text with a readable 8x8 host font.
3. CGA 80x25 text rendered with a compact 4x8 font or a selectable horizontally
   scrolled 8x8 view; document the legibility tradeoff.
4. CGA 320x200 four-color graphics mapped to a VIC-II bitmap.
5. CGA 640x200 monochrome by downsampling or an optional panned view.

Track writes to `$B8000-$BBFFF` as dirty and convert only affected cells/scan
lines. Do not emulate the CGA beam in the first release. Direct video-memory
polling software and composite-artifact color are later compatibility work.

### 6.6 Input, storage, and sound

- Translate C64 key matrix events to XT make/break scan codes. Include explicit
  mappings for PC keys absent from the C64 keyboard and support a USB keyboard
  only if it is visible through normal C64 key input or a documented API.
- Implement the minimum Intel 8272/NEC uPD765 command set needed by the selected
  BIOS: recalibrate, seek, sense interrupt, specify, read data, write data, and
  read ID.
- Keep a dirty-sector bitmap and save intentionally on menu command/clean exit.
  Never silently overwrite the user's only disk image; default to copy-on-write.
- Treat real Commodore 1571 access as a later feasibility study. First determine
  whether the available C64/C64U hardware path can safely issue IEC/1571
  commands or expose a raw sector bridge while the emulator is running. Do not
  assume that a filesystem API provides raw MFM sectors. The first experiment
  must be read-only, use a user-supplied MS-DOS-format disk, identify the exact
  adapter/firmware/API, and compare returned sectors and boot signature against
  a known image. Only after repeatable sector reads work may the bridge be
  connected to the guest XT FDC as drive A; writes require separate
  copy-on-write and explicit export approval.
- Begin PC-speaker support as a single SID/UltiSID voice updated at coarse event
  boundaries. Disable it during performance investigations.

## 7. PCem reference map

Review these PCem areas and record the exact pinned paths in the provenance
ledger before porting:

| Concern | PCem starting point | Intended use |
|---|---|---|
| 8088 instruction behavior | `src/cpu/808x.c`, CPU headers/tables | Semantics, edge cases, timing reference |
| Main machine loop | `src/pc.c` | Understand event ownership; replace desktop loop entirely |
| Port dispatch | `src/io.c` | Design a much smaller XT I/O dispatcher |
| PIC/PIT/DMA | `src/models/pic.c`, `pit.c`, `dma.c` | Register behavior and interrupt flow |
| PPI and keyboard | `src/ppi.c`, `src/keyboard/` | XT keyboard and system-port behavior |
| CGA | `src/video/` CGA implementation | Registers, modes, memory interpretation |
| Floppy | `src/floppy/`, `src/disc/` | Controller commands and image access |
| IBM PC/XT machine definitions | `src/models/model.c` and related initializers | ROM maps, installed devices, reset order |
| Memory | `src/memory/` and memory headers | Guest-region behavior; replace host allocation/cache layer |

PCem is a reference, not an architecture to transplant wholesale. Its UI,
threads, host audio/video libraries, file abstraction, plug-ins, dynarec, and
post-8088 machines are out of scope.

## 8. Milestones and acceptance gates

### Phase 0: research, licensing, and measurement

- Pin PCem and all other reference revisions.
- Decide the project license and create the provenance ledger.
- Write minimal C64U routines for turbo selection, REU detection, DMA copy, and
  UCI file-to-REU loading.
- Benchmark tight ALU/dispatch loops and REU transfers at 1, 48, and 64 MHz as
  applicable, with badlines on and off.
- Prototype the selected `.crt` layout and prove that its bootstrap can copy a
  payload to internal RAM, unmap the cartridge, enable turbo, and continue to
  access the 16 MiB REU.
- Decide page size, cache size, display mode, and realistic performance target
  from measured results.

**Gate:** publish repeatable hardware numbers and show that cached interpretation
is fast enough for an interactive simulator. If not, revise the target before
implementing peripherals.

### Phase 1: portable CPU reference and test harness

- Specify the guest-state binary layout and opcode metadata.
- Build a desktop reference runner sharing generated tables/test vectors.
- Implement reset, fetch/decode, ModR/M addressing, ALU, control flow, stack,
  prefixes, strings, interrupts, and exceptions.
- Differentially test register, flag, memory, and I/O traces.

**Gate:** pass the selected 8088 instruction suite and targeted hand-written
edge cases with deterministic traces.

### Phase 2: optimized C64U CPU and memory core

- Port hot handlers to 6502 assembly.
- Implement the REU-backed 20-bit map and internal page cache.
- Add profiling counters per opcode, cache miss, DMA byte, and scheduler event.
- Run small ROM-less 8088 programs on hardware.

**Gate:** execute CPU tests from REU without state divergence and meet the Phase
0 performance budget.

### Phase 3: minimum XT motherboard and BIOS POST

- Add I/O dispatch, PIC, PIT, PPI, keyboard queue, BIOS ROM mapping, and a debug
  character sink.
- Implement reset state (`CS:IP = FFFF:0000`) and BIOS-visible RAM sizing.
- Compare the port-I/O/interrupt trace with the same firmware in PCem.

**Gate:** the chosen generic XT BIOS completes POST and reaches a boot attempt.

### Phase 4: display and keyboard

- Implement CGA registers and text memory.
- Add 40/80-column rendering and host key translation.
- Add an emulator menu for reset, speed, disks, save, and diagnostics.

**Gate:** BIOS messages and a DOS prompt are readable; commands can be entered
reliably using the C64 keyboard.

### Phase 5: floppy boot and DOS workload

- Implement the floppy controller, DMA channel behavior needed by it, CHS image
  access, copy-on-write, and explicit save/export.
- Boot a redistributable DOS-compatible test image.
- Run file, memory, timer, keyboard, text, and CGA smoke tests.

**Gate:** cold boot, format/read/write test media, reboot, and verify persistence
without corrupting the base image.

### Phase 6: optimization and release

- Profile on every supported Ultimate model.
- Specialize common opcodes/effective addresses, reduce cache misses, batch
  peripheral work, and add safe idle-loop acceleration.
- Produce the required autostart `.crt` release. Keep the `.prg` hardware test
  as an optional developer artifact. The cartridge bootstrap must relocate hot
  code to internal RAM before normal turbo execution.
- Publish setup instructions, asset manifest examples, checksums, compatibility
  results, known limitations, and benchmark methodology.

**Release gate:** reproducible build; clean license/provenance audit; BIOS-to-DOS
demo; no bundled proprietary ROMs; no known base-image corruption path.

### Optional feasibility study: real Commodore 1571 MS-DOS boot disks

This is a nice-to-have experiment, not a version 1.0 requirement and not a
reason to weaken or reorder the CPU/opcode or PCem-driver gates. Execute it only
after the normal image-backed DOS boot is stable.

Study order:

1. Document the physical setup: real 1571 model, IEC connection or adapter,
   C64/C64U firmware/API, cable, power, and whether the drive is shared with
   the host. No unsupported hardware assumptions.
2. Prove read-only discovery and sector access outside the guest. Read the boot
   sector and a small CHS sample from a permitted MS-DOS-format disk; verify
   `55 AA`, geometry, deterministic retries, and hashes against a separately
   acquired image when available.
3. Measure latency, failure modes, drive-busy behavior, reset/reconnect, and
   whether access can coexist with turbo, REU DMA, VIC refresh, and keyboard
   input. Preserve the standard image-backed path as a fallback.
4. If raw sector access is reliable, add a narrow media-provider interface that
   maps 1571 CHS reads to the existing XT FDC path. Do not make the guest speak
   Commodore DOS commands unless a separate use case requires it.
5. Add writes only as a separate experiment with copy-on-write, explicit
   export, power-loss-safe behavior, and a disposable disk. Never write the
   physical disk by default.

Go/no-go gate: proceed only if read-only boot-sector and multi-sector reads are
repeatable, the interface is documented, and a native VICE/C64U integration
test can boot or validate the disk without regressing the normal image path.
Otherwise record the measured limitation and leave the study as a documented
adapter/media-provider proposal.

## 9. Testing strategy

Use four layers of tests:

1. **Generated unit vectors:** ALU results/flags, effective addresses, segment
   wrap, stack behavior, string prefixes, interrupts, and divide errors.
2. **Differential desktop runs:** compare instruction and device traces with
   PCem at the pinned revision, accounting for documented undefined flags.
3. **Guest diagnostics:** BIOS POST, CPU tests, timer/interrupt programs, CGA
   mode tests, keyboard scan-code tests, and floppy read/write verification.
4. **On-device tests:** REU boundary/wrap tests, cache coherency, turbo changes,
   raster stability, long-run disk safety, and performance counters.

Every bug should gain the smallest deterministic regression case possible.
Store redistributable test binaries and their source; store only hashes and
acquisition/build instructions for non-redistributable inputs.

## 10. Principal risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Interpreter is too slow | Project not useful interactively | Phase 0 benchmark gate; assembly hot path; page cache; fast mode; honest speed reporting |
| REU per-access overhead dominates | Severe slowdown | Never use byte-sized DMA in the normal path; cache/pin pages; profile working sets |
| 64 KiB host address-space pressure | Code/cache/video cannot coexist | Generated compact tables, bank ROMs out, tune cache, overlay cold monitor/UI code |
| 80-column output is unreadable | DOS usability poor | 4x8 font plus optional panning; prioritize 40-column setup/tools |
| Timing-sensitive software fails | Compatibility gaps | One guest time base, compatible/fast modes, trace comparison, document scope |
| Disk image corruption | User data loss | Copy-on-write default, dirty sectors, explicit atomic export where host API permits |
| ROM/font licensing errors | Releases cannot be distributed | No ROMs in repo, manifest hashes, open BIOS build, provenance audit |
| Turbo behavior differs by board/firmware | Unstable performance | Runtime capability checks, supported-firmware matrix, hardware CI/manual test checklist |
| Cartridge mapping conflicts with REU or turbo | Emulator cannot boot in its required package | Phase 0 `.crt` coexistence gate; use cartridge only as bootstrap/storage and execute hot code from internal RAM |

## 11. Definition of version 1.0

Version 1.0 is complete when it:

- ships an autostart `.crt` as its primary executable, validated on C64U and
  VICE, with no proprietary guest ROM embedded;
- runs on a documented C64U/U64 hardware and firmware matrix;
- detects a 16 MiB REU and safely enables/restores turbo mode;
- implements the documented 8088 instruction set well enough to pass the chosen
  conformance suite;
- boots the recommended generic XT BIOS and a redistributable DOS-compatible
  360 KiB floppy image;
- provides usable CGA text, basic 320x200 graphics, keyboard input, PIT/PIC,
  floppy read/write with copy-on-write, and basic speaker output;
- reports measured emulated speed instead of claiming nominal 4.77 MHz;
- builds reproducibly without proprietary inputs and explains how users supply
  and verify optional ROMs.

## 12. Primary references

- [PCem repository and README](https://github.com/sarah-walker-pcem/pcem/)
- [PCem 8088/8086 core (`src/cpu/808x.c`)](https://github.com/sarah-walker-pcem/pcem/blob/dev/src/cpu/808x.c)
- [PCem GPL-2.0 license](https://github.com/sarah-walker-pcem/pcem/blob/dev/COPYING)
- [Ultimate turbo-mode registers and timing notes](https://1541u-documentation.readthedocs.io/en/latest/config/turbo_mode.html)
- [Ultimate DOS/UCI file and REU commands](https://1541u-documentation.readthedocs.io/en/latest/uci/ultimate_dos_target.html)
- [Ultimate 64 product information](https://ultimate64.com/AboutUs)
- [Open-source PC/XT BIOS](https://github.com/virtualxt/pcxtbios)
