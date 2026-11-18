#!/usr/bin/env python3
"""
Процедурный генератор 3D-модели армейского внедорожника в стиле HMMWV (M1025-подобный
кузов с жёсткой крышей и круглым люком/турельным кольцом на крыше).

Модель полностью оригинальная (собрана из примитивов в этом скрипте), без чужих ассетов.

Выход (в ../model):
  humvee.gltf  — glTF 2.0 (буфер встроен), иерархия нод: люк на отдельной ноде-шарнире
  humvee.obj   — OBJ + humvee.mtl, части разнесены по объектам с именами селекций DayZ
                 (hatch_roof, hatch_roof_axis, wheel_1_1 ... ) для импорта в Blender

Система координат: Y вверх, +Z вперёд (нос машины), метры. Нижняя точка колёс на Y=0.
Запуск: python3 generate_humvee.py
"""
import base64
import json
import math
import os
import struct

import numpy as np

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model")

# --------------------------------------------------------------------------- materials
MATERIALS = {
    #  name        sRGB                     metallic rough  extra
    "paint":    ((0.330, 0.360, 0.220), 0.15, 0.60, {}),
    "dark":     ((0.110, 0.115, 0.100), 0.35, 0.65, {}),
    "rubber":   ((0.110, 0.108, 0.104), 0.00, 0.93, {}),
    "rim":      ((0.150, 0.165, 0.120), 0.40, 0.55, {}),
    "metal":    ((0.600, 0.600, 0.580), 0.85, 0.40, {}),
    "glass":    ((0.330, 0.400, 0.440), 0.10, 0.06, {"alpha": 0.55}),
    "light":    ((0.980, 0.960, 0.880), 0.00, 0.20, {"emissive": (0.35, 0.33, 0.26)}),
    "amber":    ((1.000, 0.650, 0.150), 0.00, 0.30, {"emissive": (0.25, 0.12, 0.0)}),
    "red":      ((0.800, 0.100, 0.080), 0.00, 0.30, {"emissive": (0.20, 0.0, 0.0)}),
    "interior": ((0.220, 0.230, 0.190), 0.05, 0.85, {}),
    "seat":     ((0.140, 0.140, 0.130), 0.00, 0.95, {}),
}


def srgb_to_linear(c):
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


# --------------------------------------------------------------------------- geometry core
class Geo:
    """Набор треугольников с нормалями."""

    def __init__(self, P=None, N=None, I=None):
        self.P = np.zeros((0, 3)) if P is None else np.asarray(P, float)
        self.N = np.zeros((0, 3)) if N is None else np.asarray(N, float)
        self.I = np.zeros((0, 3), int) if I is None else np.asarray(I, int).reshape(-1, 3)

    def __iadd__(self, o):
        off = len(self.P)
        self.P = np.vstack([self.P, o.P])
        self.N = np.vstack([self.N, o.N])
        self.I = np.vstack([self.I, o.I + off])
        return self

    def transformed(self, M):
        M = np.asarray(M, float)
        R, t = M[:3, :3], M[:3, 3]
        P = self.P @ R.T + t
        Nm = np.linalg.inv(R).T
        N = self.N @ Nm.T
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        I = self.I.copy()
        if np.linalg.det(R) < 0:
            I = I[:, [0, 2, 1]]
        return Geo(P, N, I)


def T(x=0.0, y=0.0, z=0.0):
    M = np.eye(4)
    M[:3, 3] = (x, y, z)
    return M


def Rx(a):
    c, s = math.cos(a), math.sin(a)
    M = np.eye(4)
    M[1, 1], M[1, 2], M[2, 1], M[2, 2] = c, -s, s, c
    return M


def Ry(a):
    c, s = math.cos(a), math.sin(a)
    M = np.eye(4)
    M[0, 0], M[0, 2], M[2, 0], M[2, 2] = c, s, -s, c
    return M


def Rz(a):
    c, s = math.cos(a), math.sin(a)
    M = np.eye(4)
    M[0, 0], M[0, 1], M[1, 0], M[1, 1] = c, -s, s, c
    return M


def S(x=1.0, y=1.0, z=1.0):
    return np.diag([x, y, z, 1.0])


def chain(*ms):
    M = np.eye(4)
    for m in ms:
        M = M @ m
    return M


MIRROR_X = S(-1, 1, 1)


def _newell(pts):
    n = np.zeros(3)
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += np.cross(a, b)
    return n


def face(pts, hint=None):
    """Плоский выпуклый многоугольник; hint — желаемое направление нормали."""
    pts = np.asarray(pts, float)
    n = _newell(pts)
    if hint is not None and np.dot(n, hint) < 0:
        pts = pts[::-1]
        n = -n
    ln = np.linalg.norm(n)
    if ln < 1e-12:
        return Geo()
    n /= ln
    k = len(pts)
    I = [(0, i, i + 1) for i in range(1, k - 1)]
    return Geo(pts, np.tile(n, (k, 1)), I)


def box(x0, x1, y0, y1, z0, z1):
    g = Geo()
    g += face([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0))
    g += face([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0))
    g += face([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0))
    g += face([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0))
    g += face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1))
    g += face([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1))
    return g


def cbox(cx, cy, cz, sx, sy, sz):
    return box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2)


def _area2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def triangulate(poly):
    """Ear clipping для простого многоугольника (CCW)."""
    idx = list(range(len(poly)))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        ear = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if _area2(a, b, c) <= 1e-10:
                continue
            bad = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = poly[j]
                if (_area2(a, b, p) > 1e-10 and _area2(b, c, p) > 1e-10
                        and _area2(c, a, p) > 1e-10):
                    bad = True
                    break
            if bad:
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            ear = True
            break
        if not ear:
            tris.append((idx[0], idx[1], idx[2]))
            idx.pop(1)
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def extrude_x(profile, x0, x1):
    """Профиль в плоскости (z, y) выдавливается вдоль X от x0 до x1."""
    prof = [tuple(p) for p in profile]
    area = sum(_area2((0, 0), prof[i], prof[(i + 1) % len(prof)]) for i in range(len(prof)))
    if area < 0:
        prof = prof[::-1]
    g = Geo()
    tris = triangulate(prof)
    for xc, hx in ((x1, 1.0), (x0, -1.0)):
        for (a, b, c) in tris:
            pts = [(xc, prof[i][1], prof[i][0]) for i in (a, b, c)]
            g += face(pts, (hx, 0, 0))
    n = len(prof)
    for i in range(n):
        (za, ya), (zb, yb) = prof[i], prof[(i + 1) % n]
        du, dv = zb - za, yb - ya
        hint = (0.0, -du, dv)
        g += face([(x0, ya, za), (x0, yb, zb), (x1, yb, zb), (x1, ya, za)], hint)
    return g


