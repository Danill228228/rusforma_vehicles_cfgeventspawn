#!/usr/bin/env python3
"""
Сборка мода @RF_Humvee — свой HMMWV M1025 по образцу ванильного M1025 DayZ:
  1. P3D (MLOD) машины: модель RF_Humvee/source/m1025.py (своя, размеры сняты с ванильного M1025 в игре),
     LOD, геометрия, точки, прокси колёс — ванильные колёса M1025 (Offroad_02_Wheel) встают в свои слоты
  2. текстура тёмного металла; окраска кузова — ванильные текстура и материалы крыши M1025 (ссылками, не копии)
  3. model.cfg
  4. упаковка PBO:  @RF_Humvee/Addons/RF_Humvee.pbo и RF_Humvee_Hatch.pbo

В исходной модели +X — левый борт, +Z — перёд; в файле P3D зеркалится Z (см. to_p3d), тогда в игре
перёд на +Z, водитель на -X, как у ванильного M1025. Запуск: python3 RF_Humvee_Mod/tools/build_mod.py
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
ROOT = os.path.dirname(MOD)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "RF_Humvee", "source"))

import m1025 as G  # noqa: E402  — своя модель M1025 (RF_Humvee/source/m1025.py)
import p3d_mlod as P3D  # noqa: E402
import paa  # noqa: E402
import pbo  # noqa: E402
import texture_atlas  # noqa: E402

SRC = os.path.join(MOD, "src")
DATA = os.path.join(SRC, "RF_Humvee", "data")
TEX_SIZE = 2048      # размер PAA; 4096 давал ~11 МБ на текстуру (BUG-0006)
OUT_ADDONS = os.path.join(MOD, "@RF_Humvee", "Addons")

# Окраска — своя текстура-атлас (texture_atlas.py): все окрашенные грани (кузов, тёмные детали, салон, сиденья)
# развёрнуты в один атлас 2048×2048 и окрашены с камуфляжем, пылью, грязью, потёртостями и подтёками. Лесная и
# пустынная окраски — две _co текстуры (config.cpp, селекция camo), рельеф и блики общие.
ATLAS_MATS = ("paint", "dark", "interior", "seat")
BODY_TEX = r"rf_humvee\data\rf_humvee_woodland_co.paa"
BODY_MAT = r"rf_humvee\data\rf_humvee_body.rvmat"
ATLAS = None          # texture_atlas.Atlas, строится в build_car_p3d
# трафареты (текст, центр, нормаль, ширина в м) в координатах модели: коды на бамперах, давление шин на крыльях,
# топливо над горловиной бака
MARKINGS = [
    ("2-7 B", (0.84, 0.57, G.FRONT_Z + 0.14), (0, 0, 1), 0.20),
    ("HQ 14", (-0.84, 0.57, G.FRONT_Z + 0.14), (0, 0, 1), 0.20),
    ("2-7 B", (0.70, 0.58, G.Z_REAR - G.BUMPER_R[2]), (0, 0, -1), 0.18),
    ("HQ 14", (-0.70, 0.58, G.Z_REAR - G.BUMPER_R[2]), (0, 0, -1), 0.18),
    ("TIRE PRESS 20 PSI", (G.FENDER_W, 1.115, G.AXLE_F), (1, 0, 0), 0.30),
    ("TIRE PRESS 20 PSI", (-G.FENDER_W, 1.115, G.AXLE_F), (-1, 0, 0), 0.30),
    ("DIESEL\nFUEL ONLY", (-G.HALF_W, 1.17, -1.45), (-1, 0, 0), 0.14),
]


def material_for(mat):
    return BODY_MAT if mat in ATLAS_MATS else ""


RES_GEOMETRY, RES_PHYS = 1e13, 4e13
RES_MEMORY, RES_LANDCONTACT, RES_ROADWAY = 1e15, 2e15, 3e15
RES_VIEWGEO, RES_FIREGEO = 6e15, 7e15

WHEELS = {  # селекция: (x в исходной модели, z, передняя?); порядок = номера прокси = слоты ванильного колеса
    "wheel_1_1": (G.TRACK_X, G.AXLE_F, True),    # левое переднее
    "wheel_1_2": (G.TRACK_X, G.AXLE_R, False),   # левое заднее
    "wheel_2_1": (-G.TRACK_X, G.AXLE_F, True),   # правое переднее
    "wheel_2_2": (-G.TRACK_X, G.AXLE_R, False),  # правое заднее
}


def to_p3d(p):
    """исходные координаты -> P3D. Отражается Z, а не X: с отражением X игра видела машину развёрнутой на 180°
    (фары на z = -2.25, водитель на x = +1.85, у ванильной Ada фара на z = +1.84, водитель на x = -1.12)
    и на первой передаче ехала задом."""
    return (float(p[0]), float(p[1]), -float(p[2]))


def texture_for(mat):
    if mat in ATLAS_MATS:
        return BODY_TEX
    rgb, _, _, extra = G.MATERIALS[mat]
    if "alpha" in extra:
        return "#(argb,8,8,3)color(%.3f,%.3f,%.3f,%.2f,ca)" % (*rgb, extra["alpha"])
    return "#(argb,8,8,3)color(%.3f,%.3f,%.3f,1,co)" % rgb


class LodBuilder:
    def __init__(self, resolution):
        self.L = P3D.Lod(resolution)
        self._pts = {}
        self._nrm = {}
        self.mass = []

    def point(self, p, mass=0.0, group=""):
        # group — своя подвижная деталь: её вершины не общие с кузовом, иначе анимация тянет и грани кузова
        # (капот, вырезанный из сетки кузова, растягивал при открытии крылья и борта)
        key = (group, *(round(c, 4) for c in p))
        if key not in self._pts:
            self._pts[key] = self.L.add_point(p)
            self.mass.append(0.0)
        i = self._pts[key]
        self.mass[i] += mass
        return i

    def normal(self, n):
        key = tuple(round(c, 3) for c in n)
        if key not in self._nrm:
            self._nrm[key] = self.L.add_normal(n)
        return self._nrm[key]

    def add_geo(self, g, texture="", material="", selections=(), uv=True, group=""):
        """g — Geo в исходных координатах; грани/нормали переводятся в соглашения P3D."""
        if not len(g.I):
            return
        if texture == BODY_TEX:
            UVc = ATLAS.uv_for(g.P[g.I])                 # своя развёртка: UV на угол треугольника
        else:
            UV = G.compute_uv(g) if uv else np.zeros((len(g.P), 2))
            UVc = UV[g.I]
        P = g.P * np.array([1.0, 1.0, -1.0])           # как to_p3d
        N = g.N * np.array([-1.0, -1.0, 1.0])         # отражённая нормаль, развернутая внутрь
        pidx = [self.point(p, group=group) for p in P]
        nidx = [self.normal(n) for n in N]
        f0 = len(self.L.faces)
        for t, (a, b, c) in enumerate(g.I):
            if len({pidx[a], pidx[b], pidx[c]}) < 3:
                continue
            self.L.faces.append(dict(
                verts=[(pidx[k], nidx[k], float(UVc[t, j, 0]), float(UVc[t, j, 1])) for j, k in enumerate((a, b, c))],
                flags=0, texture=texture, material=material))
        faces = range(f0, len(self.L.faces))
        pts = {v[0] for i in faces for v in self.L.faces[i]["verts"]}
        for s in selections:
            self.L.select(s, pts, faces)

    def add_parts(self, parts, selections=()):
        for mat, g in parts.items():
            sel = list(selections) + (["camo"] if mat in ATLAS_MATS else [])
            # Грань с текстурой-файлом PAA без rvmat игра не рисует (кузов был невидим), процедурным цветам материал не нужен.
            self.add_geo(g, texture_for(mat), material_for(mat), sel, group=",".join(selections))

    def add_component(self, g, mass, selections=()):
        """Выпуклое замкнутое тело для LOD геометрии."""
        n_comp = sum(1 for k in self.L.selections if k.lower().startswith("component")) + 1
        before = len(self.L.points)
        self.add_geo(g, "", "", ["Component%02d" % n_comp, *selections], uv=False)
        pts = sorted(self.L.selections["Component%02d" % n_comp][0])
        for i in pts:
            self.mass[i] += mass / len(pts)
        del before

    def add_memory(self, name, *points):
        idx = [self.point(to_p3d(p)) for p in points]
        self.L.select(name, idx, ())

    def add_proxy(self, path, origin, yaw180=False, selections=(), size=1.0):
        o = np.array(to_p3d(origin))
        up = np.array([0, 2.0, 0]) * size
        fw = np.array([0, 0, 1.0 if yaw180 else -1.0]) * size   # «вперёд» исходной модели после to_p3d
        idx = [self.point(tuple(o)), self.point(tuple(o + up)), self.point(tuple(o + fw))]
        n = self.normal((1.0, 0.0, 0.0))
        self.L.faces.append(dict(verts=[(i, n, 0.0, 0.0) for i in idx], flags=0, texture="", material=""))
        fi = len(self.L.faces) - 1
        num = sum(1 for k in self.L.selections if k.lower().startswith("proxy:" + path.lower())) + 1
        self.L.select("proxy:%s.%03d" % (path, num), idx, [fi])
        for s in selections:
            self.L.select(s, idx, [fi])

    def done(self, with_mass=False, props=()):
        if with_mass:
            self.L.mass = self.mass
        self.L.properties = list(props)
        return self.L


# --------------------------------------------------------------------------- дальние LOD
def simplify(parts, min_size):
    """Для дальних LOD: убирает мелкие детали — связные куски (по совпадающим точкам) с диагональю меньше min_size."""
    out = {}
    for mat, g in parts.items():
        if not len(g.I):
            out[mat] = g
            continue
        _, vid = np.unique(np.round(g.P, 4), axis=0, return_inverse=True)
        vid = vid.reshape(-1)
        parent = list(range(vid.max() + 1))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for a, b, c in vid[g.I]:
            ra, rb, rc = find(a), find(b), find(c)
            parent[rb] = ra
            parent[rc] = ra
        root = np.array([find(v) for v in vid])
        keep = np.zeros(len(g.P), bool)
        for r in np.unique(root):
            m = root == r
            if np.linalg.norm(g.P[m].max(0) - g.P[m].min(0)) >= min_size:
                keep |= m
        tris = g.I[keep[g.I].all(1)]
        used = np.unique(tris)
        remap = np.full(len(g.P), -1)
        remap[used] = np.arange(len(used))
        out[mat] = G.Geo(g.P[used], g.N[used], remap[tris])
    return out


# Видимые LOD: (разрешение, мельче чего убрать, оставить ли салон). Всем ставится lodnoshadow, как у ванильных
# машин, а тень отбрасывает только грубый LOD HULL_LOD из блоков коллизии (иначе "Too detailed shadow lod ...").
VISUAL_LODS = ((0.0, 0.0, True), (1.0, 0.15, True), (2.0, 0.45, False))
HULL_LOD = 3.0
NO_SHADOW = [("lodnoshadow", "1")]


# --------------------------------------------------------------------------- геометрия столкновений
def convex_hull_geo(points):
    """Выпуклая оболочка небольшого набора точек (через scipy-free перебор граней)."""
    pts = np.unique(np.round(np.asarray(points, float), 5), axis=0)
    c = pts.mean(0)
    faces = []
    n = len(pts)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                nrm = np.cross(pts[j] - pts[i], pts[k] - pts[i])
                ln = np.linalg.norm(nrm)
                if ln < 1e-9:
                    continue
                nrm /= ln
                d = (pts - pts[i]) @ nrm
                if np.all(d <= 1e-6) or np.all(d >= -1e-6):
                    if np.dot(nrm, pts[i] - c) < 0:
                        nrm = -nrm
                    faces.append((i, j, k, tuple(np.round(nrm, 4)), round(float(np.dot(nrm, pts[i])), 4)))
    # объединяем копланарные треугольники в многоугольники и раскладываем веером
    planes = {}
    for f in faces:
        planes.setdefault((f[3], f[4]), set()).update(f[:3])
    g = G.Geo()
    for (nrm, _), idx in planes.items():
        idx = list(idx)
        nrm = np.array(nrm)
        ctr = pts[idx].mean(0)
        ax = pts[idx[0]] - ctr
        ax /= np.linalg.norm(ax)
        ay = np.cross(nrm, ax)
        ang = [math.atan2(np.dot(pts[k] - ctr, ay), np.dot(pts[k] - ctr, ax)) for k in idx]
        ring = [pts[k] for _, k in sorted(zip(ang, idx))]
        g += G.face(ring, nrm)
    return g


def box_geo(x0, x1, y0, y1, z0, z1):
    return G.box(min(x0, x1), max(x0, x1), y0, y1, min(z0, z1), max(z0, z1))


def collision_parts():
    """[(имя, Geo, масса, [селекции])] в исходных координатах."""
    cab = [(G.ZF_B, G.YB), (G.ZF_T, G.YT), (G.Z_ROOF_R, G.YT), (G.Z_REAR + 0.05, G.TAIL_Y), (G.Z_REAR, G.YB)]
    cab_pts = [(x, y, z) for z, y in cab for x in (-G.CAB_W, G.CAB_W)]
    hood_pts = [(x, y, z) for x in (-G.FENDER_W, G.FENDER_W)
                for z, y in ((G.HOOD_Z0, 1.30), (2.22, 1.08), (2.24, 0.62), (G.HOOD_Z0, 1.06), (2.24, 1.06))]
    parts = [
        ("frame", box_geo(-0.50, 0.50, 0.40, 0.56, -2.20, 2.15), 900, ["dmgZone_chassis"]),
        ("tub", box_geo(-0.70, 0.70, 0.55, 1.30, G.Z_REAR, G.HOOD_Z0), 450, ["dmgZone_chassis"]),
        ("side_l", box_geo(0.70, 1.06, 0.55, 1.30, -1.06, 0.98), 220, ["dmgZone_chassis"]),
        ("side_r", box_geo(-0.70, -1.06, 0.55, 1.30, -1.06, 0.98), 220, ["dmgZone_chassis"]),
        ("rear_l", box_geo(0.70, 1.06, 1.08, 1.30, G.Z_REAR, -1.06), 60, ["dmgZone_fuelTank"]),
        ("rear_r", box_geo(-0.70, -1.06, 1.08, 1.30, G.Z_REAR, -1.06), 60, ["dmgZone_chassis"]),
        ("engine", box_geo(-0.66, 0.66, 0.55, 1.06, G.HOOD_Z0, 2.24), 380, ["dmgZone_engine"]),
        ("hood", convex_hull_geo(hood_pts), 120, ["dmgZone_engine"]),
        ("cabin", convex_hull_geo(cab_pts), 300, ["dmgZone_chassis"]),
        ("bumper", box_geo(-1.10, 1.10, 0.50, 1.15, 2.24, 2.46), 90, ["dmgZone_chassis"]),
    ]
    return parts


def doors_parts():
    """[(селекция места, селекция двери, коллайдер двери, зона места)]. Зона места — неподвижный блок в проёме:
    закрытая дверь его закрывает (цель «Открыть»), открытая уходит в сторону, и в проёме цель «Сесть».
    Раньше местом была сама дверь: открытая уходила вместе с ней, а проём закрывал блок салона — на передние
    места сесть было нельзя, а на задние можно через закрытую дверь."""
    xa, xb = G.DOOR_X
    seat_of = {door: seat for seat, door in SEAT_DOOR.items()}
    out = []
    for door, (side, front) in G.DOORS.items():
        (y0, y1), (z0, z1) = G.DOOR_Y, G.DOOR_Z[front]
        out.append((seat_of[door], door, box_geo(side * xa, side * xb, y0, y1, z0, z1),
                    box_geo(side * xa, side * (xb - 0.02), y0 + 0.02, y1 - 0.02, z0 + 0.03, z1 - 0.03)))
    return out


def lids_parts():
    """{селекция: коллайдер} капота и крышки багажника для View/Fire Geometry, поворачиваются вместе с ними.
    Крышка багажника на 3–4 см выше наклонной крыши блока салона, иначе луч попадает в салон."""
    hood = [(x, y, z) for x in (-G.FENDER_W, G.FENDER_W)
            for z, y in ((G.HOOD_Z0, G.FEND_Y), (G.HOOD_Z0, G.HOOD_Y0 + 0.01), (G.HOOD_Z1, G.HOOD_Y1 + 0.01),
                         (G.FRONT_Z, 1.07), (G.FRONT_Z, G.FEND_Y))]
    z0, z1 = G.ROOF_Z0, G.SH_Z1 + 0.02
    trunk = [(x, y, z) for x in (-G.TRUNK_X, G.TRUNK_X)
             for z, y in ((z0, G.sh_top(z0) + 0.03), (z1, G.sh_top(z1) + 0.03), (z1, G.sh_top(z1) - 0.06),
                          (z0, G.sh_top(z0) - 0.06))]
    return {"doors_hood": convex_hull_geo(hood), "doors_trunk": convex_hull_geo(trunk)}


def hatch_collider():
    r = G.LID_R
    pts = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        for y in (G.RING_TOP - 0.01, G.RING_TOP + 0.05):
            pts.append((r * math.cos(a), y, G.HATCH_Z + r * math.sin(a)))
    return convex_hull_geo(pts)


CREW = [  # (селекция proxyPos из config.cpp, ванильный прокси, x, z) — те же места, что memory "crew*"
    ("crew" + seat, "crew_driver" if seat == "Driver" else "crew_cargo", x, z) for seat, (x, z) in G.SEATS.items()]


def add_proxies(b):
    """Прокси экипажа и колёс — в LOD 0, View и Fire Geometry, как у ванильной Ada.
    Без прокси экипажа в View Geometry: "Proxy with bone name 'crewDriver' was not found in view geometry"."""
    for sel, model, x, z in CREW:
        # yaw180: без разворота CrewTransform давал взгляд назад (0,0,-1), у ванили (0,0,+1) — человек сидел
        # спиной вперёд и попадал телом в соседнее кресло
        b.add_proxy(r"\DZ\vehicles\wheeled\proxies\%s" % model, (x, G.SEAT_Y, z), yaw180=True, selections=[sel])
    for name, (x, z, front) in WHEELS.items():
        # ванильный ProxyOffroad_02_Wheel связывает прокси .001…004 со слотами Offroad_02_Wheel_1_1, 1_2, 2_1, 2_2
        b.add_proxy(r"\dz\vehicles\wheeled\offroad_02\proxy\offroad_02_wheel", (x, G.WHEEL_Y, z), yaw180=(x < 0),
                    selections=[name])


# --------------------------------------------------------------------------- модели
def build_car_p3d(path):
    body = G.clean(G.build_body())
    interior = G.clean(G.build_interior())
    lid = G.clean(G.build_hatch_lid())
    lid_world = {m: g.transformed(G.T(0, G.HINGE_Y, G.HINGE_Z)) for m, g in lid.items()}
    doors = {sel: G.clean(p) for sel, p in {**G.build_doors(), **G.build_lids()}.items()}

    # развёртка всех окрашенных граней (двери, капот, багажник и люк — закрыты) в свой атлас
    global ATLAS
    ATLAS = texture_atlas.Atlas()
    for parts in (body, interior, lid_world, *doors.values()):
        for mat, g in parts.items():
            if mat in ATLAS_MATS:
                ATLAS.add(g, mat)
            elif mat != "glass":
                ATLAS.add_occluder(g)                    # фары, фонари, железо — только тень в затенении
    density = ATLAS.build()
    print(f"  атлас: кусков {len(ATLAS.patches)}, плотность {density:.0f} пикс/м")

    # LOD 0…2 — визуальная модель, дальние без мелких деталей
    lods = []
    for res, min_size, with_interior in VISUAL_LODS:
        cut = (lambda p: simplify(p, min_size)) if min_size else (lambda p: p)
        v = LodBuilder(res)
        v.add_parts(cut(body))
        if with_interior:
            v.add_parts(cut(interior))
        v.add_parts(cut(lid_world), selections=["hatch_roof"])
        for sel, p in doors.items():
            v.add_parts(cut(p), selections=[sel])
        add_proxies(v)
        # самопроверка: вершины подвижной детали не принадлежат граням вне её (иначе анимация тянет кузов)
        for sel in ["hatch_roof", *doors]:
            pts, faces = v.L.selections[sel]
            outside = {vt[0] for i, f in enumerate(v.L.faces) if i not in faces for vt in f["verts"]}
            assert not pts & outside, (res, sel, len(pts & outside))
        lods.append(v.done(props=NO_SHADOW))
    # самый дальний LOD и источник тени: выпуклые блоки коллизии в камуфляже
    h = LodBuilder(HULL_LOD)
    for _, g, _, _ in collision_parts():      # блоки не в атласе: цвет — из середины крыши
        h.add_geo(g, BODY_TEX, BODY_MAT, ["camo"])
    h.add_geo(hatch_collider(), BODY_TEX, BODY_MAT, ["camo", "hatch_roof"])
    add_proxies(h)
    lods.append(h.done())

    # Geometry (масса), Geometry Phys, View/Fire geometry
    def geo_lod(res, with_doors, with_hatch, mass):
        b = LodBuilder(res)
        view_fire = res in (RES_VIEWGEO, RES_FIREGEO)
        for name, g, m, sel in collision_parts():
            if view_fire and name == "hood":
                continue        # в View/Fire Geometry вместо него поворотный капот из lids_parts
            b.add_component(g, m, sel if res == RES_FIREGEO else ())
        if with_doors:
            for seat, door, g, seat_zone in doors_parts():
                if view_fire:
                    # коллайдер двери поворачивается вместе с ней (цель «Открыть/Закрыть» и попадания), место — в проёме
                    b.add_component(g, 0, [door])
                    b.add_component(seat_zone, 0, [seat])
                else:
                    b.add_component(g, 25 if mass else 0, [seat])
            if view_fire:
                for sel, g in lids_parts().items():
                    b.add_component(g, 0, [sel] + (["dmgZone_engine"] if res == RES_FIREGEO and sel == "doors_hood" else []))
        if with_hatch:
            b.add_component(hatch_collider(), 15 if mass else 0, ["hatch_roof"])
        if res == RES_GEOMETRY:
            # Ступицы: движок ищет wheelHub (wheel_X_Y_damper_land) в Geometry LOD, как у ванильной Ada,
            # иначе "Won't simulate, wheel ... has no proper selection in geometry" и машина не создаётся.
            for name, (x, z, _) in WHEELS.items():
                hub = box_geo(x - 0.1, x + 0.1, G.WHEEL_Y - 0.1, G.WHEEL_Y + 0.1, z - 0.1, z + 0.1)
                b.add_component(hub, 20, [name + "_damper_land"])
        if res in (RES_VIEWGEO, RES_FIREGEO):
            add_proxies(b)
        props = [("autocenter", "0")] if mass else []
        return b.done(with_mass=mass, props=props)

    lods.append(geo_lod(RES_GEOMETRY, True, True, True))
    # Geometry Phys (4e13) нет, как у ванильной Ada: с ним физика строит тело без ступиц wheel_*_damper_land,
    # и машину на первом шаге выбрасывает за пределы мира ("Overflow in AABB").
    lods.append(geo_lod(RES_VIEWGEO, True, True, False))
    lods.append(geo_lod(RES_FIREGEO, True, True, False))

    # Memory
    m = LodBuilder(RES_MEMORY)
    for name, (x, z, front) in WHEELS.items():
        c = (x, G.WHEEL_Y, z)
        m.add_memory(name + "_axis", (x - 0.1, G.WHEEL_Y, z), (x + 0.1, G.WHEEL_Y, z))
        m.add_memory(name + "_damper_land", c)
        m.add_memory(name + "_damper_axis", c, (x, G.WHEEL_Y + 1.0, z))
        if front:
            m.add_memory(name + "_steering_axis", (x, G.WHEEL_Y - 0.3, z), (x, G.WHEEL_Y + 0.3, z))
    for crew, (x, z) in G.SEATS.items():
        s, y = (1 if x > 0 else -1), G.SEAT_Y
        # встать для посадки у задней кромки проёма: открытая дверь (петли спереди) уходит вперёд и наружу,
        # на прежних 1.85 м напротив середины двери стоял её край
        zg = G.DOOR_Z[z > 0][0] + 0.25
        m.add_memory("crew" + crew, (x, y, z), (x, y + 2.0, z), (x, y, z + 1.0))
        m.add_memory("pos_" + crew.lower(), (s * 1.50, 0.05, zg))
        m.add_memory("pos_" + crew.lower() + "_dir", (s * 1.10, 0.05, zg))
    m.add_memory("hatch_roof_axis", (-0.25, G.HINGE_Y, G.HINGE_Z), (0.25, G.HINGE_Y, G.HINGE_Z))
    for sel, (side, front) in G.DOORS.items():   # петли дверей: вертикальная ось по передней кромке
        x, z = side * G.DOOR_XB, G.DOOR_HINGE_Z[front]
        m.add_memory(sel + "_axis", (x, 0.65, z), (x, 1.75, z))
    for sel, (y, z, _) in G.LIDS.items():      # петли капота и багажника: ось вдоль X
        m.add_memory(sel + "_axis", (-0.5, y, z), (0.5, y, z))
    m.add_memory("hatch_roof_center", (0, G.RING_TOP, G.HATCH_Z))
    for name, p in {
        "light_1_1": (G.HEADLIGHT_X, G.HEADLIGHT_Y, G.FRONT_Z + 0.04), "light_2_1": (-G.HEADLIGHT_X, G.HEADLIGHT_Y, G.FRONT_Z + 0.04),
        # CarScript ставит лучи фар и фонарь заднего хода по этим именам; без них свет был в начале координат модели
        "light_left": (G.HEADLIGHT_X, G.HEADLIGHT_Y, G.FRONT_Z + 0.05),
        "light_right": (-G.HEADLIGHT_X, G.HEADLIGHT_Y, G.FRONT_Z + 0.05),
        "light_left_dir": (G.HEADLIGHT_X, G.HEADLIGHT_Y - 0.06, G.FRONT_Z + 1.05),
        "light_right_dir": (-G.HEADLIGHT_X, G.HEADLIGHT_Y - 0.06, G.FRONT_Z + 1.05),
        "light_reverse": (0.0, 1.00, G.Z_REAR - 0.05),
        "light_1_2": (0.86, 1.06, G.Z_REAR - 0.03), "light_2_2": (-0.86, 1.06, G.Z_REAR - 0.03),
        "light_brake_1_2": (0.86, 1.06, G.Z_REAR - 0.03), "light_brake_2_2": (-0.86, 1.06, G.Z_REAR - 0.03),
        "light_reverse_1_2": (0.86, 0.94, G.Z_REAR - 0.03), "light_reverse_2_2": (-0.86, 0.94, G.Z_REAR - 0.03),
        "exhaust_start": G.EXHAUST_START, "exhaust_end": G.EXHAUST_END,
        "dmgZone_chassis": (0, 0.9, 0), "dmgZone_engine": (0, 1.0, 1.6),
        "dmgZone_fuelTank": (-0.85, 0.90, -1.30), "fire_pos": (0, 1.0, 1.6), "refill": (-1.03, 1.02, -1.30),
        "dashboard": (0.65, 1.28, 0.62), "engine": (0, 1.0, 1.6),
    }.items():
        m.add_memory(name, p)
    lods.append(m.done())

    # Land contact и Roadway (по крыше можно ходить)
    lc = LodBuilder(RES_LANDCONTACT)
    for name, (x, z, _) in WHEELS.items():
        lc.add_memory(name + "_contact", (x, 0.0, z))
    lods.append(lc.done())
    rw = LodBuilder(RES_ROADWAY)
    x0, x1, z0, z1 = G.ROOF_RECT
    y = G.YT + 0.01
    rw.add_geo(G.face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], (0, 1, 0)), uv=False)
    lods.append(rw.done())
    P3D.write(path, lods)
    return lods


def _normal_map(h, strength):
    """Карта нормалей (_nohq) из карты высот: RGB = нормаль * 0.5 + 0.5."""
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * strength
    nrm = np.stack([-gx, gy, np.ones_like(h)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    return np.clip((nrm * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)


def _smdi(spec, gloss):
    """_smdi: R не используется (белый), G — сила блика, B — глянец; spec/gloss в 0…1."""
    s = np.stack([np.ones_like(spec), spec, gloss], -1)
    return np.clip(s * 255, 0, 255).astype(np.uint8)


def write_rvmat(path, nohq, smdi, specular, power):
    """Материал Super как у ванильных машин: свои карты нормалей и бликов, остальное процедурное."""
    stages = [nohq, "#(argb,8,8,3)color(0.5,0.5,0.5,1,DT)", "#(argb,8,8,3)color(0,0,0,0,MC)",
              "#(argb,8,8,3)color(1,1,1,1,AS)", smdi, "#(ai,32,128,1)fresnel(1.376,0.315)",
              r"dz\data\data\env_land_optic_co.paa"]
    uv = ('\tuvSource="tex";\n\tclass uvTransform\n\t{\n\t\taside[]={1,0,0};\n\t\tup[]={0,1,0};\n'
          '\t\tdir[]={0,0,1};\n\t\tpos[]={0,0,0};\n\t};\n')
    out = ["// Сгенерировано RF_Humvee_Mod/tools/build_mod.py",
           "ambient[]={1,1,1,1};", "diffuse[]={1,1,1,1};", "forcedDiffuse[]={0,0,0,0};", "emmisive[]={0,0,0,1};",
           "specular[]={%g,%g,%g,1};" % ((specular,) * 3), "specularPower=%g;" % power,
           'PixelShaderID="Super";', 'VertexShaderID="Super";']
    for i, t in enumerate(stages, 1):
        out.append('class Stage%d\n{\n\ttexture="%s";\n%s};' % (i, t, uv))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


# --------------------------------------------------------------------------- model.cfg
# Источник damper_* движок ведёт в диапазоне 0…1 (0.5 — покой, как initPhase у ванильного M1025), а ось
# wheel_*_damper_axis длиной 1 м: смещение в метрах = ход подвески travelMaxUp/Down из config.cpp. Прежние
# -1…1 → ±1 м поднимали колёса в покое на 0.5 м выше капота.
SUSP_TRAVEL = 0.25   # travelMaxUp/Down ванильного M1025 (config Offroad_02)
DOOR_OPEN_RAD = 1.2   # ≈69°
# Источники анимации дверей и места — как у ванили (Transport.GetSeatIndexFromDoor: DoorsDriver = 0 ... DoorsCargo2 = 3)
DOOR_SOURCE = {"doors_driver": "DoorsDriver", "doors_codriver": "DoorsCoDriver",
               "doors_cargo1": "DoorsCargo1", "doors_cargo2": "DoorsCargo2",
               "doors_hood": "DoorsHood", "doors_trunk": "DoorsTrunk"}
SEAT_DOOR = {"seat_driver": "doors_driver", "seat_codriver": "doors_codriver",
             "seat_cargo1": "doors_cargo1", "seat_cargo2": "doors_cargo2"}
STEER_RAD = 0.5236   # 30° = maxSteeringAngle ванильного M1025


def model_cfg():
    bones = []
    anims = []
    for name, (x, z, front) in WHEELS.items():
        i, j = name.split("_")[1:]
        bones += ['"%s_damper",""' % name]
        parent = name + "_damper"
        if front:
            bones += ['"%s_steering","%s_damper"' % (name, name)]
            parent = name + "_steering"
        bones += ['"%s","%s"' % (name, parent)]
        side = "left" if i == "1" else "right"
        pos = "front" if front else "back"
        anims.append(f"""			class damper_{i}_{j}
			{{
				type = "translation";
				source = "damper_{i}_{j}";
				selection = "{name}_damper";
				axis = "{name}_damper_axis";
				memory = 1;
				minValue = 0; maxValue = 1;
				offset0 = -{SUSP_TRAVEL}; offset1 = {SUSP_TRAVEL};
			}};""")
        if front:
            anims.append(f"""			class turn{pos}{side}
			{{
				type = "rotation";
				source = "turn{pos}{side}";
				selection = "{name}_steering";
				axis = "{name}_steering_axis";
				memory = 1;
				minValue = -1; maxValue = 1;
				angle0 = -{STEER_RAD}; angle1 = {STEER_RAD};
			}};""")
        anims.append(f"""			class wheel{pos}{side}
			{{
				type = "rotation";
				source = "wheel{pos}{side}";
				selection = "{name}";
				axis = "{name}_axis";
				memory = 1;
				sourceAddress = "loop";
				minValue = 0; maxValue = 1;
				angle0 = 0; angle1 = -6.2831855;
			}};""")
    bones.append('"hatch_roof",""')
    for sel, (side, _) in G.DOORS.items():
        bones.append('"%s",""' % sel)
        # +угол открывает левую дверь наружу (проверено по люку: та же ось вращения), правой нужен минус
        anims.append(f"""			class {sel}
			{{
				type = "rotation";
				source = "{DOOR_SOURCE[sel]}";
				selection = "{sel}";
				axis = "{sel}_axis";
				memory = 1;
				minValue = 0; maxValue = 1;
				angle0 = 0; angle1 = {side * DOOR_OPEN_RAD};
			}};""")
    for sel, (_, _, angle) in G.LIDS.items():
        bones.append('"%s",""' % sel)
        anims.append(f"""			class {sel}
			{{
				type = "rotation";
				source = "{DOOR_SOURCE[sel]}";
				selection = "{sel}";
				axis = "{sel}_axis";
				memory = 1;
				minValue = 0; maxValue = 1;
				angle0 = 0; angle1 = {angle};
			}};""")
    # Кости мест экипажа, как crewdriver/crewcodriver/crewcargo1/2 в скелете ванильной Ada: без них движок
    # не находит прокси экипажа ("Proxy with bone name 'crewDriver' was not found in view geometry").
    bones += ['"%s",""' % sel for sel, _, _, _ in CREW]
    anims.append("""			// Люк: 0 -> закрыт, 1 -> открыт (110°). Если крышка уходит внутрь салона — поменяйте знак angle1.
			class hatch_roof
			{
				type = "rotation";
				source = "HatchRoof";
				selection = "hatch_roof";
				axis = "hatch_roof_axis";
				memory = 1;
				minValue = 0; maxValue = 1;
				angle0 = 0; angle1 = 1.9198622;
			};""")
    bone_txt = ",\n\t\t\t".join(bones)
    anim_txt = "\n".join(anims)
    return f"""// Сгенерировано RF_Humvee_Mod/tools/build_mod.py
