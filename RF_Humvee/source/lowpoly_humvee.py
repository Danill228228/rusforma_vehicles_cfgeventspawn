"""
Кузов RF_Humvee из модели «Low Poly Humvee FREE» — MadTrollStudio, CC-BY-4.0 (low_poly_humvee/license.txt).

Модель (glTF) разбирается на кузов, салон, 4 двери, капот и крышку багажника (колёса модели в мод не идут:
у мода ванильное колесо M1025); сверху добавлены стёкла (в модели проёмы пустые), моторный отсек
и люк: в плите крыши и потолке вырезано отверстие, на крышу поставлено кольцо люка из generate_humvee.
Всё остальное (помощники геометрии, материалы, крышка люка) берётся из generate_humvee; константы ниже
заменяют его константы под эту модель, поэтому сборка мода импортирует этот модуль вместо генератора.
Координаты как в генераторе: +X — левый борт, Y — вверх, +Z — перёд.
"""
import functools
import json
import os

import numpy as np
from PIL import Image

from generate_humvee import *  # noqa: F401,F403 — помощники генератора; размеры ниже перекрыты под модель
from generate_humvee import DOORS, Geo, face, hatch_ring, roof_with_hole

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "low_poly_humvee")

# Размеры, снятые с модели (метры)
WHEEL_R = 0.485
WHEEL_Y = 0.475                     # низ шины на y = -0.01
AXLE_F, AXLE_R = 1.78, -1.45
TRACK_X = 0.94
YT = 1.829                          # верх плиты крыши
CEIL_Y = 1.79                       # потолок салона
ROOF_RECT = (-0.897, 0.897, -0.844, 0.849)    # плоский верх крыши (x0, x1, z0, z1)
CEIL_RECT = (-0.915, 0.915, -0.792, 0.777)
CAB_W = 1.06
YB = 1.30
ZF_B, ZF_T = 0.95, 0.85             # лобовое стекло: низ / верх
Z_ROOF_R = -0.844
Z_REAR = -2.22
TAIL_Y = 1.45
FRONT_Z = 2.23
HEADLIGHT_X, HEADLIGHT_Y = 0.50, 0.965
HOOD_Z0 = 0.95
FENDER_W = 1.11
EXHAUST_START, EXHAUST_END = (0.90, 0.40, -0.80), (1.10, 0.38, -0.86)   # перед задним колесом слева

HATCH_Z = -0.25                     # люк между передними и задними сиденьями, кольцо целиком на плоской крыше
RING_TOP = YT + 0.10
HINGE_Z = HATCH_Z - 0.455
HINGE_Y = RING_TOP + 0.012

DOOR_X = (0.97, 1.15)               # толщина двери по |x|
DOOR_Y = (0.64, 1.69)
DOOR_Z = {True: (0.02, 0.83), False: (-0.91, -0.06)}   # передняя / задняя дверь
DOOR_XB = 1.14                      # ось петель — у наружной передней кромки
DOOR_HINGE_Z = {front: z1 for front, (_, z1) in DOOR_Z.items()}
SEAT_Y = 0.86                       # верх подушки сиденья
SEATS = {"Driver": (0.685, 0.30), "CoDriver": (-0.685, 0.30), "Cargo1": (0.685, -0.58), "Cargo2": (-0.685, -0.58)}

# Капот и крышка багажника вырезаны из сетки кузова. Селекция: (y, z оси петель вдоль X, угол открытия, рад).
# Петли у передней кромки: капот наклоняется вперёд, как у настоящего HMMWV, крышка багажника поднимается
# задней кромкой. У люка петли сзади и угол с плюсом, здесь задняя кромка идёт вверх, поэтому минус.
LIDS = {"doors_hood": (1.08, 2.24, -1.31), "doors_trunk": (1.80, -0.80, -1.22)}

