# C64 x86 end-to-end execution plan for Qwen 3.6 35B

## 1. Purpose and authority

This is the operational plan for completing the C64 x86 project from the
repository state inspected on 2026-07-27. It is written for a smaller coding
model. Follow it in order and do not make the model rediscover the workspace,
toolchain, source layout, or acceptance gates.

Use the documents in this priority order:

1. This file for execution order, commands, paths, and gates.
2. `CONTINUATION.md` for historical implementation detail.
3. `PROJECT_PLAN.md` for architecture, scope, risks, and version 1.0.
4. `README.md` for user-facing setup and current feature descriptions.
5. `docs/provenance.md` for licensing and source provenance.

When they conflict, the actual source and tests win. Known stale statements are:

- The workspace is `C:\Repository\C64_x86`, not `F:\projects\C64_x86`.
- PIC, PIT, DMA channel 2, PPI/keyboard, and an initial FDC already exist.
- A media-bearing CRT is currently 49 banks and 402,256 bytes, not four banks
  and 32 KiB. The four-bank statement describes the pre-media cartridge.
- The current task is beyond the keyboard wait described in `CONTINUATION.md`;
  work is now at the BIOS floppy boot path.

Do not change the fixed version 1.0 scope without updating `PROJECT_PLAN.md`.
The required release artifact is `build\c64x86.crt`. The PRG is diagnostic only.

## 2. Non-negotiable operating rules

1. Run all commands from PowerShell in `C:\Repository\C64_x86`.
2. Use patch-based edits. Do not destructively rewrite source files.
3. Never use `git reset --hard`, `git clean`, or checkout commands that discard
   work.
4. Before each milestone, run `git status --short`. Preserve unrelated and
   pre-existing changes.
5. Never commit `.cache`, `build`, `third_party`, ROM binaries, DOS images,
   VICE, cc65, Python packages, screenshots, logs, or object files.
6. Do not hand-edit generated files:
   `src\cpu8088\state.inc`, `src\cpu8088\smoke_vector.inc`, or
   `build\cartridge_payload.inc`.
7. After changing `config\cpu8088.json` or CPU vectors, run
   `python tools\generate_cpu8088.py`, then run the full gate.
8. VICE automation must always include `-warp`. Do not remove it from
   `tools\test_vice.ps1`.
9. Add the smallest deterministic regression test for each bug before or with
   the fix.
10. One verified behavior change per commit. Stage explicit paths, never
    `git add .`.
11. Use PCem as a behavioral/timing reference. Do not copy its desktop
    architecture or host abstractions into the 6502 program.
12. Do not claim completion from a desktop trace. Native execution in the CRT
    under VICE and then on C64 Ultimate hardware is required.

At the inspected checkpoint the worktree was already dirty:

```text
 M OLDER_ROM_NOTES.md
 M src/boot/hwtest.s
 M tools/test_vice.ps1
?? tools/trace_boot.py
?? tools/trace_boot2.py
?? tools/trace_boot3.py
?? tools/trace_boot4.py
?? tools/trace_io.py
```

Treat these as pre-existing user work. `OLDER_ROM_NOTES.md` appears to contain
accidentally pasted VICE font-log output; do not delete or repair it unless the
user explicitly assigns that cleanup. The `hwtest.s` and `test_vice.ps1`
changes are active diagnostics. Never roll them back implicitly.

## 3. Exact environment and tool locations

Start every work session with:

```powershell
Set-Location C:\Repository\C64_x86
git status --short
git log -5 --oneline
```

Verified local versions at the inspected checkpoint:

```text
PowerShell workspace: C:\Repository\C64_x86
Python:              3.14.2
Git:                 2.53.0.windows.2
ca65:                2.19, Git 547d923
ld65:                2.19, Git 547d923
VICE:                3.10, x64sc
Unicorn:             2.1.4
```

Exact project-local executables and dependencies:

```text
.cache\cc65\bin\ca65.exe
.cache\cc65\bin\ld65.exe
.cache\vice-3.10\GTK3VICE-3.10-win64\bin\x64sc.exe
.cache\vice-3.10\GTK3VICE-3.10-win64\bin\cartconv.exe
.cache\python\unicorn\
```

`build.ps1` first checks PATH for `ca65` and `ld65`, then uses the above cc65
copy. Do not hard-code another compiler path.

Bootstrap only a missing dependency:

```powershell
.\tools\bootstrap_cc65.ps1
.\tools\bootstrap_test_deps.ps1
.\tools\bootstrap_vice.ps1
```

These scripts need network access. Do not run them when the corresponding local
paths already exist.

Pinned reference checkouts:

