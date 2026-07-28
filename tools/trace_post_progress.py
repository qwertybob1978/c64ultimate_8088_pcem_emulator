"""Trace native execution progress post-Milestone-C fixes.
Rebuilds cartridge, launches VICE with extended cycle limit, parses vice-out.txt/vice-mon-trace.txt for CS:IP progression patterns indicating successful POST vs stalls."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VICE_LOG = REPO_ROOT / "build" / "vice-smoke.log"
TRACE_FILE = REPO_ROOT / "build" / "vice-mon-trace.txt"


def rebuild_cartridge():
    """Build CRT using build_crt.ps1."""
    print("=== Rebuilding cartridge ===")
    result = subprocess.run(
        ["pwsh", "-ExecutionPolicy", "Bypass", "-File", str(REPO_ROOT / "build_crt.ps1")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"BUILD FAILED:\n{result.stderr}")
        return False
    # Check expected messages
    if "Valid Magic Desk CRT:" not in result.stdout:
        print(f"Unexpected build output:\n{result.stdout[-500:]}\n{result.stderr[-500:]}")
        return False
    print("Cartridge built successfully.")
    return True


def parse_vice_log(log_path):
    """Parse VICE log for key events: reset, BIOS entry points, CGA writes, errors."""
    if not log_path.exists():
        print(f"No VICE log found at {log_path}")
        return None
    
    lines = log_path.read_text().splitlines()
    
    findings = {
        "reset_seen": False,
        "bios_banner_lines": [],
        "cgawrites": [],
        "errors": [],
        "max_cycles_reached": False,
        "total_lines": len(lines),
    }
    
    for line in lines:
        if "RESET." in line and "Main CPU" in line:
            findings["reset_seen"] = True
        if "SYSTEM ERROR" in line or "Generic Turbo XT Bios" in line:
            findings["bios_banner_lines"].append(line.strip())
        if "C64WRITE" in line or "CGA" in line.upper():
            findings["cgawrites"].append(line.strip())
        if "Error -" in line and "DriveROM" not in line:
            findings["errors"].append(line.strip())
        if "cycle limit reached" in line.lower():
            findings["max_cycles_reached"] = True
            
    return findings


def analyze_progress(findings):
    """Determine POST progress level based on parsed log data."""
    if not findings:
        return "UNKNOWN: No trace data available"
        
    indicators = []
    
    if findings["reset_seen"]:
        indicators.append("CPU RESET detected ✓")
    
    if findings["bios_banner_lines"]:
        banner_count = len(set(l for l in findings["bios_banner_lines"]))
        indicators.append(f"BIOS banner seen ({banner_count} unique lines) ✓")
        if any("SYSTEM ERROR" in l for l in findings["bios_banner_lines"]):
            indicators.append("POST error message present (may indicate stall)")
            
    if findings["cgawrites"]:
        indicators.append(f"{len(findings['cgawrites'])} CGA-related write events ✓")
        
    if findings["max_cycles_reached"]:
        indicators.append("Reached cycle limit (ran full 8M cycles without hang?)")
        
    if findings["errors"]:
        non_drive_errors = [e for e in findings["errors"] if "DriveROM" not in e]
        if non_drive_errors:
            indicators.append(f"Non-drive errors found: {non_drive_errors[:3]}")
            
    return "\n".join(indicators)


if __name__ == "__main__":
    print("=" * 70)
    print("Post-Milestone-C Progress Trace")
    print("=" * 70)
    
    # Step 1: Rebuild cartridge with new video sequencer handlers
    if not rebuild_cartridge():
        sys.exit(1)
        
    # Step 2: Run VICE smoke test to generate logs
    print("\n=== Running VICE smoke test ===")
    result = subprocess.run(
        ["pwsh", "-ExecutionPolicy", "Bypass", "-File", str(REPO_ROOT / "tools" / "test_vice.ps1")],
        capture_output=True, text=True
    )
    
    vice_passed = "VICE 3.10 CRT smoke test passed" in result.stdout
    
    if not vice_passed:
        print(f"VICE TEST FAILED:\n{result.stdout[-500:]}\n{result.stderr[-500:]}")
        sys.exit(1)
        
    print("✓ VICE smoke test passed\n")
    
    # Step 3: Parse and analyze results
    print("=== Analyzing execution progress ===\n")
    findings = parse_vice_log(VICE_LOG)
    analysis = analyze_progress(findings)
    print(analysis)
    
    # Summary verdict
    print("\n" + "=" * 70)
    if findings.get("reset_seen"):
        if findings.get("bios_banner_lines"):
            print("VERDICT: POST progressed past initial reset → BIOS banner displayed")
            print("Next step: Check if BIOS completed device detection or stalled during polling.")
        else:
            print("VERDICT: CPU reset occurred but no visible BIOS output detected yet.")
            print("Next step: Increase trace depth or check for early stall conditions.")
    else:
        print("VERDICT: No clear evidence of successful boot sequence.")
        print("Next step: Investigate why RESET wasn't captured; may need extended tracing.")
    print("=" * 70)
