#!/usr/bin/env python3
"""Store-watchpoint capture: fire on first write to a chosen C64 address, dump diag region."""
import socket, struct, subprocess, sys, time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
VICE = WORKSPACE / ".cache" / "vice-3.10" / "GTK3VICE-3.10-win64" / "bin" / "x64sc.exe"
CRT = WORKSPACE / "build" / "c64x86.crt"
HOST, PORT = "127.0.0.1", 6502
WATCH = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x7F85  # fdc_last_command


def cmd(sock, ctype, body):
    rid = (int(time.time() * 1000) & 0x7FFFFFFF) | 0x100
    sock.sendall(b"\x02\x02" + struct.pack("<I", len(body)) + struct.pack("<I", rid) + bytes([ctype]) + body)
    return rid


def read_resp(sock, timeout=5.0):
    sock.settimeout(timeout)
    hdr = b""
    while len(hdr) < 12:
        c = sock.recv(12 - len(hdr))
        if not c:
            raise ConnectionError("closed")
        hdr += c
    blen = struct.unpack("<I", hdr[2:6])[0]
    rtype, rid = hdr[6], struct.unpack("<I", hdr[8:12])[0]
    body = b""
    while len(body) < blen:
        c = sock.recv(blen - len(body))
        if not c:
            raise ConnectionError("closed")
        body += c
    return rtype, rid, body


def drain_until(sock, rtype, rid, timeout=5.0):
    dl = time.time() + timeout
    while time.time() < dl:
        t, r, b = read_resp(sock, max(0.5, dl - time.time()))
        if t == rtype and r == rid:
            return b
    raise TimeoutError()


def mem_get(sock, start, end):
    body = bytes([0, start & 0xFF, start >> 8, end & 0xFF, end >> 8, 0, 0, 0])
    rid = cmd(sock, 0x01, body)
    b = drain_until(sock, 0x01, rid, timeout=20.0)
    n = struct.unpack("<H", b[:2])[0]
    return b[2:2 + n]


def main():
    proc = subprocess.Popen(
        [str(VICE), "-default", "+confirmonexit", "+sound", "-warp", "-reu", "-reusize", "16384",
         "-cartcrt", str(CRT), "-limitcycles", "2200000000",
         "-binarymonitor", "-binarymonitoraddress", f"{HOST}:{PORT}",
         "-logfile", str(WORKSPACE / "build" / "vice-smoke.log")],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sock = None
    for _ in range(30):
        try:
            sock = socket.create_connection((HOST, PORT), timeout=1.0); break
        except OSError:
            time.sleep(1.0)
    if sock is None:
        proc.kill(); raise SystemExit("no monitor")
    try:
        cmd(sock, 0x81, b"")
        for _ in range(5):
            try: read_resp(sock, 2.0)
            except TimeoutError: break
        cp = struct.pack("<HH", WATCH, WATCH) + bytes([1, 1, 0x02, 1, 0])  # stop,enabled,store,temporary,mainmem
        rid = cmd(sock, 0x12, cp)
        cpr = drain_until(sock, 0x11, rid, timeout=5.0)
        print(f"store watchpoint #{struct.unpack('<I', cpr[:4])[0]} on ${WATCH:04X}")
        cmd(sock, 0xAA, b"")
        dl = time.time() + 120
        hit_count = 0
        while time.time() < dl:
            t, r, b = read_resp(sock, max(0.5, dl - time.time()))
            if t == 0x11 and len(b) >= 5 and b[4]:
                hit_count += 1
                break
        print("HIT" if hit_count else "TIMEOUT (addr never written)")
        if hit_count:
            cmd(sock, 0xAA, b"")
            time.sleep(15)
        dump = mem_get(sock, 0x0400, 0x86FF)
        (WORKSPACE / "build" / "fault-dump.bin").write_bytes(dump)
        print(f"saved build/fault-dump.bin ({len(dump)} bytes)")
        cmd(sock, 0xBB, b"")
    finally:
        sock.close()
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill()


if __name__ == "__main__":
    main()
