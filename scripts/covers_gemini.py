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
from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'artifacts/pinterest-course/covers-v2'
OUT = WORK / 'gemini'
RAW = OUT / '_raw'
TEXTS = json.loads((WORK / 'texts.json').read_text())
CDP = ['node', str(ROOT / 'scripts/gemini_cdp.mjs')]
ANNA = WORK / 'anna_face_ref.jpg'
REFS = sorted((WORK / 'references').glob('ref_*.png'))   # all of the user's reference covers ("инстансы")
ATTACH = [ANNA] + REFS
COURSE = ROOT / 'КУРС_PINTEREST'

sys.path.insert(0, str(ROOT / 'scripts'))
import importlib.util
_s = importlib.util.spec_from_file_location('cv2', ROOT / 'scripts/covers_v2.py'); cv2 = importlib.util.module_from_spec(_s); _s.loader.exec_module(cv2)

SIZES = {'YouTube/Обложка': (1280, 720), 'VK_Видео/Обложка': (1920, 1080), 'Rutube/Обложка': (1920, 1080)}
TALL = (1080, 1920)

# A/B/C must look different, not just carry another headline
LOOKS = [
    ('спокойно и доброжелательно смотрит прямо в камеру, лёгкая улыбка с сомкнутыми губами, плечи расслаблены', 'красный акцент, плашка красная'),
    ('спокойная уверенная полуулыбка эксперта, руки спокойно скрещены на груди, смотрит прямо в камеру', 'жёлтый акцент, плашка жёлтая с чёрным текстом'),
    ('серьёзно и уверенно смотрит в камеру, одна рука на уровне груди открытой ладонью показывает в сторону заголовка', 'бело-красный акцент, плашка белая с красным текстом'),
]
EXPERT = ('Она эксперт и преподаватель курса: спокойная, уверенная, доброжелательная. Губы сомкнуты, лёгкая сдержанная улыбка без зубов. '
          'ЗАПРЕЩЕНО: открытый рот, улыбка с зубами, смех, восторг, удивление, испуг, эмоциональный порыв, рука у щеки или у лица, гримасы. '
          'Женщину НИЧЕГО не перекрывает: ни заголовок, ни плашки, ни логотип, ни карточки, ни строка поиска, ни предметы, ни текст — '
          'всё это только в стороне от неё и не заходит на её голову, волосы, лицо, тело и руки ни на миллиметр.')
REF_TEXT = ('Прикреплено несколько изображений. ПЕРВОЕ — фото Анны: возьми с него только её лицо и внешность. '
            'ОСТАЛЬНЫЕ — образцы профессиональных обложек: возьми с них уровень качества, яркость и насыщенность, объёмный 3D-шрифт с обводкой и тенью, '
            'плашки, свечение, глубину и детализацию. Людей, лица и текст с образцов НЕ переносить. ')
SERIES = ('Единый стиль всей серии курса: тёплый тёмно-красный фон с золотыми искрами и мягким боке, белые объёмные буквы с тенью, '
          'вторая строка заголовка на плашке, жёлтая плашка «УРОК». ')
PHOTO = ('Кадр — как профессиональная студийная фотосессия: объектив 85 мм, мягкий ключевой свет на лице, тёплый контровой свет по волосам, '
         'резкие глаза, естественная кожа с текстурой, без пластикового и мультяшного вида. ')
ANATOMY = ('Анатомия безупречная: естественные пропорции головы, шеи, плеч и рук; на каждой руке ровно пять пальцев нормальной длины; '
           'указательный палец обычной длины, не вытянутый и не толстый; кисть меньше лица; руки не сливаются со свитером; '
           'никаких лишних, сросшихся или изогнутых пальцев. ')

def lesson_text(n, limit=1500):
    """The narration of the lesson, so the picture is built from what the lesson actually teaches."""
    f = COURSE / TEXTS[str(n)]['folder'] / 'Текст_урока.txt'
    t = f.read_text(encoding='utf-8').replace('\r', '') if f.exists() else ''
    t = ' '.join(t.split('\n', 1)[-1].split())
    return t[:limit].rsplit(' ', 1)[0] + '…' if len(t) > limit else t

