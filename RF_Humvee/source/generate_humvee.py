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
    "dark":     ((0.150, 0.160, 0.140), 0.30, 0.70, {}),
    "rubber":   ((0.085, 0.085, 0.088), 0.00, 0.92, {}),
    "rim":      ((0.270, 0.290, 0.190), 0.35, 0.55, {}),
    "metal":    ((0.600, 0.600, 0.580), 0.85, 0.40, {}),
    "glass":    ((0.200, 0.260, 0.280), 0.10, 0.08, {"alpha": 0.45}),
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


# --------------------------------------------------------------------------- dimensions
HALF_W = 1.08                 # половина ширины нижнего кузова
INNER_X = 0.72                # граница центральной/боковой секций
WHEEL_R = 0.475
WHEEL_Y = WHEEL_R
AXLE_F, AXLE_R = 1.58, -1.66
TRACK_X = 0.905
ARCH_R = 0.52
BOT_Y = 0.52
BELT_Y = 1.25

# кабина (жёсткая крыша)
YB, YT = BELT_Y, 1.82
WB, WT = 1.02, 0.95
ZFB, ZFT = 0.85, 0.50         # лобовое стекло: низ / верх
ZRB, ZRT = -2.15, -1.88       # задняя стенка: низ / верх

# люк
HATCH_Z = -0.62
HATCH_HOLE_R = 0.47
RING_IN, RING_OUT = 0.44, 0.56
RING_TOP = YT + 0.10
LID_R = 0.43
HINGE_Z = HATCH_Z - 0.455
HINGE_Y = RING_TOP + 0.012
HATCH_OPEN_DEG = 110.0


def side_x(y):
    """X боковой стенки кабины на высоте y (правый борт +X)."""
    return WB + (WT - WB) * (y - YB) / (YT - YB)


def apillar_z(y):
    return ZFB + (ZFT - ZFB) * (y - YB) / (YT - YB)


def cpillar_z(y):
    return ZRB + (ZRT - ZRB) * (y - YB) / (YT - YB)


def arch_points(zc):
    dy = BOT_Y - WHEEL_Y
    th0 = math.asin(dy / ARCH_R)
    pts = []
    n = 18
    for k in range(n + 1):
        a = (math.pi - th0) + (th0 - (math.pi - th0)) * k / n
        pts.append((zc + ARCH_R * math.cos(a), WHEEL_Y + ARCH_R * math.sin(a)))
    return pts


def hull_profile(with_arches, floor_dip):
    top = [(2.22, 0.64), (2.22, 1.02), (2.17, 1.10), (ZFB, BELT_Y)]
    if floor_dip:
        top += [(ZFB - 0.05, 0.80), (ZRB + 0.05, 0.80), (ZRB, BELT_Y)]
    top += [(-2.30, BELT_Y), (-2.30, 0.60), (-2.24, BOT_Y)]
    if with_arches:
        top += arch_points(AXLE_R) + arch_points(AXLE_F)
    top += [(2.16, 0.56)]
    return top


