# C64 x86 implementation continuation guide

This file is a complete handoff for continuing the Intel 8088 / IBM XT
simulator on the Commodore 64 Ultimate. Read this entire file before editing
editing anything. The former planning documents were removed; use the source,
tests, configuration, and README as the current specification.

## 1. Current checkpoint

### Verified native-boot state (2026-08-01)

The current repository checkpoint is:

```text
3ef8b06 docs: document SvarDOS boot milestones
```

The SvarDOS checkpoint used `third_party/svardos/svdos-360K-disk-1.img`.
The default boot target is the SvarDOS 360 KiB image at
`third_party/svardos/svdos-360K-disk-1.img`. Do not reintroduce the removed
MS-DOS cache as the default or acceptance target.
The BIOS helper at `F000:F78D` was investigated and is normal Generic XT BIOS
CGA CRTC code; it is not a hardware stall and must not be patched without new
evidence.

The native run was instead observed looping in the BIOS speaker delay at
`F000:F9E8` (`LOOP`), with no FDC command or IRQ6 activity. The runtime patch
targeted the actual delay entry at `F000:F9D4`, where it safely replaces the
routine entry with `RET`.

Verified after that change:

- `python -m unittest tests.test_cpu8088_reference tests.test_phase0_contracts`
   passes all 41 tests.
- `build_crt.ps1` succeeds and produces a valid 49-bank CRT.
- `tools/test_vice.ps1 -SkipBuild -CycleLimit 2200000000` reaches the existing
   green-border smoke gate.

The green-border smoke gate is not yet proof of a usable DOS prompt. The next
acceptance step remains running SvarDOS through its complete boot and recording
either a real CPU/device fault or a stable DOS prompt. Live diagnostic capture
uses `tools/capture_diag_dump.py` and `tools/parse_fault_dump.py`; the immutable
`build/guest-genxt.reu` image must not be used as a substitute for live REU
state.

Repository root on the current machine:

```text
C:\Repository\C64_x86
```

Current branch and known-good commit:

```text
branch: master
commit: 3ef8b06
subject: docs: document SvarDOS boot milestones
```

The working tree was clean when this guide was created. Confirm before work:

```powershell
Set-Location C:\Repository\C64_x86
git status --short
git log -8 --oneline
```

Do not discard pre-existing changes. If the working tree is not clean, inspect
and preserve them.

Completed recent milestones, newest first:

```text
dc48342 feat(input): route C64 keyboard to XT
b00bfd5 feat(io): select XT CGA hardware
9f18f05 feat(cpu): add decimal adjust
f150476 feat(video): add status transitions
f1c8cac feat(cpu): add group3 test
e26642e feat(cpu): add group3 multiply
b628513 feat(cpu): add accumulator test
c783907 feat(cpu): add rotate family
5f0de0f feat(cpu): add complement carry
7c4d2f9 feat(video): render CGA text on C64
407f11a feat(dev): add visible VICE launcher
8cac29d feat(cpu): add ModR/M exchange
```

The end goal is not complete. Continue until the Generic XT BIOS displays via
CGA and attempts to boot the supplied SvarDOS 360 KiB floppy. Commit every
verified milestone locally.

## 2. Mandatory working rules

1. Use PowerShell commands on this Windows workspace.
2. Make source edits with the patch/edit mechanism, not destructive rewrites.
3. Preserve ignored ROMs, tools, generated builds, and DOS media.
4. Never commit ROM binaries, DOS disk images, VICE, cc65, PCem, or build output.
5. Run generated-contract checks, desktop tests, cartridge build, and VICE after
   every native CPU/device milestone.
6. VICE tests must always use warp mode. `tools/test_vice.ps1` already passes
   `-warp`; do not remove it.
7. Commit each completed milestone separately with a short Conventional Commit
   message, for example `feat(cpu): add group5 near control flow`.
8. Do not commit a milestone until tests pass and the VICE border is green.
9. PCem is a semantics/timing reference. Do not blindly port its host-specific
   C implementation to 6502 assembly.