```text
third_party\pcem
  repository: https://github.com/sarah-walker-pcem/pcem.git
  branch:     dev
  commit:     d674c4088e04a5fdc74e452c4d5284fa8920726d

third_party\pcem-roms
  repository: https://github.com/BaRRaKudaRain/PCem-ROMs.git
  branch:     master
  commit:     75bd118dd86378cac1d9d55e29e26ef82d6d57ef
```

Fetch only if absent:

```powershell
.\tools\fetch_pcem.ps1
.\tools\fetch_roms.ps1
python tools\verify_roms.py
```

## 4. Proprietary inputs and exact mappings

Never commit or redistribute these inputs.

Generic XT BIOS:

```text
File:          third_party\pcem-roms\genxt\pcxt.rom
Size:          8192 bytes
Guest mapping: FE000h-FFFFFh
SHA-256:       c3353ceed8954e586ae711373e3b3fdc923354fe6ceb9a124acb7d760bc974b5
Manifest:      config\roms.json, profile "genxt"
```

Build its ignored 1 MiB guest image with:

```powershell
python tools\build_guest_image.py --profile genxt
```

Expected output:

```text
build\guest-genxt.reu
```

MS-DOS 3.30 boot disk:

```text
File: .cache\media\msdos330\Microsoft MS-DOS 3.30 (5.25)\DISK01.IMG
Size: 368640 bytes
SHA-256: d79f283ebd2cd68e8dede44ed876da13c25024f7000bcb576177820388c424f4
Geometry: 40 cylinders, 2 heads, 9 sectors/track, 512 bytes/sector
Boot signature: 55 AA
OEM/BPB text: MSDOS3.3
Manifest: config\dos_media.json
```

Validate it with:

```powershell
python tools\validate_dos_media.py ".cache\media\msdos330\Microsoft MS-DOS 3.30 (5.25)\DISK01.IMG"
```

`build_crt.ps1` recursively finds `DISK01.IMG` under
`.cache\media\msdos330`, passes it to
`tools\generate_cartridge_include.py` and `tools\build_crt.py`, and embeds it
as cartridge media. The bootstrap stages it into the REU. A build without that
file is not an end-to-end floppy test.

## 5. Source map: edit the named file, not a guessed location

### Build and cartridge

| File | Responsibility |
|---|---|
| `build.ps1` | Generates/checks CPU contracts, assembles all native modules, links the PRG |
| `build_crt.ps1` | Builds PRG, finds DOS media, builds bootstrap, packages and validates CRT |
| `cfg\c64x86.cfg` | PRG layout: zero page `$0002-$001B`, program at `$0801` |
| `cfg\cartridge_bootstrap.cfg` | 512-byte bootstrap ROM at `$8000` |
| `src\cartridge\bootstrap.s` | Magic Desk autostart, cross-bank payload/media staging |
| `src\cartridge\media_stage.s` | Runtime media staging support |
| `tools\generate_cartridge_include.py` | Generates payload/media layout include |
| `tools\build_crt.py` | Variable-bank Magic Desk packager and structural validator |

### Native 8088 core

| File | Responsibility |
|---|---|
| `config\cpu8088.json` | Canonical state, flags, opcode metadata, handler names, cycles |
| `src\cpu8088\step.s` | Fetch/decode/execute and most opcode handlers |
| `src\cpu8088\state.s` | Registers and reset state |
| `src\cpu8088\address.s` | 20-bit segment:offset translation and wrap |
| `src\cpu8088\modrm.s` | All 8088 ModR/M effective-address forms |
| `src\cpu8088\stack.s` | REU-backed SS:SP helpers |
| `src\cpu8088\interrupts.s` | INT/IRET, IRQ/NMI latch, shadow, delivery counters |
| `src\cpu8088\divide.s` | DIV/IDIV |
| `src\cpu8088\multiply.s` | MUL/IMUL |
| `tools\ref8088\runner.py` | Deterministic desktop reference executor and BIOS tracer |
| `tools\ref8088\unicorn_oracle.py` | Independent x86-16 state/memory comparison |
| `tests\vectors\cpu8088_smoke.json` | Shared reference/native instruction vectors |
| `tests\test_cpu8088_reference.py` | Generated, reference, addressing, and Unicorn tests |

Unsupported native instructions return `CPU_STEP_INVALID` near the end of
`src\cpu8088\step.s`. Add opcodes only when a trace or conformance test requires
them; do not attempt an untested bulk implementation.

### Memory and host

