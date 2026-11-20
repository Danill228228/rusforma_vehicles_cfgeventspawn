"""
Своя модель HMMWV M1025 для мода RF_Humvee — по образцу ванильного M1025 DayZ (Offroad_02).

Модель строится из примитивов (помощники generate_humvee), размеры сняты в игре с ванильного M1025: лучами по его
геометрии (силуэт, крыша, перёд, зад) и через API машины (колёса, места экипажа, точки посадки, фары).
Ванильные модели не копируются; окраска в моде — ванильные текстура и материалы крыши M1025 (ссылками).

Координаты как в генераторе: +X — левый борт (водитель), Y — вверх от земли, +Z — перёд. В игре модель видна
как (-x, y, z) — водитель на -X, как у ванили. Сборка мода импортирует этот модуль вместо генератора:
  build_body() — неподвижный кузов, build_doors() — 4 двери, build_lids() — капот и крышка багажника,
  build_interior() — салон, build_hatch_lid() — крышка люка; ниже константы для LOD, памяти и коллизии.
"""
import math

import numpy as np

from generate_humvee import (AX_TO_Y, AX_TO_Z, MATERIALS, MIRROR_X, Geo, Rx, Ry, T, box, cbox, chain, clean,  # noqa: F401
                             compute_uv, cylinder_x, extrude_x2, face, fix_winding, lathe, periodic_field, plane_quad,
                             roof_with_hole, tube)
from generate_humvee import _area2

# ---------------------------------------------------------------- размеры (м), сняты с ванильного M1025
WHEEL_R = 0.49
WHEEL_Y = WHEEL_R
TRACK_X = 0.99                         # колея (ванильное колесо M1025 ставится в прокси на этом x)
AXLE_F, AXLE_R = 1.60, -1.73           # база 3.33
HALF_W = 1.08                          # борта и двери снаружи
FENDER_W = 1.10                        # крылья
CAB_W = 1.00                           # стойки кабины и проёмы дверей
INNER_X = 0.66                         # граница центральной части (капот, ванна) и бортов
BOT_Y = 0.45                           # низ бортов
FLOOR_Y = 0.55                         # пол салона и низ дверных проёмов
BELT_Y = YB = 1.28                     # линия окон: низ окон, верх задних бортов
YT, CEIL_Y = 1.84, 1.765               # крыша сверху и потолок
ZF_B, ZF_T = 0.80, 0.70                # лобовое стекло: низ (у капота) и верх (у крыши)
WS_Y0 = 1.32                           # низ лобового стекла
FRONT_Z = 2.27                         # передняя панель с решёткой и фарами
Z_REAR = -2.50                         # задняя панель
HOOD_Z0, HOOD_Y0 = 0.80, 1.32          # капот у стекла
HOOD_Z1, HOOD_Y1 = 2.22, 1.14          # капот у решётки
FEND_Y = 0.98                          # шов капота с крыльями и передней панелью: выше — откидывается с капотом
HEADLIGHT_X, HEADLIGHT_Y = 0.56, 0.93
EXHAUST_START, EXHAUST_END = (0.88, 0.40, -0.95), (1.08, 0.38, -1.02)   # слева под порогом перед задним колесом

# крыша: плита от лобового стекла до начала заднего ската, задние наплывы по бокам крышки багажника
ROOF_X, ROOF_Z0, ROOF_Z1 = 1.05, -1.10, 0.70
ROOF_RECT = (-ROOF_X, ROOF_X, ROOF_Z0, ROOF_Z1)
Z_ROOF_R = ROOF_Z0
SH_X_IN, SH_X_OUT = 0.74, 1.08
SH_Z0, SH_Z1, SH_Z_END = -1.05, -2.42, -2.47
TAIL_Y = 1.414                         # верх наплывов у торца
SH_SLOPE = (YT - TAIL_Y) / (ROOF_Z0 - SH_Z1)
SH_R_OUT, SH_R_IN, ROLL_R = 0.11, 0.04, 0.09   # скругления наплывов (снаружи, у крышки) и катаной кромки кормы
TG_Y0, TG_Y1, TG_D = 0.72, 1.18, 0.035  # задний борт: низ, верх, глубина ниши в задней стенке

# люк стрелка
HATCH_Z = -0.30
RING_IN, RING_OUT = 0.48, 0.58
RING_TOP = YT + 0.10
LID_R = RING_OUT - 0.01
HINGE_Z = HATCH_Z - RING_OUT + 0.03
HINGE_Y = RING_TOP + 0.012

# двери: петли на передней кромке, ось вертикальная
DOORS = {"doors_driver": (1, True), "doors_codriver": (-1, True), "doors_cargo1": (1, False), "doors_cargo2": (-1, False)}
DOOR_X = (CAB_W, HALF_W)
DOOR_Y = (FLOOR_Y, CEIL_Y)
DOOR_Z = {True: (-0.27, 0.70), False: (-1.05, -0.33)}
DOOR_XB = HALF_W - 0.01
DOOR_HINGE_Z = {front: z1 for front, (_, z1) in DOOR_Z.items()}

# места экипажа как у ванили (x, z); высота посадки SEAT_Y
SEATS = {"Driver": (0.654, 0.094), "CoDriver": (-0.715, 0.155), "Cargo1": (0.628, -0.716), "Cargo2": (-0.731, -0.716)}
SEAT_Y = 0.81

