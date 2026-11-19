#!/usr/bin/env python3
"""
Сборка мода @RF_Humvee. Машина — ванильный M1025 (Offroad_02): модель, двери, капот, багажник, колёса, салон,
физика и звук берутся из файлов игры и в мод не копируются. Своя у мода только верхняя часть кузова — деталь
RF_HumveeHatch, которую клиент прикрепляет к машине вместо скрытых ванильных camo_roof и camo_interior_roof:
  1. P3D (MLOD): src/RF_Humvee/data/rf_humvee_hatch.p3d — плита крыши и потолок с отверстием люка, задние
     наплывы кузова по бокам багажника, кольцо и откидная крышка люка
  2. model.cfg с анимацией крышки
  3. упаковка PBO: @RF_Humvee/Addons/RF_Humvee.pbo и RF_Humvee_Hatch.pbo

Размеры сняты лучами по ванильному M1025 в игре (сигналы roofscan и bodyscan тестовой миссии), граница скрытой
части — по пробной машине с подкрашенной camo_roof. Координаты как в генераторе RF_Humvee/source/generate_humvee.py:
+X — левый борт, Y — вверх, +Z — перёд; скрипт ставит деталь с поворотом 180°, и в координатах M1025 она стоит
как (-x, y, z): водитель на -X, перёд на +Z. Запуск: python3 RF_Humvee_Mod/tools/build_mod.py
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

import generate_humvee as G  # noqa: E402  — помощники геометрии (lathe, face, cbox, roof_with_hole)
import p3d_mlod as P3D  # noqa: E402
import pbo  # noqa: E402

SRC = os.path.join(MOD, "src")
DATA = os.path.join(SRC, "RF_Humvee", "data")
OUT_ADDONS = os.path.join(MOD, "@RF_Humvee", "Addons")

# Крыша M1025: верх y = 1.84, плита от лобового стекла (z = 0.70) до начала заднего ската (z = -1.10), край x = ±1.05,
# снизу полоса над дверями ≈ 7 см.
ROOF_Y, CEIL_Y = 1.84, 1.765
ROOF_X, ROOF_Z0, ROOF_Z1 = 1.05, -1.10, 0.70
CHAMFER = 0.025
# Задние наплывы по бокам багажника: снаружи x = 1.08 (к верху 1.04), изнутри 0.74 (под краем крышки багажника),
# низ — линия окон y = 1.28, верх скатывается от 1.84 (z = -1.10) до 1.41 (z = -2.42), торец z = -2.47.
SH_X_IN, SH_X_OUT, SH_Y0 = 0.74, 1.08, 1.28
SH_Z0, SH_Z_SLOPE, SH_Z1, SH_Z_END = -1.05, -1.10, -2.42, -2.47
SH_SLOPE = (ROOF_Y - 1.414) / (SH_Z_SLOPE - SH_Z1)
# Люк — на месте ванильного кольца турели (в координатах M1025 x = -0.12, z = -0.30), отверстие насквозь.
HATCH_X, HATCH_Z = 0.12, -0.30
RING_IN, RING_OUT = 0.48, 0.58
RING_TOP = ROOF_Y + 0.10
LID_R = RING_OUT - 0.01
HINGE_Z = HATCH_Z - RING_OUT + 0.03     # петли сзади: крышка поднимается передней кромкой
HINGE_Y = RING_TOP + 0.012
OPEN_RAD = 1.9198622                    # 110°

# Текстуры и материалы — ванильные: снаружи многослойный материал крыши M1025 (грязь, потёртости), потолок —
# материал её внутренней стороны. Окраска задаётся в config.cpp (селекции camo и camo_interior). Развёртка каждой
# детали попадает в ровный камуфляж атласа (u 0.60…0.76, v 0.82…0.98), где маска слоёв однородна.
ROOF_TEX = r"dz\vehicles\wheeled\offroad_02\data\offroad_02_roof_co.paa"
ROOF_MULTI = r"dz\vehicles\wheeled\offroad_02\data\offroad_02_roof_multi.rvmat"
ROOF_MAT = r"dz\vehicles\wheeled\offroad_02\data\offroad_02_roof.rvmat"
ATLAS_BOX, ATLAS_K = (0.62, 0.76, 0.83, 0.98), 0.065   # без шва по краям и тёмной пластины у u = 0.60, v = 0.90
# центры развёртки деталей по очереди: на соседние детали ложатся разные пятна камуфляжа
ATLAS_CENTERS = [(0.69, 0.90), (0.66, 0.87), (0.73, 0.94), (0.67, 0.95), (0.72, 0.86), (0.70, 0.92)]
DARK_TEX = "#(argb,8,8,3)color(0.110,0.115,0.100,1,co)"  # петли, ручка, зажимы
PARTS = {"paint": (ROOF_TEX, ROOF_MULTI, ["camo"]), "interior": (ROOF_TEX, ROOF_MAT, ["camo_interior"]),
         "dark": (DARK_TEX, "", [])}
NO_SHADOW = [("lodnoshadow", "1")]
RES_MEMORY = 1e15


def to_p3d(p):
    """исходные координаты -> P3D: отражается Z (вместе с поворотом детали на 180° — перёд на +Z, водитель на -X)."""
    return (float(p[0]), float(p[1]), -float(p[2]))


def atlas_uv(g, center):
    """Кубическая проекция в метрах вокруг центра детали, сжатая в ровный участок атласа текстуры крыши.
    Центр сдвигается так, чтобы вся деталь осталась внутри ATLAS_BOX."""
    P, N = g.P, g.N
    u0, u1, v0, v1 = ATLAS_BOX
    ax = np.argmax(np.abs(N), axis=1)
    uv = np.zeros((len(P), 2))
    for a, (u, v) in ((0, (2, 1)), (1, (0, 2)), (2, (0, 1))):
        m = ax == a
        if not m.any():
            continue
        pu, pv = P[m, u], P[m, v]
        hu, hv = ATLAS_K * (pu.max() - pu.min()) / 2, ATLAS_K * (pv.max() - pv.min()) / 2
        assert hu <= (u1 - u0) / 2 and hv <= (v1 - v0) / 2, "деталь больше ровного участка атласа"
        cu, cv = np.clip(center[0], u0 + hu, u1 - hu), np.clip(center[1], v0 + hv, v1 - hv)
        uv[m, 0] = cu + ATLAS_K * (pu - (pu.min() + pu.max()) / 2)
        uv[m, 1] = cv - ATLAS_K * (pv - (pv.min() + pv.max()) / 2)
    return uv


class LodBuilder:
    def __init__(self, resolution):
        self.L = P3D.Lod(resolution)
        self._pts = {}
        self._nrm = {}
        self._pieces = 0

    def point(self, p, group=""):
        # group — подвижная деталь: её вершины не общие с остальными, иначе анимация тянет и соседние грани
        key = (group, *(round(c, 4) for c in p))
        if key not in self._pts:
            self._pts[key] = self.L.add_point(p)
        return self._pts[key]

    def normal(self, n):
        key = tuple(round(c, 3) for c in n)
        if key not in self._nrm:
            self._nrm[key] = self.L.add_normal(n)
        return self._nrm[key]

    def add_geo(self, g, mat, selections=(), group=""):
        """g — Geo в исходных координатах; грани и нормали переводятся в соглашения P3D."""
        if not len(g.I):
            return
        texture, material, sel = PARTS[mat]
        UV = atlas_uv(g, ATLAS_CENTERS[self._pieces % len(ATLAS_CENTERS)])
        self._pieces += 1
        P = g.P * np.array([1.0, 1.0, -1.0])           # как to_p3d
        N = g.N * np.array([-1.0, -1.0, 1.0])         # отражённая нормаль, развёрнутая внутрь
        pidx = [self.point(p, group) for p in P]
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
        for s in (*selections, *sel):
            self.L.select(s, pts, faces)

    def add_pieces(self, pieces, selections=()):
        """pieces — [(материал, Geo)]: у каждой детали своя развёртка вокруг её центра."""
        for mat, g in pieces:
            self.add_geo(g, mat, selections, group=",".join(selections))

    def add_memory(self, name, *points):
        self.L.select(name, [self.point(to_p3d(p)) for p in points], ())

    def done(self, props=()):
        self.L.properties = list(props)
        return self.L


# --------------------------------------------------------------------------- верхняя часть кузова
def build_roof():
    """Плита крыши: верх с отверстием люка, скос кромки, торцы, потолок с отверстием."""
    x0, x1, z0, z1 = -ROOF_X, ROOF_X, ROOF_Z0, ROOF_Z1
    c, yc = CHAMFER, ROOF_Y - CHAMFER
    top = G.roof_with_hole(ROOF_Y, (0, 1, 0), (x0 + c, x1 - c, z0 + c, z1 - c), HATCH_Z, HATCH_X, RING_IN)
    inner = [(x0 + c, ROOF_Y, z0 + c), (x1 - c, ROOF_Y, z0 + c), (x1 - c, ROOF_Y, z1 - c), (x0 + c, ROOF_Y, z1 - c)]
    outer = [(x0, yc, z0), (x1, yc, z0), (x1, yc, z1), (x0, yc, z1)]
    low = [(x, CEIL_Y, z) for x, _, z in outer]
    edge = G.Geo()
    for i in range(4):
        j = (i + 1) % 4
        mid = np.mean([outer[i], outer[j]], axis=0)
        out_dir = (mid[0], 0, mid[2] - (z0 + z1) / 2)
        edge += G.face([inner[i], inner[j], outer[j], outer[i]], (out_dir[0], 1, out_dir[2]))
        edge += G.face([outer[i], outer[j], low[j], low[i]], out_dir)
    ceil = G.roof_with_hole(CEIL_Y, (0, -1, 0), (x0, x1, z0, z1), HATCH_Z, HATCH_X, RING_IN)
    return [("paint", top), ("paint", edge), ("interior", ceil)]


def shoulder_section(x_side, top):
    """Сечение наплыва (x, y) при верхе top: внутренняя стенка, низ, наружная стенка со скруглением к верху."""
    s = x_side
    return [(s * SH_X_IN, SH_Y0), (s * SH_X_OUT, SH_Y0), (s * (SH_X_OUT - 0.005), top - 0.14),
            (s * (SH_X_OUT - 0.035), top - 0.045), (s * (SH_X_OUT - 0.09), top), (s * (SH_X_IN + 0.03), top),
            (s * SH_X_IN, top - 0.03)]


def build_shoulder(s):
    """Задний наплыв кузова с борта s (+1 левый, -1 правый): вытянут по z, верх скатывается назад."""
    def top(z):
        return ROOF_Y - SH_SLOPE * max(0.0, SH_Z_SLOPE - z)
    zs = [SH_Z0, SH_Z_SLOPE, SH_Z1, SH_Z_END]
    tops = [top(SH_Z0), top(SH_Z_SLOPE), top(SH_Z1), top(SH_Z1) - 0.07]   # торец со скосом верхней кромки
    secs = [[(x, y, z) for x, y in shoulder_section(s, t)] for z, t in zip(zs, tops)]
    n = len(secs[0])
    g = G.Geo()
    for a, b in zip(secs[:-1], secs[1:]):
        cx, cy = np.mean([p[0] for p in a]), np.mean([p[1] for p in a])
        for i in range(n):
            j = (i + 1) % n
            # сечение выпуклое: наружу — от его центра к середине ребра
            hint = ((a[i][0] + a[j][0]) / 2 - cx, (a[i][1] + a[j][1]) / 2 - cy, 0)
            g += G.face([a[i], a[j], b[j], b[i]], hint)
    g += G.face(secs[0], (0, 0, 1))
    g += G.face(secs[-1], (0, 0, -1))
    return [("paint", g)]


def build_ring():
    """Кольцо люка на плите с трубой до потолка и крепления."""
    ring = G.lathe([(RING_IN, CEIL_Y - ROOF_Y - 0.003), (RING_OUT, -0.01), (RING_OUT, 0.06), (RING_OUT - 0.02, 0.095),
                    (RING_IN + 0.02, 0.10), (RING_IN, 0.08), (RING_IN, CEIL_Y - ROOF_Y - 0.003)], seg=64, smooth_deg=35)
    dark = G.Geo()
    for s in (1, -1):                                   # кронштейны петель
        dark += G.cbox(HATCH_X + s * 0.20, RING_TOP + 0.006, HINGE_Z - 0.005, 0.07, 0.04, 0.06)
    for a in (0.5, -0.5, math.pi / 2, -math.pi / 2):    # зажимы кольца
        x, z = HATCH_X + RING_OUT * math.sin(a), HATCH_Z + RING_OUT * math.cos(a)
        dark += G.cbox(x, ROOF_Y + 0.05, z, 0.06, 0.08, 0.06)
    return [("paint", ring.transformed(G.chain(G.T(HATCH_X, ROOF_Y, HATCH_Z), G.AX_TO_Y))), ("dark", dark)]


def build_lid():
    """Крышка (закрыта) в мировых координатах; поворачивается вокруг оси петель hatch_roof_axis."""
    dz = HATCH_Z - HINGE_Z
    lid = G.lathe([(0.0, 0.0), (LID_R, 0.0), (LID_R, 0.03), (LID_R - 0.03, 0.045), (0.28, 0.055), (0.0, 0.06)],
                  seg=64, smooth_deg=35)
    dark = G.cbox(0, 0.085, dz + 0.30, 0.26, 0.022, 0.022)                         # ручка
    for s in (1, -1):
        dark += G.cbox(s * 0.12, 0.07, dz + 0.30, 0.022, 0.035, 0.022)
        dark += G.cbox(s * 0.20, 0.012, 0.03, 0.07, 0.024, 0.10)                   # петли
    dark += G.cylinder_x(0.015, -0.26, 0.26, 12)                                   # ось петель
    M = G.T(HATCH_X, HINGE_Y, HINGE_Z)
    return [("paint", lid.transformed(G.chain(M, G.T(0, 0, dz), G.AX_TO_Y))), ("dark", dark.transformed(M))]


def build_hatch_p3d(path):
    v = LodBuilder(0.0)
    v.add_pieces(build_roof() + build_shoulder(1) + build_shoulder(-1) + build_ring())
    v.add_pieces(build_lid(), selections=["hatch_roof"])
    lid_pts, lid_faces = v.L.selections["hatch_roof"]
    outside = {vt[0] for i, f in enumerate(v.L.faces) if i not in lid_faces for vt in f["verts"]}
    assert not lid_pts & outside, "вершины крышки общие с кольцом: анимация растянет кольцо"
    m = LodBuilder(RES_MEMORY)
    m.add_memory("hatch_roof_axis", (HATCH_X - 0.3, HINGE_Y, HINGE_Z), (HATCH_X + 0.3, HINGE_Y, HINGE_Z))
    m.add_memory("rf_origin", (0.0, 0.0, 0.0))    # скрипт по ней ставит деталь началом модели в начало машины
    lods = [v.done(props=NO_SHADOW), m.done()]
    P3D.write(path, lods)
    return lods


MODEL_CFG = f"""// Сгенерировано RF_Humvee_Mod/tools/build_mod.py
class CfgSkeletons
{{
	class Default
	{{
		isDiscrete = 1;
		skeletonInherit = "";
		skeletonBones[] = {{}};
	}};
	class RF_HumveeHatch_Skeleton: Default
	{{
		skeletonBones[] = {{"hatch_roof", ""}};
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
	class rf_humvee_hatch: Default
	{{
		skeletonName = "RF_HumveeHatch_Skeleton";
		sections[] = {{"camo", "camo_interior"}};
		class Animations
		{{
			// 0 -> закрыт, 1 -> открыт: крышка поднимается передней кромкой на 110°
			class hatch_roof
			{{
				type = "rotation";
				source = "HatchRoof";
				selection = "hatch_roof";
				axis = "hatch_roof_axis";
				memory = 1;
				minValue = 0; maxValue = 1;
				angle0 = 0; angle1 = {OPEN_RAD};
			}};
		}};
	}};
}};
"""


def main():
    lods = build_hatch_p3d(os.path.join(DATA, "rf_humvee_hatch.p3d"))
    with open(os.path.join(DATA, "model.cfg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(MODEL_CFG)
    built = []
    for addon in ("RF_Humvee", "RF_Humvee_Hatch"):
        files = pbo.pack(os.path.join(OUT_ADDONS, addon + ".pbo"), os.path.join(SRC, addon), addon)
        built.append((addon, len(files)))
    for L in lods:
        print(f"  LOD {L.resolution:g}: точек {len(L.points)}, граней {len(L.faces)}, селекций {len(L.selections)}")
    print("PBO:", built)


if __name__ == "__main__":
    main()