10. The required release artifact is `build/c64x86.crt`, not only a PRG.

## 3. What currently works

The native 6502 8088 core already has these major slices:

- reset state and 20-bit segment:offset addressing;
- REU-backed guest memory and a 256-byte instruction page cache;
- all 8088 ModR/M effective-address forms with DS/SS defaults;
- register, memory, immediate, and segment-register `MOV` forms currently used;
- accumulator, ModR/M, and Group-1 arithmetic/logical operations;
- condition flags and all short conditional branches;
- register stack operations, near/far calls and returns, and immediate far jump;
- segment override and repeat-prefix decoding;
- byte/word string operations with REP/REPE/REPNE;
- software interrupts, IRET, IRQ/NMI latches, and interrupt shadow behavior;
- DIV/IDIV plus divide-error entry;
- MUL/IMUL byte and word products with CF/OF overflow reporting;
- PUSHF/POPF/SAHF/LAHF;
- immediate and DX-addressed byte/word IN/OUT dispatch;
- Group-3 NOT, Group-4 byte INC/DEC, and register word INC/DEC;
- single-bit and unmasked CL-count rotates and shifts for registers and memory;
- LOOPNE, LOOPE, LOOP, and JCXZ;
- Group-5 near indirect CALL/JMP with general ModR/M segment overrides;
- LES/LDS memory far-pointer loads;
- byte/word ModR/M XCHG;
- a four-bank 32 KiB Magic Desk CRT with a RAM-resident multi-bank loader;
- automated VICE 3.10 CRT smoke testing with a 16 MiB REU in warp mode.
- a verified 40-column projection of the guest B8000 80x25 CGA text page;

The native CRT now passes its diagnostics and enters a permanent real Generic
XT BIOS execution loop. It clears conventional/CGA RAM, copies the locally
verified 8 KiB ROM to REU physical FE000h, resets the CPU, polls the C64
keyboard after bounded batches, and renders B8000 periodically. A
500,000,000-cycle VICE warp run is stable and green after adding native
`A0`-`A3` direct-offset MOV support and a 256-byte write-back guest data cache.
The cache is coherent with the instruction page and flushes before CGA DMA.
The visible page now contains real BIOS output:

```text
SYSTEM ERROR #00, CONTINUE? GENERIC TURBO ...
```

This is the first native BIOS/CGA checkpoint. Device initialization and the
keyboard response to the prompt are the next blockers.

## 4. Exact next task: PIC/PIT and POST keyboard response

The XT PPI/DIP slice and C64 keyboard translation are complete. Port 62h now advertises color 80-column video,
03BAh remains open bus, and 03DAh supplies display-enable plus vertical-retrace
phases. The BIOS makes its first nonzero B8000 write at instruction 26,398 and
produces this real CGA page:

```text
  Generic Turbo XT Bios 1987
      for 8088 or V20 cpu
         (c)Anonymous
```

After POST delays it waits for keyboard buffer state to change:

```text
loop:           F000:E845 through E852
bytes:          FA 8B 1E 1A 00 3B 1E 1C 00 75 03 FB EB F2
meaning:        wait until BIOS keyboard-buffer head and tail differ
state:          both compared values remain zero
BDA 0040:001A: 001E (keyboard head)
BDA 0040:001C: 001E (keyboard tail)
B8000:          complete 80x25 space/attribute page plus BIOS banner
```

The mapping in `src/host/keyboard.s` covers letters, digits, Enter, Backspace,
Space, punctuation, and cursor keys and queues set-1 make codes on port 60h.
The native BIOS loop, cached memory, and direct CGA refresh are present. Replace
the provisional late vector-08 injection with an XT PIC/PIT slice and route
keyboard IRQ1 through that PIC. Extend C64 keyboard translation with the eight
PETSCII function-key codes so the BIOS `Continue?` prompt can receive F1 when
needed. Then implement DMA channel 2/FDC commands for the validated 360 KiB DOS
image.