# капот откидывается вперёд вместе с крыльями (как у M1025), крышка багажника — задней кромкой вверх.
# Селекция: (y, z оси петель вдоль X, угол открытия, рад); минус — задняя кромка вверх.
TRUNK_X = SH_X_IN
LIDS = {"doors_hood": (0.74, FRONT_Z + 0.03, -1.40), "doors_trunk": (YT, ROOF_Z0, -1.22)}


def windshield_z(y):
    return ZF_B + (ZF_T - ZF_B) * (y - WS_Y0) / (CEIL_Y - WS_Y0)


def hood_y(z):
    return HOOD_Y0 + (HOOD_Y1 - HOOD_Y0) * (z - HOOD_Z0) / (HOOD_Z1 - HOOD_Z0)


def sh_top(z):
    return YT - SH_SLOPE * max(0.0, ROOF_Z0 - z)


def arch(zc, y_top=1.04, half=0.56):
    """Колёсная арка (z, y) снизу вверх и обратно: скосы и плоский верх, как у HMMWV."""
    return [(zc + half, BOT_Y), (zc + half - 0.04, 0.88), (zc + half - 0.20, y_top), (zc - half + 0.20, y_top),
            (zc - half + 0.04, 0.88), (zc - half, BOT_Y)]


def both(g):
    h = Geo()
    h += g
    h += g.transformed(MIRROR_X)
    return h


def _ccw(poly):
    return poly[::-1] if sum(_area2((0, 0), poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))) < 0 else poly


def _new():
    return {m: Geo() for m in MATERIALS}


# ---------------------------------------------------------------- скруглённые формы
def fillet2d(pts, radii, seg=6, closed=False):
    """Скругляет углы ломаной в плоскости дугами радиуса radii[i] (0 — острый угол). Радиус уменьшается, если
    дуга не помещается на соседних отрезках; число точек от радиуса не зависит (сечения для loft совпадают)."""
    P = [np.asarray(p, float) for p in pts]
    n = len(P)
    out = []
    for i in range(n):
        if radii[i] <= 0 or (not closed and i in (0, n - 1)):
            out.append(P[i])
            continue
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        u1, u2 = a - b, c - b
        l1, l2 = np.linalg.norm(u1), np.linalg.norm(u2)
        u1, u2 = u1 / l1, u2 / l2
        th = math.acos(float(np.clip(u1 @ u2, -1, 1)))
        if th > math.pi - 1e-3:                                  # отрезки на одной прямой
            out += [b] * (seg + 1)
            continue
        tl = min(radii[i] / math.tan(th / 2), 0.45 * l1, 0.45 * l2)
        r = tl * math.tan(th / 2)
        cen = b + (u1 + u2) / np.linalg.norm(u1 + u2) * (r / math.sin(th / 2))
        p1, p2 = b + u1 * tl, b + u2 * tl
        a1, a2 = math.atan2(p1[1] - cen[1], p1[0] - cen[0]), math.atan2(p2[1] - cen[1], p2[0] - cen[0])
        d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi        # короткая дуга
        out += [cen + r * np.array([math.cos(a1 + d * k / seg), math.sin(a1 + d * k / seg)]) for k in range(seg + 1)]
    return [tuple(p) for p in out]


def loft(rows, inside, closed=False, smooth_deg=40.0):
    """Поверхность по рядам точек одинаковой длины: четырёхугольники между соседними рядами. Нормали — наружу от
    inside (точка или функция от точки), гладкие между гранями с углом меньше smooth_deg: скругления выглядят
    скруглёнными, а не гранёными."""
    R = np.asarray(rows, float)
    nr, m = R.shape[:2]
    mj = m if closed else m - 1
    ins = inside if callable(inside) else (lambda p, q=np.asarray(inside, float): q)
    Nq = np.zeros((nr - 1, mj, 3))
    ok = np.zeros((nr - 1, mj), bool)
    for i in range(nr - 1):
        for j in range(mj):
            j1 = (j + 1) % m
            a, b, c, d = R[i, j], R[i, j1], R[i + 1, j1], R[i + 1, j]
            n = np.cross(c - a, d - b)
            ln = np.linalg.norm(n)
            if ln < 1e-10:
                continue
            n /= ln
            ctr = (a + b + c + d) / 4
            Nq[i, j] = n if n @ (ctr - np.asarray(ins(ctr), float)) >= 0 else -n
            ok[i, j] = True
    cos_t = math.cos(math.radians(smooth_deg))
    g = Geo()
    for i in range(nr - 1):
        for j in range(mj):
            if not ok[i, j]:
                continue
            j1 = (j + 1) % m
            P, N = [], []
            for vi, vj in ((i, j), (i, j1), (i + 1, j1), (i + 1, j)):
                acc = np.zeros(3)
                for qi in (vi - 1, vi):
                    for qj in (((vj - 1) % m, vj) if closed else (vj - 1, vj)):
                        if 0 <= qi < nr - 1 and 0 <= qj < mj and ok[qi, qj] and Nq[qi, qj] @ Nq[i, j] > cos_t:
                            acc += Nq[qi, qj]
                P.append(R[vi, vj])
                N.append(acc / np.linalg.norm(acc))
            g += Geo(P, N, [(0, 1, 2), (0, 2, 3)])
    return fix_winding(g)


