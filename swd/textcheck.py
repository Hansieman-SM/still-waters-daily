"""Content gate for new scripts. python3 -m swd.textcheck content/scripts/<id>.json [...]
Exit 1 with every problem listed. Never weaken a rule to make a script pass - rewrite the script."""
import json, os, re, sys, datetime as dt
from . import bible

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
ARCHIVE = os.path.join(ROOT, 'content', 'archive.jsonl')
CAL = os.path.join(ROOT, 'content', 'calendar.json')

REQUIRED = {'verse': ['id', 'date', 'slot', 'theme', 'hook', 'ref', 'title', 'tiktokTitle', 'line'],
            'loop': ['id', 'date', 'slot', 'theme', 'hook', 'ref', 'title', 'tiktokTitle', 'line', 'share'],
            'evening': ['id', 'date', 'slot', 'theme', 'hook', 'lines', 'ref', 'title', 'tiktokTitle']}
BANNED = [  # prosperity / pressure / chain-letter / medical promises / denominational fights
    r'\bshare (this|it) (or|and you will)\b', r'\bif you (ignore|scroll past)\b', r'\bdon\'?t scroll\b', r'\bwithin \d+ (hours|days)\b',
    r'\bguarantee', r'\bwill (heal|cure) (you|your)\b', r'\bmoney (is|will be) coming\b', r'\bwealth\b', r'\brich(es)?\b.*\bwill\b',
    r'\bclaim (your|this) (blessing|miracle)\b', r'\bthis is your sign\b', r'\buniverse\b', r'\bmanifest', r'\bbad luck\b', r'\bcurse',
    r'\bpunish', r'\bhell\b', r'\bdamn', r'\bcatholic|\bprotestant|\bcalvin|\bpope\b|\bmormon|\bevangelical', r'\bonly true church\b',
    r'\b(stop|throw away) (your )?(medication|medicine|treatment)\b', r'\bpolitic|\belection\b|\bpresident\b|\bparty\b',
    r'\bgod the father (looks|appears)\b',
]
HOOK_MAX, LINE_MAX, TITLE_MAX = 30, 34, 80


def archive():
    return [json.loads(l) for l in open(ARCHIVE) if l.strip()] if os.path.exists(ARCHIVE) else []


def calendar_day(date):
    if not os.path.exists(CAL):
        return None
    return next((d for d in json.load(open(CAL))['days'] if d['date'] == date), None)


def check(path):
    errs, warn = [], []
    s = json.load(open(path))
    slot = s.get('slot')
    if slot not in REQUIRED:
        return [f'slot must be one of {list(REQUIRED)}'], warn
    for k in REQUIRED[slot]:
        if not s.get(k):
            errs.append(f'missing field "{k}"')
    if errs:
        return errs, warn
    if s['id'] != f"{s['date']}-{slot}-{s['id'].split(slot + '-', 1)[-1]}" or os.path.basename(path) != s['id'] + '.json':
        errs.append('id must be <date>-<slot>-<slug> and equal the file name')
    try:
        text = bible.verse(s['ref'])
    except Exception as e:
        return errs + [f'reference: {e}'], warn
    words = len(text.split())
    lim = {'verse': (8, 75), 'loop': (5, 32), 'evening': (5, 60)}[slot]
    if not lim[0] <= words <= lim[1]:
        errs.append(f'KJV text is {words} words; {slot} needs {lim[0]}-{lim[1]} (pick a shorter/longer passage)')
    if 'kjv' in s or 'text' in s:
        errs.append('do not put scripture text in the script - it is always taken verbatim from data/kjv.json by "ref"')
    if len(s['hook']) > HOOK_MAX:
        errs.append(f'hook longer than {HOOK_MAX} chars')
    if s['hook'].upper() == s['hook'] and any(c.isalpha() for c in s['hook']):
        errs.append('write the hook in normal case (the renderer capitalises it)')
    if len(s['title']) > TITLE_MAX:
        errs.append(f'title longer than {TITLE_MAX} chars')
    if s['title'].upper() == s['title']:
        errs.append('title in ALL CAPS')
    if slot == 'evening':
        if not 2 <= len(s['lines']) <= 3:
            errs.append('evening needs 2-3 short lines')
        for l in s['lines']:
            if len(l) > LINE_MAX:
                errs.append(f'line too long (> {LINE_MAX}): "{l}"')
            if not re.search(r'[.!?]$', l):
                errs.append(f'line must end with . ! or ?: "{l}"')
    own = ' '.join([s['hook'], s['title'], s['tiktokTitle'], s.get('line', ''), s.get('share', ''), ' '.join(s.get('lines', []))])
    for b in BANNED:
        if re.search(b, own, re.I):
            errs.append(f'banned wording ({b}) in "{re.search(b, own, re.I).group(0)}"')
    if s.get('scene'):
        sc = s['scene']
        if sc.startswith('art:'):
            cat = json.load(open(os.path.join(ROOT, CFG['art']['dir'], 'catalog.json')))
            if sc[4:] not in cat:
                errs.append(f'unknown painting {sc} (only art/met/catalog.json)')
            if slot != 'verse':
                errs.append('paintings only on Verse of the Day posts')
        elif sc not in CFG['scenes']:
            errs.append(f'unknown scene {sc}')
        if slot == 'evening' and sc != 'moonlake':
            warn.append('evening posts normally use the moonlake night scene')
    # calendar
    day = calendar_day(s['date'])
    if day:
        want = day['verseRef'] if slot == 'verse' else day['eveningRef'] if slot == 'evening' else None
        if want and bible.display(want) != bible.display(s['ref']):
            errs.append(f'calendar says {slot} on {s["date"]} = {want} (approved by Hans); use it')
    # repetition against the archive
    arch = [a for a in archive() if a.get('id') != s['id']]
    d0 = dt.date.fromisoformat(s['date'])
    for a in arch:
        try:
            age = abs((d0 - dt.date.fromisoformat(a['date'])).days)
        except Exception:
            continue
        if a.get('ref') == bible.display(s['ref']) and age < 45:
            msg = f'{bible.display(s["ref"])} was already used on {a["date"]} ({a["slot"]})'
            (warn if (day and slot != 'loop') else errs).append(msg)
        if a.get('title') and a['title'].lower() == s['title'].lower():
            errs.append(f'title repeats {a["date"]}')
        if a.get('hook') and a['hook'].lower() == s['hook'].lower() and age < 60:
            errs.append(f'hook repeats {a["date"]}')
    return errs, warn


if __name__ == '__main__':
    bad = 0
    for p in sys.argv[1:]:
        e, w = check(p)
        for x in w:
            print(f'WARN {os.path.basename(p)}: {x}')
        if e:
            bad += 1
            print(f'FAIL {os.path.basename(p)}'); [print('  -', x) for x in e]
        else:
            print(f'OK   {os.path.basename(p)}')
    sys.exit(1 if bad else 0)
