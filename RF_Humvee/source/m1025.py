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
                             compute_uv, cylinder_x, extrude_x2, face, lathe, periodic_field, plane_quad, roof_with_hole,
                             tube)
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

    # центральная «ванна»: пол салона и грузового отсека, задний борт
    tub = [(HOOD_Z0, BOT_Y), (HOOD_Z0, 1.10), (HOOD_Z0 - 0.04, FLOOR_Y), (Z_REAR + 0.06, FLOOR_Y + 0.25),
           (Z_REAR + 0.02, BELT_Y), (Z_REAR, BELT_Y), (Z_REAR, 0.62), (Z_REAR + 0.05, BOT_Y)]
    g, d = extrude_x2(tub, -INNER_X, INNER_X)
    p["paint"] += g
    p["dark"] += d
    # задняя стенка между наплывами до крышки багажника
    p["paint"] += face([(SH_X_IN, BELT_Y, Z_REAR), (-SH_X_IN, BELT_Y, Z_REAR), (-SH_X_IN, TAIL_Y - 0.03, Z_REAR),
                        (SH_X_IN, TAIL_Y - 0.03, Z_REAR)], (0, 0, -1))

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

    # задняя панель: фонари, бампер, фаркоп, петли заднего борта
    for s in (1, -1):
        p["red"] += cbox(s * 0.86, 1.08, Z_REAR - 0.012, 0.16, 0.10, 0.02)
        p["amber"] += cbox(s * 0.86, 0.97, Z_REAR - 0.012, 0.16, 0.06, 0.02)
        p["metal"] += cbox(s * 0.62, 0.50, Z_REAR - 0.14, 0.05, 0.10, 0.06)
    p["paint"] += box(-HALF_W + 0.02, HALF_W - 0.02, 0.48, 0.64, Z_REAR - 0.12, Z_REAR)
    p["dark"] += box(-0.16, 0.16, 0.44, 0.56, Z_REAR - 0.18, Z_REAR - 0.12)
    p["dark"] += box(-0.55, 0.55, 1.18, 1.24, Z_REAR - 0.006, Z_REAR + 0.001)

    # передний бампер и кенгурятник
    p["paint"] += box(-1.10, 1.10, 0.48, 0.66, FRONT_Z, FRONT_Z + 0.14)
    gz = FRONT_Z + 0.20
    for x in (-1.00, -0.62, -0.30, 0.30, 0.62, 1.00):
        p["dark"] += tube((x, 0.66, gz - 0.04), (x, 1.11, gz), 0.028)
    p["dark"] += tube((-1.00, 1.11, gz), (1.00, 1.11, gz), 0.028)
    p["dark"] += tube((-1.00, 0.86, gz - 0.02), (1.00, 0.86, gz - 0.02), 0.024)
    for s in (1, -1):
        p["dark"] += cbox(s * 0.46, 0.64, FRONT_Z + 0.16, 0.10, 0.05, 0.10)
        p["metal"] += cbox(s * 0.66, 0.54, FRONT_Z + 0.16, 0.05, 0.11, 0.06)

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
    return p


def _shoulder(s):
    """Задний наплыв с борта s: вытянут по z, верх скатывается назад, торец со скосом верхней кромки."""
    def section(top):
        return [(s * SH_X_IN, BELT_Y), (s * SH_X_OUT, BELT_Y), (s * (SH_X_OUT - 0.005), top - 0.14),
                (s * (SH_X_OUT - 0.035), top - 0.045), (s * (SH_X_OUT - 0.09), top), (s * (SH_X_IN + 0.03), top),
                (s * SH_X_IN, top - 0.03)]
    zs = [SH_Z0, ROOF_Z0, SH_Z1, SH_Z_END]
    tops = [sh_top(SH_Z0), sh_top(ROOF_Z0), sh_top(SH_Z1), sh_top(SH_Z1) - 0.07]
    secs = [[(x, y, z) for x, y in section(t)] for z, t in zip(zs, tops)]
    n = len(secs[0])
    g = Geo()
    for a, b in zip(secs[:-1], secs[1:]):
        cx, cy = np.mean([q[0] for q in a]), np.mean([q[1] for q in a])
        for i in range(n):
            j = (i + 1) % n
            g += face([a[i], a[j], b[j], b[i]], ((a[i][0] + a[j][0]) / 2 - cx, (a[i][1] + a[j][1]) / 2 - cy, 0))
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
        hood["dark"] += tube((s * INNER_X, hood_y(HOOD_Z0) - 0.02, HOOD_Z0 + 0.02),
                             (s * INNER_X, hood_y(2.16) - 0.02, 2.16), 0.008, 6)            # стыки капота и крыльев

    trunk = _new()
    t = 0.03
    z0, z1, y0, y1 = ROOF_Z0 - 0.01, SH_Z1 + 0.02, YT - 0.015, TAIL_Y - 0.02
    top = [(TRUNK_X, y0, z0), (-TRUNK_X, y0, z0), (-TRUNK_X, y1, z1), (TRUNK_X, y1, z1)]
    bot = [(x, y - t, z) for x, y, z in top]
    trunk["paint"] += face(top, (0, 1, 0.3))
    trunk["interior"] += face(bot, (0, -1, -0.3))
    for i in range(4):
        j = (i + 1) % 4
        mid = np.mean([top[i], top[j]], axis=0)
        trunk["paint"] += face([top[i], top[j], bot[j], bot[i]], (mid[0], 0, mid[2] - (z0 + z1) / 2))
    zh = z1 + 0.18
    trunk["dark"] += cbox(0, sh_top(zh) + 0.01, zh, 0.30, 0.025, 0.05)                       # ручка
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
