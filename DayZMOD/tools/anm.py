"""Reads and writes DayZ .anm animation files. Reads ANIMSET5 and ANIMSET6, writes ANIMSET5.

Layout, worked out from the game's own files and checked against their exact sizes:
  ANIMSET5 HEAD: one 56-byte entry per bone: name[24], two unused floats, translation offset+range,
        rotation offset+range, then u16 frames, translation keys, rotation keys, additive flag.
  ANIMSET6 HEAD: translation, rotation and scale offset+range (6 floats), u16 frames, translation,
        rotation and scale keys, u8 flag, u8 name length, name.
  DATA: for each bone: translation key frames (u16), translation values (3 u16 each),
        in ANIMSET6 scale key frames (u16) and values (3 u16 each),
        rotation key frames (u16), rotation values (4 u16 each, x y z w).
Values are quantised: value = offset + u16 / 65535 * range.

Self-check: python anm.py --check <file.anm>
"""
import struct
import sys

STRIDE = 56


class Bone:
    def __init__(self, name, additive=0):
        self.name = name
        self.additive = additive
        self.t = {}  # frame -> (x, y, z)
        self.r = {}  # frame -> (x, y, z, w)


class Anim:
    def __init__(self, fps=30, frames=1):
        self.fps = fps
        self.frames = frames
        self.bones = {}
        self.events = b""  # EVNT chunk as it is: the sync marks of step and turn animations


def _chunks(b):
    if b[:4] != b"FORM" or b[8:15] != b"ANIMSET":
        raise ValueError("not an ANIMSET file")
    pos = 20
    found = {}
    while pos < len(b):
        tag = b[pos:pos + 4]
        size = struct.unpack(">I", b[pos + 4:pos + 8])[0]
        found[tag] = (pos + 8, size)
        pos += 8 + size
    return found


def _head5(b, head, size):
    for i in range(size // STRIDE):
        e = b[head + i * STRIDE:head + (i + 1) * STRIDE]
        _, _, t_off, t_rng, r_off, r_rng = struct.unpack("<6f", e[24:48])
        frames, nt, nr, additive = struct.unpack("<4H", e[48:56])
        yield e[:24].split(b"\0")[0].decode(), t_off, t_rng, r_off, r_rng, frames, nt, nr, 0, additive


def _head6(b, head, size):
    i = head
    while i < head + size:
        t_off, t_rng, r_off, r_rng, _, _ = struct.unpack_from("<6f", b, i)
        frames, nt, nr, ns = struct.unpack_from("<4H", b, i + 24)
        length = b[i + 33]
        name = b[i + 34:i + 34 + length].decode()
        i += 34 + length
        yield name, t_off, t_rng, r_off, r_rng, frames, nt, nr, ns, 0


def read(path):
    b = open(path, "rb").read()
    chunks = _chunks(b)
    start, size = chunks[b"FPS\0"]
    anim = Anim(struct.unpack("<I", b[start:start + 4])[0])
    if b"EVNT" in chunks:
        anim.events = b[chunks[b"EVNT"][0]:chunks[b"EVNT"][0] + chunks[b"EVNT"][1]]
    head, head_size = chunks[b"HEAD"]
    pos = chunks[b"DATA"][0]
    entries = _head6(b, head, head_size) if b[15:16] == b"6" else _head5(b, head, head_size)
    for name, t_off, t_rng, r_off, r_rng, frames, nt, nr, ns, additive in entries:
        anim.frames = max(anim.frames, frames)
        bone = Bone(name, additive)
        times = struct.unpack_from("<%dH" % nt, b, pos)
        pos += 2 * nt
        for k in range(nt):
            v = struct.unpack_from("<3H", b, pos)
            pos += 6
            bone.t[times[k]] = tuple(t_off + c / 65535.0 * t_rng for c in v)
        pos += 8 * ns  # scale keys sit between the two: frame + 3 values, the player skeleton has no use for them
        times = struct.unpack_from("<%dH" % nr, b, pos)
        pos += 2 * nr
        for k in range(nr):
            v = struct.unpack_from("<4H", b, pos)
            pos += 8
            bone.r[times[k]] = tuple(r_off + c / 65535.0 * r_rng for c in v)
        anim.bones[name] = bone
    return anim


def _range(values):
    flat = [c for v in values for c in v]
    if not flat:
        return 0.0, 0.0
    low = min(flat)
    return low, max(flat) - low


def _quant(c, off, rng):
    return 0 if rng == 0 else min(65535, max(0, int(round((c - off) / rng * 65535))))


def write(anim, path):
    head = b""
    data = b""
    for bone in anim.bones.values():
        t_off, t_rng = _range(bone.t.values())
        r_off, r_rng = _range(bone.r.values())
        head += bone.name.encode().ljust(24, b"\0")
        head += struct.pack("<6f", 0, 0, t_off, t_rng, r_off, r_rng)
        head += struct.pack("<4H", anim.frames, len(bone.t), len(bone.r), bone.additive)
        for f in sorted(bone.t):
            data += struct.pack("<H", f)
        for f in sorted(bone.t):
            data += struct.pack("<3H", *[_quant(c, t_off, t_rng) for c in bone.t[f]])
        for f in sorted(bone.r):
            data += struct.pack("<H", f)
        for f in sorted(bone.r):
            data += struct.pack("<4H", *[_quant(c, r_off, r_rng) for c in bone.r[f]])

    def chunk(tag, payload):
        return tag + struct.pack(">I", len(payload)) + payload

    body = chunk(b"FPS\0", struct.pack("<I", anim.fps)) + chunk(b"HEAD", head) + chunk(b"DATA", data)
    if anim.events:
        body += chunk(b"EVNT", anim.events)
    with open(path, "wb") as f:
        f.write(b"FORM" + struct.pack(">I", 8 + 4 + len(body)) + b"ANIMSET5" + struct.pack(">I", len(body)) + body)


def check(path):
    """Round trip: every key of a game file must survive a write and a read."""
    import math
    import os
    import tempfile
    a = read(path)
    for bone in a.bones.values():
        for q in bone.r.values():
            if not bone.additive and bone.name not in ("Scene_Root", "Collision"):
                assert abs(math.sqrt(sum(c * c for c in q)) - 1) < 0.02, (bone.name, q)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "x.anm")
        write(a, out)
        b = read(out)
        assert open(out, "rb").read()[:4] == b"FORM"
    assert list(a.bones) == list(b.bones) and a.frames == b.frames
    for name, bone in a.bones.items():
        other = b.bones[name]
        for keys, again in ((bone.t, other.t), (bone.r, other.r)):
            assert sorted(keys) == sorted(again)
            for f in keys:
                assert all(abs(x - y) < 1e-3 for x, y in zip(keys[f], again[f])), (name, f)
    print("ok", len(a.bones), "bones", a.frames, "frames")


if __name__ == "__main__":
    if sys.argv[1] == "--check":
        for p in sys.argv[2:]:
            check(p)
