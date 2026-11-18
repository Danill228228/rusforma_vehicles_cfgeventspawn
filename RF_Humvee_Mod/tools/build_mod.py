#!/usr/bin/env python3
"""
Сборка мода @RF_Humvee:
  1. P3D (MLOD) машины, колеса и прокси из геометрии RF_Humvee/source/generate_humvee.py
  2. текстуры PAA (лесной и пустынный камуфляж)
  3. model.cfg
  4. упаковка PBO:  @RF_Humvee/Addons/RF_Humvee.pbo и RF_Humvee_Hatch.pbo

Система координат P3D: X вправо, Y вверх, Z вперёд (левая). В исходной модели +X — левый борт,
поэтому X зеркалится. Запуск: python3 RF_Humvee_Mod/tools/build_mod.py
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
    """исходные координаты -> P3D"""
    return (-float(p[0]), float(p[1]), float(p[2]))


def texture_for(mat):
    if mat == "paint":
        return TEX_CAMO
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
        P = g.P * np.array([-1.0, 1.0, 1.0])
        N = g.N * np.array([1.0, -1.0, -1.0])         # отражённая нормаль, развернутая внутрь
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

    def add_parts(self, parts, selections=(), extra_sel=None):
        for mat, g in parts.items():
            sel = list(selections)
            if extra_sel and mat in extra_sel:
                sel += extra_sel[mat]
            self.add_geo(g, texture_for(mat), "", sel)

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
        fw = np.array([0, 0, -1.0 if yaw180 else 1.0]) * size
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
    cab = [(G.ZF_B, G.YB), (G.ZF_T, G.YT), (G.Z_ROOF_R, G.YT), (G.Z_REAR + 0.04, 1.62), (G.Z_REAR, G.YB)]
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
        ("seat_driver", box_geo(xa, xb, 0.60, 1.88, *fr)),      # левая передняя (водитель)
        ("seat_codriver", box_geo(-xa, -xb, 0.60, 1.88, *fr)),
        ("seat_cargo1", box_geo(xa, xb, 0.60, 1.88, *rr)),
        ("seat_cargo2", box_geo(-xa, -xb, 0.60, 1.88, *rr)),
    ]


def hatch_collider():
    r = G.LID_R
    pts = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        for y in (G.RING_TOP - 0.01, G.RING_TOP + 0.05):
            pts.append((r * math.cos(a), y, G.HATCH_Z + r * math.sin(a)))
    return convex_hull_geo(pts)


# --------------------------------------------------------------------------- модели
def build_car_p3d(path):
    body = G.clean(G.build_body())
    interior = G.clean(G.build_interior())
    lid = G.clean(G.build_hatch_lid())
    lid_world = {m: g.transformed(G.T(0, G.HINGE_Y, G.HINGE_Z)) for m, g in lid.items()}

    # LOD 0 — визуальная модель
    v = LodBuilder(0.0)
    v.add_parts(body, extra_sel={"paint": ["camo"]})
    v.add_parts(interior)
    v.add_parts(lid_world, selections=["hatch_roof"], extra_sel={"paint": ["camo"]})
    for name, (x, z, front) in WHEELS.items():
        v.add_proxy(r"\RF_Humvee\data\proxy\%s" % name, (x, G.WHEEL_Y, z), yaw180=(x < 0), selections=[name])
    lods = [v.done()]

    # Geometry (масса), Geometry Phys, View/Fire geometry
    def geo_lod(res, with_doors, with_hatch, mass):
        b = LodBuilder(res)
        for _, g, m, sel in collision_parts():
            b.add_component(g, m, sel if res == RES_FIREGEO else ())
        if with_doors:
            for sel, g in doors_parts():
                b.add_component(g, 25 if mass else 0, [sel])
        if with_hatch:
            b.add_component(hatch_collider(), 15 if mass else 0, ["hatch_roof"])
        props = [("autocenter", "0")] if mass else []
        return b.done(with_mass=mass, props=props)

    lods.append(geo_lod(RES_GEOMETRY, True, True, True))
    lods.append(geo_lod(RES_PHYS, False, False, True))
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
    m.add_memory("hatch_roof_center", (0, G.RING_TOP, G.HATCH_Z))
    for name, p in {
        "light_1_1": (0.89, 0.92, 2.25), "light_2_1": (-0.89, 0.92, 2.25),
        "light_1_2": (0.90, 1.08, -2.34), "light_2_2": (-0.90, 1.08, -2.34),
        "light_brake_1_2": (0.90, 1.08, -2.34), "light_brake_2_2": (-0.90, 1.08, -2.34),
        "light_reverse_1_2": (0.90, 0.97, -2.34), "light_reverse_2_2": (-0.90, 0.97, -2.34),
        "exhaust_start": (-0.85, 0.47, -2.35), "exhaust_end": (-0.85, 0.47, -2.47),
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
    v = LodBuilder(0.0)
    v.add_parts(wheel)
    lods = [v.done()]
    cyl = G.lathe([(0.0, -0.18), (G.WHEEL_R, -0.18), (G.WHEEL_R, 0.18), (0.0, 0.18)], seg=12, smooth_deg=5)
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
def camo_texture(palette, n=1024, seed=7):
    rng = np.random.default_rng(seed)
    base, c_brown, c_black, c_light = [np.array(c, float) for c in palette]
    A = G.periodic_field(n, 46, rng) + 0.35 * G.periodic_field(n, 12, rng)
    B = G.periodic_field(n, 38, rng) + 0.30 * G.periodic_field(n, 9, rng)
    C = G.periodic_field(n, 60, rng)
    D = G.periodic_field(n, 20, rng) + 0.3 * G.periodic_field(n, 6, rng)
    img = np.tile(base, (n, n, 1))

    def put(mask, col):
        mk = np.clip(mask, 0, 1)[..., None]
        img[:] = img * (1 - mk) + col * mk
    put((A - 0.10) * 6 + 0.5, c_brown)
    put((D - 1.85) * 6 + 0.5, c_light)
    put((0.30 - np.abs(B)) * 12 * (C > -0.4), c_black)
    return np.clip(img, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- model.cfg
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
				minValue = -1; maxValue = 1;
				offset0 = -1; offset1 = 1;
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
				angle0 = -1; angle1 = 1;
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
    paa.write_paa(os.path.join(DATA, "rf_humvee_woodland_co.paa"),
                  camo_texture([(62, 74, 44), (78, 60, 40), (26, 26, 22), (128, 116, 84)]))
    paa.write_paa(os.path.join(DATA, "rf_humvee_desert_co.paa"),
                  camo_texture([(176, 150, 108), (142, 112, 78), (104, 84, 62), (206, 188, 146)], seed=11))
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
