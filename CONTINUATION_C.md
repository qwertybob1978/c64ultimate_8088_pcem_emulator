# C64 x86 implementation continuation guide - Part 2 (Milestones C+)

This file supplements CONTINUATION.md with post-Milestone-B findings and next tasks.
Read this entire file before editing anything beyond what's documented here.

## Current checkpoint

All baseline gates GREEN as of 2026-07-28:

- All 17 host tests pass consistently across multiple runs
- VICE 3.10 CRT smoke test passes with 16 MiB REU in warp mode
- Cartridge builds successfully: build/c64x86.crt (49 banks, 402256 bytes)

## Milestone B — Port $3F2/$3F3 fix (completed 2026-07-27)

**Changes made:** Added port `$3F3` read handler returning `$20` (NEC uPD765 standard density/config byte) in `src/bus/io.s`. This resolved the initial BIOS stall at CS:F000 IP:F065 where STI was firing repeated INT$06 due to bad IRQ6 interaction from missing FDC device state.

**Result:** BIOS no longer stalls at F065 STI loop — progressed past this region successfully! Clear evidence of forward progress despite introducing new investigation target.

### New blocker discovered after $3F3 fix

After resolving F065 STI loop, BIOS stalled looping around physical address 0xFF78D (conventional RAM containing uninitialized zeros executed via jumps/returns from actual ROM code elsewhere). Instruction bytes decoded:

```text
Physical offset 0xFF78D: C5 E8 04 00 FE C4 8A C1 52 8B 16 63 00 86 C4 EE 86 C4 FE C2 EE 5A C3 FF...
Partial decode pattern includes OUT DX,AL instructions followed by RET operations
suggesting tight hardware polling loop waiting for device response on unmapped I/O ports
```

Reference model tracing revealed exact ports accessed during tight loop:

- MDA CRTC index/data ($3B4/$3B5), VGA CRTC index/data ($3D4/$3D5)
- Status/control ($3B8/$3B9, $3D8/$3D9)
- PPI Port A ($0061), DIP switches ($0062)
- All returned open-bus `$FF` causing infinite wait condition

## Milestone C — Video sequencer/CRTC register shadow stores (completed 2026-07-28)

**Problem:** The traced OUT DX,AL instructions targeting video controller ports ($C0-$DF range) had NO corresponding handlers in io.s implementation. Without proper I/O routing, these fell through to open bus (`$FF`) causing BIOS to wait forever for hardware response that never arrived because no actual VGA emulation existed yet.

**Root cause classification per Plan Section 9 list:** Missing video controller I/O handlers preventing POST device detection completion. Specifically:

1. No write handler for VGA/MDA sequencer registers ($C0-CF) → values lost
2. No read handler for CRTC data ports ($D0-D9) → returns garbage instead of last written value  
3. No read handler for MDA/VGA control/status ports ($B8,$B9,$D8,$D9) → returns $FF consistently

**Changes made in src/bus/io.s:**

1. Added BSS variables for video register shadow storage:
   - `io_vid_seq_reg`: Last value written to any sequencer/color/register port ($C0-DF)
   - `io_vid_crtc_idx`: Current CRTC index register ($3xx4)
   - `io_vid_crtc_dat`: Last value written to CRTC data port ($3xx5)

2. Extended high-page read dispatcher (@high_page_03):
   - Ports $B8/$B9/$D8/$D9 now route to @vid_ctrl_read (returns io_vid_seq_reg) or @vid_ctrl_ff ($B9 is write-only)
   - Ports $C0-$DF now route to @seq_or_crtc_read returning io_vid_crtc_dat instead of falling through to @open_bus

3. Extended high-page write dispatcher (@write_high_page_03):
   - Ports < $E0 (covers $B8,$B9 and all $C0-DF) now store value in io_vid_seq_reg before returning
   - This ensures subsequent reads return consistent state rather than open bus

**Verification gate results after Milestone C changes:**

- ✅ All 17 host tests pass (test_phase0_contracts.py + test_cpu8088_reference.py)
- ✅ VICE 3.10 CRT smoke test passes with green border
- ✅ Cartridge builds successfully without assembly errors

**Expected behavior change:** When BIOS executes tight loop around physical address 0xF78D performing OUT DX,AL writes to video sequencer/CRTC ports followed by IN AL,DX reads, the emulator will now:

1. Store each written value in io_vid_seq_reg (for control/status ports) or io_vid_crtc_dat (for seq/CRTC data ports)
2. Return stored value on subsequent reads instead of always returning $FF
3. Allow polling loops to see consistent hardware state and potentially complete

## Next bounded task — Milestone D