def context(n, head, kind):
    what = {'w': 'обложка видео (вариант для A/B-теста: у каждого варианта свой угол подачи, заданный заголовком)',
            't': 'обложка короткого вертикального ролика', 'slide': 'слайд карусели', 'card': 'карточка поста', 'pin': 'пин'}[kind]
    return (f'КОНТЕКСТ (только для понимания, на картинке НЕ писать): это {what} к уроку {n} «{TEXTS[str(n)]["title"]}» '
            f'курса по Pinterest для начинающих. Содержание урока: {lesson_text(n)} '
            f'ЗАДАЧА СЦЕНЫ: предметы и сцена должны наглядно и конкретно показывать смысл именно заголовка «{head}» в контексте этого урока, '
            f'чтобы зритель понял тему без слов. Придумай сцену сам по содержанию урока, не повторяй шаблон. ')

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
REAL = 'ИЛЛЮСТРАЦИИ — КАЧЕСТВЕННЫЕ И НАСТОЯЩИЕ: фотореалистичные предметы и карточки-пины с настоящими красивыми фотографиями (интерьер, еда, одежда, товары по теме), как в живой ленте Pinterest. ЗАПРЕЩЕНЫ заглушки: пустые карточки, серые полоски вместо текста, плоские мультяшные иконки (лампочки, компасы, лупы, графики-значки, документы-значки). '

def post_prompt(n, rel, t, kind, var):
    T = TEXTS[str(n)]; prop = cv2.BRIEF[n][0]
    fmt = POST[kind][0]
    style = REF_TEXT + SERIES + PHOTO
    anna = (f'Женщина: с первого прикреплённого фото — то же лицо, каштановые волнистые волосы до плеч, горчичный вязаный свитер. '
            f'Она {LOOKS[var % 3][0]}. {EXPERT} {ANATOMY}')
    exact = 'Текст — только этот, по-русски, без ошибок, буква в букву, каждое слово один раз, НЕ добавляй своих слов и подзаголовков; никакого другого текста, цифр и водяных знаков; на предметах и строке поиска нет ни одной буквы:\n'
    if kind == 'slide':
        sl = T['carousel'][var - 1]; last = var == len(T['carousel'])
        if var == 1:
            body = (f'Обложка карусели Instagram. {anna}Женщина крупно по грудь в нижней половине; перед её телом, руками и лицом ничего нет. Предметы по смыслу урока в стороне от неё. '
                    f'{exact}1) огромный заголовок вверху: «{sl["title"].upper()}»;\n2) под ним строка: «{sl["body"]}»;\n'
                    f'3) маленькая жёлтая плашка: «УРОК {n}» — у верхнего края кадра, НЕ на женщине;\n4) внизу справа маленькая надпись: «ЛИСТАЙТЕ →».')
        else:
            head = 'ЗАДАНИЕ' if last else f'УРОК {n}'          # no slide numbers: lessons are numbered, slides are not
            body = (f'Слайд {var} карусели Instagram. {anna}Женщина по грудь в нижней правой части кадра, смотрит в камеру, рядом с текстом; '
                    f'рядом с ней — наглядная фотореалистичная сцена по смыслу этого слайда в теме урока «{T["title"]}» (например, телефон с живой лентой Pinterest, настоящие фото-карточки, экран сайта), не перекрывает её. '
                    f'{exact}1) вверху маленькая жёлтая плашка: «{head}»;\n2) огромный заголовок: «{sl["title"].upper()}»;\n'
                    f'3) под ним обычным белым текстом, крупно и читаемо: «{sl["body"]}»'
                    + (';\n4) внизу маленькая надпись: «СОХРАНИТЕ, ЧТОБЫ ВЕРНУТЬСЯ».' if last else '.'))
    elif kind == 'card':
        body = (f'Карточка для поста в Threads. {anna}Женщина крупно по грудь в нижней половине; перед её телом, руками и лицом ничего нет. Предметы по смыслу урока в стороне от неё. '
                f'{exact}1) огромный заголовок вверху: «{t.upper()}»;\n2) маленькая жёлтая плашка: «УРОК {n}» — у верхнего края кадра, НЕ на женщине.')
    else:
        pn = T['pins'][var]
        if pn['points']:
            pts = '\n'.join(f'   {k}. «{x}»' for k, x in enumerate(pn['points'], 1))
            body = (f'Пин-шпаргалка. {anna}Женщина по грудь в нижней части кадра. Аккуратная инфографика над ней: заголовок вверху, ниже нумерованный список в красных кружках с цифрами; '
                    f'список не перекрывает женщину. {exact}1) заголовок: «{t.upper()}»;\n2) список:\n{pts}\n'
                    f'3) маленькая подпись внизу: «КУРС ПО PINTEREST · УРОК {n}».')
        else:
            body = (f'Пин для Pinterest. {anna}Женщина крупно по грудь в нижней половине; перед её телом, руками и лицом ничего нет. Предметы по смыслу урока в стороне от неё. '
                    f'{exact}1) огромный заголовок вверху: «{t.upper()}»;\n2) маленькая жёлтая плашка: «УРОК {n}» — у верхнего края кадра, НЕ на женщине.')
    logo_rule = ('Логотип Pinterest — РОВНО ОДИН на всё изображение (не два и не больше), небольшой красный круглый, в верхнем левом углу кадра, далеко от женщины. '
                 if kind != 'slide' or var == 1 else 'Логотип Pinterest — ровно один, маленький, в верхнем углу кадра, далеко от женщины. ')
    return f'Создай изображение: {fmt}, не квадрат и не горизонтальное. {style}{logo_rule}{MARGIN}{REAL}\n\n{context(n, t, kind)}\n\n{body}'

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
                 'женщина крупно по грудь в нижней половине; предметы по теме — только по бокам от её головы и выше, НИЧЕГО не проходит перед её телом, руками и лицом; её фигура доходит до самого нижнего края кадра, без обрезанного края и пустых полос'
                 + ('. ВАЖНО: верхняя 1/8 и нижняя 1/8 высоты кадра — только фон, без текста и плашек; весь текст, плашка «УРОК» и лицо — в центральной части кадра' if reels else ''))
    return f'''Создай изображение: обложку для видео, {frame}.

{REF_TEXT}{SERIES}{PHOTO}

Женщина: с первого прикреплённого фото — то же лицо, каштановые волнистые волосы до плеч, горчичный вязаный свитер. Она {face}. {EXPERT} {ANATOMY}

{context(n, head, kind)}Сцена подробно: крупные детализированные фотореалистичные предметы по смыслу заголовка, с отражениями, тенями и глубиной резкости. {REAL} Логотип Pinterest — ровно один, небольшой красный круглый, СТРОГО вплотную слева от плашки «УРОК» (на той же высоте), далеко от женщины; ни плашка, ни логотип не заходят на женщину. Логотип НЕ касается и НЕ перекрывает женщину: не на голове, не на волосах, не на лице, не на теле, не на одежде, не в руках и не рядом с ними.

Оформление: {accent}.

Текст на обложке — только этот, по-русски, без ошибок, буква в букву:
1) огромный заголовок «{head}» — ровно эти слова, каждое ровно один раз, ничего не добавлять и не повторять: {lines};
2) маленькая жёлтая плашка «УРОК {n}» — {'над заголовком, у верхнего края кадра' if kind == 't' else 'рядом с заголовком'}, НЕ на женщине;
{'3) маленькая белая лента внизу: «' + ribbon + '».' if kind == 'w' else ''}
Никакого другого текста, цифр и водяных знаков; строка поиска пустая, на карточках и предметах нет ни одной буквы, ни на каком языке.'''

