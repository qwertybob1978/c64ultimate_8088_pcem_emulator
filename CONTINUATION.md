# C64 x86 implementation continuation guide

This file is a complete handoff for continuing the Intel 8088 / IBM XT
simulator on the Commodore 64 Ultimate. Read this entire file before editing
anything. Also read `PROJECT_PLAN.md` and `README.md` for the design and current
user-facing instructions.

## 1. Current checkpoint

Repository root on the current machine:

```text
F:\projects\C64_x86
```

Current branch and known-good commit:

```text
branch: master
commit: f1c8cac
subject: feat(cpu): add group3 test
```

The working tree was clean when this guide was created. Confirm before work:

```powershell
Set-Location F:\projects\C64_x86
git status --short
git log -8 --oneline
```

Do not discard pre-existing changes. If the working tree is not clean, inspect
and preserve them.

Completed recent milestones, newest first:

```text
f1c8cac feat(cpu): add group3 test
e26642e feat(cpu): add group3 multiply
b628513 feat(cpu): add accumulator test
c783907 feat(cpu): add rotate family
5f0de0f feat(cpu): add complement carry
7c4d2f9 feat(video): render CGA text on C64
407f11a feat(dev): add visible VICE launcher
8cac29d feat(cpu): add ModR/M exchange
ddd09f6 feat(cpu): add LES and LDS
3778e51 feat(cpu): add group5 near control flow
ff9baa0 docs: add continuation handoff
```

The end goal is not complete. Continue until the Generic XT BIOS displays via
CGA and attempts to boot the supplied MS-DOS 3.30 floppy. Commit every verified
milestone locally.

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

The current native CRT is still a diagnostic, not an XT boot UI. The desktop
reference model is presently used to advance the real Generic XT BIOS and find
the next missing CPU instruction.

## 4. Exact next task: DAA

Deterministic MDA/CGA status transitions are complete and break the BIOS video
polling loop. The BIOS now executes 87,742 successful instructions and stops on
instruction number 87,743 (zero-based trace index 87742):

```text
reported start: F000:E298
bytes:          27
meaning:        DAA
opcode family:  27, decimal adjust AL after addition
AX:             0203
FLAGS:          0206 before DAA
```

Implement 8088 `DAA`: use the incoming AF/CF and original AL to apply the 06h
and 60h corrections, update AF/CF plus SF/ZF/PF from adjusted AL, and choose a
deterministic convention for undefined OF that matches the project reference
and differential oracle. Cover no-adjust, low-digit, carry, and combined cases.
Regenerate, test, build, run VICE in warp mode, trace the next blocker, update
this guide, and commit the milestone. B8000 is still all zero at this blocker.

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

Run commands from `F:\projects\C64_x86`.

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
Built ...\build\c64x86.crt (4 banks, 32896 bytes)
Valid Magic Desk CRT: ...\build\c64x86.crt (4 banks, 32896 bytes)
```

Run the VICE gate. This script always uses `-warp` and must remain that way:

```powershell
.\tools\test_vice.ps1 -SkipBuild
```

Expected result:

```text
VICE 3.10 CRT smoke test passed with a 16 MiB REU.
Screenshot: F:\projects\C64_x86\build\vice-smoke.png
Log: F:\projects\C64_x86\build\vice-smoke.log
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
|---|---|
| `PROJECT_PLAN.md` | Complete architecture, requirements, phases, ROM policy, and risks |
| `README.md` | Current build, test, supported-instruction, ROM, and media instructions |
| `CONTINUATION.md` | This handoff and exact continuation point |
| `build.ps1` | Assembles and links the native diagnostic PRG |
| `build_crt.ps1` | Builds PRG, cartridge bootstrap, and final CRT |
| `Makefile` | Unix-style alternative build rules; PowerShell scripts are primary here |
| `.gitignore` | Excludes build, cache, ROM checkouts, binaries, and generated artifacts |

### CPU core

