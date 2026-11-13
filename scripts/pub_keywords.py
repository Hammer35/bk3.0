"""Collect a real-data semantic core per lesson from search suggestions.

Sources (public autocomplete endpoints, no paid APIs):
  yt  — YouTube autocomplete (suggestqueries.google.com, ds=yt)
  gg  — Google autocomplete (hl=ru, gl=RU)
  ya  — Yandex autocomplete (suggest.yandex.ru)
Each seed is expanded one level: seed, seed + each suggestion, seed + letters а..я.
A phrase scores higher when several sources return it and when it appears
higher in their lists (autocomplete order reflects popularity).

Usage: python3 scripts/pub_keywords.py [N ...]   -> artifacts/pinterest-course/publication/keywords/NN.json
"""
from pathlib import Path
import json, sys, time, urllib.parse, urllib.request, collections, re
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'artifacts/pinterest-course/publication'
OUT = SRC / 'keywords'
SEEDS = SRC / 'keyword_seeds.yaml'
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/128.0'}
LETTERS = 'абвгдежзиклмнопрстуфхцчшэя'

def get(url):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except Exception:
            time.sleep(1.5)
    return None

def suggest(source, q):
    e = urllib.parse.quote(q)
    if source == 'yt': d = get(f'https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=ru&gl=RU&q={e}')
    elif source == 'gg': d = get(f'https://suggestqueries.google.com/complete/search?client=firefox&hl=ru&gl=RU&q={e}')
    else: d = get(f'https://suggest.yandex.ru/suggest-ff.cgi?part={e}&uil=ru&v=4')
    if not d or len(d) < 2: return []
    return [x if isinstance(x, str) else x[1] for x in d[1]]

def norm(s): return re.sub(r'\s+', ' ', s.lower().replace('ё', 'е')).strip()

def collect(n, seeds, must):
    score = collections.defaultdict(float); seen = collections.defaultdict(set); raw = []
    def take(src, q):
        for pos, s in enumerate(suggest(src, q)):
            s2 = norm(s)
            if not any(m in s2 for m in must): continue
            score[s2] += 1.0 / (1 + pos * 0.15); seen[s2].add(src); raw.append([src, q, s])
        time.sleep(0.15)
    for seed in seeds:
        for src in ('yt', 'gg', 'ya'):
            take(src, seed)
            for l in LETTERS[:6]: take(src, f'{seed} {l}')
    # second level: expand the strongest phrases once more
    for s2, _ in sorted(score.items(), key=lambda x: -x[1])[:8]:
        for src in ('yt', 'ya'): take(src, s2 + ' ')
    rows = [{'phrase': k, 'score': round(v * len(seen[k]), 2), 'sources': sorted(seen[k])} for k, v in score.items()]
    rows.sort(key=lambda r: -r['score'])
    return rows, raw

if __name__ == '__main__':
    cfg = yaml.safe_load(SEEDS.read_text()); OUT.mkdir(parents=True, exist_ok=True)
    ns = [int(a) for a in sys.argv[1:]] or sorted(cfg)
    for n in ns:
        c = cfg[n]; rows, raw = collect(n, c['seeds'], [norm(m) for m in c['must']])
        (OUT / f'{n:02}.json').write_text(json.dumps({'lesson': n, 'seeds': c['seeds'], 'must': c['must'],
            'collected': time.strftime('%Y-%m-%d %H:%M'), 'keywords': rows, 'raw': raw}, ensure_ascii=False, indent=1))
        print(f'урок {n}: {len(rows)} фраз; топ: ' + ' | '.join(r['phrase'] for r in rows[:8]), flush=True)
