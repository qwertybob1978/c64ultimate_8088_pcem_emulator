#!/usr/bin/env python3
"""Parse VICE trace output for OUT DX,AL and IN AL,DX operations."""
import re
from pathlib import Path


def parse_vice_trace(trace_path='build/vice-mon-trace.txt'):
    """Parse VICE monitor trace looking for OUT/IN instructions."""
    content = Path(trace_path).read_text()
    
    # Look for OUT DX,AL pattern
    out_pattern = r'\[.*?\] @([0-9A-Fa-f]+):([0-9A-Fa-f]+)\s+OUT\s+'
    in_pattern = r'\[.*?\] @([0-9A-Fa-f]+):([0-9A-Fa-f]+)\s+IN\s+'
    
    outs = []
    ins = []
    
    for match in re.finditer(out_pattern, content):
        cs_str = match.group(1)
        ip_str = match.group(2)
        
        try:
            phys_addr = int(cs_str, 16) * 16 + int(ip_str, 16)
            
            # Get context around this instruction
            start_idx = max(0, match.start() - 200)
            end_idx = min(len(content), match.end() + 200)
            ctx = content[start_idx:end_idx].replace('\n', ' ')[:500]
            
            if 0x03D0 <= phys_addr <= 0x03DF or \
               (int(cs_str, 16) == 0xF000 and 0xF700 <= int(ip_str, 16) <= 0xF9A0):
                print(f"VGA/LOOP REGION ACCESS at @{phys_addr:#07X}: {ctx}")
                
        except ValueError:
            pass
    
    print("\n=== Summary ===")
    print("Looking for VGA sequencer port access patterns...")
    

if __name__ == '__main__':
    parse_vice_trace()
