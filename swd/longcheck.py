"""Gate for long-video scripts. python3 -m swd.longcheck content/long/<id>.json"""
import json, os, re, sys
from . import bible
from .textcheck import BANNED

ROOT = os.path.join(os.path.dirname(__file__), '..')


def check(path):
    e = []; s = json.load(open(path))
    for k in ('id', 'date', 'kind', 'passage', 'title', 'subtitle', 'minutes', 'description'):
        if not s.get(k): e.append(f'missing "{k}"')
    if e: return e
    if os.path.basename(path) != s['id'] + '.json' or '-long-' not in s['id']: e.append('id must be <date>-long-<slug> and equal the file name')
    try:
        v = bible.passage(s['passage'])
        if not 3 <= len(v) <= 30: e.append(f'{len(v)} verses; use 3-30 verses')
    except Exception as x:
        e.append(str(x))
    if not 15 <= s['minutes'] <= 60: e.append('minutes must be 15-60')
    if len(s['title']) > 100: e.append('title longer than 100')
    if any(k in s for k in ('text', 'kjv')): e.append('no scripture text in the script (always from data/kjv.json)')
    own = ' '.join([s['title'], s['subtitle'], s['description']])
    for b in BANNED:
        if re.search(b, own, re.I): e.append(f'banned wording: {re.search(b, own, re.I).group(0)}')
    if s.get('scene') and s['scene'] not in json.load(open(os.path.join(ROOT, 'config', 'channel.json')))['scenes']: e.append('unknown scene')
    return e


if __name__ == '__main__':
    bad = 0
    for p in sys.argv[1:]:
        e = check(p); print(('FAIL ' if e else 'OK   ') + os.path.basename(p)); [print('  -', x) for x in e]; bad += bool(e)
    sys.exit(1 if bad else 0)