def sweep_tube(path, r, ring=8, closed_path=False):
    """Труба радиуса r вдоль ломаной path (пружины, рычаги-дуги, серьги) с гладкими нормалями."""
    path = [np.asarray(p, float) for p in path]
    rows, ref = [], np.array([0.0, 1.0, 0.0])
    for k, p in enumerate(path):
        t = path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]
        t /= np.linalg.norm(t)
        u = np.cross(t, ref)
        if np.linalg.norm(u) < 1e-6:
            u = np.cross(t, np.array([1.0, 0, 0]))
        u /= np.linalg.norm(u)
        v = np.cross(t, u)
        rows.append([p + r * (math.cos(a) * u + math.sin(a) * v) for a in np.linspace(0, 2 * math.pi, ring, endpoint=False)])
    P = np.array(path)
    return loft(rows, lambda c: P[np.argmin(np.linalg.norm(P - c, axis=1))], closed=True, smooth_deg=70)


def d_ring(c, R=0.045, a=0.011, axis_z=False):
    """Серьга: полукольцо вниз в плоскости YZ (или XY при axis_z) и палец между ушками."""
    c = np.asarray(c, float)
    pts = []
    for t in np.linspace(0, math.pi, 10):
        q = np.array([0.0, -R * math.sin(t), R * math.cos(t)])
        pts.append(c + (q[[2, 1, 0]] if axis_z else q))
    g = sweep_tube(pts, a, ring=8)
    e0, e1 = pts[0], pts[-1]
    d = (e1 - e0) / np.linalg.norm(e1 - e0)
    g += tube(e0 - d * 0.015, e1 + d * 0.015, a * 0.8, 8)
    return g


def coil_spring(x, z, y0, y1, R=0.07, wire=0.011, turns=6):
    k = int(turns * 12)
    path = [(x + R * math.cos(2 * math.pi * turns * i / k), y0 + (y1 - y0) * i / k, z + R * math.sin(2 * math.pi * turns * i / k))
            for i in range(k + 1)]
    return sweep_tube(path, wire, ring=6)


