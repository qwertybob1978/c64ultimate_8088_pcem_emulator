"""Final analysis of F44D stall - classify root cause precisely."""
from pathlib import Path

rom_path = Path("third_party/pcem-roms/genxt/pcxt.rom")
rom = bytearray(rom_path.read_bytes())

print("=" * 80)
print("F44D STALL ROOT CAUSE CLASSIFICATION")  
print("=" * 80)

# Read current FDC implementation
fdc_path = Path("src/devices/fdc.s")
if fdc_path.exists():
    fdc_src = fdc_path.read_text()
else:
    fdc_src = ""

# Read current IO dispatcher
io_path = Path("src/bus/io.s")
if io_path.exists():
    io_src = io_path.read_text()
else:
    io_src = ""

print("""
=== DISASSEMBLED PATTERN AT PHYSICAL FF44D ===

From our decoded output, the stall loop structure is:

  [FF43B] JNE rel8          ; branch if NOT equal (retry condition)
  [FF43D] CLI               ; disable interrupts
  [FF43E] EC                ; IN AL,dx — READ hardware port
  [FF43F] A8 $01            ; TEST AL,$01 — check BIT 0
  
  OR at FF450 area:
  
  [FF44D] JNE rel8          ; retry jump
  [FF44F] CLI               
  [FF450] EC                ; IN AL,dx
  [FF451] A8 $01            ; TEST AL,$01
  [FF453] JE rel8           ; conditional exit

KEY OBSERVATION: The BIOS tests for BIT 0 == SET to EXIT the loop.
This means it expects a SPECIFIC bit in whatever register DX points to.

""")

print("=" * 80)
print("CURRENT EMULATOR STATE MACHINE ANALYSIS")
print("=" * 80)

# Check FDC main status logic
if "fdc_read_main_status" in fdc_src:
    print("\nCurrent FDC Main Status ($F4) returns:")
    print("  • When idle (result_count==0 && expected==0): #$80")
    print("  • During command execution: #$90 or #$D0")
    print("")
    print("#$80 = Bit 7 set (data ready=NO), Bit 6 clear (direction)")
    print("#$90 = Bits 7+4 set")
    print("#$D0 = Bits 7+6+5 set")
    print("")
    print("BIT 0 IS NEVER SET by any of these values!")
    
print("\n" + "=" * 80)
print("CLASSIFICATION")
print("=" * 80)

print("""
BLOCKER TYPE: INCORRECT HARDWARE STATE / MISSING DEVICE RESPONSE

SPECIFIC ISSUE:
The GenXT BIOS polls an I/O port expecting BIT 0 to become SET.
Our emulator never sets bit 0 on ANY polled register because:

1. If reading FDC Main Status ($F4): Returns #$80/$90/$D0 — 
   none have bit 0 set. BIOS wants some other signal.

2. If reading PIC ($20/$21): Our pic_read_command/pic_read_data 
   may not properly simulate IRQ masking/unmasking after STI.

3. If reading DMA page registers ($81): Returns fixed #$81,
   which has bit 0 CLEAR.

4. If reading PIT channels ($40-$43): Timer counters count down
   but may not trigger proper status bits without real timer hardware.

ROOT CAUSE HYPOTHESIS (ranked by likelihood):

PRIORITY 1 - FDC Digital Input Port ($F7):
  Current implementation returns #$00 always.
  This is used to check drive motor state, door switch, etc.
  If BIOS checks this and expects certain bits set → stall.

PRIORITY 2 - Missing DOR Write Handling:  
  Port $F2 writes control drive motors/enable interrupts.
  Our code does reset FDC and request IRQ6 when bit 2 changes,
  but doesn't properly transition the FDC through its states.

PRIORITY 3 - DMA Channel 2 Status:
  Page register reads return #$81. If BIOS waits for DMA
  acknowledgment that never comes → infinite loop.

NEXT STEPS TO IDENTIFY EXACT PORT:
""")

# Check what ports are actually dispatched in io.s
fdc_ports_in_io = []
for line in io_src.split('\n'):
    if 'cmp #$' in line.lower() or 'cpx #$' in line.lower():
        stripped = line.strip().lower()
        if any(p in stripped for p in ['$f2', '$f4', '$f5', '$f7']):
            fdc_ports_in_io.append(line.strip())

if fdc_ports_in_io:
    print(f"\nFDC-related dispatchers found in io.s ({len(fdc_ports_in_io)}):")
    for p in fdc_ports_in_io[:10]:
        print(f"  {p}")

print("""
RECOMMENDED FIX STRATEGY:

Option A: Add instrumentation to native core
  Modify src/cpu8088/step.s to log DX values before IN instructions.
  Run VICE with warp mode disabled to capture exact port accesses.

Option B: Try returning different values from each FDC port:
  • fdc_read_digital_input: Return #$FF instead of #$00
    (simulates all drives connected, no errors)
    
  • fdc_write_dor: After writing, immediately set FDC to 
    "command ready" state so MSR transitions correctly
    
  • Ensure MSR returns #$C0 after data write (not just #$90/$D0)

Option C: Trace against PCem reference behavior
  Use Unicorn oracle to run same boot sequence on x86 emulator
  and compare exact I/O port access patterns at FF44D equivalent.

VERIFICATION METHOD:
After implementing fix, rebuild cartridge and verify:
1. POST progresses past REPLACE AND STRIKE ANY KEY prompt
2. No more alternating floppy counter values in trace output
3. Boot sector loads successfully
""")

print("=" * 80)
print("CLASSIFIED AS: PHASE 3 — HARDWARE STATE MACHINE FIX")  
print("SEVERITY: BLOCKER (prevents all boot progression)")
print("=" * 80)
