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
STYLE = WORK / 'references/ref_01.png'               # the user's reference (the old approved cover had the logo on Anna)
COURSE = ROOT / 'КУРС_PINTEREST'

sys.path.insert(0, str(ROOT / 'scripts'))
import importlib.util
_s = importlib.util.spec_from_file_location('cv2', ROOT / 'scripts/covers_v2.py'); cv2 = importlib.util.module_from_spec(_s); _s.loader.exec_module(cv2)

SIZES = {'YouTube/Обложка': (1280, 720), 'VK_Видео/Обложка': (1920, 1080), 'Rutube/Обложка': (1920, 1080)}
TALL = (1080, 1920)

# A/B/C must look different, not just carry another headline
LOOKS = [
    ('уверенно и доброжелательно улыбается, рот закрыт, смотрит прямо в камеру', 'красный акцент, плашка красная'),
    ('спокойная уверенная полуулыбка эксперта, руки скрещены на груди, смотрит прямо в камеру', 'жёлтый акцент, плашка жёлтая с чёрным текстом'),
    ('серьёзно и уверенно смотрит в камеру, указывает пальцем на заголовок', 'бело-красный акцент, плашка белая с красным текстом'),
]
EXPERT = ('Она эксперт и преподаватель курса: спокойная, уверенная, доброжелательная, рот закрыт. '
          'ЗАПРЕЩЕНО: удивление, испуг, открытый рот, рука у щеки или у лица, гримасы. '
          'На женщине и перед ней НИЧЕГО нет: ни логотипа, ни карточек, ни строки поиска, ни предметов, ни текста — '
          'все предметы только в стороне от неё и не перекрывают её ни на миллиметр.')

def covers(n):
    """[(rel, headline, kind, look)]: video covers first, then posts and pins.
    kind: w = 16:9 cover, t = 9:16 cover, slide = carousel 4:5, card = Threads 4:5, pin = Pinterest 2:3."""
    out = []
    for rel, (kind, var, t, *_rest) in cv2.plan(n).items():
        out.append((rel, t, 'w' if kind == 'w' else 't', var))
    order = lambda r: (0 if r[0].startswith('YouTube/Обл') else 1 if r[0].startswith('VK_Видео') else 2 if r[0].startswith('Rutube/Обл') else 3, r[0])
    out = sorted(out, key=order)
    T = TEXTS[str(n)]
    for i, sl in enumerate(T['carousel'], 1): out.append((f'Instagram/Карусель_{i:02}.jpg', sl['title'], 'slide', i))
    out.append(('Threads/Карточка.jpg', T['threads'], 'card', 0))
    for i, pn in enumerate(T['pins']): out.append((f'Pinterest/Пин_{"AB"[i]}.jpg', pn['overlay'], 'pin', i))
    return out

def dst(n, rel): return OUT / f'{n:02}' / rel

POST = {'slide': ('ВЕРТИКАЛЬНЫЙ пост 4:5 (1080×1350)', (1080, 1350)), 'card': ('ВЕРТИКАЛЬНЫЙ пост 4:5 (1080×1350)', (1080, 1350)),
        'pin': ('ВЕРТИКАЛЬНЫЙ пин для Pinterest 2:3 (1000×1500)', (1000, 1500))}
MARGIN = 'Весь текст держи внутри кадра с полями не меньше 8% от каждого края. '