# ---------------------------------------------------------------- кузов
def build_body():
    p = _new()

    # задние борта до линии окон, с аркой; в зоне дверей — только порог до пола
    prof = [(HOOD_Z0, BOT_Y), (HOOD_Z0, FLOOR_Y), (DOOR_Z[False][0], FLOOR_Y), (DOOR_Z[False][0], BELT_Y),
            (Z_REAR, BELT_Y), (Z_REAR, 0.62), (Z_REAR + 0.05, BOT_Y)]
    a0 = len(prof)
    prof += arch(AXLE_R)[::-1]
    g, d = extrude_x2(prof, INNER_X, HALF_W, alt=set(range(a0, a0 + 5)))
    p["paint"] += both(g)
    p["dark"] += both(d)

    # центральная «ванна»: пол салона и грузового отсека, задний борт — утоплен в стенку, как у M1025
    tub = [(HOOD_Z0, BOT_Y), (HOOD_Z0, 1.10), (HOOD_Z0 - 0.04, FLOOR_Y), (Z_REAR + 0.07, FLOOR_Y + 0.25),
           (Z_REAR + 0.07, BELT_Y), (Z_REAR, BELT_Y), (Z_REAR, TG_Y1 + 0.02), (Z_REAR + TG_D, TG_Y1),
           (Z_REAR + TG_D, TG_Y0), (Z_REAR, TG_Y0 - 0.02), (Z_REAR, 0.62), (Z_REAR + 0.05, BOT_Y)]
    g, d = extrude_x2(tub, -INNER_X, INNER_X)
    p["paint"] += g
    p["dark"] += d
    # задний борт: петли снизу, замки по углам сверху, поперечное ребро
    for s in (1, -1):
        p["dark"] += tube((s * 0.30, TG_Y0 + 0.03, Z_REAR + TG_D - 0.012), (s * 0.48, TG_Y0 + 0.03, Z_REAR + TG_D - 0.012),
                          0.014, 8)
        p["dark"] += cbox(s * 0.56, TG_Y1 - 0.05, Z_REAR + TG_D - 0.01, 0.07, 0.05, 0.02)
        p["dark"] += cbox(s * 0.56, TG_Y1 - 0.05, Z_REAR + TG_D - 0.025, 0.025, 0.07, 0.02)
    p["paint"] += cbox(0, (TG_Y0 + TG_Y1) / 2, Z_REAR + TG_D - 0.008, 2 * INNER_X - 0.06, 0.04, 0.016)

    # борт за передней аркой до передней двери (выше — крыло откидывающегося капота)
    for s in (1, -1):
        p["paint"] += box(min(s * INNER_X, s * HALF_W), max(s * INNER_X, s * HALF_W), BOT_Y, FEND_Y - 0.02,
                          DOOR_Z[True][1], AXLE_F - 0.56)
    # передняя панель с решёткой и фарами (остаётся на месте, когда капот откинут)
    p["paint"] += box(-INNER_X, INNER_X, 0.62, FEND_Y, FRONT_Z - 0.04, FRONT_Z)
    for k in range(9):
        x = -0.36 + k * 0.09
        p["dark"] += box(x - 0.026, x + 0.026, 0.70, 0.94, FRONT_Z, FRONT_Z + 0.006)
    p["dark"] += box(-0.42, 0.42, 0.66, 0.68, FRONT_Z, FRONT_Z + 0.006)
    for s in (1, -1):
        M = chain(T(s * HEADLIGHT_X, HEADLIGHT_Y, FRONT_Z), AX_TO_Z)
        p["dark"] += cbox(s * HEADLIGHT_X, HEADLIGHT_Y, FRONT_Z + 0.003, 0.24, 0.22, 0.006)
        p["dark"] += lathe([(0.10, -0.02), (0.10, 0.03), (0.084, 0.035)], seg=32).transformed(M)
        p["light"] += lathe([(0.084, 0.025), (0.058, 0.034), (0.0, 0.038)], seg=32).transformed(M)

    # моторный отсек: двигатель, радиатор за решёткой, воздушный фильтр, аккумулятор, брызговики крыльев
    p["dark"] += box(-0.30, 0.30, 0.55, 0.92, 1.05, 1.85)
    p["dark"] += box(-0.20, 0.20, 0.92, 1.00, 1.15, 1.75)
    p["dark"] += box(-0.55, 0.55, 0.62, FEND_Y - 0.02, FRONT_Z - 0.20, FRONT_Z - 0.12)
    p["dark"] += cbox(0.52, 0.86, 1.25, 0.24, 0.22, 0.34)
    p["dark"] += cbox(-0.52, 0.80, 1.20, 0.26, 0.20, 0.30)
    for s in (1, -1):
        p["dark"] += box(s * INNER_X - 0.01, s * INNER_X + 0.01, 0.62, FEND_Y - 0.02, HOOD_Z0, FRONT_Z - 0.04)
    p["dark"] += box(-INNER_X, INNER_X, 0.62, 1.30, HOOD_Z0 - 0.02, HOOD_Z0)          # перегородка у салона

    # кабина: стойки A и B, низ лобового стекла, лобовое стекло в раме, козырёк
    for s in (1, -1):
        sx = s * CAB_W
        za0, za1 = windshield_z(WS_Y0), windshield_z(CEIL_Y)
        for x0, x1 in ((sx, s * HALF_W),):
            p["paint"] += box(min(x0, x1), max(x0, x1), BELT_Y, CEIL_Y, DOOR_Z[True][1], za0 + 0.02)  # стойка A
            p["paint"] += box(min(x0, x1), max(x0, x1), FLOOR_Y, CEIL_Y, -0.33, -0.27)              # стойка B
            p["paint"] += box(min(x0, x1), max(x0, x1), FLOOR_Y, BELT_Y, HOOD_Z0 - 0.10, HOOD_Z0)   # низ стойки A
    p["paint"] += box(-HALF_W, HALF_W, HOOD_Y0 - 0.06, WS_Y0, HOOD_Z0 - 0.04, HOOD_Z0 + 0.02)      # подоконник стекла
    wn = np.array([0.0, ZF_B - ZF_T, CEIL_Y - WS_Y0])
    wn /= np.linalg.norm(wn)

    def wpt(x, t):
        y = WS_Y0 + (CEIL_Y - WS_Y0) * t
        return np.array([x, y, windshield_z(y)])
    for s in (1, -1):
        q = [wpt(s * 0.05, 0.07), wpt(s * 0.94, 0.07), wpt(s * 0.94, 0.93), wpt(s * 0.05, 0.93)]
        qd = [wpt(s * 0.035, 0.03), wpt(s * 0.97, 0.03), wpt(s * 0.97, 0.97), wpt(s * 0.035, 0.97)]
        p["dark"] += plane_quad(qd, wn, 0.004)
        p["glass"] += plane_quad(q, wn, 0.008)
        pw = wpt(s * 0.48, 0.06)
        p["dark"] += tube(pw + wn * 0.02, wpt(s * 0.43, 0.55) + wn * 0.02, 0.008, 6)    # дворники
    p["dark"] += box(-0.05, 0.05, WS_Y0, CEIL_Y, windshield_z(1.5) - 0.02, windshield_z(1.5) + 0.03)

    # крыша: плита с отверстием люка, скос кромки, потолок с отверстием, кольцо люка
    c, x0, x1, z0, z1 = 0.025, -ROOF_X, ROOF_X, ROOF_Z0, ROOF_Z1
    p["paint"] += roof_with_hole(YT, (0, 1, 0), (x0 + c, x1 - c, z0 + c, z1 - c), HATCH_Z, 0.0, RING_IN)
    inner = [(x0 + c, YT, z0 + c), (x1 - c, YT, z0 + c), (x1 - c, YT, z1 - c), (x0 + c, YT, z1 - c)]
    outer = [(x0, YT - c, z0), (x1, YT - c, z0), (x1, YT - c, z1), (x0, YT - c, z1)]
    low = [(x, CEIL_Y, z) for x, _, z in outer]
    for i in range(4):
        j = (i + 1) % 4
        mid = np.mean([outer[i], outer[j]], axis=0)
        od = (mid[0], 0, mid[2] - (z0 + z1) / 2)
        p["paint"] += face([inner[i], inner[j], outer[j], outer[i]], (od[0], 1, od[2]))
        p["paint"] += face([outer[i], outer[j], low[j], low[i]], od)
    p["interior"] += roof_with_hole(CEIL_Y, (0, -1, 0), (x0, x1, z0, z1), HATCH_Z, 0.0, RING_IN)
    ring = lathe([(RING_IN, CEIL_Y - YT - 0.003), (RING_OUT, -0.01), (RING_OUT, 0.06), (RING_OUT - 0.02, 0.095),
                  (RING_IN + 0.02, 0.10), (RING_IN, 0.08), (RING_IN, CEIL_Y - YT - 0.003)], seg=64, smooth_deg=35)
    p["paint"] += ring.transformed(chain(T(0, YT, HATCH_Z), AX_TO_Y))
    for s in (1, -1):
        p["dark"] += cbox(s * 0.20, RING_TOP + 0.006, HINGE_Z - 0.005, 0.07, 0.04, 0.06)
    for a in (0.5, -0.5, math.pi / 2, -math.pi / 2):
        p["dark"] += cbox(RING_OUT * math.sin(a), YT + 0.05, HATCH_Z + RING_OUT * math.cos(a), 0.06, 0.08, 0.06)

    # задние наплывы по бокам крышки багажника (сечение выпуклое: грани наружу от его центра)
    for s in (1, -1):
        p["paint"] += _shoulder(s)

    # зеркала на кронштейнах у стоек A
    for s in (1, -1):
        p0 = np.array([s * (HALF_W + 0.02), 1.40, 0.74])
        p1 = np.array([s * (HALF_W + 0.22), 1.46, 0.74])
        p["dark"] += tube(p0, p1, 0.014, 8)
        p["dark"] += tube(p1, p1 + np.array([0, 0.20, 0]), 0.012, 8)
        p["dark"] += cbox(s * (HALF_W + 0.25), 1.58, 0.74, 0.05, 0.26, 0.18)
        p["glass"] += cbox(s * (HALF_W + 0.25), 1.58, 0.714, 0.044, 0.23, 0.004)
        # порог-подножка под дверями
        p["dark"] += box(min(s * (HALF_W - 0.02), s * (HALF_W + 0.04)), max(s * (HALF_W - 0.02), s * (HALF_W + 0.04)),
                         0.45, 0.50, DOOR_Z[False][0], DOOR_Z[True][1])
        # боковой габарит у кормы, основание антенны с пружиной на наплыве
        p["dark"] += cbox(s * (HALF_W + 0.003), 1.06, Z_REAR + 0.16, 0.006, 0.055, 0.09)
        p["red"] += cbox(s * (HALF_W + 0.007), 1.06, Z_REAR + 0.16, 0.004, 0.04, 0.07)
        za = Z_REAR + 0.34
        xa, ya = s * (SH_X_IN + SH_X_OUT) / 2, sh_top(za) - 0.003
        base = lathe([(0.0, 0.0), (0.055, 0.0), (0.055, 0.03), (0.035, 0.04), (0.035, 0.11), (0.02, 0.12), (0.0, 0.12)],
                     seg=16, smooth_deg=30)
        p["dark"] += base.transformed(chain(T(xa, ya - 0.01, za), AX_TO_Y))
        p["chassis"] += coil_spring(xa, za, ya + 0.11, ya + 0.21, R=0.018, wire=0.005, turns=7)
    # горловина бака справа (по ванили) под трафаретом топлива
    cap = lathe([(0.0, 0.0), (0.062, 0.0), (0.062, 0.012), (0.048, 0.02), (0.0, 0.022)], seg=20, smooth_deg=30)
    p["dark"] += cap.transformed(chain(T(-HALF_W, 1.03, -1.30), Ry(math.pi)))

    # корма: фонари в корпусах по углам (круглые красные в ободках, отражатель), бампер-швеллер с упорами,
    # серьги и фаркоп
    for s in (1, -1):
        xh = s * 0.86
        p["dark"] += cbox(xh, 1.03, Z_REAR - 0.03, 0.17, 0.40, 0.06)
        p["dark"] += cbox(xh, 1.03, Z_REAR - 0.062, 0.19, 0.42, 0.006)                    # рамка корпуса
        for yl in (1.13, 1.00):
            M = chain(T(xh, yl, Z_REAR - 0.065), Ry(math.pi), AX_TO_Z)                    # ось лампы — назад
            p["metal"] += lathe([(0.056, -0.01), (0.056, 0.012), (0.046, 0.016)], seg=24).transformed(M)
            p["red"] += lathe([(0.046, 0.010), (0.030, 0.018), (0.0, 0.020)], seg=24).transformed(M)
        p["red"] += cbox(xh, 0.88, Z_REAR - 0.068, 0.10, 0.05, 0.008)                    # отражатель
        p["dark"] += box(min(s * 0.95, s * 1.06), max(s * 0.95, s * 1.06), 0.46, 0.66, Z_REAR - 0.155, Z_REAR - 0.12)
        p["dark"] += cbox(s * 0.60, 0.455, Z_REAR - 0.13, 0.03, 0.05, 0.07)                  # ушко серьги
        p["chassis"] += d_ring((s * 0.60, 0.44, Z_REAR - 0.13), R=0.045)
    p["paint"] += box(-HALF_W + 0.02, HALF_W - 0.02, 0.48, 0.64, Z_REAR - 0.12, Z_REAR)
    for y0, y1 in ((0.475, 0.495), (0.625, 0.645)):                                       # полки швеллера
        p["paint"] += box(-0.92, 0.92, y0, y1, Z_REAR - 0.145, Z_REAR - 0.12)
    p["dark"] += box(-0.10, 0.10, 0.42, 0.58, Z_REAR - 0.20, Z_REAR - 0.12)                # плита фаркопа
    hook = [(0.0, 0.50 + 0.04 * math.sin(t), Z_REAR - 0.29 - 0.04 * math.cos(t))
            for t in np.linspace(math.pi, 2 * math.pi + 0.6, 12)]                       # крюк фаркопа, зев вверх
    p["chassis"] += sweep_tube(hook, 0.016, ring=8)
    p["chassis"] += tube((0, 0.50, Z_REAR - 0.20), (0, 0.50, Z_REAR - 0.25), 0.02, 8)

    # передний бампер и кенгурятник
    p["paint"] += box(-1.10, 1.10, 0.48, 0.66, FRONT_Z, FRONT_Z + 0.14)
    gz = FRONT_Z + 0.20
    for x in (-1.00, -0.62, -0.30, 0.30, 0.62, 1.00):
        p["dark"] += tube((x, 0.66, gz - 0.04), (x, 1.11, gz), 0.028)
    p["dark"] += tube((-1.00, 1.11, gz), (1.00, 1.11, gz), 0.028)
    p["dark"] += tube((-1.00, 0.86, gz - 0.02), (1.00, 0.86, gz - 0.02), 0.024)
    for s in (1, -1):
        p["dark"] += cbox(s * 0.46, 0.64, FRONT_Z + 0.16, 0.10, 0.05, 0.10)
        p["dark"] += cbox(s * 0.66, 0.56, FRONT_Z + 0.16, 0.08, 0.06, 0.05)                # ушки буксирной серьги
        p["chassis"] += d_ring((s * 0.66, 0.55, FRONT_Z + 0.17), R=0.045, axis_z=True)

    # рама, мосты, редукторы, карданы, выхлоп
    for s in (1, -1):
        p["dark"] += box(s * 0.40 - 0.05, s * 0.40 + 0.05, 0.36, 0.48, Z_REAR + 0.20, FRONT_Z - 0.06)
    for zc in (AXLE_F, AXLE_R):
        p["dark"] += cylinder_x(0.055, -0.62, 0.62, 16).transformed(T(0, WHEEL_Y + 0.08, zc))
        p["dark"] += cbox(0, WHEEL_Y + 0.08, zc, 0.32, 0.28, 0.28)
        for s in (1, -1):
            p["dark"] += cbox(s * 0.68, WHEEL_Y + 0.04, zc, 0.10, 0.26, 0.24)
            p["dark"] += tube((s * 0.56, WHEEL_Y + 0.10, zc + 0.10 * s), (s * 0.30, 0.86, zc), 0.035)
    p["dark"] += tube((0, 0.42, AXLE_R + 0.2), (0, 0.42, AXLE_F - 0.2), 0.04)
    p["metal"] += tube(EXHAUST_START, EXHAUST_END, 0.04)
    # подвеска в колёсных нишах: пружины, амортизаторы, нижние рычаги (видны за колёсами, как у ванили)
    for zc in (AXLE_F, AXLE_R):
        for s in (1, -1):
            p["chassis"] += coil_spring(s * 0.70, zc - 0.16, 0.50, 0.98)
            p["chassis"] += tube((s * 0.70, 0.46, zc + 0.16), (s * 0.67, 0.98, zc + 0.20), 0.022, 8)
            p["metal"] += tube((s * 0.69, 0.62, zc + 0.165), (s * 0.67, 0.98, zc + 0.20), 0.012, 6)
            for dz in (-0.28, 0.28):
                p["chassis"] += tube((s * 0.72, 0.44, zc), (s * 0.42, 0.42, zc + dz), 0.022, 8)
            p["chassis"] += cbox(s * 0.70, 0.47, zc - 0.16, 0.18, 0.03, 0.18)                # чашка пружины
    return p