| File | Responsibility |
|---|---|
| `src\memory\reu.s` | REU register programming and block DMA |
| `src\memory\guest_memory.s` | Guest physical reads/writes and data-cache coherence |
| `src\memory\page_cache.s` | 256-byte instruction page cache |
| `src\memory\guest_init.s` | Clears guest RAM and maps BIOS/media into REU |
| `src\host\hardware.inc` | C64U turbo, REU, and C64 hardware constants |
| `src\host\turbo.s` | Turbo detection, enable, and restore |
| `src\host\keyboard.s` | C64/PETSCII to XT set-1 translation |
| `src\boot\hwtest.s` | Startup diagnostics, native guest loop, scheduler, live trace UI |

Do not perform REU DMA through C64 RAM containing the active stack, DMA code,
IRQ handler, or live display metadata. Flush/invalidate caches before a direct
REU client reads or overwrites guest memory.

### XT devices and display

| File | Current responsibility |
|---|---|
| `src\bus\io.s` | Port dispatcher; open bus is `$FF`; routes PIC/PIT/PPI/DMA/FDC/CGA status |
| `src\devices\pic.s` | Initial 8259 ICW/OCW1, pending/mask/in-service, EOI, IRQ delivery |
| `src\devices\pit.s` | Initial 8253 channels, access modes, deterministic cycle advance, IRQ0 |
| `src\devices\dma.s` | Initial 8237 registers and channel-2 512-byte REU-to-guest transfer |
| `src\devices\fdc.s` | SPECIFY, RECALIBRATE, SENSE, SEEK, READ DATA, provisional WRITE DATA, READ ID |
| `src\video\cga.s` | Direct B8000-to-C64 40-column projection and color conversion |

Current FDC reference points:

```text
third_party\pcem\src\floppy\fdc.c
third_party\pcem\src\models\dma.c
third_party\pcem\src\models\pic.c
third_party\pcem\src\models\pit.c
third_party\pcem\src\io.c
```

Other exact PCem references:

```text
third_party\pcem\src\cpu\808x.c
third_party\pcem\src\ppi.c
third_party\pcem\src\keyboard\keyboard_xt.c
third_party\pcem\src\video\vid_cga.c
third_party\pcem\src\models\model.c
```

Record every adapted algorithm/table in `docs\provenance.md`.

## 6. Full verification gate

Run this gate after every native CPU/device milestone:

```powershell
python tools\generate_cpu8088.py --check
python -m unittest discover -s tests -v
$env:PYTHONPATH = ".cache\python"
python tools\ref8088\unicorn_oracle.py tests\vectors\cpu8088_smoke.json
Remove-Item Env:PYTHONPATH
.\build_crt.ps1
.\tools\test_vice.ps1 -SkipBuild
git diff --check
git status --short
git diff --stat
```

If a command fails, stop and fix that layer before continuing. Never commit a
red gate.

Verified baseline on 2026-07-27:

```text
Generated CPU contracts: current
Host tests: 17 passed
Unicorn vectors: all MATCH
PRG: build\c64x86-hwtest.prg
CRT: build\c64x86.crt, 49 banks, 402256 bytes
VICE: 3.10, warp mode, REU enabled, REUsize=16384, green border
```

The VICE script writes:

```text
build\vice-smoke.png
build\vice-smoke.log
```

The green border proves the diagnostic gate, not DOS boot. Inspect the
screenshot and the native trace row separately for milestone-specific evidence.

Commit a completed milestone with explicit paths:

```powershell
git diff --check
git add <only-the-files-for-this-milestone>
git diff --cached --stat
git commit -m "feat(scope): short behavior"
git status --short
```

## 7. Current implementation checkpoint

The native core already reaches Generic XT BIOS video and the BIOS floppy boot
path. Completed slices include:

- 20-bit guest memory, BIOS mapping, instruction and write-back data caches;
- a large tested subset of 8088 integer, control-flow, stack, string, port-I/O,
  interrupt, multiply/divide, shift/rotate, and segment instructions;
- Magic Desk bootstrap, variable banks, embedded media staging, and REU;
- BIOS-generated B8000 text projected to the C64 screen;
- XT PPI switches, keyboard set-1 queue, CGA status transitions;
- initial PIC, PIT, DMA channel 2, and FDC;
- FDC reset/sense handshake, SEEK/RECALIBRATE/SPECIFY/READ ID, and a one-sector
  READ DATA transfer;
- live native counters for FDC command/read activity and IRQ6 request/service.

The latest committed revision observed was:

```text
321ecf4 docs(rom): assess older IBM bios path
```

Recent functional milestones immediately before it include:

```text
d6e0e53 feat(cpu): implement modrm test opcodes
d4fcab1 fix(fdc): complete reset sense handshake
f6178c6 fix(media): stage contiguous floppy image
4396569 feat(cpu): advance bios through post
ebd6a37 feat(fdc): implement read id command
ea36975 feat(xt): stage media and add floppy path
```

The present code must not be replaced with a fresh design. Continue it.

