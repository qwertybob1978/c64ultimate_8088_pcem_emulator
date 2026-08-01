#!/usr/bin/env python3
"""Run VICE with a binary-monitor watchpoint on $07FE and dump fault state."""
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
VICE = WORKSPACE / ".cache" / "vice-3.10" / "GTK3VICE-3.10-win64" / "bin" / "x64sc.exe"
CRT = WORKSPACE / "build" / "c64x86.crt"
HOST = "127.0.0.1"
PORT = 6502


def build_command(cmd_type: int, body: bytes, req_id: int) -> bytes:
    return (
        b"\x02\x02"
        + struct.pack("<I", len(body))
        + struct.pack("<I", req_id)
        + bytes([cmd_type])
        + body
    )


def read_response(sock: socket.socket, timeout: float = 5.0):
    sock.settimeout(timeout)
    header = b""
    while len(header) < 12:
        chunk = sock.recv(12 - len(header))
        if not chunk:
            raise ConnectionError("VICE closed connection")
        header += chunk
    if header[0] != 0x02 or header[1] != 0x02:
        raise ValueError(f"Bad monitor header: {header.hex()}")
    body_len = struct.unpack("<I", header[2:6])[0]
    resp_type = header[6]
    error = header[7]
    req_id = struct.unpack("<I", header[8:12])[0]
    body = b""
    while len(body) < body_len:
        chunk = sock.recv(body_len - len(body))
        if not chunk:
            raise ConnectionError("VICE closed connection while reading body")
        body += chunk
    return resp_type, error, req_id, body


def send_command(sock: socket.socket, cmd_type: int, body: bytes) -> int:
    req_id = (int(time.time() * 1000) & 0x7FFFFFFF) | 0x100
    sock.sendall(build_command(cmd_type, body, req_id))
    return req_id


def drain_until(sock: socket.socket, target_type: int, target_rid: int, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = max(0.5, deadline - time.time())
        resp_type, error, rid, body = read_response(sock, timeout=remaining)
        if resp_type == target_type and rid == target_rid:
            return resp_type, error, rid, body
        # Events (rid == 0xffffffff) and other responses are ignored.
    raise TimeoutError(f"Did not receive response type {target_type:#x} for rid {target_rid:#x}")


def mem_get(sock: socket.socket, start: int, end: int, memspace: int = 0, bank: int = 0, timeout: float = 10.0) -> bytes:
    body = bytes([0, start & 0xFF, start >> 8, end & 0xFF, end >> 8, memspace, bank & 0xFF, bank >> 8])
    req_id = send_command(sock, 0x01, body)
    _, _, _, body = drain_until(sock, 0x01, req_id, timeout=timeout)
    if len(body) < 2:
        raise RuntimeError("Memory get response too short")
    length = struct.unpack("<H", body[:2])[0]
    return body[2 : 2 + length]


def wait_for_hit(sock: socket.socket, timeout: float = 300.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = max(0.5, deadline - time.time())
        resp_type, error, rid, body = read_response(sock, timeout=remaining)
        if resp_type == 0x11:  # checkpoint response
            # body: CN(4) CH(1) SA(2) EA(2) ST EN OP TM HC(4) IC(4) CE MS
            if len(body) < 19:
                continue
            hit = body[4]
            if hit:
                return body
        # ignore register dumps / stopped / resumed events
    raise TimeoutError("Did not hit watchpoint in time")


def main():
    if not CRT.exists():
        print(f"CRT not found: {CRT}", file=sys.stderr)
        sys.exit(1)
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
            f"{HOST}:{PORT}",
            "-logfile",
            str(WORKSPACE / "build" / "vice-smoke.log"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    sock = None
    for _ in range(30):
        try:
            sock = socket.create_connection((HOST, PORT), timeout=1.0)
            break
        except (ConnectionRefusedError, TimeoutError, OSError):
            time.sleep(1.0)
    if sock is None:
        print("Could not connect to VICE binary monitor", file=sys.stderr)
        proc.kill()
        sys.exit(1)

    try:
        # Ping wakes the monitor; responses include register dump and stopped event.
        send_command(sock, 0x81, b"")
        # Read a few responses to confirm the connection is alive, then continue.
        for _ in range(5):
            try:
                read_response(sock, timeout=2.0)
            except TimeoutError:
                break

        # Watchpoint on store to the failure sentinel at $85F0.
        start = end = 0x85F0
        cp_body = struct.pack("<HH", start, end)
        cp_body += bytes([1, 1, 0x02, 1, 0])  # stop, enabled, store, temporary, main mem
        req_id = send_command(sock, 0x12, cp_body)
        _, _, _, cp_resp = drain_until(sock, 0x11, req_id, timeout=5.0)
        cp_num = struct.unpack("<I", cp_resp[:4])[0]
        print(f"Set watchpoint #{cp_num} on store to ${start:04X}")

        # Resume emulation and wait immediately for the failure sentinel.
        send_command(sock, 0xAA, b"")
        wait_for_hit(sock, timeout=300.0)
        print("Watchpoint hit, dumping memory...")

        # Dump the whole diagnostic region in one go.
        dump = mem_get(sock, 0x0400, 0x86FF, timeout=30.0)
        (WORKSPACE / "build" / "fault-dump.bin").write_bytes(dump)
        print(f"Saved build/fault-dump.bin ({len(dump)} bytes)")

        # Quit VICE
        send_command(sock, 0xBB, b"")
    finally:
        sock.close()
        try:
            proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    main()
