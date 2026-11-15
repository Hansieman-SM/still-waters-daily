"""Weekly long Sunday video (16:9, ~30 min): a Bible passage read slowly by George, three times, each reading followed
by a silent pass of the same verses for quiet reflection, over a calm moving landscape with soft piano.
python3 -m swd.long content/long/<id>.json out/<id>   -> <id>.mp4, <id>_thumb.jpg (1280x720), <id>.meta.json

Script: {"id","date","kind":"scripture","passage":"Psalm 121","title","subtitle","minutes":30,"scene":"moonlake","readings":3,"description"}"""
import json, os, sys, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from . import tts, music, bible, longkit
from .longkit import W, H
from .scenes import SCENES

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
FONTS = os.path.join(ROOT, 'fonts', 'ass')
INTRO, OUTRO, GAP, VERSE_PAUSE = 9.0, 14.0, 3.0, 2.4
WORDS = {3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight'}


def build_audio(verses, script, seed):
    v = CFG['voice']; k = tts.kokoro(); clips = []
    for label, text in verses:
        a, _, vend = tts.narrate([{'text': text}], v['voice'], v['lang'], v['speed'] * 0.94, 0.55, lead=0.0)
        clips.append(a[:int((vend + 0.15) * tts.SR)])
    intro_ref, _, iv = tts.narrate([{'text': f"{bible.passage_title(script['passage']).replace('–', ' to ').replace(':', ', verses ')}."}],
                                   v['voice'], v['lang'], v['speed'] * 0.94, 0.4, lead=0.0)
    return clips, intro_ref[:int((iv + 0.1) * tts.SR)]


def timeline(verses, clips, intro_clip, minutes, readings):
    """-> events [(t0, t1, kind, idx)], voice placements [(t, clip)], total, silent_spans"""
    durs = [len(c) / tts.SR for c in clips]
    read_len = sum(d + VERSE_PAUSE for d in durs)
    target = minutes * 60
    if not readings:   # auto: as many readings as needed so each verse rests ~20-35 s in the quiet passes
        readings = int(max(3, min(8, round((target - INTRO - OUTRO) / (read_len + len(verses) * 28 + 2 * GAP)))))
    fixed = INTRO + OUTRO + readings * read_len + (2 * readings) * GAP
    silent_each = max(9.0, (target - fixed) / (readings * len(verses)))
    t = INTRO; ev, voice, quiet = [], [(INTRO - 3.2, intro_clip)], []
    for r in range(readings):
        for i, d in enumerate(durs):
            ev.append((t, t + d + VERSE_PAUSE - 0.2, 'read', i)); voice.append((t + 0.35, clips[i])); t += d + VERSE_PAUSE
        t += GAP; q0 = t
        for i in range(len(verses)):
            ev.append((t, t + silent_each - 0.3, 'quiet', i)); t += silent_each
        quiet.append((q0, t)); t += GAP
    return ev, voice, t + OUTRO, quiet, silent_each, readings


def thumbnail(frame, script, path):
    im = Image.fromarray(frame).resize((1280, 720), Image.LANCZOS)
    dark = Image.new('RGB', im.size, (8, 12, 28)); im = Image.blend(im, dark, 0.25)
    title = bible.passage_title(script['passage']) if not script.get('thumbTitle') else script['thumbTitle']
    lines = [(title, ImageFont.truetype(os.path.join(FONTS, 'SWDCormorantSemiBold.ttf'), 132), (246, 240, 228), 0),
             (script.get('subtitle', ''), ImageFont.truetype(os.path.join(FONTS, 'SWDCormorant.ttf'), 60), (246, 240, 228), 0),
             (f"{script.get('minutes', 30)} MINUTES OF PEACE · KJV", ImageFont.truetype(os.path.join(FONTS, 'Lato-Regular.ttf'), 30), (229, 194, 122), 5)]
    y = 190
    mask = Image.new('L', im.size, 0); md = ImageDraw.Draw(mask); txt = Image.new('RGB', im.size); td = ImageDraw.Draw(txt)
    for s, f, col, tr in lines:
        if not s:
            continue
        w = sum(f.getlength(c) + tr for c in s) - tr; x = (1280 - w) / 2
        for c in s:
            md.text((x, y), c, font=f, fill=255); td.text((x, y), c, font=f, fill=col); x += f.getlength(c) + tr
        y += int(sum(f.getmetrics()) * 1.08) + 6
    sh = mask.filter(ImageFilter.GaussianBlur(10)).point(lambda v: min(255, int(v * 1.7)))
    im.paste((0, 0, 0), (0, 0), sh.point(lambda v: int(v * 0.75)))
    im.paste(txt, (0, 0), mask)
    im.save(path, quality=92)


def render(path, outdir):
    s = json.load(open(path)); sid = s['id']; os.makedirs(outdir, exist_ok=True)
    seed = int(hashlib.sha1(sid.encode()).hexdigest()[:8], 16)
    verses = bible.passage(s['passage'])
    clips, intro_clip = build_audio(verses, s, seed)
    ev, voice_at, total, quiet, silent_each, readings = timeline(verses, clips, intro_clip, s.get('minutes', 30), s.get('readings'))

    # audio: voice track + tiled piano, music a little louder during the silent passes
    sr = tts.SR; n = int(total * sr)
    vt = np.zeros(n, np.float32)
    for t0, c in voice_at:
        a = int(t0 * sr); vt[a:a + len(c)] += c[:max(0, n - a)]
    chunk, minfo = music.compose(150, seed)
    mus = longkit.tile_music(chunk, total, sr)
    tt = np.arange(n) / sr
    gain = np.full(n, 0.15, np.float32)
    for q0, q1 in quiet:
        gain += 0.17 * (np.clip((tt - q0) / 4, 0, 1) * np.clip((q1 - tt) / 4, 0, 1)).astype(np.float32)
    gain[tt < INTRO - 3.5] = 0.32; gain[tt > total - OUTRO] = 0.32
    mix = mus * gain + np.stack([vt, vt]) * 0.92
    mix /= max(1.0, np.max(np.abs(mix)) / 0.97)
    wav = os.path.join(outdir, sid + '.wav'); longkit.write_wav(wav, mix, sr)

    # background loop
    scene_name = s.get('scene') or 'moonlake'
    scene = SCENES[scene_name](np.random.default_rng(seed + 1), W, H, 80)
    yy = np.arange(H, dtype=np.float32)[:, None]
    shade = (1 - 0.32 * np.exp(-((yy - 380) / 330) ** 2)).astype(np.float32)[..., None]
    bg = os.path.join(outdir, 'bg.mp4'); longkit.bg_loop(scene, bg, leg=40.0, shade=shade)
    thumb_frame = (np.clip(scene.frame(12.0) * shade, 0, 1) * 255).astype(np.uint8)

    # text
    A = longkit.ASS()
    A.style('Brand', 'Lato', 30, 'E2DDD2', align=7, mv=52, ml=118, mr=0, outline=1)
    A.style('Title', 'SWD Cormorant SemiBold', 104, 'F6F0E4', align=5, ml=200, mr=200, outline=3)
    A.style('Sub', 'SWD Cormorant', 54, 'F6F0E4', align=8, mv=560, ml=200, mr=200, outline=2)
    A.style('Gold', 'Lato', 34, 'E5C27A', align=8, mv=150, spacing=6, outline=2)
    A.style('Verse', 'SWD Cormorant', 74, 'F6F0E4', align=8, mv=225, ml=230, mr=230, outline=3)
    A.style('Small', 'Lato', 32, 'E2DDD2', align=2, mv=70, outline=2)
    A.add(0, total, 'Brand', CFG['channel'], fade=(0, 0))
    title = bible.passage_title(s['passage'])
    A.add(0.3, INTRO - 0.4, 'Title', title, fade=(900, 700), extra='\\pos(960,430)')
    A.add(0.8, INTRO - 0.4, 'Sub', s.get('subtitle', ''), fade=(900, 700))
    A.add(1.2, INTRO - 0.4, 'Small', f'King James Version  ·  Read slowly, {WORDS[readings]} times, with quiet in between', fade=(900, 700))
    for i, (t0, t1, kind, idx) in enumerate(ev):
        label, text = verses[idx]
        prev_same = i and ev[i - 1][3] == idx - 1 and ev[i - 1][2] == kind
        A.add(t0, t1, 'Gold', label.upper() + ' (KJV)', fade=(500, 500))
        A.add(t0, t1, 'Verse', text, fade=(800, 800))
    for k, (q0, q1) in enumerate(quiet):
        A.add(q0 - GAP + 0.3, q0 + 4.5, 'Small', 'Quiet reflection  ·  let the words settle', fade=(800, 800))
    A.add(total - OUTRO + 0.5, total - 0.3, 'Title', CFG['channel'], fade=(900, 1200), extra='\\pos(960,420)')
    A.add(total - OUTRO + 1.0, total - 0.3, 'Sub', 'Subscribe for a daily word of peace', fade=(900, 1200))
    ass = os.path.join(outdir, sid + '.ass'); A.write(ass)

    # logo overlay
    from .render import logo_sprite
    lg = (logo_sprite() * 255).astype(np.uint8); lp = os.path.join(outdir, 'logo.png')
    Image.fromarray(lg, 'RGBA').resize((52, 52), Image.LANCZOS).save(lp)
    mp4 = os.path.join(outdir, sid + '.mp4')
    longkit.assemble(bg, wav, ass, total, mp4, FONTS, overlay_png=lp, overlay_xy=(56, 38))
    os.remove(wav); os.remove(bg)
    thumbnail(thumb_frame, s, os.path.join(outdir, sid + '_thumb.jpg'))

    chapters, t = ['00:00 Introduction'], INTRO
    blocks = []
    for r in range(readings):
        blocks.append(('Reading ' + str(r + 1), ev[r * 2 * len(verses)][0]))
        blocks.append(('Quiet reflection ' + str(r + 1), quiet[r][0]))
    for name, t0 in blocks:
        chapters.append(f'{int(t0 // 60):02d}:{int(t0 % 60):02d} {name}')
    meta = {k: s[k] for k in ('id', 'date', 'kind', 'passage', 'title', 'subtitle') if k in s}
    meta.update({'readings': readings, 'seconds': round(total, 1), 'minutes': round(total / 60, 1), 'verses': len(verses), 'silentSecondsPerVerse': round(silent_each, 1),
                 'scene': scene_name, 'chapters': chapters, 'music': minfo, 'kind': 'long',
                 'provenance': {'scripture': 'King James Version (public domain), verbatim from data/kjv.json',
                                'voice': 'Kokoro-82M bm_george via kokoro-onnx (Apache-2.0 / MIT)',
                                'music': 'generative piano, swd/music.py (own code)', 'visuals': 'procedural, swd/scenes.py (own code)'}})
    json.dump(meta, open(os.path.join(outdir, sid + '.meta.json'), 'w'), indent=1, ensure_ascii=False)
    return meta


if __name__ == '__main__':
    m = render(sys.argv[1], sys.argv[2])
    print(json.dumps({k: m[k] for k in ('id', 'minutes', 'verses', 'silentSecondsPerVerse', 'chapters')}))