def tail_line(y_front, z_front, z_end, r=ROLL_R, seg=8):
    """Профиль (z, y) верха кормы: скат вдоль наплывов и катаная кромка дугой вниз; последняя точка — конец дуги,
    где она становится вертикальной (на плоскости z_end)."""
    yc = y_front - SH_SLOPE * (z_front - z_end)
    return fillet2d([(z_front, y_front), (z_end, yc), (z_end, yc - 1.0)], [0, r, 0], seg=seg)[:-1]


def _shoulder(s):
    """Задний наплыв с борта s: сечение со скруглёнными верхними кромками, верх скатывается назад и у кормы
    загибается дугой вниз (как катаные наплывы ванильного M1025); нормали гладкие."""
    def section(top):
        h = top - BELT_Y
        pts = [(SH_X_IN, BELT_Y), (SH_X_OUT, BELT_Y), (SH_X_OUT, top), (SH_X_IN, top)]
        r_out, r_in = min(SH_R_OUT, 0.8 * h), min(SH_R_IN, 0.3 * h)
        return [(s * x, y) for x, y in fillet2d(pts, [0, 0, r_out, r_in], seg=6, closed=True)]
    y0 = YT - 0.003                                         # чуть ниже крыши: там, где наплыв заходит под неё
    prof = [(SH_Z0, y0)] + tail_line(y0, ROOF_Z0, Z_REAR)
    secs = [[(x, y, z) for x, y in section(t)] for z, t in prof]
    zs, tops = np.array([z for z, _ in prof]), np.array([t for _, t in prof])

    def inside(c):                                          # середина сечения на этом z
        top = np.interp(c[2], zs[::-1], tops[::-1])
        return (s * (SH_X_IN + SH_X_OUT) / 2, BELT_Y + 0.45 * (top - BELT_Y), c[2])
    g = loft(secs, inside, closed=True)
    g += face(secs[0], (0, 0, 1))
    g += face(secs[-1], (0, 0, -1))
    return g


