"""Video covers drawn by Gemini (Nano Banana) in the visible Chrome on port 9335.

One cover per run, then it is opened for the user in Gradia:
  python3 scripts/covers_gemini.py next            # first cover not made yet (lesson order)
  python3 scripts/covers_gemini.py make 1 YouTube/Обложка_B.jpg
  python3 scripts/covers_gemini.py list 1          # covers of a lesson and their state

Style source: the approved cover (lesson 1, YouTube A) + Anna's portrait. Text is given verbatim.
Output: artifacts/pinterest-course/covers-v2/gemini/NN/<platform>/<file>, exact platform size.
"""
from pathlib import Path
import sys, json, subprocess, time, shutil
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'artifacts/pinterest-course/covers-v2'
OUT = WORK / 'gemini'
RAW = OUT / '_raw'
TEXTS = json.loads((WORK / 'texts.json').read_text())
CDP = ['node', str(ROOT / 'scripts/gemini_cdp.mjs')]
ANNA = WORK / 'anna_face_ref.jpg'
STYLE = OUT / '01/YouTube_Обложка_A_v1.png'          # approved by the user 21.10.2026
COURSE = ROOT / 'КУРС_PINTEREST'

sys.path.insert(0, str(ROOT / 'scripts'))
import importlib.util
_s = importlib.util.spec_from_file_location('cv2', ROOT / 'scripts/covers_v2.py'); cv2 = importlib.util.module_from_spec(_s); _s.loader.exec_module(cv2)

SIZES = {'YouTube/Обложка': (1280, 720), 'VK_Видео/Обложка': (1920, 1080), 'Rutube/Обложка': (1920, 1080)}
TALL = (1080, 1920)

# A/B/C must look different, not just carry another headline
LOOKS = [
    ('радостно и уверенно улыбается, смотрит прямо в камеру', 'красный акцент, плашка красная'),
    ('удивлена, брови подняты, рот приоткрыт, рука у щеки', 'жёлтый акцент, плашка жёлтая с чёрным текстом'),
    ('серьёзно и уверенно смотрит в камеру, указывает пальцем на заголовок', 'бело-красный акцент, плашка белая с красным текстом'),
]

def covers(n):
    """[(rel, headline, kind, look)] in a fixed order."""
    out = []
    for rel, (kind, var, t, *_rest) in cv2.plan(n).items():
        out.append((rel, t, 'w' if kind == 'w' else 't', var))
    order = lambda r: (0 if r[0].startswith('YouTube/Обл') else 1 if r[0].startswith('VK_Видео') else 2 if r[0].startswith('Rutube/Обл') else 3, r[0])
    return sorted(out, key=order)

def dst(n, rel): return OUT / f'{n:02}' / rel

def prompt(n, rel, t, kind, var):
    T = TEXTS[str(n)]; prop = cv2.BRIEF[n][0]
    face, accent = LOOKS[var % 3]
    head = t.upper()
    ribbon = T['title'].upper()
    if kind == 'w':
        frame = ('горизонтальную, строго 16:9, не квадрат. Огромный заголовок слева, женщина крупно по грудь справа, '
                 'предметы по теме между ними')
    else:
        reels = 'Instagram/Reels' in rel
        frame = ('ВЕРТИКАЛЬНУЮ, строго 9:16 (1080×1920), не квадрат и не горизонтальную. Огромный заголовок в верхней трети, '
                 'женщина крупно по грудь в нижней половине, предметы по теме вокруг'
                 + ('. Весь текст и лицо держи в центральной зоне 3:4 (не у самого верха и низа кадра)' if reels else ''))
    return f'''Создай изображение: обложку для видео, {frame}.

Стиль, шрифт, качество, обводка и объём букв, свечение — точно как на втором прикреплённом изображении (это утверждённая обложка курса), но композиция и предметы ДРУГИЕ: не повторяй строку поиска и карточки со второго изображения, нарисуй предметы ниже заново.

Женщина: с первого прикреплённого фото — то же лицо, каштановые волнистые волосы до плеч, горчичный вязаный свитер. Она {face}.

Тема урока {n}: «{T['title']}». Предметы по теме: {prop}. Можно аккуратный красный круглый логотип Pinterest рядом с предметами — не на голове и не в руках женщины.

Оформление: {accent}. Тёмный насыщенный фон со свечением и искрами.

Текст на обложке — только этот, по-русски, без ошибок, буква в букву:
1) огромный заголовок: «{head}» (одна из строк — на плашке);
2) маленькая жёлтая плашка: «УРОК {n}»;
{'3) маленькая белая лента внизу: «' + ribbon + '».' if kind == 'w' else ''}
Никакого другого текста, цифр и водяных знаков.'''

