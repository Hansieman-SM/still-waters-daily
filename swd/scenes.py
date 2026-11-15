"""Calm, softly moving backgrounds in the Still Waters Daily style (flat illustrated landscapes, own code).
Every scene: Scene(rng, W, H, total).frame(t) -> float32 HxWx3 in 0..1. Motion is always visible but gentle:
slow push-in, shimmering water, twinkling stars, swaying wheat, drifting mist."""
import numpy as np, cv2

HORIZON = 1150


def hexc(h):
    h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def vgrad(H, W, stops):
    ys = np.linspace(0, 1, H)
    pos = [p for p, _ in stops]; cols = np.stack([hexc(c) for _, c in stops])
    g = np.stack([np.interp(ys, pos, cols[:, k]) for k in range(3)], -1).astype(np.float32)
    return np.repeat(g[:, None, :], W, 1)


def ridge(W, base, amp, rng, waves=3):
    x = np.arange(W, dtype=np.float32); y = np.full(W, base, np.float32)
    for k in range(waves):
        y += amp / (k + 1) * np.sin(x / W * np.pi * (1.2 + k * 1.7 + rng.uniform(0, .8)) + rng.uniform(0, 6.28))
    return y


def fill_below(img, yline, col, soft=1.5):
    H, W = img.shape[:2]
    yy = np.arange(H, dtype=np.float32)[:, None]
    a = np.clip((yy - yline[None, :]) / soft + 0.5, 0, 1)[..., None]
    img[:] = img * (1 - a) + col * a


def disc(H, W, cx, cy, r, soft=2.0):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return np.clip((r - d) / soft + 0.5, 0, 1), d