# стёкла (в модели проёмы пустые): лобовое — наклонная плоскость z(y), окна дверей — плоскость x
WINDSHIELD = [(0.055, 1.345), (1.022, 1.345), (0.986, 1.667), (0.942, 1.70), (0.87, 1.722), (0.055, 1.722)]
DOOR_GLASS = {True: (1.07, 0.149, 0.679, 1.267, 1.627), False: (1.079, -0.659, -0.179, 1.274, 1.624)}

COLORS = {  # цвет палитры модели -> материал генератора
    (165, 150, 128): "paint", (145, 131, 112): "paint", (59, 60, 60): "dark",
    (145, 92, 56): "amber", (231, 231, 231): "light", (90, 72, 64): "red",
}


def windshield_z(y):
    return 0.876 - 0.1398 * (y - 1.35)


@functools.lru_cache(maxsize=None)
def load():
    """Треугольники модели: T (n,3,3) и нормали N (n,3,3) в координатах генератора, материал и номер куска."""
    with open(os.path.join(MODEL, "scene.gltf"), encoding="utf-8") as f:
        g = json.load(f)
    buf = np.fromfile(os.path.join(MODEL, g["buffers"][0]["uri"]), np.uint8)

    def acc(i):
        a = g["accessors"][i]
        bv = g["bufferViews"][a["bufferView"]]
        n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[a["type"]]
        dt = np.dtype({5126: "<f4", 5125: "<u4", 5123: "<u2"}[a["componentType"]])
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        rows = np.lib.stride_tricks.as_strided(buf[off:], (a["count"], n * dt.itemsize),
                                               (bv.get("byteStride") or n * dt.itemsize, 1))
        return rows.copy().view(dt).reshape(a["count"], n).astype(float)

    def world(i, M):
        node = g["nodes"][i]
        # shortcut: читаются только ноды с matrix (так в этой модели), TRS-ноды потребуют сборки матрицы
        assert not {"translation", "rotation", "scale"} & node.keys(), node["name"]
        if "matrix" in node:
            M = M @ np.array(node["matrix"]).reshape(4, 4).T
        if "mesh" in node:
            return M
        for c in node.get("children", []):
            r = world(c, M)
            if r is not None:
                return r
        return None

    M = world(g["scenes"][g.get("scene", 0)]["nodes"][0], np.eye(4))
    prim = g["meshes"][0]["primitives"][0]
    P, Nv = acc(prim["attributes"]["POSITION"]), acc(prim["attributes"]["NORMAL"])
    UV, I = acc(prim["attributes"]["TEXCOORD_0"]), acc(prim["indices"]).astype(int).reshape(-1, 3)
    R = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]) @ M[:3, :3]     # glTF (x, y, z) -> генератор (z, y, -x)
    P = P @ R.T + np.array([M[2, 3], M[1, 3], -M[0, 3]])
    Nv = Nv @ np.linalg.inv(R)
    Nv /= np.maximum(np.linalg.norm(Nv, axis=1, keepdims=True), 1e-12)
    T, N = P[I], Nv[I]
    # намотку каждой грани по её нормали: у модели doubleSided, и часть граней может смотреть внутрь
    flip = np.einsum("ij,ij->i", np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), N.sum(1)) < 0
    T[flip], N[flip] = T[flip][:, ::-1], N[flip][:, ::-1]

    tex = np.asarray(Image.open(os.path.join(MODEL, g["images"][0]["uri"])).convert("RGB"))
    uv = UV[I].mean(1) % 1.0
    px = tex[(uv[:, 1] * tex.shape[0]).astype(int), (uv[:, 0] * tex.shape[1]).astype(int)]
    mat = np.array([COLORS[tuple(int(c) for c in p)] for p in px], dtype=object)

    # связные куски по совпадающим вершинам
    _, vid = np.unique(np.round(T.reshape(-1, 3), 4), axis=0, return_inverse=True)
    vid = vid.reshape(-1, 3)
    parent = np.arange(vid.max() + 1)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b, c in vid:
        ra = find(a)
        parent[find(b)] = ra
        parent[find(c)] = ra
    comp = np.array([find(a) for a in vid[:, 0]])
    return T, N, mat, comp


