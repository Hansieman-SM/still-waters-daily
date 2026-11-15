"""Voice-over with Kokoro (voice bm_george). narrate() takes a list of parts and returns audio plus, per part,
a timing map so the renderer can highlight exactly the line that is being read (read-along)."""
import os, re
import numpy as np
from scipy.signal import resample_poly

SR = 44100
MODEL_DIR = os.environ.get('SWD_MODELS', os.path.join(os.path.dirname(__file__), '..', 'models'))
_k = None


def kokoro():
    global _k
    if _k is None:
        from kokoro_onnx import Kokoro
        _k = Kokoro(os.path.join(MODEL_DIR, 'kokoro-v1.0.onnx'), os.path.join(MODEL_DIR, 'voices-v1.0.bin'))
    return _k


def speakable(s):
    s = s.replace('LORD', 'Lord').replace('GOD', 'God').replace('—', ', ').replace('–', ' to ')
    return re.sub(r'\s+', ' ', s).strip()


def chunks(text):
    """Split at sentence ends and at ; : (natural breath points in KJV). Returns [(start_char, end_char, piece)]."""
    out, start = [], 0
    for m in re.finditer(r'[.!?;:]["”’)]?(\s+|$)', text):
        end = m.end()
        piece = text[start:end].strip()
        if piece:
            out.append((start, end, piece))
        start = end
    if text[start:].strip():
        out.append((start, len(text), text[start:].strip()))
    return out


def _trim(a, sr):
    idx = np.where(np.abs(a) > 0.004)[0]
    if not len(idx):
        return a
    return a[max(0, idx[0] - int(0.02 * sr)):min(len(a), idx[-1] + int(0.08 * sr))]


def narrate(parts, voice='bm_george', lang='en-gb', speed=0.9, pause=0.45, lead=0.15):
    """parts: list of dicts {text, gap (seconds after, default pause)}.
    -> audio float32 @44.1k, timings [ {start, end, map: [(char_start, char_end, t0, t1)]} per part ], voice_end"""
    k = kokoro()
    audio = [np.zeros(int(lead * SR), np.float32)]
    t = lead; timings = []
    for part in parts:
        text = part['text']; pm = []; p0 = t
        cs = chunks(text)
        for j, (a0, a1, piece) in enumerate(cs):
            wav, sr = k.create(speakable(piece), voice=voice, speed=speed, lang=lang)
            wav = _trim(np.asarray(wav, np.float32), sr)
            wav = resample_poly(wav, 147, 80).astype(np.float32)
            L = len(wav) / SR
            pm.append((a0, a1, t, t + L))
            audio.append(wav); t += L
            if j < len(cs) - 1:
                g = 0.28 if piece.rstrip('”"’)').endswith((';', ':')) else 0.38
                audio.append(np.zeros(int(g * SR), np.float32)); t += g
        timings.append({'start': p0, 'end': t, 'map': pm})
        g = part.get('gap', pause)
        audio.append(np.zeros(int(g * SR), np.float32)); t += g
    voice_end = timings[-1]['end']
    a = np.concatenate(audio)
    return a / (np.max(np.abs(a)) + 1e-9) * 0.89, timings, voice_end


def char_time(timing, c):
    """Time at which character index c of a part is spoken (linear inside each chunk)."""
    for a0, a1, t0, t1 in timing['map']:
        if c < a1:
            c = max(c, a0)
            return t0 + (t1 - t0) * (c - a0) / max(1, a1 - a0)
    return timing['end']