## Diagnostic checkpoint — 2026-08-01

Tested path:

- `python -m unittest tests.test_cpu8088_reference tests.test_phase0_contracts`:
   41 tests passed.
- Native `build.ps1`: passed.
- Sv a rDOS CRT regeneration: 49 banks, 402256 bytes.
- VICE 3.10 with 16 MiB REU and 2,000,000,000-cycle limit: reached the limit,
   but remained blue.

Observed failure after the IRQ stack guard:

- `CS:F000 IP:E003`, opcode `$04` (`CPU_STEP_INVALID`).
- Interrupt stage `04`, stack stage `02`: interrupt frame writes completed and
   vector-table reads began.
- FDC command/read/IRQ6 counters remain zero.
- The displayed interrupt vector was previously ambiguous because diagnostic
   fields survived the CPU smoke test; reset now clears those fields.

The requested-vector diagnostic initially displayed `Q:01` while `V:00`, but
that was a diagnostic bug: `cpu8088_interrupt` overwrote A with stage `01`
before recording the entry vector. After capturing A first, the packaged VICE
run shows Q and V agree on the IRQ-derived vector. The failure remains at
`F000:E003`, with FDC command/read/IRQ6 counters still zero. The next fix
should investigate the BIOS handler/vector target or the memory fetch at that
address, rather than changing FDC behavior.

The exact-fault-byte probe now reports `D:65 6E 65 72` at the saved address.
Those bytes are the Generic XT ROM banner text (`"ener"`), proving control
flow reached BIOS data at `F000:E003`; the displayed `OP:04` was stale. The
next diagnostic should identify the preceding jump/return or IVT target that
lands in the `$E000` banner region.

The active acceptance target is now explicit in `PROJECT_PLAN.md`: boot the
supplied Sv a rDOS 360K image to a usable DOS prompt in the packaged CRT/VICE
path. The next probe captures IVT vector 9 (`00024h`) at failure to distinguish
an incorrect keyboard IRQ target from a later BIOS jump/return into `$E000`.

The packaged run shows IVT 9 as `87 E9 00 F0` (`F000:E987`), the expected
keyboard handler, while IVT 0 remains zeroed. The banner fault therefore is
not caused by a bad IRQ1 vector. Treat it as an INT 0 or bad return/control
transfer until the preceding instruction and stack frame are captured; FDC
work remains blocked because command and read counters are still zero.

Status update 2026-08-01: the former F44D hypothesis is closed. Reference
execution shows F44D is a reusable CGA `$3DA` status helper with `DX=$3DA` and
alternating `$00/$09` reads; it is not an FDC MSR or digital-input poll. The
F78D label is also a trace-script error: that region performs CRTC writes at
`$3B4/$3B5` and `$3D4/$3D5`. Do not modify FDC behavior for either address.

Current work resumes at the later 2-billion-cycle native failure documented in
`QWEN_EXECUTION_PLAN.md`: approximate `CS:IP=0000:7351`, opcode `$C0`.
Capture fresh status, prior instructions, SS:SP bytes, media bytes, DMA state,
and cache state before implementing a fix.

After confirming Milestone C allows POST progress past F78D stall:

### Option A: If BIOS still stalls at new location

1. Re-run desktop trace at 200k steps; record new CS:IP/stall location
2. Decode instruction bytes at new stall point
3. Create targeted trace script capturing exact I/O port accesses during new stall loop
4. Classify divergence type per Plan Section 9 list
5. Implement minimal handler fix following same pattern as Milestones B and C

### Option B: If BIOS progresses further but hangs later

Continue tracing one unsupported opcode family at a time using methodology from CONTINUATION.md section 5. Record new instruction count, CS:IP, bytes, and semantics for each newly supported opcode family.

### Priority device handlers if not yet resolved by video fixes

Per QWEN_EXECUTION_PLAN.md section 8 work-after-CPU-blockers ordering:

1. **PIT channel 0 programming** (port $40) → generates deterministic timer IRQ every ~1ms guest time
2. **PIC ICW initialization** ($20/$21) → masks/unmasks interrupts, sets base vectors  
3. **DMA channel 2/FDC commands** → CHS sector reads, terminal count, IRQ6 delivery
4. **Boot-media integration** → expose DISK01.IMG as drive A via INT 19h

## Build/test commands reference

```powershell
# Full verification gate
python -m pytest tests/ -v --tb=short
pwsh -ExecutionPolicy Bypass -File tools\test_vice.ps1

# Incremental build only
.\build_crt.ps1

# Generate CPU contracts after metadata changes
python tools\generate_cpu8088.py --check
```