def _geo(T, N, k):
    """Треугольники k с обеих сторон: в DayZ грани односторонние, а модель рассчитана на двусторонние."""
    P, Nn = T[k].reshape(-1, 3), N[k].reshape(-1, 3)
    I = np.arange(len(P)).reshape(-1, 3)
    return Geo(np.vstack([P, P]), np.vstack([Nn, -Nn]), np.vstack([I, I[:, ::-1] + len(P)]))


def _pane(pts, hint):
    g = face(pts, hint)
    g += face(pts, -np.asarray(hint, float))
    return g


@functools.lru_cache(maxsize=None)
def _split():
    """Роль каждого треугольника: "body", "interior", "roof", "wheel:<id>" или селекция двери."""
    T, N, mat, comp = load()
    mat = mat.copy()
    role = np.empty(len(T), dtype=object)
    by_side = {(side, front): sel for sel, (side, front) in DOORS.items()}
    wheels, doors = [], []
    for r in np.unique(comp):
        m = comp == r
        pts = T[m].reshape(-1, 3)
        lo, hi = pts.min(0), pts.max(0)
        ext, c = hi - lo, (lo + hi) / 2
        if (mat[m] == "dark").all() and ext[1] > 0.9 and ext[0] < 0.4:
            role[m] = "wheel:%d" % r
            wheels.append(c)
        elif (lo[0] > 0.9 or hi[0] < -0.9) and ext[1] > 0.9 and ext[2] > 0.7:
            role[m] = by_side[(1 if c[0] > 0 else -1, bool(c[2] > 0))]
            doors.append(role[m][0])
        elif lo[1] > 1.65 and hi[1] > 1.82 and ext[2] > 1.5:
            role[m] = "roof"
        elif (lo > (-0.95, 0.44, -0.95)).all() and (hi < (0.95, 1.45, 0.80)).all():
            role[m] = "interior"
            if (mat[m] == "paint").any():   # сиденья тёмные, остальное в салоне — обшивка
                mat[m & (mat == "paint")] = "seat" if min(abs(lo[0]), abs(hi[0])) > 0.4 and lo[0] * hi[0] > 0 else "interior"
        else:
            role[m] = "body"
    # самопроверка: части нашлись и стоят там, где ждут WHEELS/memory-точки сборки
    assert sorted(doors) == sorted(DOORS), doors
    assert len(wheels) == 4 and (role == "roof").any(), (len(wheels), "крыша")
    for c in wheels:
        assert abs(abs(c[0]) - TRACK_X) < 0.01 and abs(c[1] - WHEEL_Y) < 0.01, c
        assert min(abs(c[2] - AXLE_F), abs(c[2] - AXLE_R)) < 0.01, c
    cz = T.mean(1)[:, 2]
    mat[(mat == "red") & (cz > 0)] = "dark"       # спереди тот же цвет — затемнённые фары

    # капот и крышка багажника — части самой большой сетки кузова, вместе с подкладкой снизу
    c, lo, hi = T.mean(1), T.min(1), T.max(1)
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)[:, None]
    shell = comp == np.bincount(comp[role == "body"]).argmax()
    hood = shell & (lo[:, 2] > 0.93) & (
        (lo[:, 1] > 1.05)                                                       # верх и крылья
        | ((hi[:, 1] > 1.12) & (np.abs(nrm[:, 0]) > 0.9) & (np.abs(c[:, 0]) > 1.04))   # борта крыльев целиком
        | ((c[:, 1] > 0.95) & (nrm[:, 1] < -0.9) & (np.abs(c[:, 0]) < 1.1)))    # подкладка капота
    for r in np.unique(comp[(role == "body") & ~shell]):   # воздухозаборник с карманом и замки на капоте
        m = comp == r
        p = T[m].reshape(-1, 3)
        if p[:, 2].min() > 1.2 and p[:, 1].max() > 1.15 and p[:, 2].max() < 2.21 and np.abs(p[:, 0]).max() < 0.6:
            hood |= m
    trunk = shell & (c[:, 2] < -0.86) & (hi[:, 2] < -0.70) & (lo[:, 1] > 1.38) & (
        (nrm[:, 1] > 0.4) | ((nrm[:, 1] < -0.85) & (c[:, 1] > 1.35)))           # наклонная крыша и подкладка
    role[hood], role[trunk] = "doors_hood", "doors_trunk"
    for m, (n0, n1) in ((hood, (500, 800)), (trunk, (30, 60))):
        assert n0 < m.sum() < n1, m.sum()
    return role, mat


