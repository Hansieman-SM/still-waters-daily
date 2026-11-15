"""Render one Still Waters Daily Short from a script JSON.
python3 -m swd.render content/scripts/<id>.json out/<id>   -> <id>.mp4, <id>_thumb.jpg, <id>.meta.json

Look (matches the channel since Nov 2026): logo top-left, gold letter-spaced hook heading with a short rule,
KJV text in Cormorant Garamond with read-along highlighting (unread lines dimmed), reference in Lato,
voice-over (bm_george, reference first), soft original piano, and a SUBSCRIBE button at the end."""
import json, os, subprocess, sys, wave, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from . import tts, music, bible
from .scenes import SCENES, Art

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
W, H, FPS = CFG['video']['width'], CFG['video']['height'], CFG['video']['fps']
CREAM = (246, 240, 228); GOLD = (229, 194, 122); SOFT = (226, 221, 210); INK = (38, 38, 50)
SAFE = (60, 150, 1020, 1460)          # x0, y0, x1, y1: all text must stay inside (Shorts UI sits outside)
DIM = 0.42
F = lambda n: os.path.join(ROOT, 'fonts', n)


def font(name, size, var=None):
    f = ImageFont.truetype(F(name), size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f


SERIF = lambda s: font('CormorantGaramond[wght].ttf', s, 'Medium')
SANS = lambda s: font('Lato-Regular.ttf', s)


def wrap(text, fnt, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if fnt.getlength(test) <= maxw or not cur:
            cur = test
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    if len(lines) >= 2 and len(lines[-1].split()) == 1:          # no single orphan word on the last line
        a = lines[-2].split()
        if len(a) > 2:
            lines[-2] = ' '.join(a[:-1]); lines[-1] = a[-1] + ' ' + lines[-1]
    return lines


def sprite(text, fnt, fill, track=0, shadow=0.75):
    """Straight-alpha RGBA float sprite of one line of text with a soft shadow."""
    w = int(fnt.getlength(text) + track * len(text)) + 60
    asc, desc = fnt.getmetrics(); h = asc + desc + 40
    m = Image.new('L', (w, h), 0); d = ImageDraw.Draw(m); x = 30
    if track:
        for ch in text:
            d.text((x, 20), ch, font=fnt, fill=255); x += fnt.getlength(ch) + track
    else:
        d.text((x, 20), text, font=fnt, fill=255)
    a = np.asarray(m, np.float32) / 255
    sh = np.clip(np.asarray(m.filter(ImageFilter.GaussianBlur(7)), np.float32) / 255 * 1.6, 0, 1) * shadow
    al = np.maximum(a, sh)
    rgb = (np.array(fill, np.float32) / 255 * a[..., None]) / np.maximum(al[..., None], 1e-4)
    return np.dstack([rgb, al])


def blend(img, spr, cx, cy, k=1.0, left=False):
    bh, bw = spr.shape[:2]
    x0 = int(cx - 30) if left else int(cx - bw / 2); y0 = int(cy - bh / 2)
    a0, b0 = max(0, -y0), max(0, -x0); a1, b1 = min(bh, H - y0), min(bw, W - x0)
    if a1 <= a0 or b1 <= b0 or k <= 0:
        return
    reg = img[y0 + a0:y0 + a1, x0 + b0:x0 + b1].astype(np.float32) / 255
    s = spr[a0:a1, b0:b1]; al = s[..., 3:4] * k
    img[y0 + a0:y0 + a1, x0 + b0:x0 + b1] = ((reg * (1 - al) + s[..., :3] * al) * 255).astype(np.uint8)


def logo_sprite():
    """Cross above a half sun on still water, cream and gold (the channel mark)."""
    S = 4; im = Image.new('RGBA', (80 * S, 80 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    g = GOLD + (255,); c = CREAM + (255,)
    d.pieslice([18 * S, 38 * S, 62 * S, 82 * S], 180, 360, fill=g)
    for i, (y, w) in enumerate(((63, 34), (69, 26), (75, 16))):
        d.rounded_rectangle([(40 - w / 2) * S, y * S, (40 + w / 2) * S, (y + 3.5) * S], radius=2 * S, fill=g)
    d.rectangle([4 * S, 57 * S, 76 * S, 60 * S], fill=c)
    d.rectangle([37.5 * S, 8 * S, 42.5 * S, 58 * S], fill=c)
    d.rectangle([27 * S, 18 * S, 53 * S, 23 * S], fill=c)
    im = im.resize((64, 64), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255
    return a


def pill_sprite():
    bw, bh = 520, 88; S = 3
    im = Image.new('RGBA', (bw * S + 60 * S, bh * S + 60 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    sh = Image.new('L', im.size, 0); ImageDraw.Draw(sh).rounded_rectangle([30 * S, 34 * S, (30 + bw) * S, (34 + bh) * S], radius=bh * S // 2, fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(10 * S))
    im.putalpha(sh)
    base = Image.new('RGBA', im.size, (0, 0, 0, 0)); bd = ImageDraw.Draw(base)
    bd.rounded_rectangle([30 * S, 30 * S, (30 + bw) * S, (30 + bh) * S], radius=bh * S // 2, fill=(243, 236, 224, 255))
    f = SANS(40 * S); txt = CFG['subscribe']['button']; tr = 6 * S
    tw = sum(f.getlength(ch) + tr for ch in txt) - tr
    x0 = 30 * S + (bw * S - tw - 46 * S) / 2; x = x0 + 46 * S; y = 30 * S + (bh * S - 48 * S) / 2 - 4 * S
    for ch in txt:
        bd.text((x, y), ch, font=f, fill=INK + (255,)); x += f.getlength(ch) + tr
    bx = x0; by = 30 * S + bh * S / 2 - 2 * S      # bell
    bd.pieslice([bx, by - 20 * S, bx + 28 * S, by + 12 * S], 180, 360, fill=INK + (255,))
    bd.rectangle([bx, by - 4 * S, bx + 28 * S, by + 10 * S], fill=INK + (255,))
    bd.rectangle([bx - 4 * S, by + 8 * S, bx + 32 * S, by + 12 * S], fill=INK + (255,))
    bd.ellipse([bx + 9 * S, by + 12 * S, bx + 19 * S, by + 20 * S], fill=INK + (255,))
    im = Image.alpha_composite(im.convert('RGBA'), base)
    im = im.resize((im.width // S, im.height // S), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255
    a[..., :3] = np.where(a[..., 3:4] > 0, a[..., :3], 0)
    return a


class Layout:
    """All text sprites with their positions and the time each one lights up."""
    def __init__(self, script, timings, art=None):
        self.items = []          # dicts: spr, cx, cy, on (time it becomes bright), group
        self.boxes = []
        slot = script['slot']
        self.add(sprite(script['hook'].upper(), SANS(37), GOLD, track=7, shadow=0.7), W / 2, 357, -1, 'head')
        y = 470
        if art is not None:
            self.art = art; y = 430 + art.shape[0] + 70
        text = bible.shown(script['ref'])
        quoted = slot != 'verse'
        if quoted:
            text = '“' + text + '”'
        if slot == 'evening':
            lf = SERIF(64)
            for ln in script['lines']:
                y += 52
                self.add(sprite(ln, lf, CREAM, shadow=0.8), W / 2, y, None, 'lines'); y += 50
            # each line is its own spoken part
            for i, it in enumerate([x for x in self.items if x['group'] == 'lines']):
                it['on'] = timings[i]['start'] - 0.05
            y += 40
            vt = timings[len(script['lines']) + 1]
        else:
            vt = timings[1]
        size = {'verse': 76, 'evening': 66, 'loop': 80}[slot]
        while True:
            vf = SERIF(size); lines = wrap(text, vf, 860)
            lh = int(sum(vf.getmetrics()) * 1.12)
            if y + lh * len(lines) + 90 <= SAFE[3] or size <= 50:
                break
            size -= 3
        pos = 0
        for ln in lines:
            c = text.find(ln.split()[0], pos); pos = c + len(ln)
            on = tts.char_time(vt, max(0, c - (1 if quoted and c == 0 else 0)))
            if slot == 'loop' or (slot == 'verse' and c == 0):
                on = -1                 # loops fully lit; first verse line lit from frame one (hook)
            else:
                on -= 0.08
            self.add(sprite(ln, vf, CREAM, shadow=0.8), W / 2, y + lh / 2, on, 'verse')
            y += lh
        y += 30
        self.ref_y = y + 20
        self.ref_dim = sprite(bible.display(script['ref']) + ' (KJV)', SANS(38), SOFT, shadow=0.7)
        self.ref_on = sprite(bible.display(script['ref']) + ' (KJV)', SANS(38), GOLD, shadow=0.7)
        self.ref_time = vt['end'] - 0.1 if slot != 'loop' else -1
        self.box(self.ref_dim, W / 2, self.ref_y)

    def add(self, spr, cx, cy, on, group):
        self.items.append({'spr': spr, 'cx': cx, 'cy': cy, 'on': on, 'group': group}); self.box(spr, cx, cy)

    def box(self, spr, cx, cy):
        h, w = spr.shape[:2]
        self.boxes.append((cx - w / 2 + 30, cy - h / 2 + 20, cx + w / 2 - 30, cy + h / 2 - 20))

    def draw(self, img, t, dim=True):
        for it in self.items:
            k = 1.0 if (not dim or it['on'] < 0) else DIM + (1 - DIM) * float(np.clip((t - it['on']) / 0.3, 0, 1))
            blend(img, it['spr'], it['cx'], it['cy'], k)
        if not dim or self.ref_time < 0 or t >= self.ref_time + 0.3:
            blend(img, self.ref_on, W / 2, self.ref_y, 1.0)
        else:
            k = float(np.clip((t - self.ref_time) / 0.3, 0, 1))
            blend(img, self.ref_dim, W / 2, self.ref_y, 0.75 * (1 - k))
            blend(img, self.ref_on, W / 2, self.ref_y, k)


def art_sprite(path, credit):
    im = Image.open(path).convert('RGB'); im.thumbnail((600, 560), Image.LANCZOS)
    fr = Image.new('RGB', (im.width + 16, im.height + 16), (176, 146, 92)); fr.paste(im, (8, 8))
    a = np.dstack([np.asarray(fr, np.float32) / 255, np.ones(fr.size[::-1], np.float32)])
    return a, sprite(credit, SANS(22), SOFT, shadow=0.7)


def parts_for(script):
    ref = bible.spoken(script['ref']); text = bible.verse(script['ref'])
    if script['slot'] == 'evening':
        return [{'text': l, 'gap': 0.3} for l in script['lines']] + [{'text': ref, 'gap': 0.35}, {'text': text}]
    return [{'text': ref, 'gap': 0.35}, {'text': text}]


def render(script_path, outdir):
    s = json.load(open(script_path)); sid = s['id']; os.makedirs(outdir, exist_ok=True)
    seed = s.get('seed') or int(hashlib.sha1(sid.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    v = CFG['voice']
    voice, timings, vend = tts.narrate(parts_for(s), v['voice'], v['lang'], v['speed'], v['sentencePause'])
    loop = s['slot'] == 'loop'
    total = vend + (CFG['video']['loopOutroSeconds'] if loop else CFG['video']['outroSeconds'])
    mus, minfo = music.compose(total + 0.5, seed)
    mixd = music.mix(voice, mus, vend, total, loop)
    wav = os.path.join(outdir, sid + '.wav')
    o = wave.open(wav, 'wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(music.SR)
    o.writeframes((mixd.T * 32767).astype('<i2').tobytes()); o.close()

    scene_name = s.get('scene') or rng.choice(CFG['sceneDefaults'][s['slot']])
    art = credit = None
    if scene_name.startswith('art:'):
        cat = json.load(open(os.path.join(ROOT, CFG['art']['dir'], 'catalog.json')))
        a = cat[scene_name[4:]]
        art, credit = art_sprite(os.path.join(ROOT, CFG['art']['dir'], a['file']), a['credit'])
        scene = Art(np.random.default_rng(seed + 1), W, H, total, os.path.join(ROOT, CFG['art']['dir'], a['file']))
    else:
        scene = SCENES[scene_name](np.random.default_rng(seed + 1), W, H, total)
    L = Layout(s, timings, art)
    logo = logo_sprite(); name = sprite(CFG['channel'], SANS(40), SOFT, shadow=0.6); pill = pill_sprite()
    sub = sprite(CFG['subscribe']['sub'], SANS(27), SOFT, shadow=0.7)
    yy = np.arange(H, dtype=np.float32)[:, None]
    shade = (1 - 0.30 * np.exp(-((yy - 760) / 520) ** 2) - 0.18 * np.exp(-((yy - 230) / 160) ** 2)).astype(np.float32)[..., None]

    def paint_static(img, t, dim=True, with_pill=None):
        blend(img, logo, 128, 217, 0.97)
        blend(img, name, 177, 222, 0.95, left=True)
        rule_y = 400
        img[rule_y:rule_y + 2, W // 2 - 60:W // 2 + 60] = (img[rule_y:rule_y + 2, W // 2 - 60:W // 2 + 60] * 0.3 + np.array(GOLD) * 0.7).astype(np.uint8)
        if art is not None:
            blend(img, art, W / 2, 430 + art.shape[0] / 2, 1.0)
            blend(img, credit, W / 2, 430 + art.shape[0] + 26, 0.9)
        L.draw(img, t, dim)
        if with_pill:
            k = with_pill
            blend(img, pill, W / 2, 1532, k); blend(img, sub, W / 2, 1622, k * 0.9)

    mp4 = os.path.join(outdir, sid + '.mp4')
    nfr = int(round(total * FPS))
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-i', wav, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '48000',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
                           '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '192k', '-shortest', mp4], stdin=subprocess.PIPE)
    pill_t = vend + 0.15
    for i in range(nfr):
        t = i / FPS
        img = (np.clip(scene.frame(t) * shade, 0, 1) * 255).astype(np.uint8)
        k = float(np.clip((t - pill_t) / 0.45, 0, 1))
        paint_static(img, t, True, k)
        ff.stdin.write(img.tobytes())
    ff.stdin.close(); ff.wait()
    if ff.returncode:
        raise SystemExit('ffmpeg failed')
    os.remove(wav)

    th = (np.clip(scene.frame(total * 0.5) * shade, 0, 1) * 255).astype(np.uint8)
    paint_static(th, total, dim=False)
    Image.fromarray(th).save(os.path.join(outdir, sid + '_thumb.jpg'), quality=92)

    boxes = L.boxes + [(W / 2 - 290, 1532 - 44, W / 2 + 290, 1640)]
    meta = {k: s[k] for k in ('id', 'date', 'slot', 'theme', 'hook', 'ref', 'title') if k in s}
    meta.update({'scene': scene_name, 'seed': seed, 'seconds': round(total, 2), 'voiceSeconds': round(vend, 2),
                 'kjv': bible.verse(s['ref']), 'display': bible.display(s['ref']) + ' (KJV)', 'music': minfo,
                 'voice': v['voice'], 'textBoxes': [[round(x) for x in b] for b in boxes],
                 'lineTimes': [round(it['on'], 2) for it in L.items if it['group'] != 'head'],
                 'provenance': {'scripture': 'King James Version (public domain), verbatim from data/kjv.json',
                                'visuals': 'procedural, swd/scenes.py (own code)' if art is None else 'The Met Open Access (CC0) + own code',
                                'music': 'generative piano, swd/music.py (own code, no samples)',
                                'voice': 'Kokoro-82M bm_george via kokoro-onnx (Apache-2.0 / MIT)',
                                'fonts': 'Cormorant Garamond, Lato (SIL Open Font License)'}})
    json.dump(meta, open(os.path.join(outdir, sid + '.meta.json'), 'w'), indent=1, ensure_ascii=False)
    return meta


if __name__ == '__main__':
    m = render(sys.argv[1], sys.argv[2])
    print(json.dumps({k: m[k] for k in ('id', 'scene', 'seconds', 'voiceSeconds')}))