## 5. How to trace the BIOS to the next blocker

First ensure the Generic XT guest image exists:

```powershell
python tools/build_guest_image.py --profile genxt
```

This creates ignored `build/guest-genxt.reu`. Then run this read-only trace
snippet from the repository root. It prints the final 12 instructions when an
unsupported opcode is reached:

```powershell
@'
import json, sys
from pathlib import Path
sys.path.insert(0, 'tools/ref8088')
from runner import Reference8088

spec = json.loads(Path('config/cpu8088.json').read_text())
cpu = Reference8088(spec)
cpu.memory[:] = Path('build/guest-genxt.reu').read_bytes()
cpu.reset()
last = []

for index in range(200000):
    trace = cpu.step()
    last.append((index, trace))
    last = last[-12:]
    if trace['status'] != 'ok':
        for number, entry in last:
            opcode = entry['opcode'] if entry['opcode'] is not None else -1
            after = entry['after']
            print(
                f"{number:06d} {entry['cs']:04X}:{entry['ip']:04X} "
                f"{opcode:02X} {entry['mnemonic']} {entry['status']} "
                f"AX={after['AX']:04X} BX={after['BX']:04X} "
                f"CX={after['CX']:04X} SP={after['SP']:04X}"
            )
        break
else:
    print('No unsupported instruction in 200000 steps')
'@ | python -
```

After every newly supported opcode family, rerun this trace and record the new
instruction count, CS:IP, bytes, and semantics in the next commit or this file.
Do not assume the first apparent loop is stuck: the BIOS RAM test intentionally
iterated thousands of times before reaching its video dispatch.

## 6. Build and test commands

Run commands from `C:\Repository\C64_x86`.

Install missing project-local tools only when necessary:

```powershell
.\tools\bootstrap_cc65.ps1
.\tools\bootstrap_test_deps.ps1
.\tools\bootstrap_vice.ps1
```

Generate CPU assembly contracts after editing CPU metadata or vectors:

```powershell
python tools\generate_cpu8088.py
python tools\generate_cpu8088.py --check
```

Run the deterministic reference model and Unicorn comparison:

```powershell
python tools\ref8088\runner.py tests\vectors\cpu8088_smoke.json
$env:PYTHONPATH = ".cache\python"
python tools\ref8088\unicorn_oracle.py tests\vectors\cpu8088_smoke.json
Remove-Item Env:PYTHONPATH
```

Run all host tests:

```powershell
python -m unittest discover -s tests -v
```

Build the required CRT:

```powershell
.\build_crt.ps1
```

Expected final build messages include:

```text
Built build/c64x86-hwtest.prg
Built ...\build\c64x86.crt (49 banks, 402256 bytes)
Valid Magic Desk CRT: ...\build\c64x86.crt (49 banks, 402256 bytes)
```

Run the VICE gate. This script always uses `-warp` and must remain that way:

```powershell
.\tools\test_vice.ps1 -SkipBuild
```

Expected result:

```text
VICE 3.10 CRT smoke test passed with a 16 MiB REU.
Screenshot: C:\Repository\C64_x86\build\vice-smoke.png
Log: C:\Repository\C64_x86\build\vice-smoke.log
```

The screenshot should have a green border. The VICE script checks it
automatically. It also verifies `REUsize=16384`, cartridge loading, and reaching
the cycle limit. Never run a non-warp automated VICE test.

Before committing:

```powershell
git diff --check
git status --short
git diff --stat
```

Commit only the files belonging to the milestone:

```powershell
git add <explicit file list>
git commit -m "feat(cpu): <short milestone>"
git status --short
```

## 7. Important files and what each one does

### Top level

| Path | Purpose |
| --- | --- |
| `README.md` | Current build, test, supported-instruction, ROM, and media instructions |
| `CONTINUATION.md` | This handoff and exact continuation point |
| `build.ps1` | Assembles and links the native diagnostic PRG |
| `build_crt.ps1` | Builds PRG, cartridge bootstrap, and final CRT |
| `Makefile` | Unix-style alternative build rules; PowerShell scripts are primary here |
| `.gitignore` | Excludes build, cache, ROM checkouts, binaries, and generated artifacts |