class CfgSkeletons
{{
	class Default
	{{
		isDiscrete = 1;
		skeletonInherit = "";
		skeletonBones[] = {{}};
	}};
	class RF_Humvee_Skeleton: Default
	{{
		skeletonBones[] =
		{{
			{bone_txt}
		}};
	}};
}};

class CfgModels
{{
	class Default
	{{
		sectionsInherit = "";
		sections[] = {{}};
		skeletonName = "";
	}};
	class rf_humvee: Default
	{{
		skeletonName = "RF_Humvee_Skeleton";
		sections[] = {{"camo"}};
		class Animations
		{{
{anim_txt}
		}};
	}};
}};
"""


def main():
    lods = build_car_p3d(os.path.join(DATA, "rf_humvee.p3d"))
    # своя текстура: лесная и пустынная окраска, общие рельеф (по высоте сколов, царапин, грязи) и блики
    wheels = [(x, G.WHEEL_Y, z, G.WHEEL_R) for x, z, _ in WHEELS.values()]
    ATLAS.rasterize()
    # атлас рисуется в ATLAS.size (4096), в PAA уходит TEX_SIZE: сверхсэмплинг 2x2, UV не меняются
    k = ATLAS.size // TEX_SIZE
    co, height, spec, gloss = ATLAS.paint("woodland", wheels, MARKINGS)
    paa.write_paa(os.path.join(DATA, "rf_humvee_woodland_co.paa"), paa.downscale(co, k))
    paa.write_paa(os.path.join(DATA, "rf_humvee_body_nohq.paa"), paa.downscale_normals(_normal_map(height, 0.35), k))
    paa.write_paa(os.path.join(DATA, "rf_humvee_body_smdi.paa"), paa.downscale(_smdi(spec, gloss), k))
    co, _, _, _ = ATLAS.paint("desert", wheels, MARKINGS)
    paa.write_paa(os.path.join(DATA, "rf_humvee_desert_co.paa"), paa.downscale(co, k))
    write_rvmat(os.path.join(DATA, "rf_humvee_body.rvmat"),  # BUG-0009: путь ФС, не путь P3D
                r"rf_humvee\data\rf_humvee_body_nohq.paa",
                r"rf_humvee\data\rf_humvee_body_smdi.paa", 0.75, 250)    # как у ванильного M1025: блик узкий и слабый
    with open(os.path.join(DATA, "model.cfg"), "w", encoding="utf-8") as f:
        f.write(model_cfg())

    built = []
    if "--no-pbo" in sys.argv:                 # только текстуры/модель, без упаковки PBO
        print("PBO пропущен (--no-pbo)")
        return
    for addon in ("RF_Humvee", "RF_Humvee_Hatch"):
        files = pbo.pack(os.path.join(OUT_ADDONS, addon + ".pbo"), os.path.join(SRC, addon), addon)
        built.append((addon, len(files)))
    for L in lods:
        print(f"  LOD {L.resolution:g}: точек {len(L.points)}, граней {len(L.faces)}, селекций {len(L.selections)}")
    print("PBO:", built)


if __name__ == "__main__":
    main()