Important current limitations:

- There are no deterministic desktop unit tests for PIC/PIT/DMA/FDC yet.
- FDC command `$05` currently enters the read path; real write-back is absent.
- READ DATA performs a single 512-byte sector transfer and returns a fixed
  seven-byte result. Multi-sector/EOT behavior is not yet complete.
- DMA support is the narrow channel-2 path needed for boot, not a general 8237.
- CGA ports other than deterministic status are largely unmodeled; rendering
  reads B8000 directly.
- The renderer shows only the left 40 cells of an 80-column guest page.
- Disk copy-on-write, explicit save/export, 320x200 CGA, speaker, menu, speed
  modes, profiling, hardware benchmarks, and release packaging remain.

## 7a. Codex audit on 2026-07-28

Qwen recorded later work in `CONTINUATION_C.md`, not in this plan. Its claimed
`F000:F78D` video-port stall was a trace-script error: the script searched for
mnemonic `OUT`, while the runner emits `OUT DX,acc`. Correct tracing shows
`F000:F788-F796` is a normal BIOS helper writing CRTC index/data pairs to
`$3B4/$3B5` and `$3D4/$3D5`; it is not a polling loop.

Qwen's broad `src/bus/io.s` shadow-register patch was removed because it made
FDC reads `$3F3/$3F4/$3F5/$3F7` unreachable and compared an outgoing data byte
instead of the port before FDC writes. The original `$3F2/$3F5` write routing
was already present.

Codex then made these bounded fixes:

- added the non-enhanced FDC `$3F3` read value `$20`;
- made READ ID command `$0A` consume its required drive/head parameter;
- corrected READ ID results from invalid `R=2,N=9` to `R=1,N=2`;
- added source-contract regressions for FDC high-page routing and READ ID;
- fixed the live diagnostic's screen/color addresses;
- added a native row-23 `CS:IP` and opcode display.

The gate now has 20 passing host tests, a valid 49-bank/402256-byte CRT, and a
passing VICE 3.10 warp/16 MiB REU smoke test. A 500-million-cycle native run
ended at `F000:E259`, opcode `$E2`, with FDC/read/IRQ6 counters all zero. This
is a finite BIOS delay loop (`MOV CX,$2956; LOOP $FE`): the desktop reference
enters it at instruction 26,461, executes 10,582 iterations, and exits at
instruction 37,042. Do not add video or FDC behavior to fix this loop. Use a
longer native run to reach the next checkpoint, or profile/accelerate only after
proving the native CX value is making forward progress.

A one-billion-cycle native run then displayed the real BIOS message
`SYSTEM ERROR #00, CONTINUE?` and reached `F000:F997`, also opcode `$E2`, with
all FDC/read/IRQ6 counters still zero. Bytes `33 C9 E2 FE` are
`XOR CX,CX; LOOP $FE`, a deliberate 65,536-iteration speaker-delay loop, not a
keyboard or device poll. Do not add video, keyboard, or FDC behavior to fix
either finite loop. Use a longer native run to reach the next checkpoint. Add
loop acceleration only as an explicit fast-mode feature with guest-cycle/PIT
accounting; do not introduce a BIOS-address-specific skip.




## 7b. Qwen continuation constraints and known failure modes (2026-07-28)

This section exists because a smaller model tends to overfit to the last
screenshot, make broad speculative changes, or rediscover already disproven
hypotheses. Follow these constraints literally.

### Scope and source-of-truth rules

- Work from the current checkout and existing architecture. Do not replace the
  CPU, bus, FDC, DMA, or memory-cache design with a new abstraction.
- Inspect the exact source and generated bytes before editing. A trace script,
  screenshot interpretation, or guessed hardware behavior is not evidence by
  itself.
- Make one bounded change at a time, add a focused regression, build, and run
  the smallest gate that can prove the change. Keep unrelated Qwen/user files
  untouched.
- Never restore a broad I/O shadow patch without proving every affected port
  remains reachable. Preserve existing FDC routes at `$3F2`, `$3F3`, `$3F4`,
  `$3F5`, and `$3F7`; compare the port number before comparing the data byte.
- Trace tools must match the runner's actual event representation. The runner
  records `OUT DX,acc`, not a standalone mnemonic named `OUT`; validate a trace
  script against a known event before drawing conclusions.

### Native-test interpretation

- Build commands are from the repository root:

  ```powershell
  .\build.ps1
  .\build_crt.ps1
  python -m unittest discover -s tests -v
  powershell -ExecutionPolicy Bypass -File tools\test_vice.ps1 -SkipBuild -CycleLimit 100000000
  ```

- The short 100M-cycle VICE gate is currently green after commit `59378f5`.
  A green short gate does not imply the 2B-cycle run is fixed.