### CPU core

| Path | Purpose |
| --- | --- |
| `config/cpu8088.json` | Canonical register layout, flag masks, opcode metadata, handlers, and cycles |
| `src/cpu8088/step.s` | Main native fetch/decode/execute implementation; most next CPU work goes here |
| `src/cpu8088/state.s` | 8088 register state and reset behavior |
| `src/cpu8088/state.inc` | Generated state/opcode constants; do not hand-edit |
| `src/cpu8088/smoke_vector.inc` | Generated native smoke program and expectations; do not hand-edit |
| `src/cpu8088/modrm.s` | Native 8088 ModR/M decoding and effective address calculation |
| `src/cpu8088/address.s` | Segment:offset to 20-bit physical address behavior |
| `src/cpu8088/stack.s` | REU-backed SS:SP push/pop helpers |
| `src/cpu8088/interrupts.s` | Interrupt entry and boundary delivery helpers |
| `src/cpu8088/divide.s` | Native bounded byte/word signed/unsigned division |
| `src/cpu8088/multiply.s` | Native byte/word signed/unsigned multiplication |
| `src/host/keyboard.s` | PETSCII/C64 key to XT set-1 scan-code routing |
| `src/cpu8088/core.inc` | Shared CPU imports/constants |
| `tools/generate_cpu8088.py` | Generates `state.inc` and `smoke_vector.inc` from config/vectors |
| `tools/ref8088/runner.py` | Deterministic desktop 8088 reference model and BIOS trace engine |
| `tools/ref8088/unicorn_oracle.py` | Differential oracle for vector register/flag/memory behavior |
| `tests/vectors/cpu8088_smoke.json` | Canonical desktop and native instruction vectors |
| `tests/test_cpu8088_reference.py` | Reference determinism, generation, address, and Unicorn tests |

### Guest memory and host hardware

| Path | Purpose |
| --- | --- |
| `src/memory/reu.s` | REU register programming and transfers |
| `src/memory/guest_memory.s` | Guest physical memory access through the REU |
| `src/memory/page_cache.s` | 256-byte C64-RAM instruction page cache |
| `src/memory/guest_init.s` | Clears XT RAM and maps the local Generic XT BIOS at FE000h |
| `src/host/hardware.inc` | C64 Ultimate turbo and REU hardware constants |
| `src/host/turbo.s` | Turbo-mode setup |
| `src/bus/io.s` | Current XT I/O dispatcher; open bus plus ports 80h/81h latches |
| `src/video/cga.s` | REU-to-C64 CGA text renderer, color mapping, and native banner diagnostic |
| `src/boot/hwtest.s` | Native startup, diagnostics, BIOS scheduler, and failure UI |

### Cartridge

| Path | Purpose |
| --- | --- |
| `src/cartridge/bootstrap.s` | Autostart ROM and RAM-relocated cross-bank payload copier |
| `cfg/cartridge_bootstrap.cfg` | 256-byte bootstrap linker layout at cartridge address 8000h |
| `cfg/c64x86.cfg` | Native PRG memory/link layout |
| `tools/generate_cartridge_include.py` | Emits payload addresses/sizes for bootstrap assembly |
| `tools/build_crt.py` | Packages four Magic Desk banks and validates CRT structure |
| `tools/test_vice.ps1` | Warp-mode VICE CRT/REU/screenshot smoke gate |

### ROM, PCem, and media tooling