def lathe(profile, seg=48, smooth_deg=40.0, a0=0.0, a1=2 * math.pi):
    """Тело вращения вокруг локальной оси X. profile: [(r, h)], обход так,
    чтобы наружная нормаль = (dh, -dr)."""
    prof = [np.array(p, float) for p in profile]
    segn = []
    for i in range(len(prof) - 1):
        d = prof[i + 1] - prof[i]
        n = np.array([d[1], -d[0]])
        ln = np.linalg.norm(n)
        segn.append(n / ln if ln > 1e-12 else np.array([1.0, 0.0]))
    cos_t = math.cos(math.radians(smooth_deg))
    g = Geo()
    angs = [a0 + (a1 - a0) * j / seg for j in range(seg + 1)]
    for i in range(len(prof) - 1):
        ns = segn[i]
        n_start, n_end = ns, ns
        if i > 0 and np.dot(segn[i - 1], ns) > cos_t:
            n_start = segn[i - 1] + ns
        if i < len(segn) - 1 and np.dot(segn[i + 1], ns) > cos_t:
            n_end = segn[i + 1] + ns
        P, N, I = [], [], []
        for (r, h), (nr, nh) in ((prof[i], n_start), (prof[i + 1], n_end)):
            ln = math.hypot(nr, nh)
            nr, nh = nr / ln, nh / ln
            for a in angs:
                ca, sa = math.cos(a), math.sin(a)
                P.append((h, r * ca, r * sa))
                N.append((nh, nr * ca, nr * sa))
        m = len(angs)
        for j in range(seg):
            a, b, c, d = j, j + 1, m + j + 1, m + j
            I += [(a, b, c), (a, c, d)]
        g += Geo(P, N, I)
    return fix_winding(g)


def fix_winding(g):
    P, N, I = g.P, g.N, g.I.copy()
    for k, (a, b, c) in enumerate(I):
        cr = np.cross(P[b] - P[a], P[c] - P[a])
        if np.dot(cr, N[a] + N[b] + N[c]) < 0:
            I[k] = (a, c, b)
    return Geo(P, N, I)


def cylinder_x(r, h0, h1, seg=24):
    return lathe([(0, h0), (r, h0), (r, h1), (0, h1)], seg=seg, smooth_deg=10)


AX_TO_Y = Rz(math.pi / 2)        # локальная ось X -> мировая Y
AX_TO_Z = Ry(-math.pi / 2)       # локальная ось X -> мировая Z


def plane_quad(corners, hint, eps):
    """Четырёхугольник, слегка выдвинутый вдоль hint (для стёкол/накладок)."""
    h = np.asarray(hint, float)
    h /= np.linalg.norm(h)
    pts = [np.asarray(c, float) + h * eps for c in corners]
    return face(pts, h)


# --------------------------------------------------------------------------- extra helpers
def extrude_x2(profile, x0, x1, skip=(), alt=()):
    """Как extrude_x, но: skip — индексы рёбер без боковой грани, alt — рёбра во втором материале.
    Профиль (z, y) обязан идти против часовой стрелки. Возвращает (основная Geo, Geo рёбер alt)."""
    prof = [tuple(p) for p in profile]
    area = sum(_area2((0, 0), prof[i], prof[(i + 1) % len(prof)]) for i in range(len(prof)))
    assert area > 0, "профиль должен быть CCW"
    g, ga = Geo(), Geo()
    for xc, hx in ((x1, 1.0), (x0, -1.0)):
        for (a, b, c) in triangulate(prof):
            g += face([(xc, prof[i][1], prof[i][0]) for i in (a, b, c)], (hx, 0, 0))
    n = len(prof)
    for i in range(n):
        if i in skip:
            continue
        (za, ya), (zb, yb) = prof[i], prof[(i + 1) % n]
        f = face([(x0, ya, za), (x0, yb, zb), (x1, yb, zb), (x1, ya, za)], (0.0, -(zb - za), yb - ya))
        if i in alt:
            ga += f
        else:
            g += f
    return g, ga


def align_x(d):
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    x = np.array([1.0, 0, 0])
    v = np.cross(x, d)
    c = float(np.dot(x, d))
    M = np.eye(4)
    if np.linalg.norm(v) < 1e-9:
        if c < 0:
            M = Rz(math.pi)
        return M
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    M[:3, :3] = np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))
    return M


def tube(p0, p1, r, seg=14):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    return cylinder_x(r, -r * 0.6, L + r * 0.6, seg).transformed(chain(T(*p0), align_x(p1 - p0)))


# --------------------------------------------------------------------------- dimensions
HALF_W = 1.06                 # борта нижнего кузова
FENDER_W = 1.12               # крылья над передними колёсами
INNER_X = 0.68                # граница центральной/боковой секций
WHEEL_R = 0.482
WHEEL_Y = WHEEL_R
AXLE_F, AXLE_R = 1.62, -1.66
TRACK_X = 0.935
BOT_Y = 0.55
BELT_Y = 1.30

CAB_W = 1.04                  # борта кабины (вертикальные, броня)
ZF_B, ZF_T = 0.88, 0.66       # лобовое стекло: низ / верх
YB, YT = BELT_Y, 1.92
Z_ROOF_R = -1.50              # конец плоской крыши
Z_REAR = -2.32

HATCH_Z = -0.55
HATCH_HOLE_R = 0.47
RING_IN, RING_OUT = 0.44, 0.57
RING_TOP = YT + 0.10
LID_R = 0.43
HINGE_Z = HATCH_Z - 0.455
HINGE_Y = RING_TOP + 0.012
HATCH_OPEN_DEG = 110.0

