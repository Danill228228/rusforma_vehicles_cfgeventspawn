"""Упаковка PBO (без бинаризации) — формат, который читает DayZ/Arma."""
import hashlib
import os
import struct
import time


def pack(out_path, src_dir, prefix):
    files = []
    for root, _, names in os.walk(src_dir):
        for n in sorted(names):
            full = os.path.join(root, n)
            rel = os.path.relpath(full, src_dir).replace("/", "\\")
            if rel.lower().endswith((".py", ".pyc", ".md")):
                continue
            files.append((rel, open(full, "rb").read()))
    files.sort(key=lambda f: f[0].lower())
    ts = int(time.time())
    hdr = bytearray(b"\0" + struct.pack("<5I", 0x56657273, 0, 0, 0, 0))
    hdr += b"prefix\0" + prefix.encode() + b"\0" + b"\0"
    for rel, data in files:
        hdr += rel.encode("latin-1") + b"\0" + struct.pack("<5I", 0, len(data), 0, ts, len(data))
    hdr += b"\0" + struct.pack("<5I", 0, 0, 0, 0, 0)
    body = bytes(hdr) + b"".join(d for _, d in files)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(body + b"\0" + hashlib.sha1(body).digest())
    return [r for r, _ in files]


def list_pbo(path):
    b = open(path, "rb").read()
    o = 1 + 20
    props = []
    while True:
        e = b.index(b"\0", o)
        k = b[o:e].decode()
        o = e + 1
        if not k:
            break
        e = b.index(b"\0", o)
        props.append((k, b[o:e].decode()))
        o = e + 1
    entries = []
    while True:
        e = b.index(b"\0", o)
        name = b[o:e].decode("latin-1")
        o = e + 1
        mime, orig, res, ts, size = struct.unpack_from("<5I", b, o)
        o += 20
        if not name:
            break
        entries.append((name, size))
    data_start = o
    total = data_start + sum(s for _, s in entries)
    ok = hashlib.sha1(b[:total]).digest() == b[total + 1:total + 21]
    return props, entries, ok