# --------------------------------------------------------------------------- body parts
def build_body():
    parts = {m: Geo() for m in MATERIALS}

    # нижний кузов: две боковые секции с арками + центральная с проёмом салона
    side = extrude_x(hull_profile(True, False), INNER_X, HALF_W)
    parts["paint"] += side
    parts["paint"] += side.transformed(MIRROR_X)
    parts["paint"] += extrude_x(hull_profile(False, True), -INNER_X, INNER_X)

    # подкрылки (тёмные) — тонкая полоса по контуру арки внутри
    for zc in (AXLE_F, AXLE_R):
        ap = arch_points(zc)
        for s in (1, -1):
            for i in range(len(ap) - 1):
                (za, ya), (zb, yb) = ap[i], ap[i + 1]
                pts = [(s * (INNER_X + 0.01), ya - 0.002, za), (s * (INNER_X + 0.01), yb - 0.002, zb),
                       (s * (HALF_W - 0.004), yb - 0.002, zb), (s * (HALF_W - 0.004), ya - 0.002, za)]
                parts["dark"] += face(pts, (0, -1, 0) if abs(za - zc) < 0.3 else
                                      (0, -(zb - za), (yb - ya)))

    # кабина: лобовая панель, борта, задняя стенка
    FL = np.array([WB, YB, ZFB]); FR = np.array([-WB, YB, ZFB])
    TL = np.array([WT, YT, ZFT]); TR = np.array([-WT, YT, ZFT])
    RBL = np.array([WB, YB, ZRB]); RBR = np.array([-WB, YB, ZRB])
    RTL = np.array([WT, YT, ZRT]); RTR = np.array([-WT, YT, ZRT])
    front_n = _newell([FL, FR, TR, TL]); front_n *= np.sign(front_n[2])
    parts["paint"] += face([FL, FR, TR, TL], front_n)
    for s in (1, -1):
        q = [np.array([s * WB, YB, ZFB]), np.array([s * WB, YB, ZRB]),
             np.array([s * WT, YT, ZRT]), np.array([s * WT, YT, ZFT])]
        n = _newell(q); n *= np.sign(n[0]) * s
        parts["paint"] += face(q, n)
    back_n = _newell([RBL, RBR, RTR, RTL]); back_n *= -np.sign(back_n[2])
    parts["paint"] += face([RBL, RBR, RTR, RTL], back_n)

    # крыша с вырезом под люк (верх + потолок)
    parts["paint"] += roof_with_hole(YT, (0, 1, 0))
    parts["interior"] += roof_with_hole(YT - 0.035, (0, -1, 0))
    # торцы крыши (козырёк)
    parts["paint"] += box(-WT - 0.015, WT + 0.015, YT - 0.03, YT + 0.012, ZFT - 0.02, ZFT + 0.04)

    # лобовое стекло: две половины
    def front_pt(x, t):
        y = YB + (YT - YB) * t
        return np.array([x, y, apillar_z(y)])
    for s in (1, -1):
        t0, t1 = 0.10, 0.90
        w0 = WB + (WT - WB) * t0 - 0.07
        w1 = WB + (WT - WB) * t1 - 0.07
        q = [front_pt(s * 0.045, t0), front_pt(s * w0, t0), front_pt(s * w1, t1), front_pt(s * 0.045, t1)]
        parts["glass"] += plane_quad(q, front_n, 0.006)
    # центральная стойка лобового стекла
    parts["dark"] += plane_quad([front_pt(0.045, 0.05), front_pt(-0.045, 0.05),
                                 front_pt(-0.045, 0.95), front_pt(0.045, 0.95)], front_n, 0.004)
    # дворники
    for xw in (0.45, -0.45):
        p = front_pt(xw, 0.07)
        parts["dark"] += cbox(p[0] + (0.18 if xw > 0 else -0.18), p[1] + 0.015, p[2] + 0.012, 0.42, 0.012, 0.012)

    # боковые стёкла (по два на борт) + щели дверей + ручки
    for s in (1, -1):
        def sp(y, z, out=0.006):
            return np.array([s * (side_x(y) + out), y, z])
        y0, y1 = 1.33, 1.74
        win_f = [sp(y0, apillar_z(y0) - 0.10), sp(y0, -0.20), sp(y1, -0.20), sp(y1, apillar_z(y1) - 0.10)]
        win_r = [sp(y0, -0.40), sp(y0, -1.06), sp(y1, -1.06), sp(y1, -0.40)]
        win_c = [sp(y0 + 0.08, -1.30), sp(y0 + 0.08, cpillar_z(y0 + 0.08) + 0.14),
                 sp(y1 - 0.04, cpillar_z(y1 - 0.04) + 0.14), sp(y1 - 0.04, -1.30)]
        hint = (s, 0.12, 0)
        parts["glass"] += face(win_f, hint)
        parts["glass"] += face(win_r, hint)
        parts["dark"] += face(win_c, hint)  # глухая бронированная панель грузового отсека
        # дверные щели на кабине
        for zg in (-0.30, -1.13):
            parts["dark"] += face([sp(YB, zg - 0.006, 0.004), sp(YB, zg + 0.006, 0.004),
                                   sp(YT - 0.02, zg + 0.006, 0.004), sp(YT - 0.02, zg - 0.006, 0.004)], hint)
        # щель вдоль А-стойки
        parts["dark"] += face([sp(YB, ZFB - 0.06, 0.004), sp(YB, ZFB - 0.048, 0.004),
                               sp(YT - 0.02, apillar_z(YT - 0.02) - 0.048, 0.004),
                               sp(YT - 0.02, apillar_z(YT - 0.02) - 0.06, 0.004)], hint)
        # щели на нижнем кузове
        xo = s * (HALF_W + 0.003)
        for zg in (ZFB - 0.054, -0.30, -1.13):
            parts["dark"] += face([(xo, BOT_Y + 0.05, zg - 0.006), (xo, BOT_Y + 0.05, zg + 0.006),
                                   (xo, BELT_Y - 0.002, zg + 0.006), (xo, BELT_Y - 0.002, zg - 0.006)], (s, 0, 0))
        # ручки дверей
        for zh in (-0.16, -0.99):
            parts["dark"] += cbox(s * (HALF_W + 0.015), 1.12, zh, 0.03, 0.04, 0.16)
        # зеркала
        parts["dark"] += cbox(s * (WB + 0.08), 1.33, ZFB - 0.06, 0.16, 0.025, 0.025)
        parts["dark"] += cbox(s * (WB + 0.17), 1.42, ZFB - 0.06, 0.04, 0.24, 0.16)
        parts["glass"] += cbox(s * (WB + 0.17), 1.42, ZFB - 0.085, 0.034, 0.21, 0.004)

    # заднее стекло
    def back_pt(x, t):
        y = YB + (YT - YB) * t
        return np.array([x, y, cpillar_z(y)])
    parts["glass"] += plane_quad([back_pt(0.55, 0.40), back_pt(-0.55, 0.40),
                                  back_pt(-0.55, 0.85), back_pt(0.55, 0.85)], back_n, 0.006)

    # решётка радиатора
    parts["dark"] += box(-0.60, 0.60, 0.64, 1.00, 2.220, 2.232)
    for k in range(11):
        x = -0.55 + k * 0.11
        parts["paint"] += box(x - 0.022, x + 0.022, 0.64, 1.00, 2.220, 2.245)
    parts["paint"] += box(-0.62, 0.62, 0.995, 1.025, 2.215, 2.245)
    parts["paint"] += box(-0.62, 0.62, 0.62, 0.645, 2.215, 2.245)

    # фары, поворотники
    for s in (1, -1):
        bezel = lathe([(0.115, -0.01), (0.115, 0.03), (0.095, 0.035)], seg=32)
        lens = lathe([(0.095, 0.025), (0.06, 0.032), (0.0, 0.036)], seg=32)
        M = chain(T(s * 0.86, 0.885, 2.22), AX_TO_Z)
        parts["dark"] += bezel.transformed(M)
        parts["light"] += lens.transformed(M)
        parts["amber"] += cbox(s * 0.86, 0.71, 2.232, 0.13, 0.06, 0.03)
        # задние фонари
        parts["red"] += cbox(s * 0.88, 1.00, -2.305, 0.14, 0.12, 0.02)
        parts["amber"] += cbox(s * 0.88, 0.88, -2.305, 0.14, 0.06, 0.02)

    # бамперы
    parts["paint"] += box(-1.10, 1.10, 0.40, 0.60, 2.20, 2.34)
    parts["dark"] += box(-0.30, 0.30, 0.44, 0.56, 2.34, 2.36)  # площадка под лебёдку
    for s in (1, -1):
        parts["metal"] += cbox(s * 0.62, 0.50, 2.37, 0.04, 0.10, 0.06)   # буксирные проушины
        parts["metal"] += cbox(s * 0.62, 0.45, -2.40, 0.04, 0.10, 0.06)
    parts["paint"] += box(-1.06, 1.06, 0.40, 0.60, -2.38, -2.28)
    parts["dark"] += box(-0.18, 0.18, 0.40, 0.50, -2.42, -2.38)  # фаркоп

    # рама, мосты, дифференциалы
    for s in (1, -1):
        parts["dark"] += box(s * 0.40 - 0.05, s * 0.40 + 0.05, 0.36, 0.52, -2.25, 2.15)
    for zc in (AXLE_F, AXLE_R):
        parts["dark"] += cylinder_x(0.055, -0.78, 0.78, 16).transformed(T(0, WHEEL_Y + 0.08, zc))
        parts["dark"] += cbox(0, WHEEL_Y + 0.08, zc, 0.30, 0.26, 0.26)
        for s in (1, -1):  # бортовые редукторы-«портальники»
            parts["dark"] += cbox(s * 0.72, WHEEL_Y + 0.04, zc, 0.10, 0.26, 0.22)
    parts["dark"] += cylinder_x(0.035, -1.4, 1.4, 12).transformed(chain(T(0, 0.45, 0.0), AX_TO_Z))
    # выхлоп
    parts["metal"] += cylinder_x(0.04, 0.0, 0.25, 12).transformed(chain(T(-0.85, 0.45, -2.25), AX_TO_Z,
                                                                          Ry(math.pi)))

    # капот: воздухозаборник и замки
    parts["dark"] += box(-0.50, 0.50, 1.24, 1.255, 0.88, 0.98)
    for s in (1, -1):
        hood_y = 1.10 + (2.17 - 2.05) / (2.17 - ZFB) * (BELT_Y - 1.10)
        parts["dark"] += cbox(s * 0.95, hood_y + 0.01, 2.06, 0.06, 0.03, 0.10)

    # антенна
    parts["dark"] += cbox(0.92, BELT_Y + 0.05, -2.18, 0.10, 0.10, 0.10)
    parts["dark"] += cylinder_x(0.007, 0.0, 1.6, 8).transformed(chain(T(0.92, BELT_Y + 0.10, -2.18),
                                                                       AX_TO_Y, Rz(-0.08)))

    # кольцо люка (неподвижная часть)
    ring = lathe([(RING_IN, -0.035), (RING_OUT, -0.035), (RING_OUT, 0.06), (RING_OUT - 0.02, 0.095),
                  (RING_IN + 0.02, 0.10), (RING_IN, 0.08), (RING_IN, -0.035)], seg=64, smooth_deg=35)
    parts["paint"] += ring.transformed(chain(T(0, YT, HATCH_Z), AX_TO_Y))
    # кронштейны шарнира
    for s in (1, -1):
        parts["dark"] += cbox(s * 0.20, RING_TOP + 0.006, HINGE_Z - 0.005, 0.07, 0.04, 0.06)
    return parts


