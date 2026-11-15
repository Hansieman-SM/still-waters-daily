"""What must be written next. python3 -m swd.plan [--days 7] [--from YYYY-MM-DD]
Prints JSON: the missing (date, slot) items of the rolling buffer with the calendar entry for that day,
plus the references/hooks used recently so the writer avoids repeats."""
import json, os, sys, datetime as dt
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
STATE = os.path.join(ROOT, 'state', 'posts.json')
ARCHIVE = os.path.join(ROOT, 'content', 'archive.jsonl')
CAL = json.load(open(os.path.join(ROOT, 'content', 'calendar.json')))


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {'posts': {}}


def archive():
    return [json.loads(l) for l in open(ARCHIVE) if l.strip()] if os.path.exists(ARCHIVE) else []


def plan(days=7, start=None):
    tz = ZoneInfo(CFG['schedule']['timezone']); now = dt.datetime.now(tz)
    st = load_state()['posts']; arch = archive()
    taken = {(p['date'], p['slot']) for p in st.values() if p.get('status') not in ('failed', 'cancelled')}
    taken |= {(a['date'], a['slot']) for a in arch}
    if start is None:   # first calendar day after the last day that is fully covered
        start = (now + dt.timedelta(days=1)).date()
    cal = {d['date']: d for d in CAL['days']}
    missing = []
    for i in range(days):
        day = (start + dt.timedelta(days=i)).isoformat()
        for s in CFG['schedule']['slots']:
            if (day, s['slot']) in taken:
                continue
            pub = dt.date.fromisoformat(day) + dt.timedelta(days=s['dayOffset'])
            c = cal.get(day)
            item = {'date': day, 'slot': s['slot'], 'publishes': f"{pub} {s['time']} {CFG['schedule']['timezone']}",
                    'week': c and c['week'], 'weekTheme': c and c['weekTheme'], 'dayTheme': c and c['dayTheme']}
            if c and s['slot'] == 'verse':
                item['ref'] = c['verseRef']
            elif c and s['slot'] == 'evening':
                item.update(ref=c['eveningRef'], eveningTheme=c['eveningTheme'])
            elif not c:
                item['note'] = 'NO CALENDAR ENTRY - extend content/calendar.json first (see rules) and tell Hans'
            missing.append(item)
    recent = arch[-120:]
    return {'now': now.isoformat(timespec='minutes'), 'missing': missing,
            'recentRefs': sorted({a['ref'] for a in recent}),
            'recentHooks': [a.get('hook') for a in recent if a.get('hook')][-40:],
            'recentTitles': [a.get('title') for a in recent if a.get('title')][-40:],
            'calendarEnds': CAL['days'][-1]['date']}


if __name__ == '__main__':
    a = sys.argv
    days = int(a[a.index('--days') + 1]) if '--days' in a else CFG['schedule']['bufferDays']
    start = dt.date.fromisoformat(a[a.index('--from') + 1]) if '--from' in a else None
    print(json.dumps(plan(days, start), indent=1, ensure_ascii=False))
