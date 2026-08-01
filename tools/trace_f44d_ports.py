"""Trace exact DX port values during F44D stall region."""
import sys
from pathlib import Path

# Read VICE out.txt to extract step-by-step execution
out_path = Path("build/vice-out.txt")
if not out_path.exists():
    print(f"ERROR: {out_path} not found", file=sys.stderr)
    sys.exit(1)

lines = out_path.read_text(encoding="utf-8", errors="replace").splitlines()

print("=" * 80)
print("TRACING I/O PORTS AROUND STALL AT CS:F000 IP:F44D")
print("=" * 80)

# Parse steps showing CS:IP progression
stall_region_steps = []
prev_cs_ip = None
step_count = 0

for i, line in enumerate(lines):
    # Look for lines like "CS=F000 IP=F4XX" or similar patterns
    stripped = line.strip().lower()
    
    # Match memory addresses around FF4xx range (physical)
    if "ff4" in stripped and ("opcode" in stripped or "op=" in stripped):
        try:
            parts = stripped.split()
            cs_val = ip_val = opcode_str = ""
            
            for p in parts:
                if p.startswith("cs="):
                    cs_val = p[3:]
                elif p.startswith("ip="):
                    ip_val = p[3:]
                elif p.startswith("op="):
                    opcode_str = p[3:].upper()
            
            phys_addr = int(cs_val, 16) << 4 + int(ip_val, 16) if cs_val and ip_val else 0
            
            if 0xFF400 <= phys_addr < 0xFF500:
                step_count += 1
                entry = {
                    'line': i,
                    'raw': line.strip(),
                    'cs': cs_val.upper(),
                    'ip': ip_val.upper(),
                    'phys': f"{phys_addr:X}",
                    'opcode': opcode_str,
                }
                
                # Capture IN_AL_DX (OP=EC) and OUT instructions
                if opcode_str == "EC":  # IN AL,DX - read from DX port
                    entry['type'] = 'IN'
                elif opcode_str.startswith("E6"):  # OUT DX,AL
                    entry['type'] = 'OUT_E6'
                elif opcode_str.startswith("EE"):  # OUT DX,AL variant
                    entry['type'] = 'OUT_EE'
                elif opcode_str in ('75', '74'):  # JNE/JE conditional jumps
                    entry['type'] = 'COND_JUMP'
                elif opcode_str == 'FA':  # CLI
                    entry['type'] = 'CLI'
                else:
                    entry['type'] = 'OTHER'
                    
                stall_region_steps.append(entry)
        except (ValueError, IndexError):
            continue

print(f"\nTotal steps in physical address range FF400-FF4FF: {len(stall_region_steps)}")

if not stall_region_steps:
    print("\nNo steps found in target region. Checking broader F000:Fxxx range...")
    # Broader search
    broad_steps = []
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if "f000:f4" in stripped or ("ff4" in stripped and "op=" in stripped):
            broad_steps.append((i, line.strip()))
    
    print(f"Broad matches around F000:F4xx: {len(broad_steps)}")
    for idx, l in broad_steps[:50]:
        print(f"  Line {idx}: {l}")
else:
    print("\n--- Detailed trace of I/O operations near stall ---\n")
    
    # Group by instruction type
    io_reads = [s for s in stall_region_steps if s['type'] == 'IN']
    io_writes = [s for s in stall_region_steps if 'OUT' in s.get('type', '')]
    cond_jumps = [s for s in stall_region_steps if s['type'] == 'COND_JUMP']
    
    print(f"IN_AL_DX reads:   {len(io_reads)}")
    print(f"OUT writes:       {len(io_writes)}")
    print(f"Conditional jumps:{len(cond_jumps)}")
    
    print("\n=== Last 30 instructions before/during stall ===\n")
    display_steps = stall_region_steps[-30:] if len(stall_region_steps) > 30 else stall_region_steps
    
    for step in display_steps:
        marker = ""
        if step['phys'].endswith('44D') or step['ip'] == 'F44D':
            marker = " <-- STALL POINT"
        
        indent = f"{step['cs']}:{step['ip']}"
        op_info = f"[{step['opcode']:>6}]"
        
        if step['type'] == 'IN':
            action = "IN AL,dx"
        elif step['type'] == 'OUT_E6':
            action = "OUT dx,AL"  
        elif step['type'] == 'OUT_EE':
            action = "OUT dx,AX"
        elif step['type'] == 'COND_JUMP':
            jump_type = "JNE" if step['opcode'] == '75' else "JEZ/JE"
            action = f"{jump_type}"
        elif step['type'] == 'CLI':
            action = "CLI"
        else:
            action = step['opcode']
            
        print(f"  {indent} {action:>12}  (line ~{step['line']}){marker}")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