| Path | Purpose |
| --- | --- |
| `config/roms.json` | Pinned BIOS file paths, hashes, sizes, and guest mappings |
| `tools/fetch_pcem.ps1` | Fetches pinned PCem source into ignored `third_party/pcem` |
| `tools/fetch_roms.ps1` | Fetches pinned PCem-ROMs into ignored `third_party/pcem-roms` |
| `tools/verify_roms.py` | Verifies local ROM checkout against manifest |
| `tools/build_guest_image.py` | Builds ignored 1 MiB `build/guest-genxt.reu` |
| `config/dos_media.json` | Hashes, source URLs, geometry, and non-redistribution policy for DOS disks |
| `tools/validate_dos_media.py` | Validates the supplied DOS boot disk and BPB |
| `references/pcem.commit` | Pinned PCem dev commit |
| `references/pcem-roms.commit` | Pinned PCem-ROMs commit |
| `references/cc65.version` | Recorded local cc65 version |

## 8. Local ignored dependencies and assets

These paths exist on the current machine but are intentionally ignored by Git:

```text
.cache\cc65\bin\ca65.exe
.cache\cc65\bin\ld65.exe
.cache\vice-3.10\GTK3VICE-3.10-win64\bin\x64sc.exe
.cache\vice-3.10\GTK3VICE-3.10-win64\bin\cartconv.exe
.cache\python\unicorn\
third_party\pcem\
third_party\pcem-roms\
build\guest-genxt.reu
build\c64x86.crt
```

Pinned external sources:

```text
PCem repository: https://github.com/sarah-walker-pcem/pcem.git
PCem branch:     dev
PCem commit:     d674c4088e04a5fdc74e452c4d5284fa8920726d

ROM repository: https://github.com/BaRRaKudaRain/PCem-ROMs.git
ROM branch:     master
ROM commit:     75bd118dd86378cac1d9d55e29e26ef82d6d57ef

Generic XT ROM: third_party\pcem-roms\genxt\pcxt.rom
ROM guest map:  FE000-FFFFF
ROM SHA-256:    c3353ceed8954e586ae711373e3b3fdc923354fe6ceb9a124acb7d760bc974b5
```

PCem source areas most useful for inspiration:

```text
third_party\pcem\src\cpu\808x.c       8088 semantics and timing reference
third_party\pcem\src\video\vid_cga.c CGA behavior reference
third_party\pcem\src\floppy\         floppy controller/media reference
```

Use `rg` to locate exact current PCem paths if the subtree names differ.

## 9. DOS media location and policy

The default supplied boot media is SvarDOS 360 KiB. DOS media and generated
CRT/build artifacts must remain outside Git unless explicitly documented as
small source metadata.

Local paths:

```text
third_party\svardos\svdos-360K-disk-1.img
```

Hashes and geometry:

```text
SvarDOS image:    third_party\svardos\svdos-360K-disk-1.img
image size:       368640 bytes
geometry:         40 cylinders, 2 heads, 9 sectors/track, 512 bytes/sector
boot signature:   55 AA
OEM/BPB text:      SvarDOS media metadata
```

Validate it with:

```powershell
python tools\validate_dos_media.py "third_party\svardos\svdos-360K-disk-1.img"
```

Do not place DOS data inside the CRT. Eventually the emulator needs a local
development path that loads the disk into an ignored REU region or packages a
separate user-side media artifact. The release repository should contain only
the manifest, validator, and instructions.

## 10. Work after remaining CPU blockers

Continue the BIOS trace one unsupported opcode family at a time. Once CPU
coverage is sufficient, the open-port behavior in `src/bus/io.s` will prevent
real POST/boot progress. Implement the minimum XT device slices in this order,
with desktop reference tests and native smoke gates for each:

1. **8259 PIC**: masks, initialization words, pending IRQ selection, EOI, IRQ0
   and IRQ6 delivery.
2. **8253 PIT**: channel 0 programming and deterministic timer IRQ generation.
3. **8255/PPI and keyboard/DIP behavior**: enough POST-visible switches and
   keyboard status for the selected Generic XT BIOS.
4. **CGA register model**: ports 3D4/3D5, mode/color/status ports, B8000 memory,
   text-mode cursor and 80x25 character state.
