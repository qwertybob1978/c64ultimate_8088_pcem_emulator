# C64 x86

Native Intel 8088 / IBM PC-XT simulation for the Commodore 64 Ultimate.

For an exact implementation checkpoint and step-by-step continuation handoff,
see [`CONTINUATION.md`](CONTINUATION.md).

The project is in Phase 0. The current target program validates the host
features on which the simulator will depend:

- software-controlled C64U turbo mode;
- REU register presence;
- a non-destructive 16 MiB REU capacity probe;
- guarded C64-to-REU and REU-to-C64 block transfers;
- the 8088 register block, PC/XT reset state, and 20-bit segmented addressing;
- manifest-verified BIOS placement into a raw 1 MiB guest-memory image.

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the architecture and milestones.

## Build requirements

- cc65, including `ca65` and `ld65`
- GNU Make, or PowerShell on Windows
- Python 3 for host-side tests

On Windows, install the portable project-local cc65 toolchain with:

```powershell
./tools/bootstrap_cc65.ps1
```

It is unpacked under `.cache/cc65`, which is ignored by Git. `build.ps1`
automatically uses this copy when cc65 is not available on `PATH`.

Build with either:

```sh
make
```

or:

```powershell
./build.ps1
```

The output is `build/c64x86-hwtest.prg`.

Build the required autostart cartridge executable with:

```powershell
./build_crt.ps1
```

The primary output is `build/c64x86.crt`. It is a four-bank, 32 KiB Magic Desk
cartridge. On reset, a ROM bootstrap initializes the C64, relocates its loader
to `$0200`, copies the diagnostic payload across Magic Desk banks into internal
RAM, clears BSS, disables the cartridge through `$DE00`,
and continues at the relocated entry point. The REU at `$DF00` remains
available. The `.prg` remains a developer diagnostic artifact.

## Running the hardware diagnostic

1. Configure a 16 MiB REU in the Ultimate settings.
2. Set Turbo Control to `U64 Turbo Registers` or `Turbo Enable Bit`.
3. Load and run `c64x86-hwtest.prg`.
4. Confirm that turbo control, REU presence, and the 16 MiB probe all report
   `OK`. The diagnostic also checks the 8088 reset address and executes a small
   cached guest instruction stream; both CPU checks should report `OK`.

The capacity test temporarily changes one byte at REU addresses `$000000` and
`$800000`, but saves and restores both bytes before returning. Turbo settings
are likewise restored before the program returns to BASIC.

The border starts red and changes to green only after every required REU and
8088 check passes. VICE does not emulate the C64 Ultimate turbo register, so
`TURBO CONTROL: NOT AVAILABLE` is expected in desktop smoke tests.

## VICE smoke test

Install the pinned, project-local VICE 3.10 package on Windows with:

```powershell
./tools/bootstrap_vice.ps1
```

It is downloaded from the official VICE SourceForge release archive, verified
against `config/vice.json`, and unpacked below `.cache`, which is ignored by
Git. No system-wide installation or user VICE configuration is changed.

Build and boot the CRT in cycle-accurate `x64sc` with a 16 MiB REU:

```powershell
./tools/test_vice.ps1
```

The script validates the cartridge independently with VICE `cartconv`, starts
from VICE defaults, explicitly enables a 16384 KiB REU, boots the Magic Desk
CRT in warp mode, and checks the log and final green diagnostic border. The
ignored evidence files are `build/vice-smoke.log` and
`build/vice-smoke.png`.

## Current 8088 execution subset