class Base:
    """Pre-rendered canvas (8% larger) with a slow push-in; subclasses add animated layers."""
    S = 1.08

    def __init__(self, rng, W, H, total):
        self.W, self.H, self.total, self.rng = W, H, total, rng
        self.BW, self.BH = int(W * self.S), int(H * self.S)
        self.canvas = self.paint(self.BW, self.BH)
        self.zoom_dir = 1 if rng.random() < 0.7 else -1

    def view(self, t, img=None):
        img = self.canvas if img is None else img
        p = t / max(self.total, 1)
        z = 1.0 + 0.045 * (p if self.zoom_dir > 0 else 1 - p)
        s = self.W / self.BW * z
        cx, cy = self.BW / 2, self.BH / 2
        M = np.float32([[s, 0, self.W / 2 - cx * s], [0, s, self.H / 2 - cy * s]])
        return cv2.warpAffine(img, M, (self.W, self.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def frame(self, t):
        return self.view(t)


def sparkles(rng, n, x0, x1, y0, y1, wmin=10, wmax=46):
    """Horizontal glints on water, denser near a vertical axis; each twinkles with its own phase."""
    xs = rng.normal((x0 + x1) / 2, (x1 - x0) / 4, n); ys = rng.uniform(y0, y1, n) ** 1.0
    ws = rng.uniform(wmin, wmax, n) * (0.5 + (ys - y0) / (y1 - y0))
    return np.stack([xs, ys, ws, rng.uniform(0, 6.28, n), rng.uniform(0.6, 1.6, n)], 1)


def draw_sparkles(img, sp, t, col, k=1.0, ox=0, oy=0, scale=1.0):
    H, W = img.shape[:2]
    for x, y, w, ph, sp_ in sp:
        a = (0.5 + 0.5 * np.sin(ph + t * sp_ * 2.2)) ** 2 * k
        if a < 0.05:
            continue
        X0 = int((x - w / 2) * scale + ox); X1 = int((x + w / 2) * scale + ox); Y = int(y * scale + oy)
        if 0 <= Y < H - 2:
            X0, X1 = max(0, X0), min(W, X1)
            if X1 > X0:
                img[Y:Y + 2, X0:X1] = img[Y:Y + 2, X0:X1] * (1 - a) + col * a


class Meadow(Base):
    """Blue-hour meadow with a winding stream that shimmers (as on 'You are not alone')."""
    def paint(self, W, H):
        r = self.rng; hz = int(HORIZON * self.S)
        img = vgrad(H, W, [(0, '#3e5170'), (0.35, '#5f7090'), (0.52, '#8d97a8'), (0.6, '#a9aeb4'), (1, '#a9aeb4')])
        fill_below(img, ridge(W, hz - 70, 40, r), hexc('#55665f'), 3)
        fill_below(img, ridge(W, hz - 20, 30, r), hexc('#3f5848'), 2)
        yy = np.arange(H, dtype=np.float32)[:, None]
        fg = vgrad(H, W, [(0, '#3f6a3c'), (hz / H, '#3f6a3c'), (1, '#2c5528')])
        a = np.clip((yy - hz) / 3, 0, 1)[..., None]; img[:] = img * (1 - a) + fg * a
        noise = cv2.GaussianBlur(r.standard_normal((H, W)).astype(np.float32), (0, 0), 1.2)
        img += (noise * 0.025 * (yy > hz))[..., None] * np.array([0.6, 1, 0.5], np.float32)
        # stream: centre line wiggles, width grows towards the viewer
        ys = np.arange(hz, H); p = (ys - hz) / (H - hz)
        cx = W / 2 + np.sin(p * 4.2 + r.uniform(0, 3)) * 120 * p + r.uniform(-40, 40) * (1 - p)
        half = 6 + 320 * p ** 1.6
        self.stream = np.zeros((H, W), np.float32)
        xx = np.arange(W, dtype=np.float32)
        for i, y in enumerate(ys):
            self.stream[y] = np.clip((half[i] - np.abs(xx - cx[i])) / 3 + 0.5, 0, 1)
        water = vgrad(H, W, [(0, '#9fa9bd'), (hz / H, '#9fa9bd'), (1, '#5d6e92')])
        img[:] = img * (1 - self.stream[..., None]) + water * self.stream[..., None]
        self.sp = sparkles(r, 160, W / 2 - 260, W / 2 + 260, hz + 40, H - 20, 8, 40)
        self.sp = self.sp[self.stream[self.sp[:, 1].astype(int).clip(0, H - 1), self.sp[:, 0].astype(int).clip(0, W - 1)] > 0.5]
        return np.clip(img, 0, 1)

    def frame(self, t):
        c = self.canvas.copy()
        draw_sparkles(c, self.sp, t, hexc('#e4e8f0'), 0.55)
        return self.view(t, c)


class MoonLake(Base):
    """Night lake: moon with halo, twinkling stars, a moon path that ripples on the water."""
    def paint(self, W, H):
        r = self.rng; hz = int(HORIZON * self.S)
        img = vgrad(H, W, [(0, '#0d1428'), (0.45, '#18223c'), (hz / H, '#26314c'), (1, '#0e1529')])
        self.mx, self.my = W / 2 + 70 + r.uniform(0, 40), int(250 * self.S)
        m, d = disc(H, W, self.mx, self.my, 62)
        img += (np.exp(-(d / 230) ** 2) * 0.18)[..., None] * hexc('#c8cede')
        img[:] = img * (1 - m[..., None]) + hexc('#cfcab8') * m[..., None]
        fill_below(img, ridge(W, hz - 25, 18, r), hexc('#141b30'), 2)
        yy = np.arange(H, dtype=np.float32)[:, None]
        wat = vgrad(H, W, [(0, '#1a2440'), (hz / H, '#1a2440'), (1, '#0b1124')])
        a = np.clip((yy - hz) / 2, 0, 1)[..., None]; img[:] = img * (1 - a) + wat * a
        n = 260
        self.stars = np.stack([r.uniform(0, W, n), r.uniform(0, hz - 60, n) ** 1.0, r.uniform(0.25, 0.9, n), r.uniform(0, 6.28, n), r.uniform(0.5, 2.0, n)], 1)
        self.stars = self.stars[np.hypot(self.stars[:, 0] - self.mx, self.stars[:, 1] - self.my) > 120]
        self.sp = sparkles(r, 150, self.mx - 60, self.mx + 60, hz + 15, H - 30, 14, 60)
        return np.clip(img, 0, 1)

    def frame(self, t):
        c = self.canvas.copy()
        for x, y, b, ph, s in self.stars:
            a = b * (0.55 + 0.45 * np.sin(ph + t * s))
            X, Y = int(x), int(y)
            c[Y:Y + 3, X:X + 3] = c[Y:Y + 3, X:X + 3] * (1 - a * 0.8) + a * 0.8 * hexc('#e8ecf6')
        draw_sparkles(c, self.sp, t, hexc('#c9c8bc'), 0.6)
        return self.view(t, c)


class Sunset(Base):
    """Purple-amber sunset over the sea, sun on the horizon, a glittering sun path."""
    def paint(self, W, H):
        r = self.rng; hz = int(HORIZON * self.S)
        img = vgrad(H, W, [(0, '#2f2a44'), (0.3, '#5a4560'), (0.47, '#9a7468'), (hz / H, '#d8a86a'), (1, '#3a2e3e')])
        self.sx = W / 2 + r.uniform(-60, 60)
        m, d = disc(H, W, self.sx, hz - 8, 58)
        img += (np.exp(-(d / 260) ** 2) * 0.22)[..., None] * hexc('#ffd59a')
        img[:] = img * (1 - m[..., None]) + hexc('#f1d7a6') * m[..., None]
        fill_below(img, ridge(W, hz - 30, 34, r), hexc('#3e2d3c'), 2)
        yy = np.arange(H, dtype=np.float32)[:, None]
        sea = vgrad(H, W, [(0, '#5e4652'), (hz / H, '#7a5a5c'), (0.8, '#4a3946'), (1, '#33283a')])
        a = np.clip((yy - hz) / 2, 0, 1)[..., None]; img[:] = img * (1 - a) + sea * a
        self.sp = sparkles(r, 230, self.sx - 150, self.sx + 150, hz + 10, H - 30, 14, 70)
        return np.clip(img, 0, 1)

    def frame(self, t):
        c = self.canvas.copy()
        draw_sparkles(c, self.sp, t, hexc('#f3d9a8'), 0.7)
        return self.view(t, c)


class Wheat(Base):
    """Golden wheat field at dusk that sways in a soft breeze (as on 'Worried about tomorrow?')."""
    def paint(self, W, H):
        r = self.rng; hz = int(HORIZON * self.S)
        img = vgrad(H, W, [(0, '#2c2a48'), (0.35, '#5b4766'), (0.5, '#a07a6a'), (hz / H, '#c99a62'), (1, '#c99a62')])
        m, d = disc(H, W, W / 2 + r.uniform(-100, 100), hz - 40, 64)
        img += (np.exp(-(d / 240) ** 2) * 0.15)[..., None] * hexc('#ffdca0')
        img[:] = img * (1 - m[..., None]) + hexc('#e8c79a') * m[..., None]
        fill_below(img, ridge(W, hz - 20, 30, r), hexc('#4a3a40'), 2)
        self.hz = hz
        field = vgrad(H - hz, W, [(0, '#8a6a3a'), (0.4, '#9a7438'), (1, '#6a4a22')])
        strokes = np.zeros((H - hz, W), np.float32)
        for _ in range(9000):
            x = r.uniform(0, W); y = r.uniform(0, H - hz) ** 1.0
            L = 8 + 70 * (y / (H - hz)) ** 1.3
            cv2.line(strokes, (int(x), int(y)), (int(x + r.uniform(-3, 3)), int(y - L)), float(r.uniform(0.3, 1.0)), 1 + int(r.random() < y / (H - hz)) + int(r.random() < (y / (H - hz)) ** 2), cv2.LINE_AA)
        strokes = cv2.GaussianBlur(strokes, (0, 0), 0.8)
        field += strokes[..., None] * hexc('#e0b56a') * 0.35
        self.field = np.clip(field, 0, 1).astype(np.float32)
        img[hz:] = self.field
        return np.clip(img, 0, 1)

    def frame(self, t):
        c = self.canvas.copy()
        h = self.field.shape[0]
        yy, xx = np.mgrid[0:h, 0:self.BW].astype(np.float32)
        depth = (yy / h) ** 1.2
        dx = (np.sin(t * 1.1 + xx / 260 + yy / 90) * 2.5 + np.sin(t * 0.6 + xx / 600) * 3.5) * depth
        c[self.hz:] = cv2.remap(self.field, xx + dx, yy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        return self.view(t, c)


class DawnLake(Base):
    """Soft dawn over a still lake with tree line, drifting mist and gentle ripples."""
    def paint(self, W, H):
        r = self.rng; hz = int(HORIZON * self.S)
        img = vgrad(H, W, [(0, '#41567a'), (0.3, '#7a86a6'), (0.48, '#c9a7a6'), (hz / H, '#ecc79e'), (1, '#ecc79e')])
        line = ridge(W, hz - 14, 8, r, 4)
        x = 0.0
        while x < W:                                   # conifer tree line
            h = r.uniform(25, 75) * (0.6 + 0.4 * np.sin(x / W * 5 + 1) ** 2); w = h * r.uniform(0.28, 0.4)
            xs = np.arange(max(0, int(x - w)), min(W, int(x + w)))
            line[xs] = np.minimum(line[xs], hz - 14 - h * (1 - np.abs(xs - x) / w))
            x += r.uniform(w * 0.6, w * 1.4)
        fill_below(img, line, hexc('#3d4a52'), 1.5)
        yy = np.arange(H, dtype=np.float32)[:, None]
        refl = np.flipud(img[2 * hz - H:hz]) if 2 * hz - H > 0 else None
        lake = img[hz:].copy()
        if refl is not None:
            lake = refl[:H - hz] * 0.82 + hexc('#3c4a66') * 0.18
        img[hz:] = lake
        self.hz = hz
        self.sp = sparkles(r, 120, W / 2 - 300, W / 2 + 300, hz + 20, H - 30, 20, 80)
        mist = cv2.GaussianBlur(r.random((H // 8, W // 4)).astype(np.float32), (0, 0), 6)
        self.mist = cv2.resize((mist - mist.min()) / (mist.max() - mist.min()), (W * 2, H))
        return np.clip(img, 0, 1)

    def frame(self, t):
        c = self.canvas.copy()
        draw_sparkles(c, self.sp, t, hexc('#f4e2cc'), 0.45)
        off = int(t * 14) % self.BW
        band = self.mist[:, off:off + self.BW]
        yy = np.arange(self.BH, dtype=np.float32)[:, None]
        w = np.exp(-((yy - self.hz + 30) / 90) ** 2) * 0.35
        c = c * (1 - (band * w)[..., None]) + hexc('#f1e6dc') * (band * w)[..., None]
        return self.view(t, c)


class Art(Base):
    """Public-domain painting: blurred, darkened copy as background; the painting itself is framed by render.py."""
    S = 1.06

    def __init__(self, rng, W, H, total, path):
        self.path = path
        super().__init__(rng, W, H, total)

    def paint(self, W, H):
        im = cv2.cvtColor(cv2.imread(self.path), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        h, w = im.shape[:2]; s = max(W / w, H / h)
        im = cv2.resize(im, (int(w * s) + 1, int(h * s) + 1))
        y0 = (im.shape[0] - H) // 2; x0 = (im.shape[1] - W) // 2
        bg = cv2.GaussianBlur(im[y0:y0 + H, x0:x0 + W], (0, 0), 38)
        return np.clip(bg * 0.38 + hexc('#0d1020') * 0.25, 0, 1)


SCENES = {'meadow': Meadow, 'moonlake': MoonLake, 'sunset': Sunset, 'wheat': Wheat, 'dawnlake': DawnLake}