5. **C64 CGA renderer**: copy/translate dirty CGA text cells into a visible C64
   screen. Use an original or clearly licensed font; do not copy an unknown IBM
   font ROM.
6. **NEC uPD765-compatible floppy controller and DMA channel 2**: commands,
   status/result phases, CHS sector reads, terminal count, IRQ6.
7. **Boot-media integration**: expose the SvarDOS image as drive A, let BIOS INT 19h
   load sector 0 to 0000:7C00, verify 55AA, and transfer control.
8. **DOS evidence**: show BIOS/CGA text followed by the SvarDOS boot message or
   command prompt in a warp-mode VICE screenshot.

Start correctness-first. Device timing can be approximate but deterministic
until basic boot works. Keep device timing deterministic; do not add random
wall-clock timing.

## 11. Known traps and constraints

- The 8088 has a 20-bit wrapping physical address space.
- Segment override applies to ModR/M memory operands, but string destinations
  always use ES; only appropriate string sources may be overridden.
- Loading SS and STI create a one-instruction interrupt shadow.
- INC/DEC preserve CF.
- Shift count zero changes neither operand nor flags.
- Original 8088 CL shift counts are not masked like later x86 processors.
- OF for multi-bit shifts is architecturally undefined. The current reference
  and native implementation clear it to match the Unicorn oracle used here.
- Divide faults preserve the original faulting return IP in this core.
- The CRT bootstrap executes its bank-switching copier from RAM at 0200h. Do not
  switch cartridge banks while executing code in the cartridge window.
- Bank 0 reserves 8000-80FF for bootstrap; payload starts at 8100. Later banks
  continue at 8000. Four banks provide 32 KiB total minus bootstrap.
- Native guest memory is REU-backed. Ordinary C64 RAM pointers are not guest
  physical addresses.
- VICE does not emulate the C64 Ultimate turbo register, but it does test C64,
  cartridge, and REU behavior. Use warp mode to make tests fast.
- The current I/O bus returns FF for unimplemented ports except debug latches
  80h/81h. This is not enough for an XT boot.
- Generated files must match their JSON sources. If
  `generate_cpu8088.py --check` fails, regenerate rather than hand-editing the
  generated `.inc` files.
- The multi-bank cartridge change was required because the native payload grew
  beyond the first bank. Do not reintroduce the old 7936-byte payload cap.
- Keep copyrighted ROM and DOS assets out of Git and out of distributable CRTs.

## 12. Definition of the requested visible result

Do not call the project complete merely because the desktop reference BIOS
trace advances. The requested stopping point is a real native cartridge run in
VICE warp mode that visibly shows an XT/CGA boot attempt using the supplied DOS
disk. Minimum acceptable evidence:

1. `build/c64x86.crt` builds and validates.
2. VICE launches it with a 16 MiB REU and `-warp`.
3. The native core runs the Generic XT BIOS, not only the diagnostic vector.
4. CGA text generated by the guest appears on the C64 display.
5. The floppy boot sector is read from the validated SvarDOS image data.
6. Execution reaches 0000:7C00 and begins the SvarDOS boot sector.
7. A screenshot shows XT BIOS/DOS boot text or a DOS prompt.
8. All desktop tests, Unicorn vectors, CRT validation, and VICE gates pass.
9. Every milestone has its own local commit and the final working tree is clean.

If a full DOS prompt cannot yet be reached, do not hide the gap. Record the
exact trace/device blocker, preserve the last verified milestone in a commit,
and update this file with the next explicit continuation point.

## 9b. Milestone A — Root-cause classification (completed 2026-07-27)

### Observed values

| Item | Value |
| --- | --- |
| BIOS stall location | CS:F000 IP:F065 repeating every ~350 steps starting step ~25k |
| Bytes at F065 | `FB FC 55 06 1E 56 57 52 51 53 50` = STI CLD PUSH BP PUSH ES PUSH SI PUSH DI PUSH DX PUSH CX PUSH BX PUSH AX |
| INT $06 firings | Native VICE: repeated; Desktop runner.py: ZERO across 100k+ steps |
| IVT state | All handlers properly installed by POST code (verified via memory dump) |
| Keyboard BDA 0040:001A/001C | Both remain 0x001E (head == tail → empty buffer) |
| FDC/PIC/DMA port accesses before stall | Zero writes observed in desktop reference model |
| Opcode validity | No unsupported opcodes detected around F065 region |

