# Optimization options

This document records performance options for the C64 x86 8088 emulator. It is
an engineering plan, not permission to weaken 8088 behavior. Every optimization
must preserve the CPU/device contract and be measured in native VICE and, where
possible, on a C64 Ultimate.

## Current facts

- The target is a 6510/8500-class host with a 16 MiB REU backing guest memory.
- The native interpreter is hand-written 6502 assembled by `ca65`; there is no
  C compiler optimization level to enable.
- `src/boot/hwtest.s` executes 64 guest instructions per batch, then polls input,
  renders 25 CGA text rows, and updates the FDC diagnostic row.
- `src/cpu8088/step.s` uses a linear opcode comparison chain. Most instructions
  call shared address, memory, ALU, stack, or I/O helpers.
- `src/memory/page_cache.s` has one 256-byte instruction page in C64 RAM.
- `src/memory/guest_memory.s` has one 256-byte data page in C64 RAM. Dirty data
  is written to REU on an explicit flush or page replacement.
- `src/video/cga.s` reads 25 rows of 160 bytes from REU for each full text
  render. This is up to 4,000 bytes and 25 REU transfers per render.
- `src/devices/dma.s` flushes the data cache before a floppy DMA transfer, then
  transfers through a 256-byte buffer. A 512-byte sector therefore needs two
  REU transfers after the cache flush.
- Turbo is already detected and set to the maximum supported index in
  `src/host/turbo.s` and `src/boot/hwtest.s`.
- `build.ps1` invokes `ca65` with debug information and `ld65` with a map and
  label file. These options mainly affect artifacts and diagnostics, not the
  hot-path instruction count.
- The current native gate is a 2.2-billion-cycle VICE smoke run. It proves that
  the CRT runs to the existing diagnostic gate, not that it reaches a DOS prompt
  or that it runs at a useful guest instruction rate.

## Measurement before editing

Add counters before making a performance claim. At minimum record:

| Counter | Owner | Purpose |
| --- | --- | --- |
| guest instructions | boot scheduler | throughput denominator |
| host C64 batches | `hwtest.s` | scheduler overhead |
| instruction-page refills | `page_cache.s` | instruction locality |
| data-page refills | `guest_memory.s` | data locality |
| data-page flushes | `guest_memory.s` | write-back cost |
| REU transfers and bytes | `reu.s` | DMA overhead and volume |
| video renders and rows | `cga.s` | display tax |
| device polls | `hwtest.s` | host-service tax |
| interrupt entries | `interrupts.s`/PIC | event frequency |
| invalid or memory failures | CPU runner | correctness guard |

Use a fixed boot image, fixed VICE version, `-warp`, and the same cycle limit.
Report guest instructions completed and counter deltas, not only wall-clock
runtime. VICE's `-warp` mode is useful for repeatability but is not a C64U speed
measurement. A hardware run must record turbo setting, REU size, firmware, and
whether badline execution is enabled.

A useful first benchmark is a deterministic guest loop that runs from one code
page and touches a known data page. A second benchmark should replay the BIOS
boot path. The two separate locality patterns prevent a cache optimization from
looking good only because of an artificial loop.

## Recommended order

### 1. Remove diagnostic work from the release hot loop

The current boot loop always calls `cga_render_text_40` and
`display_fdc_runtime` after each 64-instruction batch. Keep the full renderer
for interactive/debug mode, but add a selectable display cadence, for example:

- render every N batches while the guest is running;
- render immediately after a guest write to CGA memory or a CRTC mode/address
  change;
- update the diagnostic row only on counter changes or at a slower cadence.

This is likely the safest first win because it does not alter guest CPU
semantics. The renderer already flushes before reading video memory, so reducing
its call frequency also reduces cache write-back pressure. Preserve a forced
render path for faults and prompts.

Risk: delayed visible output and missed transient screen states. Gate with a
screen-update test and retain an interactive/debug cadence.

### 2. Increase guest batching carefully

Raise `boot_steps_remaining` above 64 and measure throughput at 128, 256, 512,
and 1024 instructions. Poll input, interrupts, PIT advancement, and display at
explicit scheduler boundaries rather than after every instruction.

The correct boundary is not necessarily the largest batch. A batch must still
service pending IRQ/NMI work, keyboard input, and video often enough for BIOS
wait loops and interactive software. Use a maximum instruction count plus an
interrupt/event deadline, not an unbounded loop.

Risk: keyboard latency, delayed PIT/FDC service, and altered interrupt timing.
Do not change architectural instruction results or accept a new BIOS timeout.

### 3. Specialize the cache fast paths

