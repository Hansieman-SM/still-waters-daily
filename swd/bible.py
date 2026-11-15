"""Verbatim KJV lookup. Never type scripture by hand: always go through verse().
>>> parse('1 John 4:7-8') -> ('1 John', 4, 7, 8)"""
import json, os, re

ROOT = os.path.join(os.path.dirname(__file__), '..')
_B = None
ALIAS = {'Psalm': 'Psalms', 'Song of Songs': 'Song of Solomon', 'Revelations': 'Revelation'}
ORD = {'1': 'First', '2': 'Second', '3': 'Third'}


def books():
    global _B
    if _B is None:
        _B = json.load(open(os.path.join(ROOT, 'data', 'kjv.json'), encoding='utf-8'))
    return _B


def parse(ref):
    m = re.fullmatch(r'\s*((?:[123] )?[A-Za-z ]+?)\s+(\d+):(\d+)(?:\s*[-–]\s*(\d+))?\s*', ref)
    if not m:
        raise ValueError(f'bad reference: {ref!r} (use e.g. "Psalm 23:1" or "Matthew 6:33-34")')
    book, ch, v1, v2 = m.group(1).strip(), int(m.group(2)), int(m.group(3)), int(m.group(4) or m.group(3))
    key = ALIAS.get(book, book)
    if key not in books():
        raise ValueError(f'unknown book {book!r}')
    if v2 < v1 or v2 - v1 > 4:
        raise ValueError(f'verse range {v1}-{v2} not allowed (max 5 verses)')
    return key, ch, v1, v2


def verse(ref):
    key, ch, v1, v2 = parse(ref)
    chap = books()[key][ch - 1] if 0 < ch <= len(books()[key]) else None
    if not chap or v2 > len(chap):
        raise ValueError(f'{ref} does not exist in the KJV')
    t = re.sub(r'\s+', ' ', ' '.join(chap[v - 1] for v in range(v1, v2 + 1))).strip()
    return re.sub(r'\s+([,;:.?!])', r'\1', t)          # dataset quirk: 'LORD , for' -> 'LORD, for'


def passage(ref, max_verses=40):
    """Whole chapter ('Psalm 121') or a range ('Isaiah 40:1-11'). -> [(label 'Psalm 121:1', verbatim text)]"""
    m = re.fullmatch(r'\s*((?:[123] )?[A-Za-z ]+?)\s+(\d+)(?::(\d+)(?:\s*[-–]\s*(\d+))?)?\s*', ref)
    if not m:
        raise ValueError(f'bad passage {ref!r}')
    book = ALIAS.get(m.group(1).strip(), m.group(1).strip()); ch = int(m.group(2))
    if book not in books() or not 0 < ch <= len(books()[book]):
        raise ValueError(f'{ref} does not exist in the KJV')
    chap = books()[book][ch - 1]
    v1 = int(m.group(3) or 1); v2 = int(m.group(4) or (m.group(3) or len(chap)))
    if v2 > len(chap) or v2 < v1 or v2 - v1 + 1 > max_verses:
        raise ValueError(f'{ref}: bad verse range (max {max_verses} verses)')
    name = 'Psalm' if book == 'Psalms' else book
    return [(f'{name} {ch}:{v}', re.sub(r'\s+([,;:.?!])', r'\1', re.sub(r'\s+', ' ', chap[v - 1]).strip())) for v in range(v1, v2 + 1)]


def passage_title(ref):
    p = passage(ref); a = p[0][0]; b = p[-1][0].split(':')[1]
    return a if len(p) == 1 else (a.split(':')[0] if a.endswith(':1') and len(p) == len(passage(a.split(':')[0])) else f'{a}–{b}')


def shown(ref):
    """Verbatim KJV text for the screen/caption; only a dangling , ; : at the very end is dropped (standard quoting)."""
    return re.sub(r'[,;:]$', '', verse(ref))


def display(ref):
    """'Psalms 23:1' -> 'Psalm 23:1', ranges with an en dash."""
    key, ch, v1, v2 = parse(ref)
    name = 'Psalm' if key == 'Psalms' else key
    return f"{name} {ch}:{v1}" + (f"–{v2}" if v2 != v1 else '')


def spoken(ref):
    """'1 John 4:7-8' -> 'First John 4, verses 7 to 8.'"""
    key, ch, v1, v2 = parse(ref)
    name = 'Psalm' if key == 'Psalms' else key
    p = name.split(' ', 1)
    if p[0] in ORD:
        name = ORD[p[0]] + ' ' + p[1]
    vs = f"verse {v1}" if v1 == v2 else f"verses {v1} to {v2}"
    return f"{name} {ch}, {vs}."


if __name__ == '__main__':
    import sys
    for r in sys.argv[1:]:
        print(display(r), '|', spoken(r), '|', verse(r))