HOOD_Z0, HOOD_Z1 = 0.86, 2.18     # капот: от лобового стекла до переднего края
HOOD_Y0, HOOD_Y1 = 1.33, 1.10     # высота центральной части капота
FEND_Y0, FEND_Y1 = 1.29, 1.05     # высота крыльев


def windshield_z(y):
    return ZF_B + (ZF_T - ZF_B) * (y - YB) / (YT - YB)


def hood_y(z):
    return HOOD_Y0 + (HOOD_Y1 - HOOD_Y0) * (z - HOOD_Z0) / (HOOD_Z1 - HOOD_Z0)


def fender_y(z):
    return FEND_Y0 + (FEND_Y1 - FEND_Y0) * (z - HOOD_Z0) / (2.14 - HOOD_Z0)


def rear_arch(zc):
    return [(zc - 0.56, BOT_Y), (zc - 0.53, 0.92), (zc - 0.37, 1.07), (zc + 0.37, 1.07),
            (zc + 0.53, 0.92), (zc + 0.58, BOT_Y)]


# --------------------------------------------------------------------------- body parts
def build_body():
    parts = {m: Geo() for m in MATERIALS}

    def add2(pair, mat_main="paint", mat_alt="dark"):
        parts[mat_main] += pair[0]
        parts[mat_alt] += pair[1]

    def both_sides(pair, mat_main="paint", mat_alt="dark"):
        add2(pair, mat_main, mat_alt)
        add2((pair[0].transformed(MIRROR_X), pair[1].transformed(MIRROR_X)), mat_main, mat_alt)

    # --- боковые секции нижнего кузова (двери снизу + задние арки)
    ra = rear_arch(AXLE_R)
    prof = [(HOOD_Z0, BOT_Y), (HOOD_Z0, BELT_Y), (Z_REAR, BELT_Y), (Z_REAR, 0.64), (Z_REAR + 0.05, BOT_Y)]
    a0 = len(prof)
    prof += ra
    arch_edges = set(range(a0, a0 + len(ra) - 1))
    both_sides(extrude_x2(prof, INNER_X, HALF_W, alt=arch_edges))

    # --- центральная «ванна» с полом салона
    tub = [(HOOD_Z0, BOT_Y), (HOOD_Z0, BELT_Y), (HOOD_Z0 - 0.05, 0.82), (Z_REAR + 0.06, 0.82),
           (Z_REAR + 0.02, BELT_Y), (Z_REAR, BELT_Y), (Z_REAR, 0.64), (Z_REAR + 0.05, BOT_Y)]
    add2(extrude_x2(tub, -INNER_X, INNER_X))

    # --- передние крылья: широкие, с высоко вырезанной аркой
    zc = AXLE_F
    fend = [(2.20, 0.76), (2.15, FEND_Y1), (HOOD_Z0, FEND_Y0), (HOOD_Z0, BOT_Y), (zc - 0.60, BOT_Y),
            (zc - 0.56, 0.93), (zc - 0.38, 1.075), (zc + 0.30, 1.075), (zc + 0.50, 0.86), (2.17, 0.77)]
    both_sides(extrude_x2(fend, 0.64, FENDER_W, alt={4, 5, 6, 7, 8}))

    # --- центральная часть капота + решётка
    hood = [(2.24, 0.62), (2.24, 1.05), (2.19, HOOD_Y1), (HOOD_Z0, HOOD_Y0), (HOOD_Z0, BOT_Y), (2.10, BOT_Y)]
    add2(extrude_x2(hood, -0.66, 0.66))
    for k in range(13):
        x = -0.54 + k * 0.09
        parts["dark"] += box(x - 0.026, x + 0.026, 0.68, 0.99, 2.240, 2.246)
    parts["dark"] += box(-0.60, 0.60, 0.635, 0.655, 2.240, 2.246)

    # жалюзи воздухозаборника на капоте (смещены к пассажиру)
    slope = math.atan2(HOOD_Y0 - HOOD_Y1, HOOD_Z1 - HOOD_Z0)
    zc_v = 1.20
    base = chain(T(-0.18, hood_y(zc_v) + 0.004, zc_v), Rx(slope))
    parts["dark"] += cbox(0, 0, 0, 0.70, 0.006, 0.42).transformed(base)
    for k in range(8):
        parts["paint"] += cbox(0, 0.012, -0.18 + k * 0.05, 0.66, 0.016, 0.018).transformed(base)
    # стыки капота и крыльев
    for s in (1, -1):
        parts["dark"] += tube((s * 0.655, hood_y(HOOD_Z0) - 0.03, HOOD_Z0 + 0.02),
                              (s * 0.655, hood_y(2.16) - 0.03, 2.16), 0.008, 6)

    # фары в крыльях, решётки фар, поворотники
    fn = np.array([0.0, (2.20 - 2.15), (FEND_Y1 - 0.76)])
    fn /= np.linalg.norm(fn)
    tilt = math.atan2(fn[1], fn[2])
    for s in (1, -1):
        M = chain(T(s * 0.89, 0.92, 2.183), Rx(-tilt), AX_TO_Z)
        parts["dark"] += lathe([(0.105, -0.02), (0.105, 0.03), (0.088, 0.035)], seg=32).transformed(M)
        parts["light"] += lathe([(0.088, 0.025), (0.06, 0.034), (0.0, 0.038)], seg=32).transformed(M)
        parts["amber"] += cbox(s * 0.74, 0.86, 2.20, 0.08, 0.06, 0.03)
        # резиновые Т-замки капота на боках крыльев
        parts["rubber"] += cbox(s * (FENDER_W + 0.008), 0.97, 2.02, 0.016, 0.16, 0.035)
        parts["rubber"] += cbox(s * (FENDER_W + 0.008), 1.04, 2.02, 0.016, 0.03, 0.12)
        # затемнённая маскировочная фара над поворотником
        parts["dark"] += cbox(s * 0.74, 0.96, 2.205, 0.07, 0.05, 0.03)

    # --- кабина: полая оболочка (без пола и без крыши — крыша отдельно, с люком)
    cab = [(ZF_B, YB), (ZF_T, YT), (Z_ROOF_R, YT), (Z_REAR + 0.04, 1.62), (Z_REAR, YB)]
    # рёбра: 0 лобовое, 1 крыша (отдельно, с люком), 2 скос, 3 зад, 4 низ (открыт в салон)
    g, _ = extrude_x2(cab, -CAB_W, CAB_W, skip={1, 4})
    parts["paint"] += g
    parts["paint"] += roof_with_hole(YT, (0, 1, 0))
    parts["interior"] += roof_with_hole(YT - 0.035, (0, -1, 0))
    for s in (1, -1):  # водостоки
        parts["dark"] += box(s * CAB_W - 0.012, s * CAB_W + 0.012, YT - 0.02, YT + 0.012, Z_ROOF_R, ZF_T)
    parts["dark"] += box(-CAB_W, CAB_W, YT - 0.02, YT + 0.012, ZF_T - 0.012, ZF_T + 0.02)

    # лобовое стекло: две плоские половины в толстой раме
    wn = np.array([0.0, ZF_B - ZF_T, YT - YB])
    wn /= np.linalg.norm(wn)

    def wpt(x, t):
        y = YB + (YT - YB) * t
        return np.array([x, y, windshield_z(y)])
    for s in (1, -1):
        q = [wpt(s * 0.06, 0.13), wpt(s * 0.95, 0.13), wpt(s * 0.95, 0.92), wpt(s * 0.06, 0.92)]
        qd = [wpt(s * 0.045, 0.11), wpt(s * 0.97, 0.11), wpt(s * 0.97, 0.94), wpt(s * 0.045, 0.94)]
        parts["dark"] += plane_quad(qd, wn, 0.004)
        parts["glass"] += plane_quad(q, wn, 0.008)
        for xw in (s * 0.50,):   # дворники
            p = wpt(xw, 0.12)
            parts["dark"] += tube(p + wn * 0.02, wpt(xw - s * 0.05, 0.55) + wn * 0.02, 0.008, 6)
    # козырёк над стеклом
    parts["paint"] += box(-CAB_W, CAB_W, YT - 0.05, YT, ZF_T - 0.02, ZF_T + 0.05)

    # двери: бронеплиты с маленькими окнами и X-рёбрами
    for s in (1, -1):
        xa, xb = CAB_W, CAB_W + 0.045
        y_top = 1.88
        front = [(0.84, 0.60), (0.84, 1.30), (windshield_z(y_top) - 0.03, y_top), (-0.27, y_top), (-0.27, 0.60)]
        rear = [(-0.31, 0.60), (-0.31, y_top), (-1.02, y_top), (-1.02, 0.60)]
        for poly in (front, rear):
            ccw = poly[::-1] if sum(_area2((0, 0), poly[i], poly[(i + 1) % len(poly)])
                                    for i in range(len(poly))) < 0 else poly
            g, _ = extrude_x2(ccw, xa, xb)
            parts["paint"] += g if s > 0 else g.transformed(MIRROR_X)
        xo = s * (xb + 0.002)

        def win(zf_fn, z_back, y0=1.42, y1=1.80):
            return [(xo, y0, zf_fn(y0)), (xo, y0, z_back), (xo, y1, z_back), (xo, y1, zf_fn(y1))]
        f_win = win(lambda y: windshield_z(y) - 0.15, -0.16)
        r_win = win(lambda y: -0.43, -0.92)
        for w in (f_win, r_win):
            w = np.array(w)
            c = w.mean(0)
            frame = c + (w - c) * np.array([1, 1.16, 1.10])
            parts["dark"] += face(frame, (s, 0, 0))
            parts["glass"] += face(w + np.array([s * 0.003, 0, 0]), (s, 0, 0))
        # X-рёбра на нижних панелях
        for z0, z1 in ((-0.20, 0.76), (-0.95, -0.38)):
            y0, y1 = 0.68, 1.26
            zc_, yc_ = (z0 + z1) / 2, (y0 + y1) / 2
            L = math.hypot(z1 - z0, y1 - y0)
            ang = math.atan2(y1 - y0, z1 - z0)
            for a in (ang, -ang):
                parts["paint"] += cbox(0, 0, 0, 0.012, 0.035, L).transformed(
                    chain(T(s * (xb + 0.006), yc_, zc_), Rx(-a)))
            for (pa, pb) in (((z0, y0), (z1, y0)), ((z0, y1), (z1, y1)), ((z0, y0), (z0, y1)), ((z1, y0), (z1, y1))):
                parts["paint"] += tube((s * (xb + 0.004), pa[1], pa[0]), (s * (xb + 0.004), pb[1], pb[0]), 0.012, 6)
        # петли и ручки
        for zh in (0.80, -0.35):
            for yh in (0.80, 1.62):
                parts["dark"] += cbox(s * (xb + 0.012), yh, zh, 0.03, 0.10, 0.06)
        for zh in (-0.22, -0.96):
            parts["dark"] += cbox(s * (xb + 0.015), 1.34, zh, 0.03, 0.035, 0.12)
        # стойка B и щель
        parts["dark"] += box(s * CAB_W - 0.01, s * (CAB_W + 0.03), 0.60, y_top, -0.31, -0.27)
        # зеркала на кронштейнах
        p0 = np.array([s * (CAB_W + 0.04), 1.42, 0.80])
        p1 = np.array([s * (CAB_W + 0.24), 1.48, 0.80])
        parts["dark"] += tube(p0, p1, 0.014, 8)
        parts["dark"] += tube(p1, p1 + np.array([0, 0.22, 0]), 0.012, 8)
        parts["dark"] += cbox(s * (CAB_W + 0.27), 1.62, 0.80, 0.05, 0.28, 0.19)
        parts["glass"] += cbox(s * (CAB_W + 0.27), 1.62, 0.773, 0.044, 0.25, 0.004)
        # бортовая панель грузового отсека (без окна) — рёбра жёсткости
        for zr in (-1.30, -1.80):
            parts["paint"] += cbox(s * (CAB_W + 0.006), 1.60, zr, 0.012, 0.50, 0.03)
        # порог-подножка
        parts["dark"] += box(s * HALF_W - 0.02 if s > 0 else -HALF_W - 0.03,
                             HALF_W + 0.03 if s > 0 else -HALF_W + 0.02, 0.55, 0.59, -1.02, 0.84)

    # задняя стенка: фонари, бампер, фаркоп
    for s in (1, -1):
        parts["red"] += cbox(s * 0.90, 1.08, Z_REAR - 0.012, 0.16, 0.10, 0.02)
        parts["amber"] += cbox(s * 0.90, 0.97, Z_REAR - 0.012, 0.16, 0.06, 0.02)
        parts["metal"] += cbox(s * 0.62, 0.50, Z_REAR - 0.14, 0.05, 0.10, 0.06)
    parts["paint"] += box(-1.04, 1.04, 0.50, 0.68, Z_REAR - 0.12, Z_REAR)
    parts["dark"] += box(-0.16, 0.16, 0.46, 0.58, Z_REAR - 0.18, Z_REAR - 0.12)
    parts["dark"] += box(-0.55, 0.55, 1.40, 1.55, Z_REAR - 0.006, Z_REAR + 0.001)  # петли заднего борта

    # передний бампер + кенгурятник
    parts["paint"] += box(-1.10, 1.10, 0.50, 0.68, 2.24, 2.38)
    for s in (1, -1):
        parts["metal"] += cbox(s * 0.66, 0.56, 2.40, 0.05, 0.11, 0.06)
    gz = 2.44
    xs = (-1.00, -0.62, -0.30, 0.30, 0.62, 1.00)
    for x in xs:
        parts["dark"] += tube((x, 0.68, gz - 0.04), (x, 1.13, gz), 0.028)
    parts["dark"] += tube((-1.00, 1.13, gz), (1.00, 1.13, gz), 0.028)
    parts["dark"] += tube((-1.00, 0.88, gz - 0.02), (1.00, 0.88, gz - 0.02), 0.024)
    for s in (1, -1):
        parts["dark"] += tube((s * 1.00, 1.13, gz), (s * 1.06, 1.06, 2.16), 0.026)
        parts["dark"] += tube((s * 1.00, 0.88, gz - 0.02), (s * 1.06, 0.84, 2.20), 0.022)
        parts["dark"] += cbox(s * 0.46, 0.66, 2.40, 0.10, 0.05, 0.10)

    # рама, мосты, редукторы, выхлоп
    for s in (1, -1):
        parts["dark"] += box(s * 0.40 - 0.05, s * 0.40 + 0.05, 0.38, 0.55, -2.25, 2.20)
    for zc in (AXLE_F, AXLE_R):
        parts["dark"] += cylinder_x(0.055, -0.62, 0.62, 16).transformed(T(0, WHEEL_Y + 0.09, zc))
        parts["dark"] += cbox(0, WHEEL_Y + 0.09, zc, 0.32, 0.28, 0.28)
        for s in (1, -1):
            parts["dark"] += cbox(s * 0.66, WHEEL_Y + 0.04, zc, 0.10, 0.28, 0.24)
            parts["dark"] += tube((s * 0.55, WHEEL_Y + 0.10, zc + 0.10 * s), (s * 0.30, 0.90, zc), 0.035)
    parts["dark"] += tube((0, 0.45, -1.4), (0, 0.45, 1.4), 0.04)
    parts["metal"] += tube((-0.85, 0.47, -1.9), (-0.85, 0.47, -2.45), 0.04)

    # антенна на заднем углу
    parts["dark"] += cbox(CAB_W + 0.04, 1.55, -2.12, 0.08, 0.12, 0.10)
    parts["dark"] += tube((CAB_W + 0.04, 1.60, -2.12), (CAB_W + 0.14, 3.20, -2.30), 0.007, 6)

    # кольцо люка и шарнир
    ring = lathe([(RING_IN, -0.035), (RING_OUT, -0.035), (RING_OUT, 0.06), (RING_OUT - 0.02, 0.095),
                  (RING_IN + 0.02, 0.10), (RING_IN, 0.08), (RING_IN, -0.035)], seg=64, smooth_deg=35)
    parts["paint"] += ring.transformed(chain(T(0, YT, HATCH_Z), AX_TO_Y))
    for s in (1, -1):
        parts["dark"] += cbox(s * 0.20, RING_TOP + 0.006, HINGE_Z - 0.005, 0.07, 0.04, 0.06)
    # крепления на кольце (без оружия)
    for a in (0.35, -0.35, math.pi / 2, -math.pi / 2):
        x, z = RING_OUT * math.sin(a), HATCH_Z + RING_OUT * math.cos(a)
        parts["dark"] += cbox(x, YT + 0.05, z, 0.06, 0.08, 0.06)
    return parts


