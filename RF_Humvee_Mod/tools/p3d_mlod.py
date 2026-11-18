"""Чтение/запись P3D в формате MLOD (редактируемый формат Object Builder, DayZ/Arma)."""
import struct


def _asciiz(b, o):
    e = b.index(b"\0", o)
    return b[o:e].decode("latin-1"), e + 1


class Lod:
    def __init__(self, resolution):
        self.resolution = float(resolution)
        self.points = []        # (x, y, z, flags)
        self.normals = []       # (x, y, z)
        self.faces = []         # dict(verts=[(pi, ni, u, v)...], flags, texture, material)
        self.selections = {}    # name -> (set(point idx), set(face idx))
        self.mass = None        # list per point or None
        self.properties = []    # [(name, value)]
        self.sharp_edges = []

    def add_point(self, p, flags=0):
        self.points.append((float(p[0]), float(p[1]), float(p[2]), flags))
        return len(self.points) - 1

    def add_normal(self, n):
        self.normals.append(tuple(float(c) for c in n))
        return len(self.normals) - 1

    def select(self, name, points=(), faces=()):
        s = self.selections.setdefault(name, (set(), set()))
        s[0].update(points)
        s[1].update(faces)


def read(path):
    b = open(path, "rb").read()
    assert b[:4] == b"MLOD", b[:4]
    ver, nlod = struct.unpack_from("<II", b, 4)
    o = 12
    lods = []
    for _ in range(nlod):
        assert b[o:o + 4] == b"P3DM", b[o:o + 4]
        hs, ver_l, npt, nnr, nfc, fl = struct.unpack_from("<IIIIII", b, o + 4)
        o += hs
        L = Lod(0)
        for i in range(npt):
            L.points.append(struct.unpack_from("<fffI", b, o)); o += 16
        for i in range(nnr):
            L.normals.append(struct.unpack_from("<fff", b, o)); o += 12
        for i in range(nfc):
            nv = struct.unpack_from("<I", b, o)[0]; o += 4
            verts = []
            for k in range(4):
                pi, ni, u, v = struct.unpack_from("<IIff", b, o); o += 16
                if k < nv:
                    verts.append((pi, ni, u, v))
            flags = struct.unpack_from("<I", b, o)[0]; o += 4
            tex, o = _asciiz(b, o)
            mat, o = _asciiz(b, o)
            L.faces.append(dict(verts=verts, flags=flags, texture=tex, material=mat))
        assert b[o:o + 4] == b"TAGG", b[o:o + 4]
        o += 4
        while True:
            act = b[o]; o += 1
            name, o = _asciiz(b, o)
            ln = struct.unpack_from("<I", b, o)[0]; o += 4
            data = b[o:o + ln]; o += ln
            if name == "#EndOfFile#":
                break
            if name == "#Mass#":
                L.mass = list(struct.unpack("<%df" % (ln // 4), data))
            elif name == "#Property#":
                L.properties.append((data[:64].split(b"\0")[0].decode(), data[64:].split(b"\0")[0].decode()))
            elif name == "#SharpEdges#":
                L.sharp_edges = list(struct.unpack("<%dI" % (ln // 4), data))
            elif not name.startswith("#"):
                pts = {i for i in range(npt) if data[i]}
                fcs = {i for i in range(nfc) if data[npt + i]}
                L.selections[name] = (pts, fcs)
        L.resolution = struct.unpack_from("<f", b, o)[0]; o += 4
        lods.append(L)
    return lods


def _tagg(name, data):
    return b"\x01" + name.encode("latin-1") + b"\0" + struct.pack("<I", len(data)) + data


def write(path, lods):
    out = bytearray(b"MLOD" + struct.pack("<II", 0x101, len(lods)))
    for L in lods:
        npt, nnr, nfc = len(L.points), len(L.normals), len(L.faces)
        out += b"P3DM" + struct.pack("<IIIIII", 28, 0x100, npt, nnr, nfc, 0)
        for p in L.points:
            out += struct.pack("<fffI", p[0], p[1], p[2], int(p[3]) if len(p) > 3 else 0)
        for n in L.normals:
            out += struct.pack("<fff", *n)
        for f in L.faces:
            v = f["verts"]
            out += struct.pack("<I", len(v))
            for k in range(4):
                pi, ni, u, vv = v[k] if k < len(v) else (0, 0, 0.0, 0.0)
                out += struct.pack("<IIff", pi, ni, u, vv)
            out += struct.pack("<I", f.get("flags", 0))
            out += f.get("texture", "").encode("latin-1") + b"\0"
            out += f.get("material", "").encode("latin-1") + b"\0"
        out += b"TAGG"
        if L.sharp_edges:
            out += _tagg("#SharpEdges#", struct.pack("<%dI" % len(L.sharp_edges), *L.sharp_edges))
        if L.mass is not None:
            out += _tagg("#Mass#", struct.pack("<%df" % npt, *L.mass))
        for k, v in L.properties:
            out += _tagg("#Property#", k.encode().ljust(64, b"\0")[:64] + v.encode().ljust(64, b"\0")[:64])
        for name, (pts, fcs) in L.selections.items():
            data = bytearray(npt + nfc)
            for i in pts:
                data[i] = 1
            for i in fcs:
                data[npt + i] = 1
            out += _tagg(name, bytes(data))
        out += _tagg("#EndOfFile#", b"")
        out += struct.pack("<f", L.resolution)
    with open(path, "wb") as fh:
        fh.write(out)