- The infinite harness is `tools\run_long_tests.ps1`; it archives each run
  under `build\long-runs\run-*`. Inspect one completed run's screenshot and log
  before changing code. Do not treat a brown/non-green border as a diagnosis;
  decode the displayed fields or add explicit instrumentation.
- The earlier BIOS delay checkpoints (`F000:E259`/`F000:F997`, opcode `$E2`)
  are finite `LOOP` delays. They are not device polls and must not be fixed
  with video, keyboard, or FDC changes.

### Completed cache/DMA lesson

The previous deterministic banner failure was a real cache-coherency bug:
floppy DMA wrote directly to REU while the CPU write-back page cache held dirty
stack/return data. Invalidating the cache discarded those writes and sent
execution to `F600:8003` (the BIOS banner, not code). Commit `59378f5` flushes
the dirty page before DMA, while saving the FDC REU source pointer first because
cache flush reuses the REU address registers. Do not reintroduce either ordering
error.

### Current next checkpoint

After the cache fix, 100M passes but the 2B harness fails reproducibly at a
later RAM-execution state. The current diagnostic appears approximately as
`CS:IP = 0000:7351`, last opcode `$C0` (verify with direct instrumentation
before implementing anything). `$C0` is not an 8088 instruction; it may be an
unsupported/invalid opcode report or evidence of another corrupted control-flow
or RAM image. First determine which by recording:

1. `boot_failure_status` (invalid vs memory error);
2. current and previous two CS:IP/opcode values;
3. SS:SP and the bytes at SS:SP before/after the last DMA/interrupt;
4. FDC command, DMA address/page/count, and cache dirty/tag state.

Then compare the exact RAM bytes with the boot-sector/media image and the
pinned desktop reference. Do not implement opcode `$C0` until the guest bytes
prove that a valid 8088 path requires it.

### Required handoff format

Every Qwen continuation update must end with:

- exact commit and dirty files;
- exact build/test commands and pass/fail results;
- one reproducible native command;
- decoded CS:IP, status, opcode bytes, and device counters;
- one proposed next bounded task.


## 8. Execution method for every milestone

For each milestone below, use this loop:

1. Reproduce one exact failing native state.
2. Record CS:IP, opcode bytes or I/O sequence, relevant device registers,
   expected behavior, and actual behavior.
3. Compare the same narrow behavior with the pinned PCem source or an
   independent specification.
4. Add a deterministic host regression. Put CPU cases in
   `tests\vectors\cpu8088_smoke.json`; put structural/tooling tests in
   `tests\test_phase0_contracts.py`; add a focused new device test module for
   device models/tooling.
5. Implement the smallest native fix in the named module.
6. Run the full gate.
7. Capture milestone evidence from `build\vice-smoke.png`, the VICE log, or a
   deterministic trace.
8. Remove only temporary diagnostics introduced by this milestone. Preserve
   generally useful counters.
9. Commit only that milestone.
10. Update `CONTINUATION.md` with the new exact checkpoint before ending a work
    session that has not completed the project.

Do not spend several milestones implementing speculative completeness. Advance
the actual BIOS/DOS path first, then complete version 1.0 features behind
separate gates.

## 9. Milestone A: stabilize and identify the exact floppy blocker

Goal: obtain one unambiguous native I/O/IRQ/DMA trace for the current failure.

Files:

```text
src\boot\hwtest.s
src\bus\io.s
src\devices\pic.s
src\devices\dma.s
src\devices\fdc.s
tools\test_vice.ps1
```

Steps:

1. Preserve the pre-existing live trace edits. Make the automated VICE window
   hidden again only after the current diagnostic investigation is finished.
2. Keep the diagnostic row outside guest CGA output. Report at minimum:
   last FDC command, command parameter count, MSR phase, DOR, DMA channel-2
   address/count/page/mask/mode, PIC IRQ6 requests/deliveries, CPU IRQ6 service,
   FDC result reads, ST0/ST1/ST2, and current CS:IP.
3. Run the 8,000,000-cycle default VICE gate. Increase `-CycleLimit` only when
   the trace proves forward progress; continue using warp.
4. Classify the blocker as exactly one of:
   unsupported opcode, wrong I/O routing, wrong FDC phase/MSR, bad IRQ6,
   incorrect DMA programming/terminal count, wrong CHS/media offset, cache
   incoherence, or BIOS-visible status/result mismatch.
5. Write the observed values and the next single fix into `CONTINUATION.md`.

Acceptance:

- Repeated VICE runs reach the same CS:IP/device state.
- The diagnostic identifies one cause rather than merely “BIOS does not boot.”
- All baseline gates still pass.