def roof_with_hole(y, hint):
    """Прямоугольник крыши с круглым отверстием (кольцевая лента между окружностью и контуром)."""
    xmin, xmax, zmin, zmax = -CAB_W, CAB_W, Z_ROOF_R, ZF_T
    cx, cz = 0.0, HATCH_Z
    corners = [(xmax, zmax), (xmin, zmax), (xmin, zmin), (xmax, zmin)]
    angs = set(math.atan2(z - cz, x - cx) % (2 * math.pi) for x, z in corners)
    n = 72
    angs |= {2 * math.pi * k / n for k in range(n)}
    angs = sorted(angs)

    def outer(a):
        dx, dz = math.cos(a), math.sin(a)
        ts = []
        if abs(dx) > 1e-9:
            ts += [(xmax - cx) / dx, (xmin - cx) / dx]
        if abs(dz) > 1e-9:
            ts += [(zmax - cz) / dz, (zmin - cz) / dz]
        t = min(t for t in ts if t > 0)
        return cx + dx * t, cz + dz * t

    g = Geo()
    for i in range(len(angs)):
        a, b = angs[i], angs[(i + 1) % len(angs)]
        oa, ob = outer(a), outer(b)
        ia = (cx + HATCH_HOLE_R * math.cos(a), cz + HATCH_HOLE_R * math.sin(a))
        ib = (cx + HATCH_HOLE_R * math.cos(b), cz + HATCH_HOLE_R * math.sin(b))
        g += face([(ia[0], y, ia[1]), (oa[0], y, oa[1]), (ob[0], y, ob[1]), (ib[0], y, ib[1])], hint)
    return g