# ---------------------------------------------------------------- капот и крышка багажника
def build_lids():
    """{селекция: parts} в координатах кузова (закрыты)."""
    hood = _new()
    # центральная часть капота с решёткой воздухозаборника
    prof = [(FRONT_Z, FEND_Y), (FRONT_Z, 1.06), (HOOD_Z1, HOOD_Y1), (HOOD_Z0, HOOD_Y0), (HOOD_Z0, FEND_Y + 0.25)]
    g, _ = extrude_x2(_ccw(prof), -INNER_X, INNER_X)
    hood["paint"] += g
    slope = math.atan2(HOOD_Y0 - HOOD_Y1, HOOD_Z1 - HOOD_Z0)
    base = chain(T(0, hood_y(1.90) + 0.004, 1.90), Rx(slope))
    hood["dark"] += cbox(0, 0, 0, 0.62, 0.006, 0.30).transformed(base)
    for k in range(6):
        hood["paint"] += cbox(0, 0.012, -0.125 + k * 0.05, 0.58, 0.016, 0.018).transformed(base)
    # крылья с арками: откидываются вместе с капотом, как у M1025
    zc = AXLE_F
    fend = [(FRONT_Z, 0.74), (FRONT_Z, 1.06), (HOOD_Z1, HOOD_Y1 - 0.02), (HOOD_Z0, HOOD_Y0 - 0.03), (HOOD_Z0, 0.96)]
    fend += [(zc - 0.56, 0.96), (zc - 0.40, 1.04), (zc + 0.30, 1.04), (zc + 0.50, 0.90), (FRONT_Z - 0.02, 0.76)]
    g, d = extrude_x2(_ccw(fend), INNER_X, FENDER_W, alt={5, 6, 7, 8})
    hood["paint"] += both(g)
    hood["dark"] += both(d)
    for s in (1, -1):
        hood["amber"] += cbox(s * 0.88, 0.86, FRONT_Z + 0.012, 0.10, 0.06, 0.024)          # поворотники
        hood["dark"] += cbox(s * 0.88, 0.95, FRONT_Z + 0.012, 0.08, 0.05, 0.024)           # маскировочные фары
        hood["dark"] += cbox(s * (FENDER_W + 0.008), 0.99, 2.02, 0.016, 0.14, 0.035)       # резиновые замки
        hood["amber"] += cbox(s * (FENDER_W + 0.004), 0.95, 2.16, 0.008, 0.04, 0.07)       # боковые габариты
        hood["dark"] += tube((s * INNER_X, hood_y(HOOD_Z0) - 0.02, HOOD_Z0 + 0.02),
                             (s * INNER_X, hood_y(2.16) - 0.02, 2.16), 0.008, 6)            # стыки капота и крыльев

    trunk = _new()
    t, xw, crown = 0.03, TRUNK_X - 0.006, 0.022
    # линия крышки по центру: скат и катаная кромка до задней стенки; поперёк — выпуклость crown
    line = [np.array(q) for q in tail_line(YT - 0.015, ROOF_Z0 - 0.01, Z_REAR + 0.012)]
    line.append(np.array([Z_REAR + 0.012, BELT_Y + 0.012]))
    nrm = []
    for k in range(len(line)):
        d = line[min(k + 1, len(line) - 1)] - line[max(k - 1, 0)]
        nrm.append(np.array([d[1], -d[0]]) / np.linalg.norm(d))              # (z, y) наружу: вверх и назад
    xs = np.linspace(-xw, xw, 15)

    def surf(off):
        return [[(x, q[1] + n[1] * (crown * (1 - (x / xw) ** 2) + off), q[0] + n[0] * (crown * (1 - (x / xw) ** 2) + off))
                 for q, n in zip(line, nrm)] for x in xs]
    top, bot = surf(0.0), surf(-t)
    trunk["paint"] += loft(top, (0, 0.9, -1.7))
    trunk["interior"] += loft(bot, (0, 3.0, -3.0))
    for k in (0, -1):                                                         # боковые кромки
        trunk["paint"] += loft([top[k], bot[k]], lambda c: (0, c[1], c[2]))
    for k in (0, -1):                                                         # передняя кромка и низ загиба
        q = [top[0][k], top[-1][k], bot[-1][k], bot[0][k]]
        trunk["paint"] += face(q, (0, 0, 1) if k == 0 else (0, -1, 0))
    # замок с ручкой на скате у кормы, петли у крыши
    zh = Z_REAR + 0.42
    yh = YT - 0.015 - SH_SLOPE * (ROOF_Z0 - 0.01 - zh) + crown
    tilt = math.atan(SH_SLOPE)
    M = chain(T(0, yh, zh), Rx(-tilt))                                        # локальный верх — по нормали ската
    trunk["dark"] += cbox(0, 0.004, 0, 0.26, 0.008, 0.10).transformed(M)
    trunk["dark"] += cbox(0, 0.016, -0.02, 0.16, 0.016, 0.022).transformed(M)
    for s in (1, -1):
        trunk["dark"] += cbox(s * 0.07, 0.010, -0.02, 0.02, 0.02, 0.03).transformed(M)
        trunk["dark"] += cylinder_x(0.016, min(s * 0.36, s * 0.56), max(s * 0.36, s * 0.56), 10).transformed(
            T(0, YT - 0.006, ROOF_Z0 - 0.025))
    return {"doors_hood": hood, "doors_trunk": trunk}