def roof_with_hole(y, hint):
    """Прямоугольник крыши с круглым отверстием (кольцевая лента между окружностью и контуром)."""
    xmin, xmax, zmin, zmax = -WT, WT, ZRT, ZFT
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
    # приборная панель
    parts["interior"] += box(-0.95, 0.95, 1.12, 1.36, 0.56, 0.78)
    parts["dark"] += box(0.20, 0.70, 1.30, 1.37, 0.56, 0.62)       # щиток приборов
    # центральный тоннель (широкий — как у прототипа)
    parts["interior"] += box(-0.21, 0.21, 0.80, 1.14, -1.40, 0.80)
    parts["dark"] += box(-0.17, 0.17, 1.14, 1.16, -0.30, 0.40)     # консоль/рация
    parts["dark"] += cbox(0.0, 1.24, 0.15, 0.30, 0.16, 0.24)       # радиостанция
    # сиденья
    for zc in (-0.05, -1.00):
        for s in (1, -1):
            x = s * 0.45
            parts["seat"] += cbox(x, 1.00, zc, 0.44, 0.12, 0.46)
            parts["interior"] += cbox(x, 0.88, zc, 0.36, 0.16, 0.36)
            back = cbox(0, 0.30, 0, 0.44, 0.60, 0.10)
            parts["seat"] += back.transformed(chain(T(x, 1.03, zc - 0.25), Rx(-0.20)))
    # руль (водитель слева: +X)
    wheel = lathe([(0.17 + 0.022 * math.cos(a), 0.022 * math.sin(a))
                   for a in np.linspace(0, 2 * math.pi, 13)], seg=40, smooth_deg=60)
    M = chain(T(0.45, 1.38, 0.42), Rx(-0.95), AX_TO_Z)
    parts["seat"] += wheel.transformed(M)
    parts["seat"] += cylinder_x(0.02, -0.17, 0.17, 8).transformed(chain(M, Rz(0)))
    parts["dark"] += cylinder_x(0.03, 0.0, 0.30, 10).transformed(chain(T(0.45, 1.38, 0.42), Rx(-0.95),
                                                                        AX_TO_Z, Ry(math.pi)))
    # ремень/подножка стрелка под люком
    parts["seat"] += cbox(0, 1.05, HATCH_Z, 0.62, 0.03, 0.14)
    # ящик с боеприпасами в грузовом отсеке
    parts["dark"] += cbox(0.40, 0.92, -1.75, 0.30, 0.24, 0.48)
    parts["dark"] += cbox(-0.40, 0.92, -1.75, 0.30, 0.24, 0.48)
    return parts


