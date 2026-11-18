#!/usr/bin/env python3
"""
Сборка мода @RF_Humvee:
  1. P3D (MLOD) машины, колеса и прокси из геометрии RF_Humvee/source/generate_humvee.py
  2. текстуры PAA (лесной и пустынный камуфляж)
  3. model.cfg
  4. упаковка PBO:  @RF_Humvee/Addons/RF_Humvee.pbo и RF_Humvee_Hatch.pbo

В исходной модели +X — левый борт, +Z — перёд; в файле P3D зеркалится Z (см. to_p3d), тогда в игре
перёд на +Z, водитель на -X, как у ванильной Ada. Запуск: python3 RF_Humvee_Mod/tools/build_mod.py
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

import generate_humvee as G  # noqa: E402
import p3d_mlod as P3D  # noqa: E402
import paa  # noqa: E402
import pbo  # noqa: E402

SRC = os.path.join(MOD, "src")
DATA = os.path.join(SRC, "RF_Humvee", "data")
OUT_ADDONS = os.path.join(MOD, "@RF_Humvee", "Addons")

TEX_CAMO = r"rf_humvee\data\rf_humvee_woodland_co.paa"
MAT_BODY = r"rf_humvee\data\rf_humvee_body.rvmat"   # пустынная окраска — только своя текстура в config.cpp
SURFACES = {  # материал генератора: (цвет, rvmat) — грани с файловой текстурой обязаны иметь rvmat
    "rubber": (r"rf_humvee\data\rf_humvee_rubber_co.paa", r"rf_humvee\data\rf_humvee_rubber.rvmat"),
    "dark": (r"rf_humvee\data\rf_humvee_metal_co.paa", r"rf_humvee\data\rf_humvee_metal.rvmat"),
}


def material_for(mat, camo=TEX_CAMO):
    if mat == "paint":
        return MAT_BODY
    return SURFACES[mat][1] if mat in SURFACES else ""
RES_GEOMETRY, RES_PHYS = 1e13, 4e13
RES_MEMORY, RES_LANDCONTACT, RES_ROADWAY = 1e15, 2e15, 3e15
RES_VIEWGEO, RES_FIREGEO = 6e15, 7e15

WHEELS = {  # селекция: (x в исходной модели, z, передняя?)
    "wheel_1_1": (G.TRACK_X, G.AXLE_F, True),    # левое переднее
    "wheel_2_1": (-G.TRACK_X, G.AXLE_F, True),   # правое переднее
    "wheel_1_2": (G.TRACK_X, G.AXLE_R, False),   # левое заднее
    "wheel_2_2": (-G.TRACK_X, G.AXLE_R, False),  # правое заднее
}


def to_p3d(p):
    """исходные координаты -> P3D. Отражается Z, а не X: с отражением X игра видела машину развёрнутой на 180°
    (фары на z = -2.25, водитель на x = +1.85, у ванильной Ada фара на z = +1.84, водитель на x = -1.12)
    и на первой передаче ехала задом."""
    return (float(p[0]), float(p[1]), -float(p[2]))


def texture_for(mat, camo=TEX_CAMO):
    if mat == "paint":
        return camo
    if mat in SURFACES:
        return SURFACES[mat][0]
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

    def point(self, p, mass=0.0):
        key = tuple(round(c, 4) for c in p)
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

    def add_geo(self, g, texture="", material="", selections=(), uv=True):
        """g — Geo в исходных координатах; грани/нормали переводятся в соглашения P3D."""
        if not len(g.I):
            return
        UV = G.compute_uv(g) if uv else np.zeros((len(g.P), 2))
        P = g.P * np.array([1.0, 1.0, -1.0])           # как to_p3d
        N = g.N * np.array([-1.0, -1.0, 1.0])         # отражённая нормаль, развернутая внутрь
        pidx = [self.point(p) for p in P]
        nidx = [self.normal(n) for n in N]
        f0 = len(self.L.faces)
        for a, b, c in g.I:
            if len({pidx[a], pidx[b], pidx[c]}) < 3:
                continue
            self.L.faces.append(dict(
                verts=[(pidx[k], nidx[k], float(UV[k, 0]), float(UV[k, 1])) for k in (a, b, c)],
                flags=0, texture=texture, material=material))
        faces = range(f0, len(self.L.faces))
        pts = {v[0] for i in faces for v in self.L.faces[i]["verts"]}
        for s in selections:
            self.L.select(s, pts, faces)

    def add_parts(self, parts, selections=(), extra_sel=None, camo=TEX_CAMO):
        for mat, g in parts.items():
            sel = list(selections)
            if extra_sel and mat in extra_sel:
                sel += extra_sel[mat]
            # Грань с текстурой-файлом PAA без rvmat игра не рисует (кузов был невидим), процедурным цветам материал не нужен.
            self.add_geo(g, texture_for(mat, camo), material_for(mat, camo), sel)

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
    xa, xb = G.CAB_W, G.CAB_W + 0.06
    fr = (-0.27, 0.84)
    rr = (-1.02, -0.31)
    return [
        ("seat_driver", box_geo(xa, xb, 0.60, G.YT - 0.04, *fr)),      # левая передняя (водитель)
        ("seat_codriver", box_geo(-xa, -xb, 0.60, G.YT - 0.04, *fr)),
        ("seat_cargo1", box_geo(xa, xb, 0.60, G.YT - 0.04, *rr)),
        ("seat_cargo2", box_geo(-xa, -xb, 0.60, G.YT - 0.04, *rr)),
    ]


def hatch_collider():
    r = G.LID_R
    pts = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        for y in (G.RING_TOP - 0.01, G.RING_TOP + 0.05):
            pts.append((r * math.cos(a), y, G.HATCH_Z + r * math.sin(a)))
    return convex_hull_geo(pts)


CREW = [  # (селекция proxyPos из config.cpp, ванильный прокси, x, z) — те же места, что memory "crew*"
    ("crewDriver", "crew_driver", 0.47, -0.02),
    ("crewCoDriver", "crew_cargo", -0.47, -0.02),
    ("crewCargo1", "crew_cargo", 0.47, -0.98),
    ("crewCargo2", "crew_cargo", -0.47, -0.98),
]


def add_proxies(b):
    """Прокси экипажа и колёс — в LOD 0, View и Fire Geometry, как у ванильной Ada.
    Без прокси экипажа в View Geometry: "Proxy with bone name 'crewDriver' was not found in view geometry"."""
    for sel, model, x, z in CREW:
        # yaw180: без разворота CrewTransform давал взгляд назад (0,0,-1), у ванили (0,0,+1) — человек сидел
        # спиной вперёд и попадал телом в соседнее кресло
        b.add_proxy(r"\DZ\vehicles\wheeled\proxies\%s" % model, (x, 1.08, z), yaw180=True, selections=[sel])
    for name, (x, z, front) in WHEELS.items():
        b.add_proxy(r"\RF_Humvee\data\proxy\%s" % name, (x, G.WHEEL_Y, z), yaw180=(x < 0), selections=[name])


# --------------------------------------------------------------------------- модели
def build_car_p3d(path, camo=TEX_CAMO):
    body = G.clean(G.build_body())
    interior = G.clean(G.build_interior())
    lid = G.clean(G.build_hatch_lid())
    lid_world = {m: g.transformed(G.T(0, G.HINGE_Y, G.HINGE_Z)) for m, g in lid.items()}
    doors = {sel: G.clean(p) for sel, p in G.build_doors().items()}

    # LOD 0…2 — визуальная модель, дальние без мелких деталей
    lods = []
    for res, min_size, with_interior in VISUAL_LODS:
        cut = (lambda p: simplify(p, min_size)) if min_size else (lambda p: p)
        v = LodBuilder(res)
        v.add_parts(cut(body), extra_sel={"paint": ["camo"]}, camo=camo)
        if with_interior:
            v.add_parts(cut(interior), camo=camo)
        v.add_parts(cut(lid_world), selections=["hatch_roof"], extra_sel={"paint": ["camo"]}, camo=camo)
        for sel, p in doors.items():
            v.add_parts(cut(p), selections=[sel], extra_sel={"paint": ["camo"]}, camo=camo)
        add_proxies(v)
        lods.append(v.done(props=NO_SHADOW))
    # самый дальний LOD и источник тени: выпуклые блоки коллизии в камуфляже
    h = LodBuilder(HULL_LOD)
    for _, g, _, _ in collision_parts():
        h.add_geo(g, camo, MAT_BODY, ["camo"], uv=True)
    h.add_geo(hatch_collider(), camo, MAT_BODY, ["camo", "hatch_roof"], uv=True)
    add_proxies(h)
    lods.append(h.done())

    # Geometry (масса), Geometry Phys, View/Fire geometry
    def geo_lod(res, with_doors, with_hatch, mass):
        b = LodBuilder(res)
        for _, g, m, sel in collision_parts():
            b.add_component(g, m, sel if res == RES_FIREGEO else ())
        if with_doors:
            for sel, g in doors_parts():
                # в View/Fire Geometry коллайдер двери поворачивается вместе с ней (цель «Сесть»/«Открыть» и попадания)
                door = [SEAT_DOOR[sel]] if res in (RES_VIEWGEO, RES_FIREGEO) else []
                b.add_component(g, 25 if mass else 0, [sel] + door)
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
    seats = {  # (селекция места, x сиденья, z сиденья, сторона)
        "Driver": ("driver", 0.47, -0.02),
        "CoDriver": ("codriver", -0.47, -0.02),
        "Cargo1": ("cargo1", 0.47, -0.98),
        "Cargo2": ("cargo2", -0.47, -0.98),
    }
    for crew, (nm, x, z) in seats.items():
        s = 1 if x > 0 else -1
        o = (x, 1.08, z)
        m.add_memory("crew" + crew, o, (x, 3.08, z), (x, 1.08, z + 1.0))
        m.add_memory("pos_" + nm, (s * 1.85, 0.05, z + 0.25))
        m.add_memory("pos_" + nm + "_dir", (s * 1.30, 0.05, z + 0.25))
    m.add_memory("hatch_roof_axis", (-0.25, G.HINGE_Y, G.HINGE_Z), (0.25, G.HINGE_Y, G.HINGE_Z))
    for sel, (side, front) in G.DOORS.items():   # петли дверей: вертикальная ось по передней кромке
        x, z = side * G.DOOR_XB, G.DOOR_HINGE_Z[front]
        m.add_memory(sel + "_axis", (x, 0.65, z), (x, 1.75, z))
    m.add_memory("hatch_roof_center", (0, G.RING_TOP, G.HATCH_Z))
    for name, p in {
        "light_1_1": (G.HEADLIGHT_X, G.HEADLIGHT_Y, G.FRONT_Z + 0.04), "light_2_1": (-G.HEADLIGHT_X, G.HEADLIGHT_Y, G.FRONT_Z + 0.04),
        # CarScript ставит лучи фар и фонарь заднего хода по этим именам; без них свет был в начале координат модели
        "light_left": (G.HEADLIGHT_X, G.HEADLIGHT_Y, G.FRONT_Z + 0.05),
        "light_right": (-G.HEADLIGHT_X, G.HEADLIGHT_Y, G.FRONT_Z + 0.05),
        "light_left_dir": (G.HEADLIGHT_X, G.HEADLIGHT_Y - 0.06, G.FRONT_Z + 1.05),
        "light_right_dir": (-G.HEADLIGHT_X, G.HEADLIGHT_Y - 0.06, G.FRONT_Z + 1.05),
        "light_reverse": (0.0, 1.00, G.Z_REAR - 0.05),
        "light_1_2": (0.90, 1.08, -2.34), "light_2_2": (-0.90, 1.08, -2.34),
        "light_brake_1_2": (0.90, 1.08, -2.34), "light_brake_2_2": (-0.90, 1.08, -2.34),
        "light_reverse_1_2": (0.90, 0.97, -2.34), "light_reverse_2_2": (-0.90, 0.97, -2.34),
        "exhaust_start": G.EXHAUST_START, "exhaust_end": G.EXHAUST_END,
        "dmgZone_chassis": (0, 0.9, 0), "dmgZone_engine": (0, 1.0, 1.6),
        "dmgZone_fuelTank": (0.85, 1.0, -1.8), "fire_pos": (0, 1.0, 1.6),
        "dashboard": (0.47, 1.38, 0.62), "engine": (0, 1.0, 1.6),
    }.items():
        m.add_memory(name, p)
    lods.append(m.done())

    # Land contact и Roadway (по крыше можно ходить)
    lc = LodBuilder(RES_LANDCONTACT)
    for name, (x, z, _) in WHEELS.items():
        lc.add_memory(name + "_contact", (x, 0.0, z))
    lods.append(lc.done())
    rw = LodBuilder(RES_ROADWAY)
    rw.add_geo(G.face([(-G.CAB_W, G.YT + 0.01, G.Z_ROOF_R), (G.CAB_W, G.YT + 0.01, G.Z_ROOF_R),
                       (G.CAB_W, G.YT + 0.01, G.ZF_T), (-G.CAB_W, G.YT + 0.01, G.ZF_T)], (0, 1, 0)), uv=False)
    lods.append(rw.done())
    P3D.write(path, lods)
    return lods


def build_wheel_p3d(path):
    wheel = G.clean(G.build_wheel())
    lods = []
    for res, min_size, _ in VISUAL_LODS:
        v = LodBuilder(res)
        v.add_parts(simplify(wheel, min_size) if min_size else wheel)
        lods.append(v.done(props=NO_SHADOW))
    cyl = G.lathe([(0.0, -0.18), (G.WHEEL_R, -0.18), (G.WHEEL_R, 0.18), (0.0, 0.18)], seg=12, smooth_deg=5)
    h = LodBuilder(HULL_LOD)          # дальний LOD и тень колеса: 12-гранный цилиндр
    h.add_geo(convex_hull_geo(cyl.P), texture_for("rubber"), material_for("rubber"), uv=False)
    lods.append(h.done())
    for res, mass in ((RES_GEOMETRY, True), (RES_VIEWGEO, False), (RES_FIREGEO, False)):
        b = LodBuilder(res)
        b.add_component(convex_hull_geo(cyl.P), 40 if mass else 0)
        lods.append(b.done(with_mass=mass, props=[("autocenter", "0")] if mass else []))
    P3D.write(path, lods)


def build_proxy_p3d(path):
    b = LodBuilder(0.0)
    n = b.normal((1.0, 0.0, 0.0))
    idx = [b.point((0, 0, 0)), b.point((0, 0.002, 0)), b.point((0, 0, 0.001))]
    b.L.faces.append(dict(verts=[(i, n, 0.0, 0.0) for i in idx], flags=0, texture="", material=""))
    P3D.write(path, [b.done()])


# --------------------------------------------------------------------------- текстуры
def _stamp(mask, rng, count, rmin, rmax, value=1.0):
    """Сколы: count кружков радиусом rmin…rmax в бесшовной маске (перенос через край)."""
    n = mask.shape[0]
    for _ in range(count):
        cx, cy = rng.integers(0, n, 2)
        r = rng.uniform(rmin, rmax)
        k = int(math.ceil(r))
        dy, dx = np.mgrid[-k:k + 1, -k:k + 1]
        disc = np.clip(r + 0.5 - np.hypot(dx, dy), 0, 1) * value
        ys, xs = (cy + np.arange(-k, k + 1)) % n, (cx + np.arange(-k, k + 1)) % n
        mask[np.ix_(ys, xs)] = np.maximum(mask[np.ix_(ys, xs)], disc)


def _scratches(mask, rng, count, lmin, lmax):
    """Царапины: тонкие отрезки толщиной в пиксель, бесшовно."""
    n = mask.shape[0]
    for _ in range(count):
        x0, y0 = rng.uniform(0, n, 2)
        a, L = rng.uniform(0, math.pi), rng.uniform(lmin, lmax)
        t = np.arange(0, L, 0.5)
        xs = (x0 + t * math.cos(a)).astype(int) % n
        ys = (y0 + t * math.sin(a)).astype(int) % n
        mask[ys, xs] = np.maximum(mask[ys, xs], rng.uniform(0.4, 1.0))


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


def paint_textures(palette, dust, n=2048, seed=7):
    """Краска кузова: трёхцветный камуфляж с чёткими краями пятен (как НАТО на M1025), зерно, грязь, пыль,
    сколы до металла и царапины. Возвращает (_co, _nohq, _smdi). palette: основа, второй цвет, чёрный."""
    rng = np.random.default_rng(seed)
    base, c_second, c_black = [np.array(c, float) for c in palette]
    A = G.periodic_field(n, 0.07 * n, rng) + 0.35 * G.periodic_field(n, 0.018 * n, rng)
    B = G.periodic_field(n, 0.06 * n, rng) + 0.35 * G.periodic_field(n, 0.015 * n, rng)
    img = np.tile(base, (n, n, 1))

    def put(mask, col):
        mk = np.clip(mask, 0, 1)[..., None]
        img[:] = img * (1 - mk) + col * mk
    put((A - 0.35) * 30 + 0.5, c_second)        # крутой порог — край пятна чёткий, как у трафаретной окраски
    put((B - 0.85) * 30 + 0.5, c_black)
    # въевшаяся грязь крупными пятнами и зерно краски
    grime = np.clip(G.periodic_field(n, 0.12 * n, rng), -1.5, 1.5)
    img *= (0.93 - 0.05 * grime)[..., None]
    img *= (1 + 0.03 * G.periodic_field(n, 1.2, rng))[..., None]
    dust_m = np.clip((G.periodic_field(n, 0.03 * n, rng) - 0.8) * 0.4, 0, 0.35)
    put(dust_m, np.array(dust, float))
    # сколы до грунта и металла, царапины
    chips, scr = np.zeros((n, n)), np.zeros((n, n))
    _stamp(chips, rng, int(1.2 * n), 0.8, 3.5)
    _scratches(scr, rng, int(0.2 * n), 0.01 * n, 0.04 * n)
    put(chips * 0.85, np.array([92, 92, 86.0]))
    put(scr * 0.35, np.array([120, 118, 106.0]))
    h = 0.35 * G.periodic_field(n, 1.5, rng) + 0.6 * G.periodic_field(n, 0.015 * n, rng) - 2.0 * chips - 0.8 * scr
    spec = 0.22 + 0.45 * chips + 0.25 * scr - 0.15 * dust_m
    gloss = 0.28 + 0.40 * chips + 0.2 * scr - 0.2 * dust_m
    return np.clip(img, 0, 255).astype(np.uint8), _normal_map(h, 0.6), _smdi(spec, gloss)


def surface_textures(base, dust, spec, gloss, n=1024, seed=3, scratches=0):
    """Резина и тёмный металл: зерно, пятна, пыль, при желании царапины. Возвращает (_co, _nohq, _smdi)."""
    rng = np.random.default_rng(seed)
    img = np.tile(np.array(base, float), (n, n, 1))
    img *= (1 + 0.06 * G.periodic_field(n, 1.0, rng) + 0.05 * G.periodic_field(n, 0.04 * n, rng))[..., None]
    dust_m = np.clip((G.periodic_field(n, 0.05 * n, rng) - 0.6) * 0.3, 0, 0.25)[..., None]
    img = img * (1 - dust_m) + np.array(dust, float) * dust_m
    scr = np.zeros((n, n))
    if scratches:
        _scratches(scr, rng, scratches, 0.01 * n, 0.05 * n)
        img = img * (1 - 0.4 * scr[..., None]) + np.array([96, 96, 90.0]) * 0.4 * scr[..., None]
    h = G.periodic_field(n, 1.0, rng) + 0.5 * G.periodic_field(n, 0.02 * n, rng) - scr
    sp = np.full((n, n), spec) + 0.3 * scr - 0.3 * dust_m[..., 0]
    gl = np.full((n, n), gloss) + 0.3 * scr
    return np.clip(img, 0, 255).astype(np.uint8), _normal_map(h, 0.5), _smdi(sp, gl)


def write_rvmat(path, nohq, smdi, specular, power):
    """Материал Super как у ванильных машин: свои карты нормалей и бликов, остальное процедурное."""
    stages = [nohq, "#(argb,8,8,3)color(0.5,0.5,0.5,1,DT)", "#(argb,8,8,3)color(0,0,0,0,MC)",
              "#(argb,8,8,3)color(1,1,1,1,AS)", smdi, "#(ai,32,128,1)fresnel(1.26,0.85)",
              r"dz\data\data\env_land_co.paa"]
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
SUSP_TRAVEL = 0.16
DOOR_OPEN_RAD = 1.2   # ≈69°
# Источники анимации дверей и места — как у ванили (Transport.GetSeatIndexFromDoor: DoorsDriver = 0 ... DoorsCargo2 = 3)
DOOR_SOURCE = {"doors_driver": "DoorsDriver", "doors_codriver": "DoorsCoDriver",
               "doors_cargo1": "DoorsCargo1", "doors_cargo2": "DoorsCargo2"}
SEAT_DOOR = {"seat_driver": "doors_driver", "seat_codriver": "doors_codriver",
             "seat_cargo1": "doors_cargo1", "seat_cargo2": "doors_cargo2"}
STEER_RAD = 0.5585   # 32° = maxSteeringAngle в config.cpp (было ±1 рад = 57°)


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
	class rf_humvee_wheel: Default {{}};
}};
"""