def build_interior():
    parts = {m: Geo() for m in MATERIALS}
    parts["interior"] += box(-1.00, 1.00, 1.14, 1.40, 0.60, 0.80)          # приборная панель
    parts["dark"] += box(0.18, 0.72, 1.33, 1.41, 0.60, 0.66)
    parts["interior"] += box(-0.22, 0.22, 0.82, 1.16, -1.45, 0.82)         # широкий тоннель
    parts["dark"] += cbox(0.0, 1.26, 0.15, 0.32, 0.18, 0.26)               # радиостанция
    for zc in (-0.02, -0.98):
        for s in (1, -1):
            x = s * 0.47
            parts["seat"] += cbox(x, 1.02, zc, 0.44, 0.12, 0.46)
            parts["interior"] += cbox(x, 0.90, zc, 0.36, 0.16, 0.36)
            back = cbox(0, 0.30, 0, 0.44, 0.60, 0.10)
            parts["seat"] += back.transformed(chain(T(x, 1.05, zc - 0.25), Rx(-0.20)))
    wheel = lathe([(0.17 + 0.022 * math.cos(a), 0.022 * math.sin(a))
                   for a in np.linspace(0, 2 * math.pi, 13)], seg=40, smooth_deg=60)
    M = chain(T(0.47, 1.40, 0.46), Rx(-0.95), AX_TO_Z)
    parts["seat"] += wheel.transformed(M)
    parts["seat"] += cylinder_x(0.02, -0.17, 0.17, 8).transformed(M)
    parts["dark"] += cylinder_x(0.03, 0.0, 0.30, 10).transformed(chain(M, Ry(math.pi)))
    parts["seat"] += cbox(0, 1.08, HATCH_Z, 0.62, 0.03, 0.14)              # подножка стрелка
    for s in (1, -1):
        parts["dark"] += cbox(s * 0.42, 0.95, -1.80, 0.32, 0.26, 0.50)     # ящики в отсеке
    return parts


