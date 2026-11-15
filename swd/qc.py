"""Automatic technical QC. python3 -m swd.qc out/<id>/<id>.mp4 -> writes <id>.qc.json, exit 1 on failure.
The contact sheet (tools/sheet.sh) must still be LOOKED at before scheduling."""
import json, os, re, subprocess, sys

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
SAFE = (40, 120, 1040, 1700)


def qc(mp4):
    errs, info = [], {}
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height,r_frame_rate:format=duration,size',
                                    '-of', 'json', mp4], capture_output=True, text=True).stdout)
    v = [s for s in pr['streams'] if s['codec_type'] == 'video'][0]; a = [s for s in pr['streams'] if s['codec_type'] == 'audio']
    dur = float(pr['format']['duration'])
    info.update(duration=round(dur, 2), width=v['width'], height=v['height'], fps=v['r_frame_rate'], sizeMB=round(int(pr['format']['size']) / 1e6, 1))
    vc = CFG['video']
    if (v['width'], v['height']) != (vc['width'], vc['height']): errs.append('wrong resolution')
    if v['r_frame_rate'] != f"{vc['fps']}/1": errs.append('wrong frame rate')
    if not a: errs.append('no audio')
    meta_p = mp4.replace('.mp4', '.meta.json')
    m = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
    if not m: errs.append('meta.json missing')
    slot = m.get('slot', 'verse'); lim = vc['limits'][slot]
    if not lim['minSeconds'] <= dur <= lim['maxSeconds']: errs.append(f'duration {dur:.1f}s outside {lim["minSeconds"]}-{lim["maxSeconds"]} for {slot}')
    out = subprocess.run(['ffmpeg', '-nostats', '-i', mp4, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', out)[-1]); P = float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', out)[-1])
    info.update(lufs=I, peakDb=P)
    if not -17 <= I <= -11: errs.append(f'loudness {I} LUFS')
    if P > -0.9: errs.append(f'true peak {P} dBFS')
    sil = subprocess.run(['ffmpeg', '-i', mp4, '-af', 'silencedetect=n=-45dB:d=0.7', '-f', 'null', '-'], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r'silence_start: (-?[\d.]+)', sil)]
    if starts: errs.append(f'dead silence (>0.7 s) at {starts[:3]}')
    blk = subprocess.run(['ffmpeg', '-i', mp4, '-vf', 'blackdetect=d=0.1:pix_th=0.03', '-an', '-f', 'null', '-'], capture_output=True, text=True).stderr
    if 'black_start' in blk: errs.append('black frames detected')
    for b in m.get('textBoxes', []):           # nothing cut off or under the Shorts UI
        if b[0] < SAFE[0] or b[1] < SAFE[1] or b[2] > SAFE[2] or b[3] > SAFE[3]:
            errs.append(f'text box {b} outside the safe area {SAFE}')
    lt = m.get('lineTimes', [])
    if any(t > dur - 1.0 for t in lt): errs.append('a line lights up less than 1 s before the end')
    if m and dur - m.get('voiceSeconds', 0) > 3.5: errs.append('tail after voice longer than 3.5 s')
    if not os.path.exists(mp4.replace('.mp4', '_thumb.jpg')): errs.append('thumbnail missing')
    res = {'file': os.path.basename(mp4), 'pass': not errs, 'errors': errs, **info}
    json.dump(res, open(mp4.replace('.mp4', '.qc.json'), 'w'), indent=1)
    return res


if __name__ == '__main__':
    bad = 0
    for f in sys.argv[1:]:
        r = qc(f); print(json.dumps(r)); bad += not r['pass']
    sys.exit(1 if bad else 0)