def cdp(*a, timeout=120):
    r = subprocess.run(CDP + list(a), capture_output=True, text=True, timeout=timeout)
    if r.returncode: raise RuntimeError(r.stderr[-500:])
    return r.stdout.strip()

def gemini(p, raw_dir):
    cdp('newchat')
    cdp('upload', 'Files', str(ANNA), str(STYLE))
    cdp('eval', "(()=>{const e=document.querySelector('rich-textarea .ql-editor, [contenteditable=true]');e.focus();return !!e})()")
    cdp('type', p); time.sleep(1)
    cdp('eval', "document.querySelector('button[aria-label*=\"Send\"]').click()")
    for _ in range(60):
        time.sleep(5)
        s = json.loads(json.loads(cdp('eval', "JSON.stringify({n:[...document.querySelectorAll('button[aria-label=\"Download full size image\"]')].length,busy:!!document.querySelector('[aria-label*=\"Stop\"]')})")))
        if s['n'] and not s['busy']: break
    else: raise RuntimeError('gemini: no image')
    raw_dir.mkdir(parents=True, exist_ok=True)
    before = set(raw_dir.iterdir())
    cdp('download', str(raw_dir), timeout=90)
    for _ in range(90):
        new = [f for f in set(raw_dir.iterdir()) - before if not f.name.endswith('.crdownload')]
        if new: return new[0]
        time.sleep(1)
    raise RuntimeError('download failed')

def fit_size(src, out, size):
    im = Image.open(src).convert('RGB')
    im = ImageOps.fit(im, size, Image.Resampling.LANCZOS, centering=(0.5, 0.45))
    out.parent.mkdir(parents=True, exist_ok=True)
    for q in (93, 90, 86):
        im.save(out, 'JPEG', quality=q, optimize=True)
        if out.stat().st_size < 1900 * 1024: break

def make(n, rel):
    item = next(c for c in covers(n) if c[0] == rel)
    _, t, kind, var = item
    finish(n, rel, kind, gemini(prompt(n, rel, t, kind, var), RAW))

def finish(n, rel, kind, raw):
    w, h = Image.open(raw).size
    if (kind == 'w') != (w > h): print(f'ВНИМАНИЕ: Gemini дал {w}×{h}, не тот формат')
    size = next((s for k, s in SIZES.items() if rel.startswith(k)), TALL)
    out = dst(n, rel); fit_size(raw, out, size)
    shutil.move(raw, RAW / f'{n:02}_{rel.replace("/", "_").rsplit(".", 1)[0]}_{w}x{h}{raw.suffix}')
    subprocess.run(['pkill', '-f', '^python3 /snap/gradia/[0-9]+/usr/bin/gradia '])   # one preview window at a time
    subprocess.Popen(['setsid', '/snap/bin/gradia', str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(time.strftime('%H:%M'), f'готово: урок {n} {rel} {Image.open(out).size} (исходник {w}×{h})')
    print(out)

def install(n):
    """Copy a finished lesson into КУРС_PINTEREST, keeping the old covers in a backup folder."""
    folder = TEXTS[str(n)]['folder']
    bak_root = ROOT / 'artifacts/pinterest-course/backup-covers-20261021' / folder
    for rel, *_ in covers(n):
        src, dstf = dst(n, rel), COURSE / folder / rel
        if dstf.exists() and not (bak_root / rel).exists():
            (bak_root / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(dstf, bak_root / rel)
        shutil.copy2(src, dstf)
    print(f'урок {n} установлен в КУРС_PINTEREST ({len(covers(n))} обложек)')

def run(first=1, last=42):
    for n in range(first, last + 1):
        for rel, *_ in covers(n):
            if dst(n, rel).exists(): continue
            for attempt in range(3):
                try: make(n, rel); break
                except Exception as e: print(f'ошибка {n} {rel}: {e}', flush=True); time.sleep(30)
            else: sys.exit(f'остановлено на уроке {n} {rel}')
        install(n)

if __name__ == '__main__':
    cmd, *a = sys.argv[1:]
    if cmd == 'list':
        for rel, t, kind, var in covers(int(a[0])): print('✔' if dst(int(a[0]), rel).exists() else '·', rel, '—', t)
    elif cmd == 'make': make(int(a[0]), a[1])
    elif cmd == 'finish': finish(int(a[0]), a[1], 'w' if 'Обложка' in a[1] else 't', Path(a[2]))
    elif cmd == 'install': install(int(a[0]))
    elif cmd == 'run': run(*map(int, a))
    elif cmd == 'next':
        for n in range(1, 43):
            todo = [c for c in covers(n) if not dst(n, c[0]).exists()]
            if todo: make(n, todo[0][0]); break