def build_wheel():
    """Колесо с осью вдоль X; внешняя сторона = +X."""
    parts = {m: Geo() for m in MATERIALS}
    tire = [(0.245, -0.160), (0.32, -0.176), (0.39, -0.178), (0.43, -0.168), (0.452, -0.145),
            (0.458, -0.11), (0.458, 0.11), (0.452, 0.145), (0.43, 0.168), (0.39, 0.178), (0.32, 0.176),
            (0.245, 0.160)]
    parts["rubber"] += lathe(tire, seg=64, smooth_deg=45)
    nblk = 26
    for k in range(nblk):
        for row, hc in ((0, -0.075), (1, 0.075)):
            phi = 2 * math.pi * (k + 0.5 * row) / nblk
            # основной блок протектора, слегка под углом (ёлочка)
            blk = cbox(0, 0, 0, 0.14, 0.028, 0.075).transformed(Ry(0.25 if row else -0.25))
            parts["rubber"] += blk.transformed(chain(Rx(phi), T(hc, 0.466, 0)))
            # плечевые грунтозацепы на боковине
            sh = cbox(0, 0, 0, 0.022, 0.07, 0.06)
            parts["rubber"] += sh.transformed(chain(Rx(phi), T(0.17 if row else -0.17, 0.43, 0)))
    rim = [(0.0, -0.12), (0.235, -0.12), (0.252, -0.15), (0.252, 0.152), (0.236, 0.152), (0.228, 0.10),
           (0.14, 0.085), (0.118, 0.122), (0.0, 0.13)]
    parts["rim"] += lathe(rim, seg=48, smooth_deg=30)
    for k in range(8):
        a = 2 * math.pi * k / 8
        parts["metal"] += cylinder_x(0.014, 0.085, 0.118, 8).transformed(
            T(0, 0.165 * math.cos(a), 0.165 * math.sin(a)))
        a2 = a + math.pi / 8
        parts["rubber"] += cylinder_x(0.022, 0.093, 0.097, 12).transformed(
            T(0, 0.205 * math.cos(a2), 0.205 * math.sin(a2)))
    for k in range(12):
        a = 2 * math.pi * (k + 0.5) / 12
        parts["metal"] += cylinder_x(0.010, 0.148, 0.160, 6).transformed(
            T(0, 0.240 * math.cos(a), 0.240 * math.sin(a)))
    parts["rim"] += lathe([(0.075, 0.13), (0.075, 0.16), (0.05, 0.17), (0.0, 0.172)], seg=24)
    return parts


def build_hatch_lid():
    """Крышка люка в локальных координатах шарнира (ось шарнира = локальная X)."""
    parts = {m: Geo() for m in MATERIALS}
    lid = lathe([(0.0, -0.012), (LID_R, -0.012), (LID_R, 0.022), (LID_R - 0.02, 0.036),
                 (0.25, 0.046), (0.0, 0.05)], seg=64, smooth_deg=35)
    off = T(0, 0, HATCH_Z - HINGE_Z)
    parts["paint"] += lid.transformed(chain(off, AX_TO_Y))
    parts["interior"] += lathe([(0.0, -0.0125), (LID_R - 0.04, -0.0125)], seg=48).transformed(
        chain(off, T(0, -0.001, 0), AX_TO_Y, Rx(math.pi)))
    dz = HATCH_Z - HINGE_Z
    parts["dark"] += cbox(0, 0.075, dz + 0.20, 0.24, 0.02, 0.02)
    for s in (1, -1):
        parts["dark"] += cbox(s * 0.11, 0.06, dz + 0.20, 0.02, 0.03, 0.02)
        parts["dark"] += cbox(s * 0.20, 0.012, 0.03, 0.06, 0.02, 0.10)
    parts["dark"] += cbox(0, -0.035, dz + 0.05, 0.20, 0.02, 0.02)
    parts["metal"] += cylinder_x(0.014, -0.25, 0.25, 12)
    for a in (-0.6, 0.0, 0.6):
        parts["glass"] += cbox(0.30 * math.sin(a), 0.065, dz + 0.30 * math.cos(a) - 0.02, 0.07, 0.03, 0.012)
    return parts


