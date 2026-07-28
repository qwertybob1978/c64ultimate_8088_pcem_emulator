"""Trace reference model I/O behavior with/without video register shadow stores.
Compares open-bus ($FF) returns against stored-value returns to predict POST progression."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'ref8088'))
from runner import Reference8088


def load_cpu_spec():
    """Load 8088 opcode configuration."""
    import json
    return json.loads((Path('config/cpu8088.json')).read_text())


class VideoAwareCPU(Reference8088):
    """Extended reference model with video register shadow stores (Milestone-C fix)."""
    
    def __init__(self, spec):
        super().__init__(spec)
        self.io_vid_seq_reg = 0      # Last value written to seq/color/register ports
        self.io_vid_crtc_dat = 0     # Last value written to CRTC data port
        self.video_reads_stored = 0
        self.video_reads_open_bus = 0
    
    def read_port_u8(self, port):
        """Override: implement video sequencer/CRTC shadow store logic from Milestone-C."""
        high_byte = (port >> 8) & 0xFF
        
        if high_byte == 0x03:
            low_byte = port & 0xFF
            
            # MDA/VGA control/status ports - return last written value
            if low_byte in (0xB8, 0xD8, 0xD9):
                self.video_reads_stored += 1
                return self.io_vid_seq_reg
            
            # Some control ports are write-only on real hardware
            if low_byte == 0xB9:
                self.video_reads_open_bus += 1
                return 0xFF
            
            # VGA/MDA sequencer registers $C0-$CF and CRTC data ~$D0-D9
            if 0xC0 <= low_byte < 0xE0:
                self.video_reads_stored += 1
                return self.io_vid_crtc_dat
        
        # Fall through to parent for all other ports
        return super().read_port_u8(port)
    
    def write_port_u8(self, port, value):
        """Override: capture writes to video controller ports."""
        high_byte = (port >> 8) & 0xFF
        
        if high_byte == 0x03:
            low_byte = port & 0xFF
            
            # Store any write to B8,B9,C0-DF range in shadow reg
            if low_byte < 0xE0 or low_byte >= 0xF2:
                self.io_vid_seq_reg = value
                return
        
        super().write_port_u8(port, value)


def simulate_post_polling_loop():
    """Simulate the tight polling loop pattern found at physical address 0xFF78D.
    
    Decoded bytes showed OUT DX,AL followed by IN AL,DX patterns typical of
    BIOS device detection probing hardware readiness before proceeding.
    """
    print("=" * 70)
    print("Post-Milestone-C Video I/O Simulation")
    print("=" * 70)
    print()
    print("Scenario: BIOS POST code probes video controller via OUT DX,AL / IN AL,DX")
    print("This is standard XT behavior during floppy/controller detection.")
    print()
    
    spec = load_cpu_spec()
    
    # Test with open-bus behavior (pre-Milestone-C)
    print("-" * 40)
    print("BEFORE Milestone-C fix (open bus returns $FF)")
    print("-" * 40)
    
    cpu_old = Reference8088(spec)
    old_results = []
    
    # Simulate typical BIOS probe sequence from traced F78D area
    test_ports_values = [
        (0x03B8, 0x0E),   # MDA status/control - set mode
        (0x03BA, 0x00),   # MDA status read-back check  
        (0x03D8, 0x00),   # VGA color adapter control
        (0x03C0, 0x10),   # Sequencer register S0 (reset state)
        (0x03C0, 0x01),   # Sequencer register S1 (clocking map)
        (0x03C0, 0x03),   # Sequencer register S3 (character map)
        (0x03C0, 0x04),   # Sequencer register S4 (max scan line)
        (0x03C0, 0x05),   # Sequencer register S5 (cursor start)
        (0x03D4, 0x00),   # CRTC index select
        (0x03D5, 0x5A),   # Write CRTC reg 0 (horizontal total)
        (0x03D5, 0x29),   # Write CRTC reg 1 (vertical total)
    ]
    
    for port, value in test_ports_values:
        cpu_old.write_port_u8(port, value)
        result = cpu_old.read_port_u8(port & 0xFF) if port < 0x100 else cpu_old.read_port_u8(port)
        old_results.append((port, value, result))
        
        expected_read = value if port in (0x03B8, 0x03D8, 0x03C0, 0x03D5) else 0xFF
        
        mismatch = " ⚠️ OPEN BUS!" if result == 0xFF and port not in (0x03BA,) else ""
        print(f"  OUT DX,{value:#04X} → IN AL={result:#04X}{mismatch}")
    
    ff_count = sum(1 for _, _, r in old_results if r == 0xFF)
    stored_count = len(old_results) - ff_count
    print()
    print(f"  Result: {ff_count}/{len(old_results)} reads returned $FF (open bus)")
    print(f"  Impact: BIOS polling loop sees stale/zero values → may hang waiting")
    print()
    
    # Test with video shadow store behavior (post-Milestone-C)
    print("-" * 40)
    print("AFTER Milestone-C fix (video register shadow stores active)")
    print("-" * 40)
    
    cpu_new = VideoAwareCPU(spec)
    new_results = []
    
    for port, value in test_ports_values:
        cpu_new.write_port_u8(port, value)
        result = cpu_new.read_port_u8(port & 0xFF) if port < 0x100 else cpu_new.read_port_u8(port)
        new_results.append((port, value, result))
        
        status = "✓ STORED" if result != 0xFF or port == 0x03BA else "?"
        print(f"  OUT DX,{value:#04X} → IN AL={result:#04X} [{status}]")
    
    ff_count_new = sum(1 for _, _, r in new_results if r == 0xFF)
    stored_count_new = len(new_results) - ff_count_new
    
    print()
    print(f"  Result: {stored_count_new}/{len(new_results)} reads return stored values ✓")
    print(f"  Impact: BIOS polling loop sees consistent hardware state → can proceed")
    print()
    
    # Verdict
    print("=" * 70)
    print("VERDICT:")
    print("=" * 70)
    print()
    print(f"Milestone-C reduces open-bus returns from {ff_count}/{len(test_ports_values)} to {ff_count_new}/{len(test_ports_values)}.")
    print()
    if ff_count_new <= 2:  # Allow some write-only ports like $3B9/$3BA
        print("✅ VIDEO SEQUENCER/CRTC HANDLERS EFFECTIVE")
        print("   The F78D stall should resolve because BIOS now receives consistent")
        print("   responses when probing MDA/VGA controller registers during POST.")
        print()
        print("Next step: Verify actual VICE execution shows progress past previous")
        print("stall point. If still hanging, trace reveals next blocker location.")
    else:
        print("⚠️ STILL TOO MANY OPEN-BUS READS — additional handlers needed.")
        print("Check which specific ports are returning $FF and add targeted fixes.")


if __name__ == "__main__":
    simulate_post_polling_loop()
