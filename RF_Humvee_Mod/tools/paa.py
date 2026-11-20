"""Запись текстур PAA (DXT1, без LZO) для DayZ/Arma и обратное чтение для проверки."""
import struct

import numpy as np


def _to565(c):
    c = np.clip(np.rint(c), 0, 255).astype(np.uint32)
    return ((c[..., 0] >> 3) << 11) | ((c[..., 1] >> 2) << 5) | (c[..., 2] >> 3)


def _from565(v):
    v = v.astype(np.uint32)
    r = ((v >> 11) & 31) * 255 / 31
    g = ((v >> 5) & 63) * 255 / 63
    b = (v & 31) * 255 / 31
    return np.stack([r, g, b], -1)


def dxt1_encode(img):
    """img: HxWx3 uint8, H и W кратны 4."""
    h, w, _ = img.shape
    blk = img.reshape(h // 4, 4, w // 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3).astype(float)
    hi, lo = blk.max(1), blk.min(1)
    inset = (hi - lo) / 16.0                      # поджатие концов палитры: меньше ошибка на блоках с выбросами
    hi, lo = hi - inset, lo + inset
    c0, c1 = _to565(hi), _to565(lo)
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    p0, p1 = _from565(c0), _from565(c1)
    pal = np.stack([p0, p1, (2 * p0 + p1) / 3, (p0 + 2 * p1) / 3], 1)          # N x 4 x 3
    d = ((blk[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)              # N x 16 x 4
    idx = d.argmin(-1).astype(np.uint32)
    idx[c0 == c1] = 0
    bits = np.zeros(len(blk), np.uint32)
    for i in range(16):
        bits |= idx[:, i] << (2 * i)
    out = np.zeros((len(blk), 2), np.uint32)
    out = np.empty(len(blk), dtype=[("c0", "<u2"), ("c1", "<u2"), ("bits", "<u4")])
    out["c0"], out["c1"], out["bits"] = c0, c1, bits
    return out.tobytes()


def dxt1_decode(data, w, h):
    a = np.frombuffer(data, dtype=[("c0", "<u2"), ("c1", "<u2"), ("bits", "<u4")])
    p0, p1 = _from565(a["c0"]), _from565(a["c1"])
    pal = np.stack([p0, p1, (2 * p0 + p1) / 3, (p0 + 2 * p1) / 3], 1)
    idx = np.stack([(a["bits"] >> (2 * i)) & 3 for i in range(16)], 1)
    px = np.take_along_axis(pal, idx[..., None].astype(int).repeat(3, -1), 1)
    return px.reshape(h // 4, w // 4, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(h, w, 3)


def downscale(img, k):
    """Усреднение блоков k x k (k - степень двойки): сверхсэмплинг из генератора вместо пережатия."""
    while k > 1:
        m = img.astype(np.float32)
        img = np.clip(np.rint((m[0::2, 0::2] + m[1::2, 0::2] + m[0::2, 1::2] + m[1::2, 1::2]) / 4), 0, 255).astype(np.uint8)
        k //= 2
    return img


def downscale_normals(img, k):
    """То же для карты нормалей: после усреднения вектор нормализуется заново."""
    while k > 1:
        v = img.astype(np.float32) / 255 * 2 - 1
        v = (v[0::2, 0::2] + v[1::2, 0::2] + v[0::2, 1::2] + v[1::2, 1::2]) / 4
        v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
        img = np.clip(np.rint((v * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)
        k //= 2
    return img


def info_paa(path):
    """Разбор заголовка PAA: тип, размер, число мипов, LZO-флаг."""
    b = open(path, "rb").read()
    typ = struct.unpack_from("<H", b, 0)[0]
    o = 2
    while b[o:o + 4] == b"GGAT":
        o += 12 + struct.unpack_from("<I", b, o + 8)[0]
    o += 2 + struct.unpack_from("<H", b, o)[0] * 3
    mips = []
    while True:
        w, h = struct.unpack_from("<HH", b, o)
        if w == 0 or h == 0:
            break
        size = int.from_bytes(b[o + 4:o + 7], "little")
        mips.append((w & 0x7FFF, h, size, bool(w & 0x8000)))
        o += 7 + size
    return {"type": hex(typ), "size": (mips[0][0], mips[0][1]), "mips": len(mips),
            "lzo": any(m[3] for m in mips), "bytes": len(b)}


def _mips(img):
    out = [img]
    while min(out[-1].shape[:2]) > 4:
        m = out[-1].astype(float)
        m = (m[0::2, 0::2] + m[1::2, 0::2] + m[0::2, 1::2] + m[1::2, 1::2]) / 4
        out.append(np.clip(np.rint(m), 0, 255).astype(np.uint8))
    return out


def write_paa(path, img):
    img = np.asarray(img)[..., :3].astype(np.uint8)
    avg = img.reshape(-1, 3).mean(0)
    head = bytearray(struct.pack("<H", 0xFF01))
    head += b"GGATCGVA" + struct.pack("<I", 4) + bytes([int(avg[2]), int(avg[1]), int(avg[0]), 255])
    head += b"GGATCXAM" + struct.pack("<I", 4) + b"\xff\xff\xff\xff"
    offs_pos = len(head) + 12
    head += b"GGATSFFO" + struct.pack("<I", 64) + b"\0" * 64
    head += struct.pack("<H", 0)                      # палитра: 0 цветов
    body = bytearray()
    offsets = []
    for m in _mips(img):
        h, w = m.shape[:2]
        data = dxt1_encode(m)
        offsets.append(len(head) + len(body))
        body += struct.pack("<HH", w, h) + struct.pack("<I", len(data))[:3] + data
    body += b"\0" * 6
    for i, o in enumerate(offsets[:16]):
        struct.pack_into("<I", head, offs_pos + 4 * i, o)
    with open(path, "wb") as f:
        f.write(head + body)


def read_paa(path):
    b = open(path, "rb").read()
    assert struct.unpack_from("<H", b, 0)[0] == 0xFF01
    o = 2
    while b[o:o + 4] == b"GGAT":
        ln = struct.unpack_from("<I", b, o + 8)[0]
        o += 12 + ln
    npal = struct.unpack_from("<H", b, o)[0]
    o += 2 + npal * 3
    w, h = struct.unpack_from("<HH", b, o)
    size = int.from_bytes(b[o + 4:o + 7], "little")
    return dxt1_decode(b[o + 7:o + 7 + size], w, h)