# --------------------------------------------------------------------------- camo texture
CAMO_SCALE = 0.30      # повторов текстуры на метр


def periodic_field(n, sigma, rng):
    f = np.fft.fft2(rng.standard_normal((n, n)))
    k = np.fft.fftfreq(n)
    k2 = k[:, None] ** 2 + k[None, :] ** 2
    field = np.real(np.fft.ifft2(f * np.exp(-2 * (math.pi ** 2) * k2 * sigma ** 2)))
    return (field - field.mean()) / field.std()


def make_woodland(n=1024, seed=7):
    """Оригинальный лесной 4-цветный камуфляж, бесшовный (периодический шум)."""
    rng = np.random.default_rng(seed)
    green = np.array([62, 74, 44])
    brown = np.array([78, 60, 40])
    black = np.array([26, 26, 22])
    khaki = np.array([128, 116, 84])
    A = periodic_field(n, 46, rng) + 0.35 * periodic_field(n, 12, rng)
    B = periodic_field(n, 38, rng) + 0.30 * periodic_field(n, 9, rng)
    C = periodic_field(n, 60, rng)
    D = periodic_field(n, 20, rng) + 0.3 * periodic_field(n, 6, rng)
    img = np.tile(green, (n, n, 1)).astype(float)

    def paint(mask_soft, col):
        m = np.clip(mask_soft, 0, 1)[..., None]
        img[:] = img * (1 - m) + col * m

    paint((A - 0.10) * 6 + 0.5, brown)
    paint((D - 1.85) * 6 + 0.5, khaki)
    paint((0.30 - np.abs(B)) * 12 * (C > -0.4) + 0.0, black)
    return np.clip(img, 0, 255).astype(np.uint8)


def compute_uv(g):
    """Кубическая проекция: UV по двум осям, перпендикулярным главной оси нормали."""
    P, N = g.P, g.N
    uv = np.zeros((len(P), 2))
    ax = np.argmax(np.abs(N), axis=1)
    sgn = np.sign(N[np.arange(len(N)), ax])
    for a, (u, v) in ((0, (2, 1)), (1, (0, 2)), (2, (0, 1))):
        m = ax == a
        uu, vv = P[m, u], P[m, v]
        uu = np.where(sgn[m] > 0, uu, -uu + 0.37)
        uv[m, 0] = uu * CAMO_SCALE + 0.13 * a
        uv[m, 1] = -vv * CAMO_SCALE + 0.29 * a
    return uv


def dirt_colors(g):
    y = g.P[:, 1]
    t = np.clip((y - 0.45) / 0.75, 0, 1) ** 0.8
    dirt = np.array(srgb_to_linear((0.80, 0.72, 0.60)))
    c = dirt[None, :] * (1 - t[:, None]) + t[:, None]
    return np.hstack([c, np.ones((len(y), 1))])


# --------------------------------------------------------------------------- export
def clean(parts):
    return {m: g for m, g in parts.items() if len(g.I)}


def png_bytes(img):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def write_gltf(path, meshes, nodes, scene_roots, camo_png):
    mat_names = list(MATERIALS.keys())
    materials = []
    for name in mat_names:
        rgb, metal, rough, extra = MATERIALS[name]
        pbr = {"baseColorFactor": [*srgb_to_linear(rgb), extra.get("alpha", 1.0)],
               "metallicFactor": metal, "roughnessFactor": rough}
        if name == "paint":
            pbr["baseColorFactor"] = [1, 1, 1, 1]
            pbr["baseColorTexture"] = {"index": 0}
        m = {"name": name, "doubleSided": True, "pbrMetallicRoughness": pbr}
        if "alpha" in extra:
            m["alphaMode"] = "BLEND"
        if "emissive" in extra:
            m["emissiveFactor"] = list(extra["emissive"])
        materials.append(m)

    blob = bytearray()
    views, accessors, gmeshes = [], [], []

    def add_view(data, target):
        while len(blob) % 4:
            blob.append(0)
        off = len(blob)
        blob.extend(data)
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": target})
        return len(views) - 1

    def add_acc(arr, ctype, typ, target, minmax=False):
        v = add_view(arr.tobytes(), target)
        a = {"bufferView": v, "componentType": ctype, "count": len(arr), "type": typ}
        if minmax:
            a["min"], a["max"] = arr.min(0).tolist(), arr.max(0).tolist()
        accessors.append(a)
        return len(accessors) - 1

    mesh_index = {}
    for mname, parts in meshes:
        prims = []
        for mat, g in parts.items():
            attrs = {"POSITION": add_acc(g.P.astype(np.float32), 5126, "VEC3", 34962, True),
                     "NORMAL": add_acc(g.N.astype(np.float32), 5126, "VEC3", 34962),
                     "TEXCOORD_0": add_acc(compute_uv(g).astype(np.float32), 5126, "VEC2", 34962)}
            if mat in ("paint", "rubber", "rim"):
                attrs["COLOR_0"] = add_acc(dirt_colors(g).astype(np.float32), 5126, "VEC4", 34962)
            ai = add_acc(g.I.astype(np.uint32).ravel(), 5125, "SCALAR", 34963)
            prims.append({"attributes": attrs, "indices": ai, "material": mat_names.index(mat)})
        mesh_index[mname] = len(gmeshes)
        gmeshes.append({"name": mname, "primitives": prims})

    gnodes = []
    for n in nodes:
        n = dict(n)
        if "mesh" in n:
            n["mesh"] = mesh_index[n["mesh"]]
        gnodes.append(n)

    gltf = {
        "asset": {"version": "2.0", "generator": "RF_Humvee generate_humvee.py"},
        "scene": 0,
        "scenes": [{"name": "Scene", "nodes": scene_roots}],
        "nodes": gnodes,
        "meshes": gmeshes,
        "materials": materials,
        "textures": [{"sampler": 0, "source": 0, "name": "camo_woodland"}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}],
        "images": [{"name": "camo_woodland", "mimeType": "image/png",
                    "uri": "data:image/png;base64," + base64.b64encode(camo_png).decode()}],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(blob),
                     "uri": "data:application/octet-stream;base64," + base64.b64encode(bytes(blob)).decode()}],
        "extras": {"hatch": {"node": "hatch_roof", "axis": "x", "openAngleDeg": -HATCH_OPEN_DEG}},
    }
    with open(path, "w") as f:
        json.dump(gltf, f, separators=(",", ":"))