Suggested commit only if reusable instrumentation changed:

```text
test(boot): expose <specific state>
```

## 10. Milestone B: deterministic XT device regression harness

Goal: stop debugging PIC/PIT/DMA/FDC solely through screenshots.

Files to add or extend:

```text
tests\test_xt_devices.py
tools\ref8088\            # only if shared desktop device helpers are needed
src\devices\pic.s
src\devices\pit.s
src\devices\dma.s
src\devices\fdc.s
```

Implement host-side deterministic tests for the behavior used by Generic XT:

- PIC ICW1-ICW4 sequence, OCW1 mask, priority, pending IRQ, non-specific EOI;
- PIT channel 0 low/high reload, mode 2/3 behavior used by BIOS, deterministic
  IRQ0 request;
- DMA channel 2 address/count flip-flop, page register `$81`, mask, mode,
  decrement/terminal-count behavior, and 64 KiB boundary rule;
- FDC DOR reset edge and four SENSE INTERRUPT results;
- SPECIFY, RECALIBRATE, SEEK, SENSE INTERRUPT, READ ID, READ DATA result phases;
- CHS-to-LBA mapping:
  `LBA = ((cylinder * 2 + head) * 9) + (sector - 1)`;
- sector 0 copy from media REU storage into guest `0000:7C00`;
- result bytes and IRQ6 ordering.

The desktop helper may be a small behavioral model; it must not attempt to run
6502 assembly. Use it to state the contract the assembly must meet. Cite PCem
paths in `docs\provenance.md`.

Acceptance:

- New device tests fail for the identified bug before the fix and pass after it.
- Existing 17 tests and all CPU vectors remain green.

Commit:

```text
test(xt): cover floppy boot transaction
```

## 11. Milestone C: BIOS reads sector 0 to 0000:7C00

Goal: complete the minimum correct FDC/DMA/PIC path for the boot sector.

Primary files:

```text
src\devices\fdc.s
src\devices\dma.s
src\devices\pic.s
src\bus\io.s
src\memory\guest_memory.s
src\memory\page_cache.s
src\boot\hwtest.s
```

Required behavior:

1. Route ports `$3F2`, `$3F4`, `$3F5`, `$3F7`, DMA `$00-$0F`, and page `$81`
   with correct read/write direction.
2. Honor FDC command, execution, and result phases in the main status register;
   RQM/DIO/CB bits must match what the BIOS polls.
3. Handle the DOR reset transition and IRQ6 exactly once per required event.
4. Decode READ DATA parameters C/H/R/N/EOT/GPL/DTL. For the first gate, one
   512-byte N=2 sector is sufficient only if the BIOS asks for one; otherwise
   implement the requested range through EOT.
5. Validate C=0, H=0, R=1 maps to the first 512 bytes of staged `DISK01.IMG`.
6. Copy through DMA channel 2 to the programmed guest address. Decrement the DMA
   count correctly and produce terminal count.
7. Invalidate instruction/data caches for the written guest range.
8. Return ST0/ST1/ST2/C/H/R/N consistent with success, then request IRQ6.
9. Add a temporary assertion/evidence check that physical `$07C00-$07DFF`
   equals the disk’s first sector and ends in `55 AA`.

Acceptance:

- Native evidence proves a disk-sector DMA into physical `$07C00`.
- The bytes at `$07DFE-$07DFF` are `55 AA`.
- BIOS INT 19h transfers execution to `0000:7C00`.
- The full gate passes.

Commit:

```text
feat(fdc): load boot sector through dma
```

## 12. Milestone D: execute the DOS boot sector

Goal: make the native 8088 core execute beyond `0000:7C00`.

Files:

```text
src\cpu8088\step.s
config\cpu8088.json
tests\vectors\cpu8088_smoke.json
tools\ref8088\runner.py
src\bus\io.s
```

Steps:

1. Trace from the first instruction at `0000:7C00`.
2. On `CPU_STEP_INVALID`, record the preceding 12 instructions, CS:IP, bytes,
   registers, flags, and required semantics.
3. Add one vector for that opcode family, including flags and memory effects.
4. Implement it in the desktop runner and native core.
5. Regenerate contracts and run Unicorn plus the full gate.
6. If execution loops on an I/O poll, switch to the relevant device milestone
   rather than adding speculative CPU instructions.
7. Repeat until the boot sector requests additional sectors or transfers into
   DOS system code.

Acceptance:

- Native core begins the validated MS-DOS 3.30 boot sector.
- There is visible DOS boot text or deterministic evidence of loading DOS
  system sectors.

Use one commit per opcode family:

```text
feat(cpu): add <8088 opcode family>
```

## 13. Milestone E: multi-sector floppy reads and DOS prompt

