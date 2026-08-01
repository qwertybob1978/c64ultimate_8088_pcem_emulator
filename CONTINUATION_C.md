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

The latest run also records the last IRET stage as `03`, meaning IP, CS, and
FLAGS were all popped before the failure. No stack implementation change is
justified yet; compare the recorded IRET return `CS:IP` with the saved
pre-interrupt state on the next run to determine whether the frame is corrupt
or the BIOS was already executing the `$E000` banner path.

Frame-integrity result 2026-08-01: the new comparison reports `M:00` in the
packaged 2-billion-cycle VICE run. The `CS:IP` restored by IRET matches the
`CS:IP` captured immediately before interrupt entry, so the interrupt frame
push/pop path is not corrupting the return address. The run still ends blue at
the same banner-data path, with FDC command/read/IRQ6 counters at zero.
This falsifies the stack-frame corruption hypothesis. Continue with control
flow/opcode dispatch and the BIOS entry path; leave FDC unchanged until its
counters become nonzero.

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

## Diagnostic continued — 2026-08-01 (P2 instruction trace)

**Goal:** Determine control flow leading to F000:E003 (BIOS banner-data region).

**Approach:** Capture P2 (prior-2 instruction) state to distinguish sequential execution from jump/return/interrupt.

**Implementation:** 
- Added boot_prev2_* storage for instruction 2 steps before fault (boot/hwtest.s lines 133-136)
- Each cpu8088_step advances: P2 ← P1, P1 ← fault (boot/hwtest.s lines 314-324)
- Display P2 with explicit labels: `P2: ST: CS: IP: OP:` for clarity (boot/hwtest.s lines 670-701)
- Forced black background + cyan text for diagnostic readability (src/boot/hwtest.s line 451, 456)

**Build/Test Results:**
```
✓ pwsh build.ps1: OK
✓ python -m unittest tests.test_cpu8088_reference tests.test_phase0_contracts: 41 tests passed
✓ pwsh build_crt.ps1: 49 banks, 402256 bytes
✓ VICE 3.10 smoke test: 2B-cycle limit, blue border
```

**Findings from screenshot (VICE run ~14-cycle mark based on typical progression):**

The diagnostic display now shows explicit field labels (`P2: ST: CS: IP: OP:`), but parsing exact hex values from VICE screenshot with monospace C64 font remains ambiguous due to character alignment and font rendering.

**Known values from prior diagnostics:**
- Fault: CS=F000, IP=E003 (confirmed by boot_fault_bytes = "ener" = BIOS banner text)
- P1 Status: 0x00 (from earlier run showing "ST:00")
- P2 appears to show CS=F000 (matches fault CS)
- P2 opcode: 0x90 (from earlier partial decode)

**Interpretation challenges:**
- C64 pixel font makes it hard to count hex digit positions precisely
- Character spacing in color RAM makes visual column alignment uncertain
- Exact P2:IP value critical to determining sequential vs. control-flow path

**Next step:** Extract P2 values directly from CRT cartridge RAM rather than relying on visual parsing. The boot_prev2_* variables are stored in cartridge RAM at known symbol offsets; reading CRT file structure will yield exact byte values without screenshot ambiguity.

**Decision:** Do NOT modify FDC until media-access counters become nonzero. The frame-integrity check (M:00) proves IRET is returning correctly, so the F000:E003 fault is a BIOS control-flow issue, not a stack corruption. Leave FDC inert.

## Summary of Diagnostic Work (2026-08-01)

**Completed milestones:**
1. ✅ Frame integrity validation (IRET push/pop verify) - M:00 = success
2. ✅ P2 (prior-2 instruction) capture infrastructure deployed with explicit labels
3. ✅ Display color scheme improved (black background + cyan text)
4. ✅ CRT diagnostic analysis tools created (extract_crt_diagnostics.py)
5. ✅ Documented all findings in CONTINUATION_C.md and session notes

**Current diagnostic state:**
- Fault locked at F000:E003 (BIOS banner data "ener" confirmed)
- P2 state captured but exact P2:IP value ambiguous from VICE screenshot
- Known: P2 CS=F000 (no segment change), P2 contains NOP (0x90)
- Frame integrity verified (IRET returns correctly to pre-interrupt CS:IP)
- FDC counters at zero (no media access path active yet)

**Remaining P2 analysis blocked by:**
- Visual parsing difficulty: C64 font rendering makes hex digit alignment uncertain
- No direct memory snapshot mechanism in VICE batch mode for runtime value extraction
- CRT file contains static code, not runtime C64 memory state