The native stepper currently implements `NOP`, `HLT`, byte/word immediate
register `MOV`, register and REU-memory ModR/M `MOV`, short and near relative `JMP`, and
the byte/word accumulator-immediate forms of `ADD`, `OR`, `ADC`, `SBB`, `AND`,
`SUB`, `XOR`, and `CMP`, including 8088 condition flags. It also supports
`CLC`/`STC`/`CLI`/`STI`/`CLD`/`STD`. All 8088 ModR/M effective-address forms
are decoded with the correct DS/SS default segment. Data operands currently
use correctness-first byte DMA; Phase 2 replaces this with a write-back page
cache. Register and memory ModR/M forms of `ADD`, `OR`, `ADC`, `SBB`, `AND`,
`SUB`, `XOR`, and `CMP` share the same native flag engine as accumulator forms.
The native control-flow slice also supports register `INC`/`DEC`, register
`PUSH`/`POP`, near relative `CALL`, near `RET`/`RET imm16`, and all sixteen
short conditional branches with REU-backed SS:SP stack accesses.
Group-4 `INC`/`DEC` extends the same carry-preserving flag behavior to byte
register and REU-memory operands.
`LOOPNE`, `LOOPE`, `LOOP`, and `JCXZ` provide the 8088 CX-controlled short
branch family without modifying arithmetic flags.
Group-5 near indirect `CALL` and `JMP` support register and memory targets,
including segment-overridden BIOS dispatch tables.
Native prefix decoding applies ES/CS/SS/DS overrides to ModR/M operands and
supports interruptible-instruction groundwork for `REP`/`REPNE`. Byte and word
`MOVS`, `CMPS`, `STOS`, `LODS`, and `SCAS` execute directly against REU-backed
guest memory, including direction-flag index updates, zero-count repetition,
and the ZF-controlled stopping rules for `REPE` and `REPNE` comparisons.
Real-mode software interrupt entry and return are native as well: `INT3`,
`INT imm8`, taken `INTO`, and `IRET` use the REU-backed IVT and SS:SP stack,
preserve the 8088 interrupt frame layout, and clear TF/IF on entry.
An asynchronous IRQ latch holds a PIC-supplied vector while IF is clear,
honors the one-instruction interrupt shadow after `STI`, and wakes a halted
guest once delivery becomes legal. A separate NMI latch bypasses IF/shadow.
Native `DIV`/`IDIV` handlers cover byte and word register or memory divisors.
They use bounded binary long division and enter interrupt 0 without modifying
the dividend on a zero divisor or a quotient that cannot fit its destination.
The same Group-3 decoder implements byte/word `NOT` for register and memory
operands without changing any FLAGS bits.
`PUSHF`/`POPF` round-trip the 8088 FLAGS image through the REU-backed stack,
while `SAHF`/`LAHF` transfer the five arithmetic status flags through AH.
Immediate far `CALL`/`JMP` and `RETF`/`RETF imm16` now update CS:IP and the
far return frame natively, including instruction-cache page changes. This
includes the `EA` reset-stub jump used by XT-compatible BIOS ROMs.
Segment setup now includes `MOV` between ES/SS/DS and register or memory
operands plus `PUSH`/`POP` for the 8088 segment registers. Loading SS arms the
same one-instruction interrupt shadow used by the boundary IRQ logic.
Group-1 immediate arithmetic (`80`–`83`) supports byte/word register and
memory destinations, including sign extension for the compact `83` encoding.
Single-bit `SHL`/`SAL`, `SHR`, and `SAR` (`D0`/`D1`, ModR/M extensions 4–7)
support byte and word register or memory destinations with 8088 CF, OF, SF,
ZF, and PF results.
The corresponding `D2`/`D3` forms iterate the unmasked 8088 `CL` count and
leave operands and flags unchanged when that count is zero.
All immediate- and DX-addressed `IN`/`OUT` forms execute natively as 8088 byte
bus transfers. The initial XT I/O dispatcher returns `$FF` for open ports and
provides `$80`/`$81` POST/debug latches with deterministic desktop traces.
Instruction fetch uses one 256-byte C64-RAM page backed by REU DMA; the
byte-at-a-time fetch remains only as a bootstrap diagnostic path.

The canonical register layout, flag masks, and implemented opcode metadata are
in `config/cpu8088.json`. Regenerate the assembly contract and native smoke
vector after changing that specification or its JSON vectors:

```sh
python tools/generate_cpu8088.py
```

Run the deterministic desktop reference model and print its instruction traces
with:

```sh
python tools/ref8088/runner.py tests/vectors/cpu8088_smoke.json --json
```

The same `native_smoke` vector generates the byte stream and expected register
values consumed by the cartridge diagnostic, preventing the desktop and native
tests from silently drifting apart.

For independent semantic comparison, install the pinned Unicorn x86 engine
into the ignored project cache and run the differential oracle:

```powershell
./tools/bootstrap_test_deps.ps1
python ./tools/ref8088/unicorn_oracle.py ./tests/vectors/cpu8088_smoke.json
```

Unicorn comparison covers architectural state and memory effects. Instruction
cycle metadata remains an 8088-specific contract informed by PCem's
`src/cpu/808x.c`, because Unicorn does not model 8088 bus timing.

The desktop oracle additionally covers 16-bit register `INC`/`DEC`,
`PUSH`/`POP`, near relative `CALL`, near `RET`, and the complete `Jcc` condition
decoder. These handlers are validated in the reference model before entering
the size-constrained native assembly dispatch.

Prefix-aware reference execution supports ES/CS/SS/DS segment overrides,
`REP`/`REPE`/`REPNE`, and byte/word `MOVS`, `CMPS`, `STOS`, `LODS`, and `SCAS`.
The Unicorn adapter accounts for its one-iteration-at-a-time REP stepping so
the comparison still covers the complete architectural instruction.
The reference core also covers unsigned/signed byte and word division,
including divide-by-zero and quotient-overflow interrupt 0. Its oracle adapter
preserves the original 8088 rule that the saved return IP follows the `DIV` or
`IDIV`; later x86 generations report the faulting instruction instead.

## PCem reference checkout

PCem is reference material and is not linked into the target program. Fetch the
pinned revision with:

```powershell
./tools/fetch_pcem.ps1
```

The checkout lives at `third_party/pcem` and is ignored by this repository.

Fetch and validate the user-requested development ROM collection with:

```powershell
./tools/fetch_roms.ps1
python ./tools/verify_roms.py
```

The ROM checkout is also ignored. Its upstream repository has no license file,
so ROM binaries must not be committed or packaged with releases.

Create a raw 1 MiB REU guest-memory image with the selected BIOS mapped into
place:

```sh
python tools/build_guest_image.py --profile genxt
```

This writes `build/guest-genxt.reu`, which is ignored because it contains the
locally acquired ROM. It can be preloaded at REU address zero for bootstrap
testing.

## User-supplied DOS boot media

The XT boot target uses Microsoft MS-DOS 3.30 `DISK01.IMG` from the WinWorld
download recorded in `config/dos_media.json`. Keep the downloaded archive and
extracted images under `.cache/media`; they are proprietary test inputs and
must never be committed or redistributed. Validate the extracted boot disk:

```powershell
python tools/validate_dos_media.py ".cache/media/msdos330/Microsoft MS-DOS 3.30 (5.25)/DISK01.IMG"
```

The expected image is a raw 360 KiB floppy with 512-byte sectors, 9 sectors
per track, 2 heads, 40 cylinders, and an `MSDOS3.3` boot sector.

## Host tests

```sh
python -m unittest discover -s tests -v
```