### PCem source comparison (third_party/pcem/src/floppy/)

**Key finding from fdc.c:** Port `$3F4` read returns MSR value based on result-phase counter (`fdc.pnum`, `fdc.ptot`). When no command is active, MSR returns `$80`. During command execution it returns `$D0` or `$90`. The main status register also has bit 7 set when data is ready to be read.

**Critical divergence #1 — Missing port `$3F2` write handler.** Our native I/O dispatcher handles reads for ports `$3F4/$3F5/$3F7` but does NOT implement any handler for writes to port `$3F2` (DMA/FDC Control Register / DOR). In PCem's fdc.c line ~230, writing `$3F2` sets motor enable bits and drive select AND triggers reset when bit 2 transitions low→high. Without this handler, our native code never receives DMA channel 2 programming or FDC reset sequences that the BIOS issues during device initialization.

**Critical divergence #2 — Missing port `$3F3` read.** PCem's fdc.c line ~630 implements a response at address offset 3 within the FDC range ($3F3), returning rate/density configuration bytes. Our native io.s maps only `$3F4/$3F5/$3F7` as readable FDC ports. Reading `$3F3` falls through to open-bus `$FF` instead of returning valid density/rate info.

**Critical divergence #3 — IRQ6 timing mismatch.** In PCem, `fdc_int()` calls `picint(1 << 6)` which latches the request into PIC IRQ6 pending flag. The actual delivery depends on CPU IF flag being set AFTER STI executes. Our native pic.s correctly services IRQ6 when unmasked and IF=1, BUT since the FDC controller never receives proper commands (due to missing $3F2/$3F3 routing), there are zero legitimate IRQ6 requests generated by the FDC logic itself. The repeated INT$06 firings suggest something ELSE is triggering them — likely an incorrect interrupt vector or spurious IRQ latch state.

### Classification: exactly one cause type per Plan Section 9 list

**Root cause = wrong I/O routing + bad IRQ6 interaction.** Specifically:

The BIOS POST code performs device detection by probing FDC ports in sequence. It writes to `$3F2` (DOR/DMA control) expecting to see side effects on hardware state. Since our native implementation ignores `$3F2` writes entirely, the FDC never enters command mode, never generates result-phase responses, and the BIOS interprets this as "no floppy controller present." However, the BIOS then proceeds anyway and attempts to boot from drive A via INT 19h → INT 08h path. At some point it enables interrupts with STI and expects the PIT timer (IRQ0) to keep running while also allowing FDC-related IRQ6 events. Because our PIC has no active IRQ sources yet (timer/PIC ICW not initialized), but the IVT entry for INT$06 points to a valid-looking FDC handler installed earlier in POST, any stray IRQ6 latch causes execution to jump to uninitialized FDC state, producing undefined behavior including the observed loop.

**Narrowest single fix:** Implement minimal port `$3F2` write handling in `src/bus/io.s` to route DOR writes to `fdc_write_dor`, AND implement port `$3F3` read to return a plausible density/rate byte (`$20`). This allows the BIOS device-detection probe to complete without hanging, after which we can verify whether the remaining stall is due to missing PIT/timer initialization (next milestone).

### Next bounded task (Milestone B)

After implementing `$3F2`/`$3F3` routing:

1. Re-run desktop trace at 200k steps; record new CS:IP/stall location
2. If progress past F065 region confirmed, add deterministic test covering PIC ICW2 ($08h base vector) + ICW4 sequencing
3. Then implement PIT channel 0 programming (port `$40`) so IRQ0 fires deterministically every ~1ms of guest time