def write_obj(path, objects, axis_points, tex_name):
    mtl_path = os.path.splitext(path)[0] + ".mtl"
    with open(mtl_path, "w") as f:
        for name, (rgb, metal, rough, extra) in MATERIALS.items():
            f.write(f"newmtl {name}\nKd {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f}\n")
            f.write(f"Ns {max(1.0, (1 - rough) * 200):.1f}\nd {extra.get('alpha', 1.0):.3f}\n")
            if "emissive" in extra:
                e = extra["emissive"]
                f.write(f"Ke {e[0]:.3f} {e[1]:.3f} {e[2]:.3f}\n")
            if name == "paint":
                f.write(f"Kd 1 1 1\nmap_Kd {tex_name}\n")
            f.write("\n")
    vb = 1
    with open(path, "w") as f:
        f.write("# RF_Humvee — сгенерировано generate_humvee.py; Y вверх, +Z вперёд, метры\n")
        f.write(f"mtllib {os.path.basename(mtl_path)}\n")
        for oname, parts in objects:
            f.write(f"o {oname}\n")
            for mat, g in parts.items():
                uv = compute_uv(g)
                for p in g.P:
                    f.write(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}\n")
                for t in uv:
                    f.write(f"vt {t[0]:.5f} {1 - t[1]:.5f}\n")
                for n in g.N:
                    f.write(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n")
                f.write(f"usemtl {mat}\n")
                for a, b, c in g.I:
                    f.write(f"f {a+vb}/{a+vb}/{a+vb} {b+vb}/{b+vb}/{b+vb} {c+vb}/{c+vb}/{c+vb}\n")
                vb += len(g.P)
        for oname, pts in axis_points:
            f.write(f"o {oname}\n")
            for p in pts:
                f.write(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}\n")
            f.write(f"l {' '.join(str(vb + i) for i in range(len(pts)))}\n")
            vb += len(pts)


def transform_parts(parts, M):
    return {m: g.transformed(M) for m, g in parts.items()}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    body = clean(build_body())
    interior = clean(build_interior())
    wheel = clean(build_wheel())
    lid = clean(build_hatch_lid())

    camo = make_woodland()
    camo_png = png_bytes(camo)
    with open(os.path.join(OUT_DIR, "humvee_camo_woodland.png"), "wb") as f:
        f.write(camo_png)

    wheels = {  # имя селекции DayZ: (x, z, повернуть на 180°)
        "wheel_1_1": (TRACK_X, AXLE_F, False),   # левое переднее (+X = левый борт)
        "wheel_2_1": (-TRACK_X, AXLE_F, True),   # правое переднее
        "wheel_1_2": (TRACK_X, AXLE_R, False),   # левое заднее
        "wheel_2_2": (-TRACK_X, AXLE_R, True),   # правое заднее
    }
    nodes = [
        {"name": "RF_Humvee", "children": [1, 2, 3, 4, 5, 6, 7]},
        {"name": "body", "mesh": "body"},
        {"name": "interior", "mesh": "interior"},
    ]
    for wname, (x, z, flip) in wheels.items():
        n = {"name": wname, "mesh": "wheel", "translation": [x, WHEEL_Y, z]}
        if flip:
            n["rotation"] = [0.0, 1.0, 0.0, 0.0]
        nodes.append(n)
    nodes.append({"name": "hatch_roof_pivot", "translation": [0.0, HINGE_Y, HINGE_Z], "children": [8]})
    nodes.append({"name": "hatch_roof", "mesh": "hatch_roof"})

    meshes = [("body", body), ("interior", interior), ("wheel", wheel), ("hatch_roof", lid)]
    write_gltf(os.path.join(OUT_DIR, "humvee.gltf"), meshes, nodes, [0], camo_png)

    objs = [("body", body), ("interior", interior)]
    for wname, (x, z, flip) in wheels.items():
        M = chain(T(x, WHEEL_Y, z), Ry(math.pi) if flip else np.eye(4))
        objs.append((wname, transform_parts(wheel, M)))
    objs.append(("hatch_roof", transform_parts(lid, T(0, HINGE_Y, HINGE_Z))))
    axis = [("hatch_roof_axis", [(-0.25, HINGE_Y, HINGE_Z), (0.25, HINGE_Y, HINGE_Z)])]
    write_obj(os.path.join(OUT_DIR, "humvee.obj"), objs, axis, "humvee_camo_woodland.png")

    mem = {
        "hatch_roof_axis": [[-0.25, HINGE_Y, HINGE_Z], [0.25, HINGE_Y, HINGE_Z]],
        "hatch_roof_center": [0.0, RING_TOP, HATCH_Z],
        "hatch_open_angle_deg": HATCH_OPEN_DEG,
        "wheel_centers": {k: [v[0], WHEEL_Y, v[1]] for k, v in wheels.items()},
        "wheel_radius": WHEEL_R,
    }
    with open(os.path.join(OUT_DIR, "memory_points.json"), "w") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)

    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview_template.html")
    if os.path.exists(tpl):
        prev_dir = os.path.join(OUT_DIR, "..", "preview")
        os.makedirs(prev_dir, exist_ok=True)
        with open(os.path.join(OUT_DIR, "humvee.gltf")) as f:
            gl = f.read().replace("</", "<\\/")
        with open(tpl) as f:
            html = f.read().replace("__GLTF__", gl)
        with open(os.path.join(prev_dir, "humvee_preview.html"), "w") as f:
            f.write(html)

    tri = sum(len(g.I) for _, p in meshes for g in p.values())
    tri += 3 * sum(len(g.I) for g in wheel.values())
    print(f"OK: {OUT_DIR}  треугольников ≈ {tri}")


if __name__ == "__main__":
    main()
