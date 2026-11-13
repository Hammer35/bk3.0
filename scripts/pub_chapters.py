"""Chapter start times per lesson: each narration paragraph -> subtitle cue where it begins."""
import re, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pub_build import lesson_dir

def cues(srt):
    out = []
    for b in re.split(r'\n\s*\n', srt.strip()):
        ls = b.strip().split('\n')
        if len(ls) >= 3 and '-->' in ls[1]:
            h, m, s = ls[1].split('-->')[0].strip().replace(',', '.').split(':')
            out.append((int(h) * 3600 + int(m) * 60 + float(s), ' '.join(ls[2:])))
    return out

def words(s): return re.findall(r'[а-яёa-z0-9]+', s.lower().replace('ё', 'е'))

def chapters(n):
    d = lesson_dir(n); cs = cues((d / '02_Текст_урока/Субтитры_полного_урока.srt').read_text())
    stream = []  # (word, time)
    for t, txt in cs:
        for w in words(txt): stream.append((w, t))
    vt = d / '02_Текст_урока/Текст_озвучки.txt'
    if not vt.exists(): return None
    paras = [p for p in re.split(r'\n\s*\n', vt.read_text().strip()) if p.strip()]
    res, pos = [], 0
    for p in paras:
        key = words(p)[:4]
        for i in range(pos, len(stream) - 3):
            if [w for w, _ in stream[i:i + 4]] == key:
                res.append((stream[i][1], p)); pos = i + 1; break
    return res

if __name__ == '__main__':
    for n in range(1, 41):
        ch = chapters(n)
        print(n, 'нет озвучки' if ch is None else [round(t) for t, _ in ch])
