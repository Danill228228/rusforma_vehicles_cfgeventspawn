#!/usr/bin/env python3
"""
Сборка мода @RF_Humvee. Машина — ванильный M1025 (Offroad_02): модель, двери, капот, багажник, колёса, физика
и звук берутся из файлов игры и в мод не копируются. Мод добавляет люк стрелка — деталь RF_HumveeHatch, которую
клиент прикрепляет к машине поверх ванильной крышки кольца турели:
  1. P3D (MLOD) люка: src/RF_Humvee/data/rf_humvee_hatch.p3d — кольцо, откидная крышка и тёмный проём под ней.
     Салон остаётся ванильным: изнутри видна ванильная закрытая крышка (она часть наружной крыши camo_roof,
     а её не скрыть без всей верхней части кузова)
  2. model.cfg с анимацией крышки
  3. упаковка PBO: @RF_Humvee/Addons/RF_Humvee.pbo и RF_Humvee_Hatch.pbo

Координаты как в генераторе RF_Humvee/source/generate_humvee.py: +X — левый борт, Y — вверх, +Z — перёд.
В P3D зеркалится Z (to_p3d), в игре модель видна как (-x, y, z): в координатах M1025 водитель на -X, перёд на +Z.
Запуск: python3 RF_Humvee_Mod/tools/build_mod.py
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

# Люк на месте ванильного кольца турели M1025. Сняты лучами по модели в игре (сигнал roofscan тестовой миссии):
# верх крыши y = 1.84, кольцо в геометрии попаданий x -0.70…0.45, z -0.70…0.10 (координаты M1025),
# поднятая крышка и её кронштейн до y = 1.97.
ROOF_Y = 1.84
HATCH_X, HATCH_Z = 0.12, -0.30          # центр кольца; в координатах M1025 x = -0.12
RING_IN, RING_OUT = 0.57, 0.66          # кольцо накрывает ванильную крышку (её радиус ≈ 0.58)
RING_TOP = ROOF_Y + 0.16                # выше ванильной крышки и кронштейна
LID_R = RING_OUT - 0.01
HINGE_Z = HATCH_Z - RING_OUT + 0.03     # петли сзади: крышка поднимается передней кромкой
HINGE_Y = RING_TOP + 0.012
OPEN_RAD = 1.9198622                    # 110°

# Текстура — ванильная текстура крыши M1025 (окраска задаётся в config.cpp через селекцию camo).
# Развёртка попадает в ровный камуфляж атласа (u 0.58…0.78, v 0.81…1.0): 0.08 UV на метр от центра крыши.
ROOF_TEX = r"dz\vehicles\wheeled\offroad_02\data\offroad_02_roof_co.paa"
ROOF_MAT = r"dz\vehicles\wheeled\offroad_02\data\offroad_02_roof.rvmat"
ATLAS_C, ATLAS_K = (0.68, 0.905), 0.08
HOLE_TEX = "#(argb,8,8,3)color(0.02,0.02,0.02,1,co)"     # проём под открытой крышкой
DARK_TEX = "#(argb,8,8,3)color(0.110,0.115,0.100,1,co)"  # петли, ручка, зажимы
PARTS = {"paint": (ROOF_TEX, ROOF_MAT, ["camo"]), "hole": (HOLE_TEX, "", []), "dark": (DARK_TEX, "", [])}
NO_SHADOW = [("lodnoshadow", "1")]
RES_MEMORY = 1e15


def to_p3d(p):
    """исходные координаты -> P3D: отражается Z (так модель в игре стоит передом на +Z, водитель на -X)."""
    return (float(p[0]), float(p[1]), -float(p[2]))


def atlas_uv(g):
    """Кубическая проекция в метрах, сжатая в ровный участок атласа текстуры крыши."""
    P, N = g.P, g.N
    ax = np.argmax(np.abs(N), axis=1)
    uv = np.zeros((len(P), 2))
    for a, (u, v) in ((0, (2, 1)), (1, (0, 2)), (2, (0, 1))):
        m = ax == a
        uv[m, 0] = ATLAS_C[0] + ATLAS_K * (P[m, u] - (HATCH_Z if u == 2 else 0.0))
        uv[m, 1] = ATLAS_C[1] - ATLAS_K * (P[m, v] - (HATCH_Z if v == 2 else ROOF_Y if v == 1 else 0.0))
    return uv


class LodBuilder:
    def __init__(self, resolution):
        self.L = P3D.Lod(resolution)
        self._pts = {}
        self._nrm = {}

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

    def add_geo(self, g, texture, material, selections=(), group=""):
        """g — Geo в исходных координатах; грани и нормали переводятся в соглашения P3D."""
        if not len(g.I):
            return
        UV = atlas_uv(g)
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
        for s in selections:
            self.L.select(s, pts, faces)

    def add_parts(self, parts, selections=()):
        for mat, g in parts.items():
            tex, rvmat, sel = PARTS[mat]
            self.add_geo(g, tex, rvmat, [*selections, *sel], group=",".join(selections))

    def add_memory(self, name, *points):
        self.L.select(name, [self.point(to_p3d(p)) for p in points], ())

    def done(self, props=()):
        self.L.properties = list(props)
        return self.L


# --------------------------------------------------------------------------- люк
def circle(y, r, hint, cx=HATCH_X, cz=HATCH_Z, n=64):
    return G.face([(cx + r * math.cos(2 * math.pi * k / n), y, cz + r * math.sin(2 * math.pi * k / n)) for k in range(n)], hint)


def build_ring():
    """Неподвижная часть: кольцо, тёмный проём (закрывает ванильную крышку под открытым люком), крепления."""
    parts = {m: G.Geo() for m in PARTS}
    ring = G.lathe([(RING_IN, -0.01), (RING_OUT, -0.01), (RING_OUT, 0.12), (RING_OUT - 0.02, 0.155),
                    (RING_IN + 0.02, 0.16), (RING_IN, 0.14), (RING_IN, -0.01)], seg=64, smooth_deg=35)
    parts["paint"] += ring.transformed(G.chain(G.T(HATCH_X, ROOF_Y, HATCH_Z), G.AX_TO_Y))
    parts["hole"] += circle(RING_TOP - 0.02, RING_IN, (0, 1, 0))
    for s in (1, -1):                                   # кронштейны петель
        parts["dark"] += G.cbox(HATCH_X + s * 0.22, RING_TOP + 0.006, HINGE_Z - 0.01, 0.08, 0.04, 0.07)
    for a in (0.5, -0.5, math.pi / 2, -math.pi / 2, math.pi):   # зажимы кольца
        x, z = HATCH_X + RING_OUT * math.sin(a), HATCH_Z + RING_OUT * math.cos(a)
        parts["dark"] += G.cbox(x, ROOF_Y + 0.06, z, 0.07, 0.09, 0.07)
    return parts


def build_lid():
    """Крышка в мировых координатах (закрыта); поворачивается вокруг оси петель hatch_roof_axis."""
    parts = {m: G.Geo() for m in PARTS}
    dz = HATCH_Z - HINGE_Z
    lid = G.lathe([(0.0, 0.0), (LID_R, 0.0), (LID_R, 0.03), (LID_R - 0.03, 0.045), (0.30, 0.055), (0.0, 0.06)],
                  seg=64, smooth_deg=35)
    parts["paint"] += lid.transformed(G.chain(G.T(0, 0, dz), G.AX_TO_Y))          # с низом: виден открытым
    parts["dark"] += G.cbox(0, 0.085, dz + 0.32, 0.28, 0.022, 0.022)              # ручка
    for s in (1, -1):
        parts["dark"] += G.cbox(s * 0.13, 0.07, dz + 0.32, 0.022, 0.035, 0.022)
        parts["dark"] += G.cbox(s * 0.22, 0.012, 0.03, 0.07, 0.024, 0.11)          # петли
    parts["dark"] += G.cylinder_x(0.016, -0.29, 0.29, 12)                          # ось петель
    return {m: g.transformed(G.T(HATCH_X, HINGE_Y, HINGE_Z)) for m, g in parts.items()}


def build_hatch_p3d(path):
    v = LodBuilder(0.0)
    v.add_parts(G.clean(build_ring()))
    v.add_parts(G.clean(build_lid()), selections=["hatch_roof"])
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
		sections[] = {{"camo"}};
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
