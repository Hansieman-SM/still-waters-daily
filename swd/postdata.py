"""Exact Metricool payloads for one rendered Short. python3 -m swd.postdata <id> [--at YYYY-MM-DDTHH:MM] [--networks instagram,tiktok,youtube]
Prints a JSON list with TWO posts (same structure as the channel's posts since 2 Nov 2026):
  1) Instagram Reel + TikTok, with videoThumbnailUrl (custom cover)
  2) YouTube Short on its own, without thumbnail (YouTube rejected custom Short thumbnails for this channel)
Each item: {blogId, date, info (string)} ready for Metricool createScheduledPost."""
import json, os, sys, datetime as dt
from zoneinfo import ZoneInfo
from . import bible

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))


def caption(s):
    ref = bible.display(s['ref']); tags = ' '.join(CFG['hashtags'][s['slot']])
    art = ''
    if (s.get('scene') or '').startswith('art:'):
        cat = json.load(open(os.path.join(ROOT, CFG['art']['dir'], 'catalog.json')))
        art = '\n' + cat[s['scene'][4:]]['captionCredit']
    if s['slot'] == 'verse':
        body = f"Verse of the Day — {ref} 🕊️\n{s['line']}\nType \"Amen\" if you receive this. 🙏\nFollow for a daily word of peace.{art}"
    elif s['slot'] == 'evening':
        body = (f"Evening Encouragement 🌙\n{' '.join(s['lines'])}\n“{bible.shown(s['ref'])}” – {ref}\n"
                f"{s.get('save', 'Save this for the nights you need it. 🙏')}\nFollow for a daily word of peace.")
    else:
        body = f"{s['line']} 🕊️ {ref}\n{s['share']}\nFollow for a daily word of peace."
    return body + '\n\n' + tags


def yt_title(s):
    ref = bible.display(s['ref']).replace('–', '-')
    t = {'verse': f"{s['title']} | {ref} #shorts", 'evening': f"{s['title']} | {ref} | Evening Encouragement #shorts",
         'loop': f"{s['title']} | {ref} #shorts"}[s['slot']]
    return t if len(t) <= 100 else f"{s['title'][:100 - len(ref) - 12]} | {ref} #shorts"


def build(sid, at=None, nets=None):
    s = json.load(open(os.path.join(ROOT, 'content', 'scripts', sid + '.json')))
    brand = CFG['metricool']['brandId']
    nets = nets or ['instagram', 'tiktok', 'youtube']
    slot = next(x for x in CFG['schedule']['slots'] if x['slot'] == s['slot'])
    if at:
        date, time = at.split('T')
    else:
        date = (dt.date.fromisoformat(s['date']) + dt.timedelta(days=slot['dayOffset'])).isoformat(); time = slot['time']
    tz = CFG['schedule']['timezone']
    off = dt.datetime.fromisoformat(f"{date}T{time}").replace(tzinfo=ZoneInfo(tz)).strftime('%z')
    url = lambda f: CFG['hosting']['releaseUrl'].format(tag=sid, file=f)
    base = {'autoPublish': True, 'draft': False, 'text': caption(s), 'firstCommentText': '', 'descendants': [], 'hasNotReadNotes': False,
            'shortener': False, 'smartLinkData': {'ids': []}, 'mediaAltText': [], 'media': [url(sid + '.mp4')],
            'publicationDate': {'dateTime': f"{date}T{time}:00", 'timezone': tz}}
    out = []
    social = [n for n in nets if n in ('instagram', 'tiktok')]
    if social:
        i = dict(base, providers=[{'network': n} for n in social], videoThumbnailUrl=url(sid + '_thumb.jpg'))
        if 'instagram' in social:
            i['instagramData'] = {'type': 'REEL', 'showReelOnFeed': True, 'isAiGenerated': False}
        if 'tiktok' in social:
            i['tiktokData'] = {'privacyOption': 'PUBLIC_TO_EVERYONE', 'disableComment': False, 'disableDuet': False, 'disableStitch': False,
                               'commercialContentThirdParty': False, 'commercialContentOwnBrand': False, 'autoAddMusic': False,
                               'isAigc': False, 'title': s['tiktokTitle'][:90]}
        out.append({'part': '+'.join(social), 'blogId': str(brand), 'date': f"{date}T{time}:00{off[:3]}:{off[3:]}", 'info': json.dumps(i, ensure_ascii=False)})
    if 'youtube' in nets:
        tags = CFG['youtubeTags'][s['slot']] + [bible.display(s['ref']).lower().replace('–', '-')]
        y = dict(base, providers=[{'network': 'youtube'}],
                 youtubeData={'title': yt_title(s), 'type': 'short', 'privacy': 'public', 'tags': tags, 'category': 'PEOPLE_BLOGS',
                              'madeForKids': False, 'isAiGeneratedContent': False})
        out.append({'part': 'youtube', 'blogId': str(brand), 'date': f"{date}T{time}:00{off[:3]}:{off[3:]}", 'info': json.dumps(y, ensure_ascii=False)})
    return out