`cpu8088_mem_read_u8` and `cpu8088_fetch_u8` repeat validity/tag checks for every
byte. Add small fast paths for the common case where the physical page tag is
unchanged. Candidate techniques, in increasing complexity:

1. Keep the current API but arrange hot state and tags in zero page.
2. Cache the current physical page high bytes once per instruction and let
   helpers test the cached page with fewer loads.
3. Add word read/write helpers for aligned ModR/M and stack operations, while
   retaining byte helpers for unaligned and wraparound cases.
4. Keep separate code-page and data-page tags/dirty state, as the current design
   already does conceptually, so instruction fetches do not pay data-cache work.

Do not remove `cpu8088_fetch_cache_write_u8`: self-modifying guest code must
update a cached instruction page when a write targets it. Any word fast path
must handle 20-bit segment wrap and page boundaries exactly.

Expected payoff: high if profiling shows cache-hit helper overhead dominates;
low if REU transfers dominate.

### 4. Move the hottest mutable state into zero page

The linker reserves only `$0002-$001B` for zero page. The CPU state and many
working variables are currently in BSS. Candidate zero-page state includes:

- current physical address and segment/offset temporaries;
- CPU IP/CS/DS/ES/SS and frequently used general registers;
- cache tags/valid/dirty flags;
- decoder temporaries used on nearly every instruction.

This requires a deliberate layout and may require reducing or reorganizing the
large `CPU_STATE_SIZE`. Do not move every variable automatically: zero-page
pressure can make code harder to reason about and can evict variables needed
by device code.

Expected payoff: medium to high in the interpreter. Risk is high because every
addressing, interrupt, and device path depends on the state layout. Add generated
layout assertions and run all CPU vectors before native boot tests.

### 5. Replace the linear opcode decoder after coverage is stable

The comparison chain in `src/cpu8088/step.s` is easy to audit but pays many
branches before reaching less-common handlers. Options:

- A 256-byte class table in ROM/RAM followed by a compact second-level dispatch.
- Coarse bit-pattern dispatch first, then a short family-local comparison.
- A jump table of handler addresses if the 6502 banking/relocation model permits
  it.
- Keep very common BIOS/DOS families in an early fast path: MOV, ALU, branches,
  stack, string, and I/O.

A table must still reject unsupported opcodes and preserve prefix handling,
`LOCK`, `REP`, segment overrides, exceptions, and instruction length. Generate
the table from `config/cpu8088.json` rather than maintaining two independent
opcode inventories.

Expected payoff: medium. Risk is high: dispatch-table bugs tend to corrupt
control flow and can look like memory or BIOS failures. Implement only after the
opcode inventory and differential tests are green.

### 6. Reduce address-calculation duplication

Most ModR/M instructions repeatedly decode the same effective address and then
recompute physical addresses for byte/word accesses. Candidate changes:

- Keep a decoded operand descriptor for the duration of one instruction.
- Store physical base plus offset once and increment it for the second byte of a
  word access.
- Combine common register-direct forms with direct register loads/stores.
- Specialize `[BX+SI]`, `[BX+DI]`, `[BP+SI]`, `[BP+DI]`, and displacement forms
  only if traces show they dominate.

All paths must retain DS versus SS defaults, segment overrides, 20-bit wrapping,
and page-crossing behavior. Differential tests must include every ModR/M mode,
word boundary, and segment-wrap case.

Expected payoff: medium to high for BIOS/DOS workloads. Risk is medium to high.

### 7. Make REU transfers larger and less frequent

The REU is fast relative to byte-at-a-time emulation, but each transfer still
has register programming overhead. Options:

- Combine adjacent row reads when video layout and destination buffer permit.
- Use a 512-byte or 1 KiB data cache when it reduces page churn.
- Keep a sector-sized DMA buffer and avoid redundant source/destination setup.
- Batch contiguous guest memory initialization and disk transfers.
- Use fixed REU address-control modes for transfers that do not need C64-address
  increments.

The current DMA path must preserve cache coherency: it flushes dirty guest data
before writing directly to REU. Any larger cache needs explicit overlap rules for
DMA, video reads, instruction fetches, and self-modifying code.

Expected payoff: high when cache misses, video, or floppy activity dominate.
Risk is medium because stale cache data causes silent guest corruption.

### 8. Add dirty tracking for CGA text rendering

Instead of copying all 25 rows each time, track guest writes to the CGA text
page and CRTC start-address changes. Maintain a dirty-row bitmap or dirty page
map. Render only changed rows, with a full-render fallback after mode changes,
DMA, cache invalidation, or diagnostic capture.

