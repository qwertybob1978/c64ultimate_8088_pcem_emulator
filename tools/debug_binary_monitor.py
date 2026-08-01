#!/usr/bin/env python3
"""Debug VICE binary monitor responses."""
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
VICE = WORKSPACE / ".cache" / "vice-3.10" / "GTK3VICE-3.10-win64" / "bin" / "x64sc.exe"
CRT = WORKSPACE / "build" / "c64x86.crt"

proc = subprocess.Popen(
    [
        str(VICE),
        "-default",
        "+confirmonexit",
        "+sound",
        "-warp",
        "-reu",
        "-reusize",
        "16384",
        "-cartcrt",
        str(CRT),
        "-limitcycles",
        "2000000000",
        "-binarymonitor",
        "-binarymonitoraddress",
        "127.0.0.1:6502",
        "-logfile",
        str(WORKSPACE / "build" / "vice-smoke.log"),
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

time.sleep(2)
sock = socket.create_connection(("127.0.0.1", 6502), timeout=2)
print("connected")

# read any pending data (none expected)
sock.settimeout(2)
try:
    data = sock.recv(1024)
    print("pre-ping data:", data.hex())
except TimeoutError:
    print("no pre-ping data")

# send ping: STX, ver2, len 0, reqid 1, cmd 0x81
ping = b"\x02\x02" + struct.pack("<I", 0) + struct.pack("<I", 1) + b"\x81"
sock.sendall(ping)
print("sent ping", ping.hex())

# read for 5 seconds
sock.settimeout(5)
try:
    data = sock.recv(4096)
    print("post-ping data:", data.hex())
except TimeoutError:
    print("no post-ping data")

sock.close()
proc.kill()
proc.wait()