# ---------------------------------------------------------------- двери
def build_doors():
    """Двери: {селекция: parts} — панель с окном, X-рёбра, петли и ручка."""
    out = {}
    xa, xb = DOOR_X
    for sel, (s, front) in DOORS.items():
        parts = _new()
        za, zb = DOOR_Z[front]
        y0, y1, fw = BELT_Y + 0.06, CEIL_Y - 0.08, 0.08
        g = Geo()   # панель до окна и рама вокруг окна: через окно видно и снаружи, и из салона
        g += box(xa, xb, FLOOR_Y, y0, za, zb)
        g += box(xa, xb, y1, CEIL_Y, za, zb)
        g += box(xa, xb, y0, y1, za, za + fw)
        g += box(xa, xb, y0, y1, zb - fw, zb)
        parts["paint"] += g if s > 0 else g.transformed(MIRROR_X)
        xm = s * (xa + xb) / 2
        pane = [(xm, y0, za + fw), (xm, y0, zb - fw), (xm, y1, zb - fw), (xm, y1, za + fw)]
        parts["glass"] += face(pane, (s, 0, 0))
        parts["glass"] += face(pane, (-s, 0, 0))
        # X-рёбра на нижней панели
        z0, z1 = za + 0.07, zb - 0.07
        ry0, ry1 = FLOOR_Y + 0.10, BELT_Y - 0.04
        zc_, yc_ = (z0 + z1) / 2, (ry0 + ry1) / 2
        L = math.hypot(z1 - z0, ry1 - ry0)
        ang = math.atan2(ry1 - ry0, z1 - z0)
        for a in (ang, -ang):
            parts["paint"] += cbox(0, 0, 0, 0.012, 0.035, L).transformed(chain(T(s * (xb + 0.006), yc_, zc_), Rx(-a)))
        for pa, pb in (((z0, ry0), (z1, ry0)), ((z0, ry1), (z1, ry1)), ((z0, ry0), (z0, ry1)), ((z1, ry0), (z1, ry1))):
            parts["paint"] += tube((s * (xb + 0.004), pa[1], pa[0]), (s * (xb + 0.004), pb[1], pb[0]), 0.012, 6)
        for yh in (FLOOR_Y + 0.25, CEIL_Y - 0.15):                                               # петли
            parts["dark"] += cbox(s * (xb + 0.012), yh, zb - 0.04, 0.03, 0.10, 0.06)
        parts["dark"] += cbox(s * (xb + 0.015), BELT_Y + 0.02, za + 0.08, 0.03, 0.035, 0.12)     # ручка
        out[sel] = parts
    return out