The current generic memory write path can mark a row when the physical address is
in `$B8000-$B8FA0`; direct DMA must mark all affected rows. A simpler first
version can mark the whole screen on any CGA write, then refine to rows.

Expected payoff: high for text workloads with sparse output. Risk is medium;
video writes from BIOS/DOS must not be missed.

### 9. Separate guest timing from host service frequency

`pit_advance_cycles` currently receives the last instruction's modeled cycle
count, while host services run at batch boundaries. Keep guest PIT/FDC timing
monotonic, but schedule host work by accumulated guest cycles rather than by a
fixed number of instructions. This permits larger batches on cheap instructions
and earlier service around deadlines.

Do not use host-cycle timing as guest timing. The emulator's architectural
interrupt order and BIOS-visible timer behavior are the compatibility contract.

Expected payoff: medium for throughput and responsiveness. Risk is medium to
high around IRQ0, IRQ6, keyboard IRQs, and `HLT`.

### 10. Fast paths for common guest instruction families

Once measurements identify the workload, add narrow handlers for common forms:

- register-to-register MOV and ALU without ModR/M memory work;
- register PUSH/POP and near CALL/RET;
- short branches and LOOP;
- byte/word string operations with cached contiguous pages;
- `IN`/`OUT` to the small set of implemented XT ports;
- BIOS memory-fill and compare loops.

A fast path may share the same flag and exception routines. It must never be an
address-specific BIOS bypass. Keep a slow reference path and compare both paths
with the same vectors.

Expected payoff: high if the BIOS/DOS trace has a stable hot mix. Risk is medium.

## Structural options

### Threaded interpreter

Use a table of handler addresses or compact handler IDs to avoid the long opcode
comparison chain. This is a plausible intermediate step between the current
switch-like decoder and translation. It has moderate code-size and relocation
complexity on 6502, but preserves instruction-by-instruction semantics.

### Basic-block interpreter

Decode a straight-line block once, cache its handler sequence and operand
metadata, and execute it until a branch, interrupt boundary, self-modifying
write, page boundary, or device-visible event. Invalidate blocks when guest code
pages are written. This should be prototyped on the desktop reference first and
then measured in native memory budget.

### 6502 code generation / block translation

Generate specialized 6502 snippets for frequently executed 8088 blocks and keep
metadata for invalidation. This has the highest potential throughput but also
needs relocation, code-cache eviction, self-modifying-code handling, interrupt
checks, and a fallback for every opcode. It is a post-correctness experiment,
not the next optimization increment.

### Guest profile specialization

A fixed Generic XT + CGA text + 360 KiB floppy profile permits compact device
and address fast paths. Keep them behind an explicit profile/configuration
boundary. Do not bake BIOS addresses, disk sectors, or DOS behavior into the
CPU core.

## Options that are not currently justified

- Removing cache flushes: unsafe; DMA and video can observe stale guest data.
- Disabling interrupts or PIT advancement: invalid for BIOS/DOS compatibility.
- Skipping unsupported opcodes or treating them as NOPs: hides CPU bugs.
- Patching BIOS loops by address: acceptable only as a temporary measured native
  diagnostic workaround, not as a general optimization.
- Increasing REU size: already 16 MiB in the target gate; it does not improve
  transfer latency.
- Changing the assembler/linker debug flags: useful for artifact hygiene, but
  unlikely to improve runtime because the target is assembly and the map/labels
  are not part of the CRT payload.
- Replacing REU memory with C64 RAM: faster but removes the 1 MiB guest-memory
  capacity and is incompatible with the fixed target architecture.
- Using VICE `-warp` as a claim of real-time speed: it changes host scheduling,
  not guest instruction cost.

## Staged execution plan

1. Add counters and a deterministic native benchmark mode. Record baseline
   instruction rate, cache misses, flushes, REU bytes, and video work.
2. Gate display and diagnostics by cadence; rerun CPU vectors, full tests, CRT
   build, and the native VICE boot gate.
3. Sweep batch sizes and choose the largest value that preserves keyboard,
   PIT/FDC, and BIOS prompt behavior.
4. Optimize cache-hit helpers and address calculation with differential tests.
5. Add dirty-row CGA rendering and measure sparse versus full-screen workloads.
6. Revisit decoder tables or threaded dispatch only after the above counters
   identify decoder cost as the dominant remaining component.
7. Prototype block interpretation separately, with explicit invalidation tests,
   before considering translation.

Each stage should be one focused commit. Keep `build/c64x86-hwtest.prg`, the CRT,
ROMs, disk images, and VICE logs out of commits. A performance change is green
only when architectural tests, the CRT build, the VICE warp gate, and the
performance counters all pass without a regression in boot behavior.