def cdp(*a, timeout=120):
    r = subprocess.run(CDP + list(a), capture_output=True, text=True, timeout=timeout)
    if r.returncode: raise RuntimeError(r.stderr[-500:])
    return r.stdout.strip()

class LimitError(RuntimeError): pass

FLOW = ['node', str(ROOT / 'scripts/flow_cdp.mjs')]
ASPECT = {'w': '16:9', 't': '9:16', 'slide': '3:4', 'card': '3:4', 'pin': '3:4'}

def flow(*a, timeout=120):
    r = subprocess.run(FLOW + list(a), capture_output=True, text=True, timeout=timeout)
    if r.returncode: raise RuntimeError(f'flow {a[0]}: ' + next((l for l in r.stderr.splitlines() if 'Error' in l), r.stderr.strip()[-200:]))
    return r.stdout.strip()

_aspect = None

def flow_prompt(p, kind):
    return p.replace('Создай изображение:', f'Сгенерируй ОДНО изображение (Нано Банан Про, формат {ASPECT[kind]}):')

def flow_gen(p, raw_dir, kind='w'):
    """One image from Google Flow (Nano Banana Pro, free there). Returns the downloaded file."""
    before = {u for u, _ in json.loads(flow('images') or '[]')}
    want = 'w' if kind == 'w' else 't'
    global _aspect
    if _aspect != ASPECT[kind]: flow('aspect', ASPECT[kind]); _aspect = ASPECT[kind]
    flow('clear')
    for f in ATTACH: flow('attach', f.name)
    flow('prompt', flow_prompt(p, kind))
    new = []
    for _ in range(60):
        time.sleep(5)
        new = [u for u, o in json.loads(flow('images') or '[]') if u not in before and o == want]
        st = json.loads(flow('state'))
        if new and not st['busy']: break
        if not st['busy'] and 'usage limit' in st['text']: raise LimitError('лимит Flow')
    if not new: raise RuntimeError('flow: no image')
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = raw_dir / f'flow_{int(time.time())}.png'
    flow('fetch', new[0], str(out))
    return out

MARK = {'flow': 98, 'app': 117}                    # sparkle centre offset from the bottom-right corner, at 768 px short side
_mark = 'flow'

