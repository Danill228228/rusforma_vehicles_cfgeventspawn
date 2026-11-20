"""
Своя текстура модели RF_Humvee: развёртка всех окрашенных граней в один атлас и процедурная окраска с износом.

Развёртка: треугольники делятся на плоские куски (общее ребро и нормали в пределах 20°), каждый кусок
проецируется на свою плоскость в метрах и укладывается в атлас полками с одинаковой плотностью пикселей.
Окраска считается по положению точки на машине (мировые координаты модели, двери и крышки закрыты), поэтому
камуфляж идёт одним узором через стыки, грязь гуще внизу и у колёсных арок, потёртости — на кромках кусков.
Палитра — по ванильному M1025: лесной камуфляж из его текстуры крыши, пустынный — песочный.
"""
import math

import numpy as np

KEY_ROUND = 4


def tri_key(t):
    return tuple(np.round(np.asarray(t, float).reshape(-1), KEY_ROUND))


class Noise3D:
    """Трилинейный value-noise на решётке с шагом cell (м) по объёму машины, плавные веса."""

    def __init__(self, seed, cell, lo=(-1.8, -0.3, -3.3), hi=(1.8, 2.6, 3.3)):
        rng = np.random.default_rng(seed)
        self.cell = cell
        self.lo = np.array(lo, float)
        n = np.ceil((np.array(hi) - self.lo) / cell).astype(int) + 2
        self.R = rng.random(tuple(n)).astype(np.float32)

    def __call__(self, P):
        q = (P - self.lo) / self.cell
        i = np.clip(np.floor(q).astype(int), 0, np.array(self.R.shape) - 2)
        f = np.clip(q - i, 0, 1)
        f = f * f * (3 - 2 * f)
        R = self.R
        out = 0
        for dx in (0, 1):
            wx = f[:, 0] if dx else 1 - f[:, 0]
            for dy in (0, 1):
                wy = f[:, 1] if dy else 1 - f[:, 1]
                for dz in (0, 1):
                    wz = f[:, 2] if dz else 1 - f[:, 2]
                    out = out + wx * wy * wz * R[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
        return out


def fbm(P, seed, cell, octaves=3, scale=None):
    """Фрактальная сумма октав; scale — растяжение по осям (например, вертикальные подтёки)."""
    if scale is not None:
        P = P * np.asarray(scale, float)
    total, amp, norm = 0, 1.0, 0
    for k in range(octaves):
        total = total + amp * Noise3D(seed + 17 * k, cell / 2 ** k)(P)
        norm += amp
        amp *= 0.5
    return total / norm


def tile_noise(n, sigma, seed):
    """Бесшовный шум n×n (сглаженный гауссом в частотной области), нормированный к среднему 0 и σ = 1."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((n, n)))
    k = np.fft.fftfreq(n)
    field = np.real(np.fft.ifft2(f * np.exp(-2 * math.pi ** 2 * (k[:, None] ** 2 + k[None, :] ** 2) * sigma ** 2)))
    return ((field - field.mean()) / field.std()).astype(np.float32)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _trilinear(B, q):
    """Значение сетки B в дробных индексах q (n,3); за краями сетки — 0."""
    i0 = np.floor(q).astype(np.int64)
    f = (q - i0).astype(np.float32)
    shp = np.array(B.shape)
    out = np.zeros(len(q), np.float32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                ii = i0 + (dx, dy, dz)
                ok = ((ii >= 0) & (ii < shp)).all(1)
                ic = np.clip(ii, 0, shp - 1)
                w = ((f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1])
                     * (f[:, 2] if dz else 1 - f[:, 2]))
                out += w * B[ic[:, 0], ic[:, 1], ic[:, 2]] * ok
    return out


def _text_mask(text, px=96):
    """Надпись трафаретом: 0…1, обрезана по краям букв; строки разделяются переводом строки."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("bahnschrift.ttf", px)
    font.set_variation_by_name("Bold Condensed")
    img = Image.new("L", (px * (len(text) + 2), px * (text.count("\n") + 3)), 0)
    ImageDraw.Draw(img).multiline_text((px, px), text, fill=255, font=font, spacing=px // 5, align="center")
    a = np.asarray(img, np.float32) / 255
    ys, xs = np.nonzero(a > 0.1)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


class Atlas:
    def __init__(self, size=4096, pad=6, max_angle_deg=20.0):
        self.size, self.pad = size, pad
        self.cos_max = math.cos(math.radians(max_angle_deg))
        self.tris = []      # (n,3,3)
        self.mats = []      # имя материала на треугольник
        self.occ = []       # треугольники не из атласа: только отбрасывают тень в запечённое затенение
        self.AO = None

    def add(self, g, mat):
        if len(g.I):
            self.tris.append(g.P[g.I])
            self.mats += [mat] * len(g.I)

    def add_occluder(self, g):
        if len(g.I):
            self.occ.append(g.P[g.I])

    # ------------------------------------------------------------ развёртка
    def build(self, density=300.0):
        T = np.concatenate(self.tris)
        mats = np.array(self.mats)
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        area = np.linalg.norm(n, axis=1) / 2
        ok = area > 1e-8                                  # вырожденные треугольники без нормали не развёртываются
        T, mats, n, area = T[ok], mats[ok], n[ok], area[ok]
        n = n / (2 * area)[:, None]
        # куски: общее ребро, тот же материал, нормали близки
        _, vid = np.unique(np.round(T.reshape(-1, 3), KEY_ROUND), axis=0, return_inverse=True)
        vid = vid.reshape(-1, 3)
        parent = np.arange(len(T))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        edges = {}
        for t, (a, b, c) in enumerate(vid):
            for e in ((a, b), (b, c), (c, a)):
                edges.setdefault((min(e), max(e)), []).append(t)
        for ts in edges.values():
            for i in range(len(ts)):
                for j in range(i + 1, len(ts)):
                    a, b = ts[i], ts[j]
                    if mats[a] == mats[b] and n[a] @ n[b] > self.cos_max:
                        ra, rb = find(a), find(b)
                        if ra != rb:
                            parent[rb] = ra
        root = np.array([find(t) for t in range(len(T))])
        groups = [np.where(root == r)[0] for r in np.unique(root)]

        patches = []
        for idx in groups:
            nn = (n[idx] * area[idx, None]).sum(0)
            nn /= max(np.linalg.norm(nn), 1e-12)
            up = np.array([0.0, 1.0, 0.0]) if abs(nn[1]) < 0.9 else np.array([0.0, 0.0, 1.0])
            u = np.cross(up, nn)
            u /= np.linalg.norm(u)
            v = np.cross(nn, u)
            o = T[idx].reshape(-1, 3).min(0)
            q = np.stack([(T[idx] - o) @ u, (T[idx] - o) @ v], -1)     # (k,3,2) в метрах
            if np.ptp(q[..., 1]) > np.ptp(q[..., 0]):
                # кусок положен «на бок»: ось u' = v, v' = -u — без зеркала, чтобы рельеф не перевернулся
                u, v = v, -u
                q = np.stack([q[..., 1], -q[..., 0]], -1)
            q0 = q.reshape(-1, 2).min(0)
            q -= q0
            span = q.reshape(-1, 2).max(0)
            patches.append(dict(idx=idx, n=nn, u=u, v=v, o=o + q0[0] * u + q0[1] * v, q=q, span=span, mat=mats[idx[0]],
                                ytop=float(T[idx][..., 1].max())))

        # укладка полками; при нехватке места плотность уменьшается
        while True:
            placed = self._pack(patches, density)
            if placed:
                break
            density *= 0.92
        self.density = density
        S = self.size
        uv = np.zeros((len(T), 3, 2))
        for p in patches:
            px = p["q"] * density + p["xy"] + self.pad
            uv[p["idx"]] = px / S
        self.T, self.n, self.patches = T, n, patches
        self.lookup_uv = {tri_key(t): uv[i] for i, t in enumerate(T)}
        # блоки дальнего LOD не в атласе: им цвет из середины самого большого окрашенного куска (крыша)
        big = max((p for p in patches if p["mat"] == "paint"), key=lambda p: p["span"].prod())
        self.solid_uv = (big["xy"] + self.pad + big["span"] * density / 2) / S
        return density

    def _pack(self, patches, density):
        """Укладка «по линии горизонта»: высокие куски первыми, каждый — в самое низкое место, где он влезает."""
        S, pad = self.size, self.pad
        sizes = [(int(math.ceil(p["span"][0] * density)) + 2 * pad + 1, int(math.ceil(p["span"][1] * density)) + 2 * pad + 1)
                 for p in patches]
        order = sorted(range(len(patches)), key=lambda i: (-sizes[i][1], -sizes[i][0]))
        sky = np.zeros(S, np.int32)
        for i in order:
            w, h = sizes[i]
            if w > S:
                return False
            win = np.lib.stride_tricks.sliding_window_view(sky, w).max(1)
            x = int(np.argmin(win))
            y = int(win[x])
            if y + h > S:
                return False
            sky[x:x + w] = y + h
            patches[i]["xy"] = np.array([x, y], float)
        return True

    def uv_for(self, tris):
        """UV (n,3,2) для треугольников по их координатам; чужие треугольники — в сплошной цвет крыши."""
        out = np.zeros((len(tris), 3, 2))
        for i, t in enumerate(tris):
            out[i] = self.lookup_uv.get(tri_key(t), self.solid_uv)
        return out

    # ------------------------------------------------------------ растр: номер куска и мировые координаты
    def rasterize(self):
        S = self.size
        pid = np.full((S, S), -1, np.int32)
        for k, p in enumerate(self.patches):
            for t in p["idx"]:
                tri = self.lookup_uv[tri_key(self.T[t])] * S - 0.5
                x0, y0 = np.floor(tri.min(0)).astype(int)
                x1, y1 = np.ceil(tri.max(0)).astype(int)
                x0, y0, x1, y1 = max(x0 - 1, 0), max(y0 - 1, 0), min(x1 + 1, S - 1), min(y1 + 1, S - 1)
                ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
                a, b, c = tri
                d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                if abs(d) < 1e-9:
                    continue
                l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / d
                l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / d
                l3 = 1 - l1 - l2
                inside = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
                pid[ys[inside], xs[inside]] = k
        self.pid = pid
        # расстояние до края куска в пикселях (до 16), по 4-соседям
        dist = np.where(pid >= 0, 16, 0).astype(np.uint8)
        border = np.zeros_like(pid, bool)
        for sh, ax in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
            border |= (pid >= 0) & (np.roll(pid, sh, ax) != pid)
        dist[border] = 0
        for k in range(1, 16):
            m = dist >= k
            near = np.zeros_like(m)
            for sh, ax in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
                near |= np.roll(dist, sh, ax) == k - 1
            dist[m & near] = k
        self.edge = dist
        ys, xs = np.nonzero(pid >= 0)
        k = pid[ys, xs]
        O = np.array([p["o"] for p in self.patches])
        U = np.array([p["u"] for p in self.patches])
        V = np.array([p["v"] for p in self.patches])
        XY = np.array([p["xy"] for p in self.patches])
        D = self.density
        lu = (xs + 0.5 - XY[k, 0] - self.pad) / D
        lv = (ys + 0.5 - XY[k, 1] - self.pad) / D
        self.pix = (ys, xs)
        self.P = (O[k] + lu[:, None] * U[k] + lv[:, None] * V[k]).astype(np.float32)
        self.N = np.array([p["n"] for p in self.patches])[k].astype(np.float32)
        self.M = np.array([p["mat"] for p in self.patches])[k]
        self.E = dist[ys, xs].astype(np.float32)
        self.MINSPAN = np.array([p["span"].min() for p in self.patches])[k].astype(np.float32)
        self.YTOP = np.array([p["ytop"] for p in self.patches])[k].astype(np.float32)

    # ------------------------------------------------------------ детали, общие для обеих окрасок
    def details(self, wheels=(), markings=()):
        """Запечённое затенение, заклёпки с подтёками, трафареты и брызги: от окраски не зависят, считаются раз."""
        if self.AO is None:
            self.AO = self._ambient_occlusion(wheels)
            self.SEAM = self._seams()
            self.RIVET, self.RSTREAK = self._rivets()
            self.MARK = np.zeros(len(self.P), np.float32)
            for text, center, normal, width in markings:
                m = self._decal(_text_mask(text), center, normal, width)
                assert (m > 0.3).any(), f"трафарет {text!r} не попал на поверхность модели"   # модель поменялась
                self.MARK = np.maximum(self.MARK, m)
            self.SPECK = self._speck_tile(seed=21)[self.pix]

    def _seams(self, cell=0.012):
        """Стыки панелей: край куска, вплотную к которому (около 1 см) край другого куска того же материала в той
        же плоскости — дверь у кузова, крышка у борта. Сгиб листа (сосед под углом) и свободный край — не стык:
        тёмная обводка по всем рёбрам делала машину рисованной."""
        b = np.nonzero(self.E < 1)[0]
        k = self.pid[self.pix][b]
        mat = np.unique(self.M, return_inverse=True)[1].ravel()[b]
        nq = np.round(self.N[b] * 10).astype(np.int64)
        out = np.zeros(len(self.P), bool)
        for off in (0.0, cell / 2):                                         # две сетки со сдвигом: стык на границе ячеек
            key = np.column_stack([np.floor((self.P[b] + off) / cell).astype(np.int64), nq, mat])
            _, g = np.unique(key, axis=0, return_inverse=True)
            g = g.ravel()
            pairs = np.unique(np.column_stack([g, k]), axis=0)               # разные куски в ячейке
            many = np.bincount(pairs[:, 0], minlength=g.max() + 1) >= 2
            out[b[many[g]]] = True
        print(f"    стыков {out.sum()} пикс. из {len(b)} краевых")
        return out

    def _ambient_occlusion(self, wheels, h=0.03, sigmas=(0.03, 0.08, 0.20), strength=(0.50, 0.30, 0.15)):
        """Затенение по объёму: поверхности модели (и колёса-прокси) — в воксели 3 см, размытие гауссом на трёх
        масштабах; чем больше «стенок» перед точкой (в 3σ по нормали — своя стенка и то, что за ней, почти не
        считаются), тем она темнее: щели, арки, углы, салон."""
        lo = np.array([-2.2, -0.6, -3.7], np.float32)
        shape = np.ceil((np.array([2.2, 3.0, 3.5]) - lo) / h).astype(int)
        occ = np.zeros(shape, np.float32)

        def mark(pts):
            idx = np.floor((pts - lo) / h).astype(np.int64)
            ok = ((idx >= 0) & (idx < shape)).all(1)
            occ[tuple(idx[ok].T)] = 1

        T = np.concatenate([self.T] + self.occ).astype(np.float32)
        L = np.linalg.norm(T - np.roll(T, 1, axis=1), axis=2).max(1)
        K = np.clip(np.ceil(L / (0.5 * h)).astype(int), 1, 400)
        for k in np.unique(K):
            tt = T[K == k]
            i, j = np.mgrid[0:k + 1, 0:k + 1]
            m = i + j <= k
            a, b = (i[m] / k).astype(np.float32), (j[m] / k).astype(np.float32)
            step = max(1, 2_000_000 // len(a))
            for c in range(0, len(tt), step):
                t = tt[c:c + step]
                pts = (t[:, None, 0] + a[None, :, None] * (t[:, None, 1] - t[:, None, 0])
                       + b[None, :, None] * (t[:, None, 2] - t[:, None, 0]))
                mark(pts.reshape(-1, 3))
        ang = np.linspace(0, 2 * math.pi, 360, endpoint=False)
        for (wx, wy, wz, r) in wheels:              # колёса — прокси, в модели их нет: протектор и боковины
            for x in np.linspace(wx - 0.16, wx + 0.16, 12):
                mark(np.stack([np.full_like(ang, x), wy + r * np.cos(ang), wz + r * np.sin(ang)], 1))
            for x in (wx - 0.16, wx + 0.16):
                for rr in np.linspace(0.05, r, 16):
                    mark(np.stack([np.full_like(ang, x), wy + rr * np.cos(ang), wz + rr * np.sin(ang)], 1))

        pad = int(math.ceil(3 * max(sigmas) / h))
        sh = tuple(int(s) + 2 * pad for s in shape)                       # нули по краям: без свёртки через край
        F = np.fft.rfftn(occ, s=sh)
        fx, fy, fz = np.fft.fftfreq(sh[0]), np.fft.fftfreq(sh[1]), np.fft.rfftfreq(sh[2])
        ao = np.ones(len(self.P), np.float32)
        open_top = (self.N[:, 1] > 0.9) & (self.P[:, 1] > 1.80)            # крыша — открытая поверхность, эталон
        for sig, st in zip(sigmas, strength):
            s2 = -2 * math.pi ** 2 * (sig / h) ** 2
            G = (np.exp(s2 * fx ** 2)[:, None, None] * np.exp(s2 * fy ** 2)[None, :, None]
                 * np.exp(s2 * fz ** 2)[None, None, :])
            B = np.fft.irfftn(F * G, s=sh)[:shape[0], :shape[1], :shape[2]].astype(np.float32)
            B *= math.sqrt(2 * math.pi) * sig / h                          # ≈ число «стенок» вокруг точки
            V = np.empty(len(self.P), np.float32)
            for c in range(0, len(self.P), 1_000_000):
                V[c:c + 1_000_000] = _trilinear(B, (self.P[c:c + 1_000_000] + 3 * sig * self.N[c:c + 1_000_000] - lo) / h - 0.5)
            base = np.median(V[open_top]) if open_top.any() else 0.0
            top = np.percentile(V, 98)
            ao *= 1 - st * np.clip((V - base) / max(top - base, 1e-3), 0, 1)
            print(f"    затенение σ={sig}: эталон {base:.2f}, p50 {np.median(V):.2f}, p98 {top:.2f}")
        return ao

    def _rivets(self, spacing=0.065, inset=5, radius=2.2):
        """Ряды заклёпок вдоль стыков больших панелей (кроме стеклопластикового капота с крыльями); под частью
        заклёпок на вертикальных панелях — ржавые подтёки вниз. Возвращает (купол 0…1, подтёк 0…1) на пиксель."""
        S, D = self.size, self.density
        rng = np.random.default_rng(31)
        big = np.array([p["mat"] == "paint" and p["span"].min() > 0.20 for p in self.patches])
        k_all = self.pid[self.pix]
        cand = (self.E == inset) & big[k_all] & ~((self.P[:, 2] > 0.75) & (self.P[:, 1] < 1.40))
        c3 = 0.03                                                           # только у стыков, не по каждому сгибу
        near = set()
        for c in np.unique(np.floor(self.P[self.SEAM] / c3).astype(np.int64), axis=0).tolist():
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        near.add((c[0] + dx, c[1] + dy, c[2] + dz))
        ci = np.nonzero(cand)[0]
        cc = np.floor(self.P[ci] / c3).astype(np.int64).tolist()
        cand[ci[[tuple(c) not in near for c in cc]]] = False
        ys, xs, ks = self.pix[0][cand], self.pix[1][cand], k_all[cand]
        sp = spacing * D
        cell = sp
        grid = {}
        chosen = []
        for x, y, k in zip(xs.tolist(), ys.tolist(), ks.tolist()):
            cx, cy = int(x // cell), int(y // cell)
            if any((x - a) ** 2 + (y - b) ** 2 < sp * sp
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1) for a, b in grid.get((cx + dx, cy + dy), ())):
                continue
            grid.setdefault((cx, cy), []).append((x, y))
            chosen.append((x, y, k))
        dome = np.zeros((S, S), np.float32)
        streak = np.zeros((S, S), np.float32)
        r = int(math.ceil(radius))
        oy, ox = np.mgrid[-r:r + 1, -r:r + 1]
        stamp = np.clip(1 - (ox ** 2 + oy ** 2) / radius ** 2, 0, 1) ** 0.5
        for x, y, k in chosen:
            if r <= x < S - r and r <= y < S - r:
                win = dome[y - r:y + r + 1, x - r:x + r + 1]
                np.maximum(win, stamp, out=win)
            p = self.patches[k]
            down = np.array([-p["u"][1], -p["v"][1]])                      # мировой «вниз» в пикселях куска
            if np.linalg.norm(down) < 0.7 or rng.random() > 0.35:
                continue
            down /= np.linalg.norm(down)
            L = rng.uniform(8, 34)
            a0 = rng.uniform(0.35, 0.9)
            for t in np.arange(radius, L):
                px, py = x + down[0] * t, y + down[1] * t
                for w in (-0.5, 0.5):
                    qx, qy = int(px - down[1] * w), int(py + down[0] * w)
                    if 0 <= qx < S and 0 <= qy < S and self.pid[qy, qx] == k:
                        streak[qy, qx] = max(streak[qy, qx], a0 * (1 - t / L))
        print(f"    заклёпок {len(chosen)}")
        return dome[self.pix], streak[self.pix]

    def _decal(self, mask, center, normal, width, up=(0.0, 1.0, 0.0)):
        """Трафарет на поверхности: маска растягивается на width м, лицом по normal, верх — к up."""
        c = np.asarray(center, np.float32)
        n = np.asarray(normal, np.float32)
        n /= np.linalg.norm(n)
        rt = np.cross(-n, np.asarray(up, np.float32))
        rt /= np.linalg.norm(rt)
        upv = np.cross(n, rt)
        hgt = width * mask.shape[0] / mask.shape[1]
        from PIL import Image                                           # маска — к разрешению атласа
        size = (max(2, round(width * self.density)), max(2, round(hgt * self.density)))
        mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).resize(size, Image.BOX), np.float32) / 255
        d = self.P - c
        sel = np.nonzero((self.N @ n > 0.85) & (np.abs(d @ n) < 0.03))[0]
        s = d[sel] @ rt / width + 0.5
        t = 0.5 - d[sel] @ upv / hgt
        ok = (s >= 0) & (s < 1) & (t >= 0) & (t < 1)
        out = np.zeros(len(self.P), np.float32)
        out[sel[ok]] = mask[(t[ok] * mask.shape[0]).astype(int), (s[ok] * mask.shape[1]).astype(int)]
        return out

    def _speck_tile(self, seed, n=1024, count=7000):
        """Брызги: случайные капли радиусом 1–3 пикселя (тайл повторяется по атласу)."""
        rng = np.random.default_rng(seed)
        m = np.zeros((n, n), np.float32)
        for _ in range(count):
            x, y = rng.integers(0, n, 2)
            r = rng.uniform(0.8, 3.0)
            ri = int(math.ceil(r))
            oy, ox = np.mgrid[-ri:ri + 1, -ri:ri + 1]
            v = np.clip(1.5 - np.hypot(ox, oy) / r, 0, 1) * rng.uniform(0.5, 1)
            yy, xx = (y + oy) % n, (x + ox) % n
            m[yy, xx] = np.maximum(m[yy, xx], v)
        S = self.size
        return np.tile(m, (S // n, S // n))

    # ------------------------------------------------------------ окраска
    def paint(self, variant, wheels=(), markings=()):
        """Возвращает (co uint8 S×S×3, height float32, spec, gloss) для варианта 'woodland' или 'desert'."""
        self.details(wheels, markings)
        S = self.size
        P, N, M, E = self.P, self.N, self.M, self.E
        n = len(P)
        y = P[:, 1]
        spec = np.full(n, 0.08, np.float32)
        gloss = np.full(n, 0.55, np.float32)          # матовая армейская краска с узким бликом, как у ванили
        height = np.zeros(n, np.float32)

        # мелкие текстуры в пространстве атласа (тайл 1024 повторяется)
        def tiled(sig, seed):
            t = tile_noise(1024, sig, seed)
            return np.tile(t, (S // 1024, S // 1024))[self.pix]
        grain = tiled(1.2, 11)
        grain2 = tiled(6.0, 12)

        paint = M == "paint"
        interior = M == "interior"
        dark = M == "dark"
        seat = M == "seat"
        top = smoothstep(0.5, 0.9, N[:, 1])

        # 1. базовый цвет: палитра ванильного M1025 (лесной камуфляж) чуть светлее — запечённое затенение и налёт
        # ниже её темнят; пустынный — выгоревший песочный
        green, brown, black = np.array([66, 73, 53]), np.array([73, 61, 48]), np.array([31, 29, 32])
        if variant == "woodland":
            # крупные чёткие пятна, вытянутые вдоль машины; доли как у ванильного M1025: чёрного ~40%, зелёного ~40%,
            # коричневого ~20% (при 19% чёрного машина читалась однотонной, «игрушечной»)
            wob = 0.010 * (fbm(P, 41, 0.05, 2) - 0.5) + 0.002 * grain2         # неровные края пятен, как от пульверизатора
            f_br = fbm(P, 1, 0.9, 3, scale=(0.8, 1.25, 0.7)) + wob
            f_bk = fbm(P, 2, 0.8, 3, scale=(0.8, 1.25, 0.7)) + wob
            t_br, t_bk = np.quantile(f_br[paint], 0.67), np.quantile(f_bk[paint], 0.60)
            wb = smoothstep(t_br - 0.004, t_br + 0.004, f_br)[:, None]
            wk = smoothstep(t_bk - 0.004, t_bk + 0.004, f_bk)[:, None]
            base = (green * (1 - wb) + brown * wb) * (1 - wk) + black * wk
            under = np.array([84, 80, 66])                                      # под сколом — грунт
            dust_col, mud_col = np.array([112, 102, 84]), np.array([58, 50, 40])
        else:
            sand, sand2 = np.array([152, 137, 110]), np.array([141, 126, 103])
            base = sand + (sand2 - sand) * smoothstep(0.45, 0.65, fbm(P, 3, 1.2, 3))[:, None]
            under = green                                                       # под песочной — старая зелёная
            dust_col, mud_col = np.array([166, 150, 122]), np.array([92, 80, 62])
        variation = 1 + 0.07 * (fbm(P, 4, 0.35, 3) - 0.5) + 0.05 * (fbm(P, 42, 0.07, 2) - 0.5) + 0.025 * grain2
        col = (base * variation[:, None]).astype(np.float32)
        col[interior] = (base[interior] * 0.85) * variation[interior, None]
        col[dark] = np.array([34, 35, 31]) * (1 + 0.08 * grain2[dark, None])
        col[seat] = np.array([46, 46, 41]) * (1 + 0.10 * grain[seat, None] + 0.05 * grain2[seat, None])
        spec[dark], gloss[dark] = 0.06, 0.35
        spec[seat], gloss[seat] = 0.03, 0.10

        # выгорание на солнце: верхние грани светлее и серее
        fade = (0.28 * top * paint)[:, None]
        col = col * (1 - fade) + col.mean(1, keepdims=True) * 1.04 * fade

        # 2. трафареты (чёрная краска, местами облезла)
        worn = smoothstep(0.40, 0.70, fbm(P, 21, 0.025, 2))
        mk = (self.MARK * (0.92 - 0.75 * worn) * (paint | dark))[:, None]
        col = col * (1 - mk) + np.array([30, 30, 28]) * mk

        # 3. стыки панелей — тонкая тёмная щель; остальные рёбра только чуть скруглены в рельефе
        seam = self.SEAM & (paint | interior)
        col[seam] *= 0.55
        height[seam] -= 1.0
        height -= 0.5 * smoothstep(2.5, 0.0, E) * (paint | interior | dark)

        # 4. запечённое затенение и копоть в углублениях (в салоне мягче — его ещё затеняет движок)
        ao = np.where(interior | seat, 1 - 0.6 * (1 - self.AO), self.AO)
        grime = np.array([38, 34, 28])
        g = (1 - ao)[:, None]
        col = col * (1 - 0.55 * g) * (0.55 + 0.45 * ao[:, None]) + grime * 0.55 * g * (0.55 + 0.45 * ao[:, None])
        spec *= 0.4 + 0.6 * ao
        gloss *= 0.7 + 0.3 * ao

        # 4б. налёт: пятна грязи и разводы разного размера — без них краска ровная, как пластик
        blot = 0.6 * tiled(3.0, 33) + 0.5 * tiled(12.0, 34)
        stain = smoothstep(0.55, 0.80, fbm(P, 43, 0.30, 3))
        film = (0.08 + 0.32 * stain) * smoothstep(0.3, 1.8, blot)               # гуще местами, а не губкой везде
        film *= paint | dark | interior
        col = col * (1 - film[:, None]) + grime * film[:, None]
        light = 0.10 * smoothstep(1.0, 2.2, -blot) * (paint | interior)          # светлые разводы высохшей пыли
        col = col * (1 - light[:, None]) + dust_col * light[:, None]
        gloss *= 1 - 0.5 * film

        # 5. подтёки с верхних кромок панелей вниз по вертикальным граням: широкие и тонкие струйки
        vert = np.abs(N[:, 1]) < 0.5
        st = fbm(P, 5, 0.5, 2, scale=(6.0, 0.30, 6.0))
        st2 = fbm(P, 44, 0.5, 2, scale=(22.0, 0.6, 22.0))
        reach = np.exp(-np.maximum(self.YTOP - y, 0) / (0.20 + 0.45 * fbm(P, 45, 0.3, 1)))
        run = np.clip(0.7 * smoothstep(0.50, 0.80, st) + 0.6 * smoothstep(0.55, 0.75, st2), 0, 1)
        run *= (vert & (paint | dark)) * reach
        col = col * (1 - 0.40 * run[:, None]) + grime * 0.40 * run[:, None]

        # 6. заклёпки: купол в рельефе, чуть светлее, часть — с ржавым подтёком
        rv = self.RIVET * paint
        col *= (1 + 0.05 * rv)[:, None]
        height += 1.6 * rv
        rust = np.array([92, 56, 34])
        rs = (self.RSTREAK * (paint | dark))[:, None]
        col = col * (1 - 0.55 * rs) + rust * 0.55 * rs

        # 7. пыль и грязь: пыль внизу и на горизонталях, засохшая грязь у днища, брызги из-под колёс
        dn = fbm(P, 6, 0.35, 3)
        low = smoothstep(1.00, 0.35, y)
        dust = 0.50 * low * (0.55 + 0.6 * dn) + 0.40 * top * smoothstep(0.40, 0.70, dn) + 0.45 * (N[:, 1] < -0.5)
        dust += 0.35 * (interior & (N[:, 1] > 0.7))                              # пол салона
        dust *= 0.7 + 0.6 * smoothstep(-1.5, 1.5, tiled(5.0, 39))               # пыль клочьями, а не ровной заливкой
        dust = np.clip(dust, 0, 0.9) * (~seat)
        col = col * (1 - dust[:, None]) + dust_col * dust[:, None]
        splash = np.zeros(n, np.float32)
        for (wx, wy, wz, r) in wheels:
            d = np.hypot(P[:, 1] - wy, P[:, 2] - wz)
            side = np.abs(P[:, 0]) > abs(wx) - 0.45
            splash = np.maximum(splash, side * smoothstep(r + 0.60, r + 0.04, d))
        caked = np.clip(smoothstep(0.30, 0.05, y) + 0.8 * splash ** 2 * smoothstep(0.45, 0.65, fbm(P, 7, 0.10, 3)), 0, 1)
        drops = np.clip(splash ** 2 * self.SPECK, 0, 0.8) * (y < 1.1)          # редкие капли, гуще у колеса
        mud = np.maximum(caked, drops) * (~seat) * (~interior)
        col = col * (1 - 0.85 * mud[:, None]) + mud_col * 0.85 * mud[:, None]
        spec *= (1 - 0.8 * np.maximum(dust, mud))
        gloss *= (1 - 0.6 * np.maximum(dust, mud))
        height += 0.8 * mud * (0.5 + 0.5 * grain)

        # 8. сколы: пятнами у кромок в потёртых местах (не пунктиром по всем рёбрам) и редкие — посреди панели;
        # краска сбита до нижнего слоя, грунта и металла; на тёмных деталях — ржавчина.
        # Только на кусках шире 8 см: у труб, рёбер и рамок весь кусок — кромка, они были бы сплошь в сколах
        zone = smoothstep(0.48, 0.66, fbm(P, 46, 0.6, 2))
        hi = fbm(P, 8, 0.08, 3) + 0.015 * grain
        thr = 0.66 - 0.06 * zone
        chip = (E < 30 * (hi - thr)) | ((hi > 0.76 - 0.04 * zone) & (zone > 0.3))
        chip &= (paint | dark | interior) & (self.MINSPAN > 0.08)
        metal = np.array([92, 90, 84])
        steel = np.array([62, 60, 56])
        mix = smoothstep(0.55, 0.75, fbm(P, 9, 0.05, 2))
        deep = smoothstep(thr + 0.04, thr + 0.10, hi)                           # глубже — до грунта и металла
        layer = under * (1 - deep[:, None]) + (np.array([84, 80, 66]) * (1 - mix[:, None]) + metal * mix[:, None]) * deep[:, None]
        chip_col = np.where(dark[:, None], steel * (1 - mix[:, None]) + rust * mix[:, None], layer)
        col[chip] = chip_col[chip] * (0.6 + 0.4 * ao[chip, None])
        spec[chip], gloss[chip] = 0.25, 0.60
        height[chip] -= 0.8
        rf = fbm(P, 10, 0.10, 3)                                               # мелкая ржавчина, гуще у кромок
        rust_dark = dark & (rf > 0.66 - 0.08 * (E < 3))
        col[rust_dark] = col[rust_dark] * 0.72 + rust * 0.28

        # 9. царапины: тонкие светлые штрихи (в пространстве атласа, тайл с отрезками)
        scr = self._scratch_tile(seed=13)[self.pix] & (paint | interior) & (fbm(P, 11, 0.4, 2) > 0.62)
        col[scr] = col[scr] * 0.78 + metal * 0.22
        spec[scr], gloss[scr] = 0.20, 0.60
        height[scr] -= 0.4

        # 10. зерно краски для рельефа
        height += 0.25 * grain

        co = np.zeros((S, S, 3), np.float32)
        co[self.pix] = col
        h = np.zeros((S, S), np.float32)
        h[self.pix] = height
        sp_ = np.zeros((S, S), np.float32)
        sp_[self.pix] = spec
        gl = np.zeros((S, S), np.float32)
        gl[self.pix] = gloss
        filled = self.pid >= 0
        co, h, sp_, gl = self._bleed([co, h, sp_, gl], filled)
        return np.clip(co, 0, 255).astype(np.uint8), h, sp_, gl

    def _scratch_tile(self, seed, n=1024, count=900):
        rng = np.random.default_rng(seed)
        m = np.zeros((n, n), bool)
        for _ in range(count):
            x, y = rng.uniform(0, n, 2)
            a = rng.uniform(0, math.pi)
            L = rng.uniform(6, 40)
            for t in np.linspace(0, L, int(L) + 1):
                m[int(y + t * math.sin(a)) % n, int(x + t * math.cos(a)) % n] = True
        S = self.size
        return np.tile(m, (S // n, S // n))

    def _bleed(self, layers, filled, steps=None):
        """Растекание цвета за края кусков на ширину отступа: без чёрных швов на мип-уровнях."""
        steps = steps or self.pad + 2
        out = [L.copy() for L in layers]
        f = filled.copy()
        for _ in range(steps):
            grow = np.zeros_like(f)
            src = [np.zeros_like(L) for L in out]
            for sh, ax in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
                nb = np.roll(f, sh, ax) & ~f & ~grow
                for L, s in zip(out, src):
                    s[nb] = np.roll(L, sh, ax)[nb]
                grow |= nb
            for L, s in zip(out, src):
                L[grow] = s[grow]
            f |= grow
        return out