| Path | Purpose |
|---|---|
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
| `src/cpu8088/core.inc` | Shared CPU imports/constants |
| `tools/generate_cpu8088.py` | Generates `state.inc` and `smoke_vector.inc` from config/vectors |
| `tools/ref8088/runner.py` | Deterministic desktop 8088 reference model and BIOS trace engine |
| `tools/ref8088/unicorn_oracle.py` | Differential oracle for vector register/flag/memory behavior |
| `tests/vectors/cpu8088_smoke.json` | Canonical desktop and native instruction vectors |
| `tests/test_cpu8088_reference.py` | Reference determinism, generation, address, and Unicorn tests |

### Guest memory and host hardware

| Path | Purpose |
|---|---|
| `src/memory/reu.s` | REU register programming and transfers |
| `src/memory/guest_memory.s` | Guest physical memory access through the REU |
| `src/memory/page_cache.s` | 256-byte C64-RAM instruction page cache |
| `src/host/hardware.inc` | C64 Ultimate turbo and REU hardware constants |
| `src/host/turbo.s` | Turbo-mode setup |
| `src/bus/io.s` | Current XT I/O dispatcher; open bus plus ports 80h/81h latches |
| `src/video/cga.s` | REU-to-C64 CGA text renderer, color mapping, and native banner diagnostic |
| `src/boot/hwtest.s` | Native startup and green/red diagnostic UI |

### Cartridge

| Path | Purpose |
|---|---|
| `src/cartridge/bootstrap.s` | Autostart ROM and RAM-relocated cross-bank payload copier |
| `cfg/cartridge_bootstrap.cfg` | 256-byte bootstrap linker layout at cartridge address 8000h |
| `cfg/c64x86.cfg` | Native PRG memory/link layout |
| `tools/generate_cartridge_include.py` | Emits payload addresses/sizes for bootstrap assembly |
| `tools/build_crt.py` | Packages four Magic Desk banks and validates CRT structure |
| `tools/test_vice.ps1` | Warp-mode VICE CRT/REU/screenshot smoke gate |

### ROM, PCem, and media tooling

| Path | Purpose |
|---|---|
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

The user supplied a WinWorld MS-DOS 3.30 download. The original Kansas City
mirror returned HTTP 404; the alternate mirror listed on the same download page
worked. The archive and extracted files are ignored and must never be committed.

Local paths:

```text
.cache\media\msdos330-360k.7z
.cache\media\msdos330\Microsoft MS-DOS 3.30 (5.25)\DISK01.IMG
.cache\media\msdos330\Microsoft MS-DOS 3.30 (5.25)\DISK02.IMG
```

Hashes and geometry:

```text
archive SHA-256: 32e8b965ac11238f1d84e1c168031f1af7a13e89e9f1986e40ffa57c6a880f5c
DISK01 SHA-256:  d79f283ebd2cd68e8dede44ed876da13c25024f7000bcb576177820388c424f4
DISK02 SHA-256:  a85e1c35057d17a556a7fe151ca3824bf82eb13621392d803f487e35ebe8af56
image size:       368640 bytes
geometry:         40 cylinders, 2 heads, 9 sectors/track, 512 bytes/sector
boot signature:   55 AA
OEM/BPB text:      MSDOS3.3
```

Validate it with:

```powershell
python tools\validate_dos_media.py ".cache\media\msdos330\Microsoft MS-DOS 3.30 (5.25)\DISK01.IMG"
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
7. **Boot-media integration**: expose `DISK01.IMG` as drive A, let BIOS INT 19h
   load sector 0 to 0000:7C00, verify 55AA, and transfer control.
8. **DOS evidence**: show BIOS/CGA text followed by the MS-DOS boot message or
   command prompt in a warp-mode VICE screenshot.

Start correctness-first. Device timing can be approximate but deterministic
until basic boot works. Keep the guest clock and device scheduler design in
`PROJECT_PLAN.md`; do not add random wall-clock timing.

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
5. The floppy boot sector is read from the validated `DISK01.IMG` data.
6. Execution reaches 0000:7C00 and begins the MS-DOS boot sector.
7. A screenshot shows XT BIOS/DOS boot text or a DOS prompt.
8. All desktop tests, Unicorn vectors, CRT validation, and VICE gates pass.
9. Every milestone has its own local commit and the final working tree is clean.

If a full DOS prompt cannot yet be reached, do not hide the gap. Record the
exact trace/device blocker, preserve the last verified milestone in a commit,
and update this file with the next explicit continuation point.