def post_prompt(n, rel, t, kind, var):
    T = TEXTS[str(n)]; prop = cv2.BRIEF[n][0]
    fmt = POST[kind][0]
    style = ('Стиль, шрифт, обводка и объём букв, свечение — как на втором прикреплённом изображении (образец стиля); '
             'ничего не копируй с него, кроме стиля. Тёмный насыщенный фон со свечением и искрами. ')
    anna = (f'Женщина: с первого прикреплённого фото — то же лицо, каштановые волнистые волосы до плеч, горчичный вязаный свитер. '
            f'Она {LOOKS[var % 3][0]}. {EXPERT} ')
    exact = 'Текст — только этот, по-русски, без ошибок, буква в букву, каждое слово один раз; никакого другого текста, цифр и водяных знаков:\n'
    if kind == 'slide':
        sl = T['carousel'][var - 1]; last = var == len(T['carousel'])
        if var == 1:
            body = (f'Обложка карусели Instagram. {anna}Женщина крупно по грудь в нижней половине. Предметы по теме урока «{T["title"]}» в стороне: {prop}. '
                    f'{exact}1) огромный заголовок вверху: «{sl["title"].upper()}»;\n2) под ним строка: «{sl["body"]}»;\n'
                    f'3) маленькая жёлтая плашка: «УРОК {n}»;\n4) внизу справа маленькая надпись: «ЛИСТАЙТЕ →».')
        else:
            head = 'ЗАДАНИЕ' if last else f'{var - 1:02}'
            body = (f'Слайд {var} карусели Instagram, без людей. Небольшая 3D-иллюстрация по смыслу слайда внизу, в теме урока «{T["title"]}». '
                    f'{exact}1) вверху крупно жёлтым: «{head}»;\n2) огромный заголовок: «{sl["title"].upper()}»;\n'
                    f'3) под ним обычным белым текстом, крупно и читаемо: «{sl["body"]}»'
                    + (';\n4) внизу маленькая надпись: «СОХРАНИТЕ, ЧТОБЫ ВЕРНУТЬСЯ».' if last else '.'))
    elif kind == 'card':
        body = (f'Карточка для поста в Threads. {anna}Женщина крупно по грудь в нижней половине. Предметы по теме в стороне: {prop}. '
                f'{exact}1) огромный заголовок вверху: «{t.upper()}»;\n2) маленькая жёлтая плашка: «УРОК {n}».')
    else:
        pn = T['pins'][var]
        if pn['points']:
            pts = '\n'.join(f'   {k}. «{x}»' for k, x in enumerate(pn['points'], 1))
            body = (f'Пин-шпаргалка, без людей. Аккуратная инфографика: заголовок вверху, ниже нумерованный список в красных кружках с цифрами, '
                    f'небольшая 3D-иллюстрация по теме внизу. {exact}1) заголовок: «{t.upper()}»;\n2) список:\n{pts}\n'
                    f'3) маленькая подпись внизу: «КУРС ПО PINTEREST · УРОК {n}».')
        else:
            body = (f'Пин для Pinterest. {anna}Женщина крупно по грудь в нижней половине. Предметы по теме в стороне: {prop}. '
                    f'{exact}1) огромный заголовок вверху: «{t.upper()}»;\n2) маленькая жёлтая плашка: «УРОК {n}».')
    logo_rule = ('Логотип Pinterest — ровно один, небольшой красный круглый, в верхнем углу кадра, далеко от женщины. '
                 if kind != 'slide' or var == 1 else 'Без логотипов. ')
    return f'Создай изображение: {fmt}, не квадрат и не горизонтальное. {style}{logo_rule}{MARGIN}\n\n{body}'

def prompt(n, rel, t, kind, var):
    if kind in POST: return post_prompt(n, rel, t, kind, var)
    T = TEXTS[str(n)]; prop = cv2.BRIEF[n][0]
    face, accent = LOOKS[var % 3]
    head = t.upper()
    plain, acc = cv2.split_headline(head, 9 if kind == 't' else 13)
    lines = (f'первая строка «{plain[0]}», вторая строка на плашке «{acc}»' if plain else f'одна строка на плашке «{acc}»')
    ribbon = T['title'].upper() if T['title'].lower() not in t.lower() else 'КУРС ПО PINTEREST С НУЛЯ'
    if kind == 'w':
        frame = ('горизонтальную, строго 16:9, не квадрат. Огромный заголовок слева, женщина крупно по грудь справа, '
                 'предметы по теме между ними')
    else:
        reels = 'Instagram/Reels' in rel
        frame = ('ВЕРТИКАЛЬНУЮ, строго 9:16 (1080×1920), не квадрат и не горизонтальную. Огромный заголовок в верхней трети, '
                 'женщина крупно по грудь в нижней половине, предметы по теме вокруг'
                 + ('. ВАЖНО: верхняя 1/8 и нижняя 1/8 высоты кадра — только фон, без текста и плашек; весь текст, плашка «УРОК» и лицо — в центральной части кадра' if reels else ''))
    return f'''Создай изображение: обложку для видео, {frame}.

Стиль, шрифт, качество, обводка и объём букв, свечение — точно как на втором прикреплённом изображении (это образец стиля), но человек, текст, композиция и предметы — свои, по описанию ниже; ничего не копируй со второго изображения, кроме стиля.

Женщина: с первого прикреплённого фото — то же лицо, каштановые волнистые волосы до плеч, горчичный вязаный свитер. Она {face}. {EXPERT}

Тема урока {n}: «{T['title']}». Предметы по теме: {prop}. Логотип Pinterest — ровно один, небольшой красный круглый, СТРОГО вплотную слева от плашки «УРОК» (на той же высоте), далеко от женщины. Логотип НЕ касается и НЕ перекрывает женщину: не на голове, не на волосах, не на лице, не на теле, не на одежде, не в руках и не рядом с ними.

Оформление: {accent}. Тёмный насыщенный фон со свечением и искрами.

Текст на обложке — только этот, по-русски, без ошибок, буква в букву:
1) огромный заголовок «{head}» — ровно эти слова, каждое ровно один раз, ничего не добавлять и не повторять: {lines};
2) маленькая жёлтая плашка: «УРОК {n}»;
{'3) маленькая белая лента внизу: «' + ribbon + '».' if kind == 'w' else ''}
Никакого другого текста, цифр и водяных знаков.'''