# ---------------------------------------------------------------- салон
def build_interior():
    p = _new()
    p["interior"] += box(-0.98, 0.98, 1.05, 1.32, HOOD_Z0 - 0.26, HOOD_Z0 - 0.04)          # приборная панель
    p["dark"] += box(0.30, 0.90, 1.24, 1.30, HOOD_Z0 - 0.27, HOOD_Z0 - 0.22)              # приборы водителя
    p["interior"] += box(-0.20, 0.20, FLOOR_Y, 0.90, -1.10, HOOD_Z0 - 0.06)              # широкий тоннель
    p["dark"] += cbox(0.0, 1.00, 0.20, 0.30, 0.16, 0.30)                                   # радиостанция
    for name, (x, z) in SEATS.items():
        p["seat"] += cbox(x, SEAT_Y - 0.06, z, 0.46, 0.12, 0.46)                           # подушка
        p["interior"] += cbox(x, (FLOOR_Y + SEAT_Y - 0.12) / 2, z, 0.38, SEAT_Y - 0.12 - FLOOR_Y, 0.38)
        back = cbox(0, 0.30, 0, 0.46, 0.60, 0.10)
        p["seat"] += back.transformed(chain(T(x, SEAT_Y - 0.04, z - 0.27), Rx(-0.18)))
    xd, zd = SEATS["Driver"]
    wheel = lathe([(0.19 + 0.022 * math.cos(a), 0.022 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 13)],
                  seg=40, smooth_deg=60)
    M = chain(T(xd, 1.22, zd + 0.42), Rx(-0.95), AX_TO_Z)
    p["seat"] += wheel.transformed(M)
    p["seat"] += cylinder_x(0.02, -0.19, 0.19, 8).transformed(M)
    p["dark"] += cylinder_x(0.03, 0.0, 0.30, 10).transformed(chain(M, Ry(math.pi)))
    for s in (1, -1):
        p["dark"] += cbox(s * 0.42, BELT_Y + 0.13, -1.85, 0.30, 0.24, 0.45)                   # ящики в грузовом отсеке
    return p


def build_hatch_lid():
    """Крышка люка в локальных координатах шарнира (ось шарнира = локальная X)."""
    p = _new()
    dz = HATCH_Z - HINGE_Z
    lid = lathe([(0.0, 0.0), (LID_R, 0.0), (LID_R, 0.03), (LID_R - 0.03, 0.045), (0.28, 0.055), (0.0, 0.06)],
                seg=64, smooth_deg=35)
    p["paint"] += lid.transformed(chain(T(0, 0, dz), AX_TO_Y))
    p["dark"] += cbox(0, 0.085, dz + 0.30, 0.26, 0.022, 0.022)
    for s in (1, -1):
        p["dark"] += cbox(s * 0.12, 0.07, dz + 0.30, 0.022, 0.035, 0.022)
        p["dark"] += cbox(s * 0.20, 0.012, 0.03, 0.07, 0.024, 0.10)
    p["metal"] += cylinder_x(0.015, -0.26, 0.26, 12)
    return p


if __name__ == "__main__":
    for name, parts in (("кузов", build_body()), ("салон", build_interior()), *build_lids().items(),
                        *build_doors().items(), ("люк", build_hatch_lid())):
        print(name, {m: len(g.I) for m, g in clean(parts).items()})