def unmark(im):
    """Flow draws a small sparkle ~98 px (at 768 px short side) from the bottom-right corner.
    Cover it with the patch right above it, feathered, so nothing else in the frame changes."""
    from PIL import ImageFilter
    w, h = im.size; k = min(w, h) / 768
    c, r = round(98 * k), round(40 * k)                 # Flow: centre offset from the corner, half-size of the patch
    if _mark == 'app': c, r = 116, 50                   # Gemini app: fixed offset in source pixels whatever the aspect
    x0, y0 = w - c - r, h - c - r
    src = im.crop((x0, y0 - 2 * r - round(6 * k), x0 + 2 * r, y0 - round(6 * k)))
    mask = Image.new('L', (2 * r, 2 * r), 0)
    ImageDraw.Draw(mask).ellipse((round(4 * k), round(4 * k), 2 * r - round(4 * k), 2 * r - round(4 * k)), fill=255)
    im = im.copy(); im.paste(src, (x0, y0), mask.filter(ImageFilter.GaussianBlur(5 * k)))
    return im

def app_gen(p, raw_dir, kind='w'):
    """One image from the Gemini app tab (gemini.google.com)."""
    cdp('newchat')
    cdp('upload', 'Files', *map(str, ATTACH))
    cdp('eval', "(()=>{const e=document.querySelector('rich-textarea .ql-editor, [contenteditable=true]');e.focus();return !!e})()")
    cdp('type', p); time.sleep(1)
    cdp('eval', "[...document.querySelectorAll('button')].find(b=>/Send|Отправить/.test(b.getAttribute('aria-label')||'')).click()")
    for _ in range(60):
        time.sleep(5)
        st = json.loads(json.loads(cdp('eval', "JSON.stringify({n:[...document.querySelectorAll('button')].filter(b=>/Download full size|полном размере/i.test(b.getAttribute('aria-label')||'')).length,busy:!![...document.querySelectorAll('button')].find(b=>/Stop|Остановить/.test(b.getAttribute('aria-label')||'')),t:(([...document.querySelectorAll('message-content')].pop()||{}).innerText||'').slice(0,200)})")))
        if st['n'] and not st['busy']: break
        if not st['busy'] and 'лимит' in st['t']: raise LimitError('лимит Gemini')
    else: raise RuntimeError('gemini: no image')
    raw_dir.mkdir(parents=True, exist_ok=True)
    before = set(raw_dir.iterdir())
    for attempt in range(3):                   # the full-size download is sometimes slow: retry the click, never regenerate
        try: cdp('download', str(raw_dir), timeout=90)
        except Exception: pass
        for _ in range(150):
            new = [f for f in set(raw_dir.iterdir()) - before if not f.name.endswith('.crdownload')]
            if new:
                for extra in new[1:]: extra.unlink()
                return new[0]
            time.sleep(1)
    raise RuntimeError('download failed')

BACKENDS = [app_gen, flow_gen]
_blocked = {}                                     # backend -> time it hit its limit

def gemini(p, raw_dir, kind='w'):
    """Try Flow, then the Gemini app; a backend that hit its limit rests 30 min."""
    for b in BACKENDS:
        if time.time() - _blocked.get(b, 0) < 1800: continue
        try:
            global _mark
            out = b(p, raw_dir, kind); _mark = 'app' if b is app_gen else 'flow'; return out
        except LimitError as e:
            print(time.strftime('%H:%M'), e, '— переключаюсь', flush=True); _blocked[b] = time.time()
    raise LimitError('лимит у всех генераторов')

def fit_size(src, out, size):
    im = Image.open(src).convert('RGB')
    im = unmark(im)
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
    finish(n, rel, kind, gemini(prompt(n, rel, t, kind, var), RAW, kind))

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
        if not src.exists(): continue                 # partial install: put in what is ready, the rest follows
        if dstf.exists() and not (bak_root / rel).exists():
            (bak_root / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(dstf, bak_root / rel)
        shutil.copy2(src, dstf)
    print(f'урок {n} установлен в КУРС_PINTEREST ({len(covers(n))} обложек)')

def run(first=1, last=42):
    for n in range(first, last + 1):
        for rel, *_ in covers(n):
            if dst(n, rel).exists(): continue
            attempt = 0
            while True:                                  # never give up: the user wants all 42 lessons
                try: make(n, rel); install(n); break
                except LimitError:
                    print(time.strftime('%H:%M'), 'лимит у всех генераторов, жду 10 минут', flush=True); time.sleep(600)
                except Exception as e:
                    attempt += 1; print(f'ошибка {n} {rel}: {e}', flush=True)
                    time.sleep(30 if attempt < 3 else 300)
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