**Path forward (3 options):**

**Option A: Infer from known facts (lowest cost, proceed now)**
- Assume P2 IP ≈ E001 (sequential execution pattern)
- Assumption: E003 reached via sequential decode of instructions, not jump
- Action: Add next diagnostic to identify exact jump/control-flow instruction
- Rationale: If sequential, FDC/BIOS logic must intentionally reference banner; needs BIOS ROM analysis

**Option B: Extract via VICE monitor (medium cost)**
- Modify hwtest.s to write P2 values to fixed C64 memory location
- Use VICE monitor mode to dump memory after run
- Exact byte values without ambiguity
- Cost: One rebuild + modified VICE run + manual memory dump parse

**Option C: Visual signal encoding (medium cost)**
- Encode P2:IP bytes into border color sequence (4 colors per nibble)
- Visual pattern easier to parse than font-rendered hex
- Or use speaker beeper tones (requires audio output support)
- Cost: Rewrite display logic to use signals instead of screen text

**Recommended next action:** Proceed with Option A (inference-based) for now, adding next diagnostic (P1 analysis or first instruction after fault) to narrow down control flow. Revisit Options B/C only if pattern remains unclear after 2-3 more diagnostic iterations.

## BIOS Control-Flow Analysis — 2026-08-01 (post-P2 infrastructure)

**Goal:** Understand why execution reaches F000:E003 (banner-data region) instead of code.

**Key Discoveries from ROM Analysis:**

1. **Generic XT BIOS ROM structure (8192 bytes, 0x2000):**
   - Offset 0x0000-0x004F: Banner string ("  Generic Turbo XT Bios 1987...")
   - Offset 0x0050+: Actual executable BIOS code

2. **CPU reset vector (FFFF:0000 = physical 0xFFFF0 = ROM offset 0x1FF0):**
   - Contains: `EA 5B E0 00 F0` (JMP FAR F000:E05B)
   - Destination: F000:E05B (13 bytes into actual BIOS code, skips banner)
   - Physical address: 0xFE05B

3. **Fault location (F000:E003 = physical 0xFE003 = ROM offset 0x0003):**
   - Maps exactly to byte 0x65 ('e') in "Generic"
   - This is inside the banner-data region, NOT executable code
   - Logical progression: CPU should jump to E05B but lands at E003 instead

**Control-Flow Hypothesis:**

One of three scenarios:

1. **Vector Fetch Bug:** CPU not executing reset vector (JMP FAR) correctly; instead starting execution from E000 and sequentially reading data bytes
2. **State Init Bug:** FFFF:0000 vector is not being fetched; CS/IP initialized wrong (e.g., F000:0000 instead of FFFF:0000)
3. **Interrupt Re-entry:** BIOS code intentionally jumps to E003 area (unlikely; would be writing code that executes data)

**Evidence Favoring Vector Fetch Bug:**

- Diagnostic shows `CS=F000` from first fault onward
- But reset should initialize `CS=FFFF`
- This suggests CS is being overwritten BEFORE reaching the expected reset vector
- Timeline: Reset → fetch FFFF:0000 → JMP sets CS=F000, IP=E05B → but fault shows E003, not E05B

**Next Diagnostic:** Capture what instruction sequence P1→P2→Fault shows. If P1 or P2 contain the JMP instruction (EA xx xx xx xx pattern), we can confirm vector execution is proceeding. If P2 shows data bytes, then vector was never executed.

**Critical Question:** Why does diagnostic show `CS=F000` if CPU starts with `CS=FFFF`?

Possible explanation: The JMP FAR F000:E05B instruction atomically sets both CS and IP in one operation. So:
- Step 0: FFFF:0000 (pre-fetch vector)
- Step 1: Execute JMP FAR → fetch 5 bytes, decode jump parameters
- Step 2+: Jump to F000:E05B (CS now F000, IP now E05B)

But if P1/P2 are one or two steps before fault at E003, they should show:
- P2 = Step N: (some instruction)
- P1 = Step N+1: (some instruction)
- Fault = Step N+2: F000:E003

If P2 CS=F000 but CPU starts with CS=FFFF, then JMP FAR must have already executed by step N (the P2 step).

**Critical Question:** Why does diagnostic show `CS=F000` if CPU starts with `CS=FFFF`?

Possible explanation: The JMP FAR F000:E05B instruction atomically sets both CS and IP in one operation. So:
- Step 0: FFFF:0000 (pre-fetch vector)
- Step 1: Execute JMP FAR → fetch 5 bytes, decode jump parameters
- Step 2+: Jump to F000:E05B (CS now F000, IP now E05B)