def _parts(k_mask, mat):
    T, N, _, _ = load()
    parts = {m: Geo() for m in MATERIALS}
    for m in set(mat[k_mask]):
        parts[m] += _geo(T, N, np.where(k_mask & (mat == m))[0])
    return parts


def build_body():
    T, N, _, _ = load()
    role, mat = _split()
    cc = T.mean(1)
    ny = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ny = ny[:, 1] / np.maximum(np.linalg.norm(ny, axis=1), 1e-12)
    roof_top = (role == "roof") & (T[:, :, 1].min(1) > YT - 0.004) & (ny > 0.99)
    ceiling = (role == "body") & (T[:, :, 1].min(1) > CEIL_Y - 0.015) & (ny < -0.99) & \
        (np.abs(cc[:, 0]) < 0.92) & (np.abs(cc[:, 2]) < 0.8)
    parts = _parts(((role == "body") | (role == "roof")) & ~roof_top & ~ceiling, mat)
    # крыша и потолок заново — с отверстием люка, плюс кольцо люка
    parts["paint"] += roof_with_hole(YT, (0, 1, 0), ROOF_RECT, HATCH_Z)
    parts["paint"] += roof_with_hole(CEIL_Y, (0, -1, 0), CEIL_RECT, HATCH_Z)
    hatch_ring(parts, YT, HATCH_Z)
    for s in (1, -1):
        parts["glass"] += _pane([(s * x, y, windshield_z(y)) for x, y in WINDSHIELD], (0, 0, 1))
    # моторный отсек (в модели под капотом пусто): блок двигателя ниже кармана воздухозаборника, радиатор, фильтр, аккумулятор
    parts["dark"] += box(-0.26, 0.26, 0.50, 0.80, 1.15, 1.85)
    parts["dark"] += box(-0.50, 0.50, 0.62, 1.00, 2.08, 2.14)
    parts["dark"] += cbox(0.62, 0.84, 1.35, 0.26, 0.24, 0.36)
    parts["dark"] += cbox(-0.62, 0.80, 1.25, 0.26, 0.20, 0.30)
    return parts


def build_lids():
    """Капот и крышка багажника: {селекция: части} в координатах кузова."""
    role, mat = _split()
    return {sel: _parts(role == sel, mat) for sel in LIDS}


def build_interior():
    role, mat = _split()
    return _parts(role == "interior", mat)


def build_doors():
    role, mat = _split()
    out = {}
    for sel, (side, front) in DOORS.items():
        parts = _parts(role == sel, mat)
        x, z0, z1, y0, y1 = DOOR_GLASS[front]
        parts["glass"] += _pane([(side * x, y0, z0), (side * x, y0, z1), (side * x, y1, z1), (side * x, y1, z0)], (side, 0, 0))
        out[sel] = parts
    return out


if __name__ == "__main__":
    T, N, mat, comp = load()
    role, mat = _split()
    print("треугольников", len(T), "кусков", len(set(comp)))
    for r in sorted(set(role)):
        print(" ", r, int((role == r).sum()))
    for name, parts in (("кузов", build_body()), ("салон", build_interior()), *build_lids().items()):
        print(name, {m: len(g.I) for m, g in parts.items() if len(g.I)})