def main():
    os.makedirs(os.path.join(DATA, "proxy"), exist_ok=True)
    lods = build_car_p3d(os.path.join(DATA, "rf_humvee.p3d"))
    build_wheel_p3d(os.path.join(DATA, "rf_humvee_wheel.p3d"))
    for name in WHEELS:
        build_proxy_p3d(os.path.join(DATA, "proxy", name + ".p3d"))
    # краска: лесная НАТО и пустынная, общие карты нормалей и бликов (одинаковый рисунок сколов, seed=7).
    # Яркость подобрана по ванильному M1025 рядом в игре: на экране у него ≈65, у прежней палитры было ≈130.
    co, nohq, smdi = paint_textures([(64, 69, 48), (72, 62, 46), (31, 31, 28)], dust=(108, 102, 88))
    paa.write_paa(os.path.join(DATA, "rf_humvee_woodland_co.paa"), co)
    paa.write_paa(os.path.join(DATA, "rf_humvee_body_nohq.paa"), nohq)
    paa.write_paa(os.path.join(DATA, "rf_humvee_body_smdi.paa"), smdi)
    co, _, _ = paint_textures([(124, 108, 82), (100, 82, 60), (74, 61, 48)], dust=(138, 128, 108))
    paa.write_paa(os.path.join(DATA, "rf_humvee_desert_co.paa"), co)
    write_rvmat(os.path.join(SRC, MAT_BODY), r"rf_humvee\data\rf_humvee_body_nohq.paa",
                r"rf_humvee\data\rf_humvee_body_smdi.paa", 0.35, 25)
    # резина и тёмный металл (рама, решётка, кенгурятник, петли)
    for name, args, (spec, power) in (("rubber", ((36, 35, 33), (105, 96, 82), 0.12, 0.15), (0.12, 8)),
                                      ("metal", ((46, 49, 42), (120, 112, 95), 0.35, 0.35), (0.5, 30))):
        co, nohq, smdi = surface_textures(*args, scratches=0 if name == "rubber" else 300)
        for kind, img in (("co", co), ("nohq", nohq), ("smdi", smdi)):
            paa.write_paa(os.path.join(DATA, "rf_humvee_%s_%s.paa" % (name, kind)), img)
        write_rvmat(os.path.join(DATA, "rf_humvee_%s.rvmat" % name), r"rf_humvee\data\rf_humvee_%s_nohq.paa" % name,
                    r"rf_humvee\data\rf_humvee_%s_smdi.paa" % name, spec, power)
    with open(os.path.join(DATA, "model.cfg"), "w", encoding="utf-8") as f:
        f.write(model_cfg())

    built = []
    for addon in ("RF_Humvee", "RF_Humvee_Hatch"):
        files = pbo.pack(os.path.join(OUT_ADDONS, addon + ".pbo"), os.path.join(SRC, addon), addon)
        built.append((addon, len(files)))
    for L in lods:
        print(f"  LOD {L.resolution:g}: точек {len(L.points)}, граней {len(L.faces)}, селекций {len(L.selections)}")
    print("PBO:", built)


if __name__ == "__main__":
    main()