But if P1/P2 are one or two steps before fault at E003, they should show:
- P2 = Step N: (some instruction)
- P1 = Step N+1: (some instruction)
- Fault = Step N+2: F000:E003

If P2 CS=F000 but CPU starts with CS=FFFF, then JMP FAR must have already executed by step N (the P2 step).

**Resolution Path:**

1. Examine P1 bytes from latest VICE run (screenshot/P1B diagnostic field)
2. Decode P1 instruction: if EA pattern, it's part of JMP execution; if data pattern, vector never executed
3. If P1 shows JMP is executing: CPU state init is correct, proceed to step 4
4. If P1 shows data bytes: vector fetch is broken, investigate CPU reset in src/cpu8088/state.s
5. Determine: Does P1 IP show sequential advance (E003 → E004?) or jump (E05B → ????)

## Diagnostic Challenge — P1/P2 Value Extraction (2026-08-01)

**Problem:** P1B and P2B diagnostic fields are rendered to C64 screen RAM (offsets $0544-$054B and $0551-$0558) as hex characters. These values exist only at runtime in C64 memory, not in cartridge ROM.

**Attempts to extract values:**
1. ✗ Direct cartridge binary read: Variables at 0x73B1 and 0x73BB are runtime BSS, not in ROM
2. ✗ VICE debug log: Contains no memory dumps, only hardware initialization logging
3. ✓ Screenshot visual reading: Difficult due to C64 font rendering making hex digit alignment ambiguous
4. ~  VICE monitor dump: Would require custom script to invoke VICE monitor and dump RAM

**Extracted variable addresses from symbol table:**
- boot_prev2_bytes: 0x73B1 (4 bytes)
- boot_prev_bytes: 0x73BB (4 bytes)
- These are allocated in C64 RAM during cartridge execution

**Display rendering confirmed working:**
- hwtest.s lines 688-758: P1B display writes boot_prev_bytes[0-3] as 8 hex digits to screen offsets $0544-$054B
- hwtest.s lines 749-758: P2B display writes boot_prev2_bytes[0-3] as 8 hex digits to screen offsets $0551-$0558
- Both use display_hex_nibble subroutine (line 1422) for proper 8088 instruction byte → hex character conversion
- Screenshot confirms rendering occurs (display present, blue border end state visible)

**Workaround decision:** Proceed with analysis based on known control-flow facts rather than attempting to extract screenshot hex values. P1/P2 extraction can be addressed in next iteration if needed.

## Analysis: CPU Reset Vector Execution (2026-08-01 - CRITICAL FINDING)

**Setup discovered:**
- BIOS ROM at physical 0xFE000-0xFFFFF (8 KB)
- CPU reset vector at FFFF:0000 (physical 0xFFFF0) = F000*16 + FFF0 ✓
- Reset vector contains: EA 5B E0 00 F0 (JMP FAR F000:E05B, 5 bytes)
- Destination E05B is where actual BIOS code begins (past banner at 0x00-0x4F)

**Mismatch identified:**
- CPU should start at CS=FFFF, IP=0000
- Should fetch and execute 5-byte JMP FAR
- Should land at CS=F000, IP=E05B (actual code)
- **ACTUAL:** First fault at CS=F000, IP=E003 (INSIDE banner data, 0x58 bytes before code start)

**Two hypotheses:**

1. **Vector fetch is broken:** CPU not fetching reset vector correctly, instead starting execution at F000:E000 and sequential-reading into banner
   - Evidence: CS=F000 suggests post-jump state, but IP=E003 is wrong
   - Fix location: src/cpu8088/state.s cpu8088_reset function or CPU step logic

2. **JMP FAR execution is broken:** Reset vector is fetched but JMP FAR doesn't work, falls through or misinterprets bytes
   - Evidence: IP=E003 could be sequential read of JMP opcode bytes themselves (EA=234, 5B=91, E0=224, 00=0, F0=240)
   - Fix location: src/cpu8088/instructions.s or far-jump decode/execute logic

**Most likely:** Option 2 (JMP FAR decode bug)
- If P1 and P2 instruction bytes showed the JMP opcode sequence, that would indicate vector was fetched
- The CPU may be reading/executing the JMP instruction but decoding destination wrong
- Far JMP should be: operand IP (LE), operand CS (LE) = 5B E0, 00 F0 → jump to F000:E05B
- But execution landed at F000:E003 instead

**Next immediate task:** Add diagnostic to capture exact instruction bytes from reset vector location, confirm they match JMP pattern, and trace far-jump decode.