def build_wheel():
    """Колесо с осью вдоль X; внешняя сторона = +X."""
    parts = {m: Geo() for m in MATERIALS}
    tire = [(0.30, -0.145), (0.37, -0.158), (0.425, -0.152), (0.447, -0.135), (0.458, -0.105),
            (0.460, 0.0), (0.458, 0.105), (0.447, 0.135), (0.425, 0.152), (0.37, 0.158), (0.30, 0.145)]
    parts["rubber"] += lathe(tire, seg=56, smooth_deg=45)
    # протектор
    nblk = 36
    for k in range(nblk):
        for row, hc in ((0, -0.068), (1, 0.068)):
            phi = 2 * math.pi * (k + 0.5 * row) / nblk
            blk = cbox(0, 0, 0, 0.115, 0.024, 0.052)
            parts["rubber"] += blk.transformed(chain(Rx(phi), T(hc, 0.462, 0), Rx(0.0)))
    rim = [(0.0, -0.12), (0.27, -0.12), (0.30, -0.14), (0.30, 0.145), (0.27, 0.145), (0.262, 0.095),
           (0.13, 0.075), (0.11, 0.115), (0.0, 0.122)]
    parts["rim"] += lathe(rim, seg=48, smooth_deg=30)
    # болты ступицы и кольцо beadlock
    for k in range(8):
        a = 2 * math.pi * k / 8
        parts["metal"] += cylinder_x(0.014, 0.075, 0.105, 8).transformed(
            T(0, 0.175 * math.cos(a), 0.175 * math.sin(a)))
    for k in range(12):
        a = 2 * math.pi * (k + 0.5) / 12
        parts["metal"] += cylinder_x(0.011, 0.14, 0.158, 6).transformed(
            T(0, 0.285 * math.cos(a), 0.285 * math.sin(a)))
    parts["metal"] += lathe([(0.075, 0.12), (0.075, 0.15), (0.05, 0.16), (0.0, 0.162)], seg=24)
    return parts