def build_long(sid, at=None):
    """Weekly long video: YouTube only (type video, with custom thumbnail), Monday 03:00 Amsterdam after the calendar Sunday."""
    s = json.load(open(os.path.join(ROOT, 'content', 'long', sid + '.json')))
    meta_p = os.path.join(ROOT, 'out', sid, sid + '.meta.json')
    chapters = s.get('chapters') or (json.load(open(meta_p))['chapters'] if os.path.exists(meta_p) else [])
    tz = CFG['schedule']['timezone']
    if at:
        date, time = at.split('T')
    else:
        date = (dt.date.fromisoformat(s['date']) + dt.timedelta(days=1)).isoformat(); time = CFG['schedule'].get('longTime', '03:00')
    off = dt.datetime.fromisoformat(f"{date}T{time}").replace(tzinfo=ZoneInfo(tz)).strftime('%z')
    url = lambda f: CFG['hosting']['releaseUrl'].format(tag=sid, file=f)
    title = bible.passage_title(s['passage'])
    text = (f"{s['description']} 🕊️\n\nThe passage is read aloud three times, each time followed by a quiet pass of the same verses for reflection.\n\n"
            + '\n'.join(chapters) + f"\n\nScripture: {title} (King James Version)\n\n"
            "Whatever you are carrying tonight, you are not alone. May His peace be with you.\n\n"
            "Subscribe to Still Waters Daily for a daily word of peace: a Bible verse every day and encouragement every evening.\n\n"
            + ' '.join(s.get('hashtags', ['#bibleverses', '#sleep', '#christianmeditation', '#scripture', '#peace', '#prayer', '#biblereading', '#faith', '#kjv'])))
    tags = [title.lower().replace('–', '-'), 'bible verses for sleep', 'scripture for sleep', 'christian meditation', 'bible reading',
            'peaceful scripture', 'calm bible verses', 'kjv', "sleep with god's word", 'prayer', 'rest'] + s.get('tags', [])
    info = {'autoPublish': True, 'draft': False, 'text': text, 'firstCommentText': '', 'descendants': [], 'hasNotReadNotes': False,
            'shortener': False, 'smartLinkData': {'ids': []}, 'mediaAltText': [], 'media': [url(sid + '.mp4')],
            'videoThumbnailUrl': url(sid + '_thumb.jpg'),
            'publicationDate': {'dateTime': f"{date}T{time}:00", 'timezone': tz}, 'providers': [{'network': 'youtube'}],
            'youtubeData': {'title': s['title'][:100], 'type': 'video', 'privacy': 'public', 'tags': tags[:15], 'category': 'PEOPLE_BLOGS',
                            'madeForKids': False, 'isAiGeneratedContent': False}}
    return [{'part': 'youtube-long', 'blogId': str(CFG['metricool']['brandId']), 'date': f"{date}T{time}:00{off[:3]}:{off[3:]}",
             'info': json.dumps(info, ensure_ascii=False)}]


if __name__ == '__main__':
    a = sys.argv
    nets = a[a.index('--networks') + 1].split(',') if '--networks' in a else None
    if '-long-' in a[1]:
        print(json.dumps(build_long(a[1], a[a.index('--at') + 1] if '--at' in a else None), indent=1, ensure_ascii=False)); sys.exit()
    print(json.dumps(build(a[1], a[a.index('--at') + 1] if '--at' in a else None, nets), indent=1, ensure_ascii=False))