Goal: satisfy all BIOS INT 13h reads needed for DOS startup.

Primary files:

```text
src\devices\fdc.s
src\devices\dma.s
src\devices\pic.s
src\bus\io.s
src\boot\hwtest.s
tests\test_xt_devices.py
```

Required behavior:

- sequential sectors through EOT;
- head and cylinder rollover for 40x2x9 geometry;
- DMA address/count continuation and terminal count;
- correct result C/H/R/N and not-found/end-of-cylinder status;
- RECALIBRATE, SEEK, SENSE, READ ID, and READ DATA ordering used by the BIOS;
- deterministic IRQ6 and EOI behavior;
- read-only base image during this milestone.

Continue the trace/fix loop for CPU and motherboard gaps exposed by DOS.

Acceptance:

- A warp-mode VICE screenshot shows the MS-DOS boot message and command prompt.
- Native execution, not the desktop runner, produces the screen.
- At least one DOS command can be entered after Milestone F.

Commit device fixes separately from CPU fixes. Final milestone commit:

```text
feat(boot): reach dos prompt
```

## 14. Milestone F: reliable keyboard input

Goal: make the DOS prompt usable from the C64 keyboard.

Files:

```text
src\host\keyboard.s
src\bus\io.s
src\devices\pic.s
src\boot\hwtest.s
tests\test_xt_devices.py
```

Tasks:

- emit XT set-1 make and break codes, not only make codes;
- add all eight PETSCII function-key codes;
- cover modifiers, Enter, Backspace, Tab, Escape, punctuation, cursor keys,
  Ctrl, Alt, and Caps Lock;
- do not overwrite an unread port `$60` byte; use a small queue;
- model the PPI keyboard acknowledge/reset behavior needed by the BIOS;
- request IRQ1 through the PIC for queued events;
- remove the automatic `Y` injection once interactive input is reliable, or
  guard it behind a diagnostic build flag.

Acceptance:

- Type `VER`, `DIR`, and an edited command at the DOS prompt.
- Make/break and modifier tests are deterministic.
- Timer IRQ0 and floppy IRQ6 continue to work while typing.

Commit:

```text
feat(input): complete xt keyboard queue
```

## 15. Milestone G: complete version 1.0 CGA display

Goal: replace the debug projection with usable CGA text and basic graphics.

Files:

```text
src\video\cga.s
src\bus\io.s
src\memory\guest_memory.s
src\memory\page_cache.s
docs\provenance.md
```

Implement in this order:

1. CGA registers `$3D4/$3D5`, mode control `$3D8`, color `$3D9`, and status
   `$3DA`.
2. Cursor shape/position and active-page/start-address behavior used by DOS.
3. Dirty tracking for `$B8000-$BBFFF`; render changed cells/lines only.
4. A readable 80x25 mode: licensed/original 4x8 font, or horizontally panned
   8x8 view. Keep the existing 40-column projection as a debug/fallback mode.
5. CGA 320x200 four-color graphics mapped to a VIC-II bitmap.
6. Optional 640x200 monochrome downsample/panned view only after 320x200 works.

Do not copy an unknown IBM font ROM. Record source, version, license, hash, and
build method for every font/table in `docs\provenance.md`.

Acceptance:

- BIOS and DOS 80x25 text are legible.
- Cursor and color attributes work.
- A redistributable CGA test program displays a verified 320x200 pattern.
- Dirty rendering does not break REU cache coherence.

Commits:

```text
feat(cga): model text registers
feat(video): render readable 80 column text
feat(video): add cga 320x200 mode
```

## 16. Milestone H: safe floppy writes and persistence

Goal: meet version 1.0 disk safety requirements.

Files:

```text
src\devices\fdc.s
src\devices\dma.s
src\cartridge\media_stage.s
src\boot\hwtest.s
tools\build_crt.py
tests\test_xt_devices.py
```

Required design:

- Correct WRITE DATA `$05`; do not route it to the read implementation.
- Guest-to-media DMA channel-2 direction.
- Dirty-sector bitmap for 720 sectors.
- Copy-on-write by default. Never alter the user’s only base image silently.
- Explicit menu command for save/export.
- Atomic export where the host API permits it; otherwise write a new named
  image and document the limitation.
- Read-only mode when no safe export path is available.

Acceptance:

1. Boot a disposable generated 360 KiB test image.
2. Create/write a file, read it back, and reboot.
3. Export to a new image.
4. Validate the base image hash is unchanged.
5. Boot the exported image and verify persistence.

Commit:

```text
feat(storage): add copy on write floppy saves
```

## 17. Milestone I: menu, reset, sound, timing, and speed modes

Goal: complete remaining user-facing version 1.0 behavior.