def build_hatch_lid():
    """Крышка люка в локальных координатах шарнира (ось шарнира = локальная X)."""
    parts = {m: Geo() for m in MATERIALS}
    lid = lathe([(0.0, -0.012), (LID_R, -0.012), (LID_R, 0.022), (LID_R - 0.02, 0.036),
                 (0.25, 0.046), (0.0, 0.05)], seg=64, smooth_deg=35)
    off = T(0, 0, HATCH_Z - HINGE_Z)
    parts["paint"] += lid.transformed(chain(off, AX_TO_Y))
    # внутренняя обшивка
    parts["interior"] += lathe([(0.0, -0.0125), (LID_R - 0.04, -0.0125)], seg=48).transformed(
        chain(off, T(0, -0.001, 0), AX_TO_Y, Rx(math.pi)))
    # ручки сверху и снизу
    parts["dark"] += cbox(0, 0.075, HATCH_Z - HINGE_Z + 0.20, 0.24, 0.02, 0.02)
    for s in (1, -1):
        parts["dark"] += cbox(s * 0.11, 0.06, HATCH_Z - HINGE_Z + 0.20, 0.02, 0.03, 0.02)
    parts["dark"] += cbox(0, -0.035, HATCH_Z - HINGE_Z + 0.05, 0.20, 0.02, 0.02)
    # петли
    for s in (1, -1):
        parts["dark"] += cbox(s * 0.20, 0.012, 0.03, 0.06, 0.02, 0.10)
    parts["metal"] += cylinder_x(0.014, -0.25, 0.25, 12)
    # смотровые призмы-перископы
    for a in (-0.6, 0.0, 0.6):
        x = 0.30 * math.sin(a)
        z = HATCH_Z - HINGE_Z + 0.30 * math.cos(a) - 0.0
        parts["glass"] += cbox(x, 0.065, z - 0.02, 0.07, 0.03, 0.012)
    return parts


# --------------------------------------------------------------------------- export
def clean(parts):
    return {m: g for m, g in parts.items() if len(g.I)}


