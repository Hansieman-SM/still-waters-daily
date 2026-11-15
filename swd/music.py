"""Original calm piano music (own code, no samples, royalty-free). Every seed gives a different key,
progression, arpeggio pattern and melody."""
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR = 44100
KEYS = {'C': 48, 'D': 50, 'Eb': 51, 'E': 52, 'F': 53, 'G': 55, 'Ab': 56, 'A': 57, 'Bb': 46}
PROGS = [
    [[0, 4, 7], [9, 12, 16], [5, 9, 12], [7, 11, 14]],     # I vi IV V
    [[0, 4, 7], [5, 9, 12], [9, 12, 16], [7, 11, 14]],     # I IV vi V
    [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]],     # I V vi IV
    [[9, 12, 16], [5, 9, 12], [0, 4, 7], [7, 11, 14]],     # vi IV I V
    [[0, 4, 7], [4, 7, 11], [5, 9, 12], [5, 9, 14]],       # I iii IV IV(add9)
    [[2, 5, 9], [7, 11, 14], [0, 4, 7], [0, 4, 7]],        # ii V I I
]
MAJOR = [0, 2, 4, 5, 7, 9, 11]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _lp(x, fc, order=2):
    return sosfilt(butter(order, fc, 'low', fs=SR, output='sos'), x)


def note(m, dur, vel, rng):
    """Soft felt-piano tone: a few inharmonic partials with fast attack and two-stage decay."""
    n = int(dur * SR); x = np.arange(n) / SR; f = hz(m)
    y = np.zeros(n)
    for k, amp in ((1, 1.0), (2, 0.42), (3, 0.16), (4, 0.07), (5, 0.03)):
        fk = f * k * (1 + 0.0004 * k * k)
        y += amp * np.sin(2 * np.pi * fk * x + rng.uniform(0, 6.28)) * np.exp(-x * (0.9 + 0.55 * k) * (f / 260) ** 0.35)
    env = (1 - np.exp(-x * 160)) * (0.65 * np.exp(-x * 1.6) + 0.35 * np.exp(-x * 0.35))
    rel = np.clip((dur - x) / 0.25, 0, 1)
    return y * env * rel * vel


def _reverb(x, rng, secs=3.4, mix=0.42):
    n = int(secs * SR); t = np.arange(n) / SR
    ir = rng.standard_normal((2, n)) * np.exp(-t * 6.0 / secs); ir[:, :int(0.015 * SR)] = 0
    ir = np.stack([_lp(ir[0], 4800), _lp(ir[1], 4400)])
    wet = np.stack([fftconvolve(x, ir[0])[:len(x)], fftconvolve(x, ir[1])[:len(x)]])
    wet /= np.max(np.abs(wet)) + 1e-9
    dry = np.stack([x, x]) / (np.max(np.abs(x)) + 1e-9)
    return dry * (1 - mix) + wet * mix


def compose(seconds, seed):
    rng = np.random.default_rng(seed)
    n = int((seconds + 4) * SR); t = np.arange(n) / SR
    kname = list(KEYS)[rng.integers(len(KEYS))]; root = KEYS[kname]
    prog = PROGS[rng.integers(len(PROGS))]
    bar = float(rng.choice([3.2, 3.6, 4.0]))
    pattern = [[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3], [0, 2, 3, 2]][rng.integers(4)]
    y = np.zeros(n)

    def put(m, at, dur, vel):
        a = max(0, int(at * SR))
        if a >= n:
            return
        s = note(m, dur, vel, rng); b = min(n, a + len(s)); y[a:b] += s[:b - a]

    nbars = int(np.ceil(seconds / bar)) + 1
    for b in range(nbars):
        ch = prog[b % len(prog)]; t0 = b * bar
        put(root - 12 + ch[0], t0, bar * 1.6, 0.55)                       # soft bass
        tones = [root + ch[0], root + ch[1], root + ch[2], root + ch[0] + 12]
        step = bar / 4
        for i, p in enumerate(pattern):
            put(tones[p], t0 + i * step + rng.uniform(-0.01, 0.01), step * 3, 0.26 + 0.05 * (i == 0))
        if rng.random() < 0.7:                                             # sparse melody
            deg = MAJOR[rng.integers(len(MAJOR))]
            m = root + 12 + deg
            if (deg - ch[0]) % 12 in (1, 6, 11):
                m = root + 12 + ch[2]
            put(m, t0 + rng.choice([0.0, bar / 2]), bar * 1.2, 0.30)
    y = _lp(y, 3800)
    pad = sum(np.sin(2 * np.pi * hz(root + d) * t) for d in (0, 7, 12)) * 0.05 * np.clip(t / 3, 0, 1)
    st = _reverb(y + pad, rng)[:, :int(seconds * SR)]
    tt = np.arange(st.shape[1]) / SR
    st *= np.clip(tt / 0.8, 0, 1) * np.clip((seconds - tt) / 1.5, 0, 1)
    return (st / (np.max(np.abs(st)) + 1e-9) * 0.8).astype(np.float32), {'key': kname, 'bar': bar}


def mix(voice, music, voice_end, total, loop=False):
    n = int(total * SR)
    v = np.zeros(n, np.float32); v[:min(n, len(voice))] = voice[:n]
    m = music[:, :n]
    if m.shape[1] < n:
        m = np.pad(m, ((0, 0), (0, n - m.shape[1])))
    t = np.arange(n) / SR
    gain = np.where(t < voice_end + 0.2, 0.16, 0.16 + np.clip((t - voice_end - 0.2) / 0.6, 0, 1) * 0.14)
    out = m * gain + np.stack([v, v]) * 0.92
    if loop:   # loops: short fades so the restart is smooth
        f = np.clip(t / 0.12, 0, 1) * np.clip((total - t) / 0.25, 0, 1)
        out *= f
    return out / max(1.0, np.max(np.abs(out)) / 0.97)