Likely files/directories:

```text
src\boot\hwtest.s
src\host\
src\devices\pit.s
src\devices\pic.s
src\bus\io.s
```

Add:

- emulator menu: reset, compatible/fast speed, disk selection, save/export,
  diagnostics, and return;
- clean guest reset without power-cycling the C64;
- PC speaker from PIT channel 2 and PPI gate, mapped initially to one
  SID/UltiSID voice;
- one guest-clock accumulator used by CPU, PIT, PIC, FDC, keyboard, speaker,
  and video;
- compatible mode with better event timing;
- fast mode with coarser batching and only verified idle-loop acceleration.

The host raster IRQ may request work but must not mutate guest device state
inside an instruction handler. Process device events at explicit safe points.

Acceptance:

- Reset and menu do not corrupt disk state.
- PIT-dependent DOS time advances consistently.
- Speaker can be disabled for performance tests.
- Compatible and fast modes both boot DOS.

Use separate commits for menu, speaker, and scheduling.

## 18. Milestone J: performance and real-hardware feasibility gate

Goal: finish the benchmark work deferred from original Phase 0.

Hardware:

- C64 Ultimate / Ultimate 64 Elite-II at up to 64 MHz;
- original Ultimate 64 at up to 48 MHz;
- configured 16 MiB REU;
- supported stable firmware with U64 Turbo Registers or Turbo Enable Bit.

Measure:

- tight ALU/dispatch throughput;
- instruction mix during BIOS and DOS;
- REU setup cost and throughput for 256, 512, and 1024-byte transfers;
- instruction/data-cache hit/miss/write-back counts;
- 1, 48, and 64 MHz as supported;
- badlines on/off;
- display and speaker on/off;
- compatible and fast modes.

Add counters per opcode family, cache miss, DMA byte, scheduler event, and
rendered dirty region. Do not optimize from intuition.

Optimization order:

1. common opcode and effective-address handlers;
2. fewer REU/cache misses;
3. larger/batched peripheral work;
4. dirty-region video;
5. proven idle-loop acceleration.

Acceptance:

- Publish repeatable methodology and results.
- Report measured effective emulation speed honestly.
- DOS is interactively usable on the supported hardware matrix, or the
  documented scope/performance claim is revised before release.

## 19. Milestone K: licensing, reproducibility, and release

Goal: satisfy every `PROJECT_PLAN.md` version 1.0 condition.

Tasks:

1. Choose and add the project license. If any PCem logic/table was adapted, use
   GPL-2.0-compatible terms and preserve attribution.
2. Complete `docs\provenance.md` for PCem logic, fonts, tables, tools, BIOS
   profiles, and test media.
3. Ensure no proprietary bytes are in Git or the public release CRT.
4. Make the public build work without proprietary inputs. Provide a manifest
   and documented user-side asset loading workflow. A local development CRT may
   contain ignored media, but it is not redistributable.
5. Update stale README/CONTINUATION statements, especially bank counts, current
   feature coverage, and exact paths.
6. Document C64U firmware/board test matrix, REU setup, turbo settings,
   keyboard map, disk safety, speed, and known limitations.
7. Add reproducible clean-worktree build instructions.
8. Run a clean license/provenance audit and complete compatibility checklist.

Release artifacts:

```text
build\c64x86.crt       # primary autostart cartridge
build\c64x86-hwtest.prg # optional developer diagnostic
```

Final acceptance checklist:

- autostart CRT validates in `cartconv`, VICE, and supported C64U hardware;
- 16 MiB REU detection and turbo enable/restore are safe;
- Generic XT BIOS boots a permitted/locally supplied 360 KiB DOS-compatible
  disk;
- CPU conformance suite passes;
- PIC, PIT, keyboard, CGA text, 320x200 graphics, floppy read/write COW, and
  speaker work;
- disk base image cannot be silently corrupted;
- measured speed and hardware matrix are published;
- no proprietary ROM/media/font is committed or distributed;
- every automated and hardware gate passes;
- final worktree is clean.

Suggested final commits:

```text
docs: complete setup and compatibility guide
build(release): prepare c64x86 v1.0
```

## 20. Stop and handoff protocol

If execution must stop before version 1.0:

1. Finish and commit the last green milestone.
2. Do not commit a partially failing implementation.
3. Preserve experimental work without overwriting pre-existing user changes.
4. Update `CONTINUATION.md` with:
   - last good commit;
   - exact command that reproduces the next failure;
   - CS:IP and opcode bytes, or exact I/O/device sequence;
   - expected and actual values;
   - files already changed;
   - tests passing/failing;
   - the next single bounded task.
5. State the unmet acceptance item plainly. A green border alone is not project
   completion.