def write_gltf(path, meshes, nodes, scene_roots):
    """meshes: list[(name, {mat: Geo})]; nodes: list[dict] (glTF nodes, mesh index by name)."""
    mat_names = list(MATERIALS.keys())
    materials = []
    for name in mat_names:
        rgb, metal, rough, extra = MATERIALS[name]
        m = {"name": name, "doubleSided": True,
             "pbrMetallicRoughness": {"baseColorFactor": [*srgb_to_linear(rgb), extra.get("alpha", 1.0)],
                                      "metallicFactor": metal, "roughnessFactor": rough}}
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

    mesh_index = {}
    for mname, parts in meshes:
        prims = []
        for mat, g in parts.items():
            P = g.P.astype(np.float32)
            N = g.N.astype(np.float32)
            I = g.I.astype(np.uint32).ravel()
            vp = add_view(P.tobytes(), 34962)
            accessors.append({"bufferView": vp, "componentType": 5126, "count": len(P), "type": "VEC3",
                              "min": P.min(0).tolist(), "max": P.max(0).tolist()})
            ap = len(accessors) - 1
            vn = add_view(N.tobytes(), 34962)
            accessors.append({"bufferView": vn, "componentType": 5126, "count": len(N), "type": "VEC3"})
            an = len(accessors) - 1
            vi = add_view(I.tobytes(), 34963)
            accessors.append({"bufferView": vi, "componentType": 5125, "count": len(I), "type": "SCALAR"})
            ai = len(accessors) - 1
            prims.append({"attributes": {"POSITION": ap, "NORMAL": an}, "indices": ai,
                          "material": mat_names.index(mat)})
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
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(blob),
                     "uri": "data:application/octet-stream;base64," + base64.b64encode(bytes(blob)).decode()}],
        "extras": {"hatch": {"node": "hatch_roof", "axis": "x", "openAngleDeg": -HATCH_OPEN_DEG}},
    }
    with open(path, "w") as f:
        json.dump(gltf, f, separators=(",", ":"))


def write_obj(path, objects, axis_points):
    """objects: list[(name, {mat: Geo})] уже в мировых координатах."""
    mtl_path = os.path.splitext(path)[0] + ".mtl"
    with open(mtl_path, "w") as f:
        for name, (rgb, metal, rough, extra) in MATERIALS.items():
            f.write(f"newmtl {name}\nKd {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f}\n")
            f.write(f"Ns {max(1.0, (1 - rough) * 200):.1f}\nd {extra.get('alpha', 1.0):.3f}\n")
            if "emissive" in extra:
                e = extra["emissive"]
                f.write(f"Ke {e[0]:.3f} {e[1]:.3f} {e[2]:.3f}\n")
            f.write("\n")
    vbase = nbase = 1
    with open(path, "w") as f:
        f.write("# RF_Humvee — сгенерировано generate_humvee.py; Y вверх, +Z вперёд, метры\n")
        f.write(f"mtllib {os.path.basename(mtl_path)}\n")
        for oname, parts in objects:
            f.write(f"o {oname}\n")
            for mat, g in parts.items():
                for p in g.P:
                    f.write(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}\n")
                for n in g.N:
                    f.write(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n")
                f.write(f"usemtl {mat}\n")
                for a, b, c in g.I:
                    f.write(f"f {a + vbase}//{a + nbase} {b + vbase}//{b + nbase} {c + vbase}//{c + nbase}\n")
                vbase += len(g.P)
                nbase += len(g.N)
        for oname, pts in axis_points:
            f.write(f"o {oname}\n")
            for p in pts:
                f.write(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}\n")
            f.write(f"l {' '.join(str(vbase + i) for i in range(len(pts)))}\n")
            vbase += len(pts)


def transform_parts(parts, M):
    return {m: g.transformed(M) for m, g in parts.items()}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    body = clean(build_body())
    interior = clean(build_interior())
    wheel = clean(build_wheel())
    lid = clean(build_hatch_lid())

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
    write_gltf(os.path.join(OUT_DIR, "humvee.gltf"), meshes, nodes, [0])

    objs = [("body", body), ("interior", interior)]
    for wname, (x, z, flip) in wheels.items():
        M = chain(T(x, WHEEL_Y, z), Ry(math.pi) if flip else np.eye(4))
        objs.append((wname, transform_parts(wheel, M)))
    objs.append(("hatch_roof", transform_parts(lid, T(0, HINGE_Y, HINGE_Z))))
    axis = [("hatch_roof_axis", [(-0.25, HINGE_Y, HINGE_Z), (0.25, HINGE_Y, HINGE_Z)])]
    write_obj(os.path.join(OUT_DIR, "humvee.obj"), objs, axis)

    # memory-точки для model.cfg / LOD Memory
    mem = {
        "hatch_roof_axis": [[-0.25, HINGE_Y, HINGE_Z], [0.25, HINGE_Y, HINGE_Z]],
        "hatch_roof_center": [0.0, RING_TOP, HATCH_Z],
        "hatch_open_angle_deg": HATCH_OPEN_DEG,
        "wheel_centers": {k: [v[0], WHEEL_Y, v[1]] for k, v in wheels.items()},
        "wheel_radius": WHEEL_R,
    }
    with open(os.path.join(OUT_DIR, "memory_points.json"), "w") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)

    # интерактивный просмотр: шаблон + встроенный glTF
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
