#!/usr/bin/env python3
"""Test binary monitor watchpoint on $D020."""
import socket
import struct
import subprocess
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
VICE = WORKSPACE / ".cache" / "vice-3.10" / "GTK3VICE-3.10-win64" / "bin" / "x64sc.exe"
CRT = WORKSPACE / "build" / "c64x86.crt"

def build(cmd_type, body, req_id):
    return b"\x02\x02" + struct.pack("<I", len(body)) + struct.pack("<I", req_id) + bytes([cmd_type]) + body

def read(sock, timeout=2):
    sock.settimeout(timeout)
    header = b""
    while len(header) < 12:
        chunk = sock.recv(12 - len(header))
        if not chunk:
            raise ConnectionError("closed")
        header += chunk
    body_len = struct.unpack("<I", header[2:6])[0]
    typ = header[6]
    err = header[7]
    rid = struct.unpack("<I", header[8:12])[0]
    body = b""
    while len(body) < body_len:
        chunk = sock.recv(body_len - len(body))
        if not chunk:
            raise ConnectionError("closed")
        body += chunk
    return typ, err, rid, body

proc = subprocess.Popen(
    [str(VICE), "-default", "+confirmonexit", "+sound", "-warp", "-reu", "-reusize", "16384",
     "-cartcrt", str(CRT), "-limitcycles", "2000000000", "-binarymonitor",
     "-binarymonitoraddress", "127.0.0.1:6502", "-logfile", str(WORKSPACE / "build" / "vice-smoke.log")],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
time.sleep(2)
sock = socket.create_connection(("127.0.0.1", 6502), timeout=2)
print("connected")

# ping
sock.sendall(build(0x81, b"", 1))
for _ in range(5):
    try:
        print("ping drain:", read(sock, 2))
    except TimeoutError:
        break

# watchpoint store d020
body = struct.pack("<HH", 0xD020, 0xD020) + bytes([1,1,0x02,1,0])
sock.sendall(build(0x12, body, 2))
for _ in range(5):
    try:
        typ, err, rid, b = read(sock, 2)
        print("cp drain:", typ, err, rid, b.hex())
        if typ == 0x11 and rid == 2:
            cp_num = struct.unpack("<I", b[:4])[0]
            print("cp num", cp_num)
    except TimeoutError:
        break

# resume
sock.sendall(build(0xAA, b"", 3))
for _ in range(5):
    try:
        print("resume drain:", read(sock, 2))
    except TimeoutError:
        break

# wait for hit
for _ in range(10):
    try:
        typ, err, rid, b = read(sock, 3)
        print("run resp:", typ, err, rid, b.hex())
    except TimeoutError:
        print("no hit yet")
        break

sock.close()
proc.kill()
proc.wait()