def cdp(*a, timeout=120):
    r = subprocess.run(CDP + list(a), capture_output=True, text=True, timeout=timeout)
    if r.returncode: raise RuntimeError(r.stderr[-500:])
    return r.stdout.strip()

class LimitError(RuntimeError): pass

def gemini(p, raw_dir):
    cdp('newchat')
    cdp('upload', 'Files', str(ANNA), str(STYLE))
    cdp('eval', "(()=>{const e=document.querySelector('rich-textarea .ql-editor, [contenteditable=true]');e.focus();return !!e})()")
    cdp('type', p); time.sleep(1)
    cdp('eval', "[...document.querySelectorAll('button')].find(b=>/Send|Отправить/.test(b.getAttribute('aria-label')||'')).click()")
    for _ in range(60):
        time.sleep(5)
        s = json.loads(json.loads(cdp('eval', "JSON.stringify({n:[...document.querySelectorAll('button')].filter(b=>/Download full size|полном размере|Скачать изображение/i.test(b.getAttribute('aria-label')||'')).length,busy:!![...document.querySelectorAll('button')].find(b=>/Stop|Остановить/.test(b.getAttribute('aria-label')||''))})")))
        if s['n'] and not s['busy']: break
        if not s['busy'] and 'лимит' in cdp('eval', "([...document.querySelectorAll('message-content')].pop()||{}).innerText||''"):
            raise LimitError('лимит Gemini')
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

def reels_extend(src, out):
    """3:4 art -> 1080x1920: the art fills the profile-grid window (y 240..1680); above and below it
    continues as a softly blurred mirror of its own edge, fading darker towards the frame edge."""
    from PIL import ImageFilter, ImageChops
    art = ImageOps.fit(Image.open(src).convert('RGB'), (1080, 1440), Image.Resampling.LANCZOS)
    top = ImageOps.flip(art.crop((0, 0, 1080, 240))).filter(ImageFilter.GaussianBlur(4))
    bot = ImageOps.flip(art.crop((0, 1200, 1080, 1440))).filter(ImageFilter.GaussianBlur(4))
    shade = Image.linear_gradient('L').resize((1080, 240))          # 0 at the seam -> 255 at the frame edge
    dark = lambda im, g: Image.composite(Image.new('RGB', im.size, (12, 8, 10)), im, g.point(lambda v: int(v * 0.85)))
    bg = Image.new('RGB', (1080, 1920))
    bg.paste(dark(top, ImageOps.flip(shade)), (0, 0)); bg.paste(dark(bot, shade), (0, 1680)); bg.paste(art, (0, 240))
    out.parent.mkdir(parents=True, exist_ok=True); bg.save(out, 'JPEG', quality=92, optimize=True)

def make(n, rel):
    item = next(c for c in covers(n) if c[0] == rel)
    _, t, kind, var = item
    finish(n, rel, kind, gemini(prompt(n, rel, t, kind, var), RAW))

def finish(n, rel, kind, raw):
    w, h = Image.open(raw).size
    if (kind == 'w') != (w > h) or (kind in POST and w >= h):
        raw.unlink(); raise RuntimeError(f'Gemini дал {w}×{h}, не тот формат — повтор')
    size = POST[kind][1] if kind in POST else next((s for k, s in SIZES.items() if rel.startswith(k)), TALL)
    out = dst(n, rel)
    fit_size(raw, out, size)
    raw.unlink()
    subprocess.run(['pkill', '-f', '/snap/gradia/[0-9]+/usr/bin/gradia'])   # one preview window at a time
    time.sleep(2)                                                               # let it exit, or the new one opens empty
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
            attempt = 0
            while attempt < 3:
                try: make(n, rel); break
                except LimitError:
                    print(time.strftime('%H:%M'), 'лимит Gemini, жду 10 минут', flush=True); time.sleep(600)
                except Exception as e:
                    attempt += 1; print(f'ошибка {n} {rel}: {e}', flush=True); time.sleep(30)
            else: sys.exit(f'остановлено на уроке {n} {rel}')
        install(n)

if __name__ == '__main__':
    cmd, *a = sys.argv[1:]
    if cmd == 'list':
        for rel, t, kind, var in covers(int(a[0])): print('✔' if dst(int(a[0]), rel).exists() else '·', rel, '—', t)
    elif cmd == 'make': make(int(a[0]), a[1])
    elif cmd == 'install': install(int(a[0]))
    elif cmd == 'run': run(*map(int, a))
    elif cmd == 'next':
        for n in range(1, 43):
            todo = [c for c in covers(n) if not dst(n, c[0]).exists()]
            if todo: make(n, todo[0][0]); break
