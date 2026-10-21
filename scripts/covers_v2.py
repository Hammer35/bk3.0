"""Video covers v2 for the Pinterest course, styled after the user's reference thumbnails.

Art (Anna + topic props, no text) comes from Gemini Nano Banana Pro; headline typography,
the Pinterest mark and real-screenshot cards are laid out in HTML and rendered by Chrome,
so Cyrillic text is always exact.

Everything is built in artifacts/pinterest-course/covers-v2/ first. КУРС_PINTEREST is touched
only by `install`, only for covers the user approved, keeping the old file next to backups.

  python3 scripts/covers_v2.py models                 # list image models visible to the key
  python3 scripts/covers_v2.py gen 1 [2 ...] [--force] # generate art for lessons
  python3 scripts/covers_v2.py render 1 [2 ...]        # compose all covers of lessons
  python3 scripts/covers_v2.py sheet 1 [2 ...]         # approval sheet per lesson
  python3 scripts/covers_v2.py install 1 [2 ...]       # copy approved covers into КУРС_PINTEREST

Key: ~/.config/gemini_image_key (put there by the user; never stored in the repo).
"""
from pathlib import Path
import sys, json, base64, subprocess, shutil, hashlib, html, time, urllib.request, urllib.error, datetime
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'artifacts/pinterest-course/covers-v2'
REFS = WORK / 'references'                      # user's reference thumbnails (style only)
ART = WORK / 'art'
OUT = WORK / 'out'
FONTS = WORK / 'fonts'
COURSE = ROOT / 'КУРС_PINTEREST'
ANNA = ROOT / 'video/pinterest-lesson/public/anna-reference.png'
KEY = Path.home() / '.config/gemini_image_key'
MODEL = 'gemini-3-pro-image-preview'
TEXTS = json.loads((WORK / 'texts.json').read_text())
CHROME = shutil.which('google-chrome') or shutil.which('chromium')

# ---------------------------------------------------------------- per-lesson art briefs
# prop: what floats next to Anna; mood: her emotion. Two moods -> two different arts per format.
BRIEF = {
    1: ('a giant glowing 3D search bar made of glass with floating photo pin cards (interior, food, fashion) flying out of it like answers', ('curious, leaning towards the cards, eyebrows raised', 'confident smile, pointing at the viewer')),
    2: ('a large magnifying glass over a wall of photo pin cards, one card lit up and sharp, the rest blurred; a small camera icon lens scanning a photo', ('focused, squinting through the magnifier', 'surprised, hand near mouth')),
    3: ('one single glossy photo pin card, a corkboard-style board holding several pins, and a profile avatar card, connected by glowing lines', ('explaining, palm open towards the objects', 'cheerful, holding a pin card')),
    4: ('a photo pin card shooting a glowing red arrow into a laptop screen showing a website', ('excited, following the arrow with her eyes', 'pointing at the laptop')),
    5: ('two doors or two ID cards side by side: a plain personal card and a premium business card with a briefcase icon and a chart', ('thoughtful choice, finger on chin', 'confident, holding the business card')),
    6: ('a giant smartphone showing a beautiful profile page with avatar, cover and boards; makeup brushes and a ring light around it', ('proud, presenting the phone', 'friendly smile, arms crossed')),
    7: ('several themed folders/boards labelled only by pictures (kitchen, cozy room, garden) arranged on shelves', ('organising, holding a board like a folder', 'satisfied smile')),
    8: ('one large board opening like a filing cabinet with neat drawers, each drawer full of photo pins', ('sorting cards into drawers', 'pleased, pointing at a drawer')),
    9: ('a golden chain link connecting a pin card to a website with a big green verification checkmark shield', ('relieved, thumbs up', 'serious, checking the link')),
    10: ('one bright pin card in a spotlight while a messy pile of overloaded cards falls into the dark', ('decisive, holding up one finger', 'pushing the messy pile away')),
    11: ('a vertical 2:3 photo frame being cropped with glowing crop corners, a camera and a palette', ('creative, framing with her fingers', 'smiling at a perfect vertical photo')),
    12: ('a pin card with large empty title and description lines being typed by floating keyboard keys', ('writing, pen in hand', 'thinking, looking up for words')),
    13: ('a pin image with a glowing speech bubble and an eye icon, an accessibility symbol made of light', ('kind explaining smile', 'listening, hand to ear')),
    14: ('a big red PUBLISH-style button (no text) being pressed, confetti of photo pins bursting out', ('excited, pressing the big button', 'celebrating, fists up')),
    15: ('a published pin card with a pencil and a wrench fixing it, sparkles around the fixed corner', ('focused repair, holding a pencil', 'relieved smile after the fix')),
    16: ('a wide funnel turning a cloud of vague topics into one sharp glowing question mark card', ('narrowing with both hands', 'aha moment, finger up')),
    17: ('floating search suggestion chips and word bubbles being collected into a jar', ('collecting words into the jar', 'reading a list, intrigued')),
    18: ('glowing keyword labels flowing into three slots: pin title, description and board name cards', ('placing a word card', 'pointing at the slots')),
    19: ('a big 3D line chart with a rising trend line and a calendar, magnifier over the peak', ('analysing the chart, impressed', 'pointing at the peak')),
    20: ('a calendar with four season icons (snowflake, flower, sun, leaf) and a crystal ball showing a trend arrow', ('planning ahead, holding the calendar', 'looking into the crystal ball')),
    21: ('neat stacks of photos, a camera, a notebook and folders labelled by colour, like a creator\'s content stock', ('organising photos on a table', 'happy with a full folder')),
    22: ('one photo splitting into many different pin cards like a fan of playing cards', ('fanning out the cards', 'amazed by many cards')),
    23: ('a weekly planner calendar with pin cards placed on days, a clock', ('planning with a pen', 'calm confident smile')),
    24: ('two piles: a pin card with a creator badge (own camera) versus a saved card with a bookmark ribbon', ('comparing the two piles', 'holding her own camera')),
    25: ('a stylish collage of cut-out photos (sofa, lamp, plant, rug) assembled on one board', ('arranging cut-outs', 'admiring the collage')),
    26: ('a checklist clipboard with numbered steps and a pin card moving through them on a conveyor', ('ticking a checklist', 'pointing at the next step')),
    27: ('three glowing 3D icons: an eye (impressions), a bookmark (saves) and a cursor click, with small bar charts', ('analysing, impressed', 'counting on her fingers')),
    28: ('a dashboard on a big monitor with charts and a summary panel', ('reviewing the dashboard', 'pointing at a chart')),
    29: ('one pin card under a microscope with tiny charts coming out of it', ('looking into the microscope', 'surprised by the numbers')),
    30: ('two pin cards on a balance scale, one heavier with a small trophy', ('comparing, weighing in hands', 'pointing at the winner')),
    31: ('a pin card with a downward red arrow and a doctor stethoscope diagnosing it', ('concerned, examining', 'determined to fix it')),
    32: ('a broken chain link and a warning triangle in front of a website with an error page', ('shocked, hands on cheeks', 'warning gesture, palm out')),
    33: ('a pin with an exaggerated fake promise being crossed out with a big red X, fake likes balloons popping', ('skeptical, arms crossed', 'stop gesture')),
    34: ('a giant padlock and a red warning shield over a profile card', ('worried, hand over mouth', 'calm, holding a key')),
    35: ('a path from a pin card to a shopping cart and a contact form with glowing footsteps', ('guiding along the path', 'happy at the finish')),
    36: ('a rich pin card with extra product price tag and recipe card attached like expansions', ('showing the extended card', 'impressed')),
    37: ('a pin card with a partnership handshake icon and a link label', ('shaking hands gesture', 'explaining with a finger up')),
    38: ('a megaphone and a target with an arrow, a small code tag bracket icon </> glowing', ('thoughtful before launch, finger on chin', 'holding the megaphone')),
    39: ('a calendar and a clock with pin cards queued on a timeline', ('scheduling, tapping the calendar', 'relaxed with coffee')),
    40: ('a friendly AI assistant hologram writing draft cards next to her, she holds a red pen to edit', ('editing a draft with a red pen', 'curious about the hologram')),
    41: ('a 30-day roadmap path with milestones and a flag at the end', ('pointing at the roadmap', 'determined walk forward pose')),
    42: ('a big checklist with green checks and a magnifier over a profile and pins', ('inspecting with a magnifier', 'thumbs up, all checked')),
}

STYLE = ('Professional YouTube thumbnail art, photorealistic, cinematic studio lighting, strong red rim light, '
         'deep dark charcoal-to-burgundy background with soft red glow and subtle bokeh, high contrast, crisp details, '
         'saturated but natural skin tones. ABSOLUTELY NO text, letters, numbers, words, logos or watermarks anywhere in the image.')
ANNA_DESC = ('The woman is Anna from the attached reference photo: same face, same shoulder-length wavy brown hair, '
             'same warm look; keep her identity exactly. Modern smart-casual outfit (rust or cream knit, gold hoop earrings). '
             'Photorealistic real person, not a cartoon.')

def art_prompt(n, fmt, k):
    prop, moods = BRIEF[n]
    mood = moods[k % 2]
    if fmt == 'h':
        lay = ('16:9 frame. Anna occupies the right 40% of the frame, upper body, large and close to camera, '
               f'expression: {mood}. Next to her, in the centre-right: {prop}, rendered as glossy 3D objects. '
               'The LEFT 55% of the frame must stay clean dark background (only soft glow), reserved for a big headline added later.')
    else:
        lay = ('9:16 vertical frame. Anna in the lower 60% of the frame, upper body, large, '
               f'expression: {mood}. Around her at mid-height: {prop}, as glossy 3D objects. '
               'The TOP 35% of the frame must stay clean dark background (only soft glow), reserved for a big headline added later.')
    return f'{lay} {ANNA_DESC} Match the energy and polish of the attached style references (but not their text). {STYLE}'

# ---------------------------------------------------------------- Gemini image API
def api(path, body=None):
    key = KEY.read_text().strip()
    url = f'https://generativelanguage.googleapis.com/v1beta/{path}'
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={'x-goog-api-key': key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r: return json.loads(r.read())

def part(path, maxside=1280):
    im = Image.open(path).convert('RGB'); im.thumbnail((maxside, maxside))
    tmp = WORK / '.part.jpg'; im.save(tmp, 'JPEG', quality=90)
    return {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(tmp.read_bytes()).decode()}}

def generate(prompt, aspect, refs, dst):
    body = {'contents': [{'parts': [{'text': prompt}] + [part(r) for r in refs]}],
            'generationConfig': {'responseModalities': ['TEXT', 'IMAGE'], 'imageConfig': {'aspectRatio': aspect, 'imageSize': '2K'}}}
    for attempt in range(4):
        try:
            r = api(f'models/{MODEL}:generateContent', body)
            for c in r.get('candidates', []):
                for p in c.get('content', {}).get('parts', []):
                    d = p.get('inline_data') or p.get('inlineData')
                    if d:
                        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(base64.b64decode(d['data']))
                        log(dst, prompt, r.get('usageMetadata')); return True
            print('  no image in response:', json.dumps(r)[:400])
        except urllib.error.HTTPError as e:
            print('  HTTP', e.code, e.read()[:300].decode('utf-8', 'replace'))
            if e.code in (400, 401, 403): return False
        time.sleep(8 * (attempt + 1))
    return False

def log(dst, prompt, usage):
    with open(WORK / 'generation_log.jsonl', 'a') as f:
        f.write(json.dumps({'file': str(dst.relative_to(WORK)), 'sha256': hashlib.sha256(dst.read_bytes()).hexdigest(),
                            'model': MODEL, 'time': datetime.datetime.now().isoformat(timespec='seconds'),
                            'usage': usage, 'prompt': prompt}, ensure_ascii=False) + '\n')

ART_SET = [('h', 0, '16:9'), ('h', 1, '16:9'), ('h', 2, '16:9'), ('v', 0, '9:16'), ('v', 1, '9:16')]

def gen(n, force=False):
    style = sorted(REFS.glob('ref_*.png'))
    for fmt, k, aspect in ART_SET:
        dst = ART / f'{n:02}' / f'{fmt}{k}.png'
        if dst.exists() and not force: continue
        refs = [ANNA] + style[(n + k) % len(style):][:1] + style[:1]
        print(f'урок {n} {fmt}{k}…', flush=True)
        generate(art_prompt(n, fmt, k), aspect, refs[:3], dst)

# ---------------------------------------------------------------- GigaChat (Kandinsky) backend
GIGA_ENV = ROOT / '.env'

def giga_ctx():
    import ssl
    ctx = ssl.create_default_context()  # system roots + Russian Trusted Root CA used by Sber
    ctx.load_verify_locations(ROOT / 'infra/certs/russian_trusted_root_ca_pem.crt')
    return ctx

def giga_token():
    import re, uuid, urllib.parse
    env = dict(re.findall(r'^(GIGACHAT_[A-Z_]+)=(.*)$', GIGA_ENV.read_text(), re.M))
    key = env['GIGACHAT_API_TOKEN'].strip().strip('"\'')
    scope = env.get('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS').strip().strip('"\'')
    req = urllib.request.Request('https://ngw.devices.sberbank.ru:9443/api/v2/oauth', urllib.parse.urlencode({'scope': scope}).encode(),
        {'Authorization': f'Basic {key}', 'RqUID': str(uuid.uuid4()), 'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=60, context=giga_ctx()) as r: return json.loads(r.read())['access_token']

def giga_generate(prompt, dst, model='GigaChat-2-Max'):
    import re
    tok = giga_token(); H = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    body = {'model': model, 'function_call': 'auto', 'messages': [
        {'role': 'system', 'content': 'Ты — профессиональный иллюстратор обложек YouTube. Рисуй без текста и надписей.'},
        {'role': 'user', 'content': prompt}]}
    req = urllib.request.Request('https://gigachat.devices.sberbank.ru/api/v1/chat/completions', json.dumps(body).encode(), H)
    with urllib.request.urlopen(req, timeout=300, context=giga_ctx()) as r: resp = json.loads(r.read())
    m = re.search(r'<img src="([^"]+)"', resp['choices'][0]['message']['content'])
    if not m: print('  нет картинки:', resp['choices'][0]['message']['content'][:300]); return False
    req = urllib.request.Request(f'https://gigachat.devices.sberbank.ru/api/v1/files/{m.group(1)}/content', headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/jpg'})
    with urllib.request.urlopen(req, timeout=300, context=giga_ctx()) as r: data = r.read()
    dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(data); log(dst, prompt, resp.get('usage')); return True

GIGA_BRIEF = {
    1: ('большой красный круглый 3D-значок Pinterest и несколько летящих фотокарточек с интерьером и едой',
        ('удивлённо приподняла брови и широко улыбается', 'уверенно улыбается и показывает пальцем на зрителя')),
}

def giga_prompt(n, fmt, k):
    prop, moods = GIGA_BRIEF.get(n, (BRIEF[n][0], BRIEF[n][1]))
    mood = moods[k % 2]
    return ('Горизонтальный широкоформатный кадр 16:9, яркое превью для YouTube, крупный портрет по грудь, женщина в правой части кадра. Женщина 35 лет, каштановые волосы до плеч, '
            f'горчичный свитер, золотые серьги-кольца, смотрит прямо в камеру, {mood}. '
            f'За её плечом {prop}. Насыщенный тёмно-бордовый фон с красным свечением, '
            'яркий контровой свет по волосам, студийное освещение лица, резкость, глянец. Без текста и надписей.')

def gen_giga(n, only, force=False):
    """Exactly one image per run: `giga 1 h0`."""
    for fmt, k, _ in ART_SET:
        if f'{fmt}{k}' != only: continue
        dst = ART / f'{n:02}' / f'{fmt}{k}.jpg'
        if dst.exists() and not force: print('уже есть:', dst); continue
        print(f'урок {n} {fmt}{k}…', flush=True)
        giga_generate(giga_prompt(n, fmt, k), dst)

# ---------------------------------------------------------------- HTML composition
PIN = (WORK / 'pinterest.svg').read_text().replace('<title>Pinterest</title>', '')

def split_headline(t, plate=13):
    """-> (plain lines, accent) : accent goes on the red plate."""
    w = t.replace('—', '').split()
    if len(w) == 1: return [], w[0]
    if len(w) == 2: return [w[0]], w[1]
    # the plate gets the longest tail that still reads as one short punch (<= plate letters)
    best = len(w) - 1
    while best > 1 and len(' '.join(w[best - 1:])) <= plate: best -= 1
    return [' '.join(w[:best])], ' '.join(w[best:])

CSS = '''
@font-face{font-family:M;src:url(FONTS/Montserrat[wght].ttf)}
@font-face{font-family:R;src:url(FONTS/Rubik[wght].ttf)}
@font-face{font-family:O;src:url(FONTS/Oswald[wght].ttf)}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:WPX;height:HPX;overflow:hidden;background:#111}
.st{position:absolute;left:0;top:0;width:WPX;height:HPX;overflow:hidden}
.art{position:absolute;inset:0;background-size:cover;background-position:var(--pos,70% 30%)}
.shade{position:absolute;inset:0}
.hl{position:absolute;font-family:O;font-weight:700;text-transform:uppercase;line-height:.95;letter-spacing:.005em}
.hl .l{display:block;color:#fff;-webkit-text-stroke:var(--sw) #000;paint-order:stroke fill;
  text-shadow:.012em .012em 0 #2a0006,.024em .024em 0 #2a0006,.036em .036em 0 #2a0006,.048em .048em 0 #2a0006,.06em .06em 0 #2a0006,.08em .1em .2em rgba(0,0,0,.8)}
.hl .l.y{color:#ffd23f}
.hl .acc{display:inline-block;background:linear-gradient(180deg,#ff3b3b,#c8102e);color:#fff;padding:.04em .22em .08em;
  border-radius:.06em;transform:rotate(-2deg) skewX(-4deg);box-shadow:.03em .06em 0 #6d0010,0 .18em .4em rgba(0,0,0,.6);margin:.08em 0;
  -webkit-text-stroke:var(--sw2) #5b000c;paint-order:stroke fill;white-space:nowrap}
.chip{position:absolute;font-family:M;font-weight:800;text-transform:uppercase;background:#ffd23f;color:#111;
  border-radius:.4em;padding:.25em .7em;box-shadow:0 .2em .5em rgba(0,0,0,.5);letter-spacing:.02em}
.rib{position:absolute;font-family:M;font-weight:800;text-transform:uppercase;background:#fff;color:#111;
  border-radius:2em;padding:.35em 1em;box-shadow:0 .2em .6em rgba(0,0,0,.6);white-space:nowrap}
.pin{position:absolute;border-radius:50%;background:radial-gradient(circle at 35% 30%,#ff6b6b,#e60023 45%,#8a0014);
  box-shadow:0 0 0 .06em #fff,0 .12em .3em rgba(0,0,0,.6),0 0 1.2em rgba(255,0,40,.55);display:flex;align-items:center;justify-content:center}
.pin svg{width:72%;height:72%;fill:#fff;filter:drop-shadow(0 .03em .02em rgba(0,0,0,.4))}
.shot{position:absolute;border-radius:14px;overflow:hidden;border:6px solid #fff;box-shadow:0 18px 40px rgba(0,0,0,.65);transform:rotate(-4deg)}
.shot img{display:block;width:100%;height:100%;object-fit:cover;object-position:50% 20%}
.num{position:absolute;font-family:M;font-weight:900;color:#fff;-webkit-text-stroke:4px #000;paint-order:stroke fill}
'''

FIT_JS = '''
document.fonts.ready.then(()=>{document.querySelectorAll('[data-fit]').forEach(el=>{
  const [w,h]=el.dataset.fit.split(',').map(Number); let s=parseFloat(el.style.fontSize);
  while(s>8&&(el.scrollWidth>w||el.scrollHeight>h)){s-=1;el.style.fontSize=s+'px'}
  el.style.width=w+'px'; document.title='ok'})});
'''

def page(W, H, body):
    css = CSS.replace('FONTS', FONTS.as_uri()).replace('WPX', f'{W}px').replace('HPX', f'{H}px')
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body><div class="st">{body}</div><script>{FIT_JS}</script></body></html>'

def headline(t, x, y, w, h, size, align='left', yellow_first=False, plate=13):
    plain, acc = split_headline(t, plate)
    lines = ''.join(f'<span class="l{" y" if yellow_first else ""}">{html.escape(p)}</span>' for p in plain)
    lines += f'<span class="l"><span class="acc">{html.escape(acc)}</span></span>'
    sw = max(2, size // 9)
    return (f'<div class="hl" data-fit="{w},{h}" style="left:{x}px;top:{y}px;width:{w}px;font-size:{size}px;'
            f'text-align:{align};--sw:{sw}px;--sw2:{max(1, sw // 2)}px;'
            f'{"" if align == "left" else "display:flex;flex-direction:column;align-items:center;"}">{lines}</div>')

def pin(x, y, d): return f'<div class="pin" style="left:{x}px;top:{y}px;width:{d}px;height:{d}px">{PIN}</div>'

def art_div(p, pos='70% 30%'):
    if p and p.exists() and abs(Image.open(p).width / Image.open(p).height - 1) < .05 and pos == '70% 30%':
        u = p.as_uri()
        return (f'<div class="art" style="background-image:url({u});background-size:cover;background-position:50% 50%;filter:blur(38px) brightness(.45) saturate(1.3);transform:scale(1.15)"></div>'
                f'<div class="art" style="left:auto;width:820px;background-image:url({u});background-size:cover;background-position:60% 30%;'
                '-webkit-mask-image:linear-gradient(90deg,transparent 0%,#000 32%);mask-image:linear-gradient(90deg,transparent 0%,#000 32%)"></div>')
    return f'<div class="art" style="background-image:url({p.as_uri()});--pos:{pos}"></div>' if p and p.exists() else \
           f'<div class="art" style="background:radial-gradient(circle at 75% 40%,#5a0f17,#121216 60%)"></div>'

def wide(variant, t, ribbon, n, art, shot):
    """1280x720 CSS px; rendered at scale 1 (YouTube) or 1.5 (VK/Rutube 1920x1080)."""
    W, H = 1280, 720
    b = [art_div(art)]
    if variant == 0:     # big stacked headline left, chip, ribbon
        b += ['<div class="shade" style="background:linear-gradient(90deg,rgba(8,8,10,.55) 0%,rgba(8,8,10,.3) 40%,rgba(8,8,10,0) 60%)"></div>',
              f'<div class="chip" style="left:48px;top:40px;font-size:26px">Урок {n}</div>',
              headline(t, 48, 110, 640, 470, 200),
              f'<div class="rib" style="left:48px;top:610px;font-size:28px">{html.escape(ribbon)}</div>']
    elif variant == 1:   # headline bottom-left over gradient, yellow first line, real screenshot card
        b += ['<div class="shade" style="background:linear-gradient(0deg,rgba(8,8,10,.95) 0%,rgba(8,8,10,.55) 45%,rgba(8,8,10,0) 70%),linear-gradient(90deg,rgba(8,8,10,.7),rgba(8,8,10,0) 55%)"></div>',
              (f'<div class="shot" style="left:60px;top:44px;width:420px;height:262px"><img src="{Path(shot).as_uri()}"></div>' if shot else ''),
              headline(t, 44, 330, 760, 360, 140, yellow_first=True),
              pin(1150, 30, 92),
              f'<div class="num" style="left:520px;top:40px;font-size:64px">#{n}</div>']
    else:                # centred-left headline, ribbon on top, big Pinterest mark
        b += ['<div class="shade" style="background:radial-gradient(ellipse at 22% 55%,rgba(10,10,12,.92) 0%,rgba(10,10,12,.7) 40%,rgba(10,10,12,0) 68%)"></div>',
              f'<div class="rib" style="left:44px;top:44px;font-size:26px;background:#e60023;color:#fff">{html.escape(ribbon)}</div>',
              headline(t, 44, 130, 700, 470, 160),
              pin(44, 610, 80),
              f'<div class="chip" style="left:140px;top:628px;font-size:24px;background:#fff">Урок {n}</div>']
    return page(W, H, ''.join(b))

def tall(variant, t, n, art, safe34=False):
    """540x960 CSS px, rendered at scale 2 -> 1080x1920."""
    W, H = 540, 960
    top = 140 if safe34 else 70            # Reels profile grid crops to 3:4 (y 120..840 in CSS px)
    b = [art_div(art, '50% 70%'),
         '<div class="shade" style="background:linear-gradient(180deg,rgba(8,8,10,.92) 0%,rgba(8,8,10,.7) 32%,rgba(8,8,10,0) 52%),linear-gradient(0deg,rgba(8,8,10,.55),rgba(8,8,10,0) 20%)"></div>']
    if variant == 0:
        b += [f'<div class="chip" style="left:50%;transform:translateX(-50%);top:{top}px;font-size:18px">Урок {n}</div>',
              headline(t, 30, top + 50, 480, 270, 104, align='center', plate=9)]
    else:
        b += [pin(30, top, 64),
              headline(t, 30, top + 80, 480, 260, 104, yellow_first=True, plate=9)]
    return page(W, H, ''.join(b))

def shoot(html_text, path, W, H, scale):
    tmp = WORK / '.render.html'; tmp.write_text(html_text, encoding='utf-8')
    png = WORK / '.render.png'
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                    f'--window-size={W},{H + 300}', f'--force-device-scale-factor={scale}', '--virtual-time-budget=4000',
                    f'--screenshot={png}', tmp.as_uri()], check=True, capture_output=True, timeout=120)
    im = Image.open(png).convert('RGB').crop((0, 0, int(W * scale), int(H * scale)))  # window is taller than the viewport
    path.parent.mkdir(parents=True, exist_ok=True)
    for q in (93, 90, 86, 82):
        im.save(path, 'JPEG', quality=q, optimize=True)
        if path.stat().st_size < 1900 * 1024: break

# cover file -> (kind, variant, text, art, extra)
def plan(n):
    T = TEXTS[str(n)]; A = ART / f'{n:02}'; sh = T.get('shots', []); title = T['title']
    S = lambda i: sh[i % len(sh)] if sh else None
    pick = lambda name: next((p for p in (A / f'{name}.jpg', A / f'{name}.png') if p.exists()), A / f'{name}.png')
    h = lambda k: pick(f'h{k}'); v = lambda k: pick(f'v{k}')
    P = {}
    for i, t in enumerate(T['yt']): P[f'YouTube/Обложка_{"ABC"[i]}.jpg'] = ('w', i, t, h(i), (S(i), title, 1))
    for i, t in enumerate(T['vk']): P[f'VK_Видео/Обложка_{"AB"[i]}.jpg'] = ('w', (i + 1) % 3, t, h((i + 1) % 3), (S(i + 1), title, 1.5))
    for i, t in enumerate(T['ru']): P[f'Rutube/Обложка_{"ABC"[i]}.jpg'] = ('w', (i + 2) % 3, t, h((i + 2) % 3), (S(i + 2), title, 1.5))
    for i, t in enumerate(T['shorts'], 1): P[f'YouTube/Shorts_{i}_обложка.jpg'] = ('t', (i - 1) % 2, t, v((i - 1) % 2), False)
    for i, t in enumerate(T['clips'], 1): P[f'VK_Клипы/Клип_{i}_обложка.jpg'] = ('t', i % 2, t, v(i % 2), False)
    for i, t in enumerate(T['rus'], 1): P[f'Rutube/Shorts_{i}_обложка.jpg'] = ('t', (i - 1) % 2, t, v(i % 2), False)
    for i, t in enumerate(T['reels'], 1): P[f'Instagram/Reels_{i}_обложка.jpg'] = ('t', i % 2, t, v((i - 1) % 2), True)
    # Rutube C exists only where the course already has it
    for k in list(P):
        if k.startswith('Rutube/Обложка_C') and not (COURSE / T['folder'] / k).exists(): P.pop(k)
    return P

def render(n, only=None):
    for rel, (kind, var, t, art, extra) in plan(n).items():
        if only and rel != only: continue
        dst = OUT / f'{n:02}' / rel
        if kind == 'w':
            shot, title, scale = extra
            ribbon = title if title.lower() != t.lower() else 'Курс по Pinterest с нуля'
            shoot(wide(var, t, ribbon, n, art, shot), dst, 1280, 720, scale)
        else:
            shoot(tall(var, t, n, art, extra), dst, 540, 960, 2)
        print(' ', dst.relative_to(WORK), Image.open(dst).size, flush=True)

def sheet(n):
    P = plan(n); d = OUT / f'{n:02}'
    wides = [k for k, v in P.items() if v[0] == 'w']; talls = [k for k, v in P.items() if v[0] == 't']
    cw, ch = 640, 360; tw, th = 270, 480; pad = 34
    W = max(3 * (cw + 20), 8 * (tw + 14)) + 40
    rows_w = (len(wides) + 2) // 3
    H = 90 + rows_w * (ch + pad + 20) + th + pad + 40
    S = Image.new('RGB', (W, H), '#1b1d22'); dr = ImageDraw.Draw(S)
    f = ImageFont.truetype(str(FONTS / 'Montserrat[wght].ttf'), 30); f.set_variation_by_axes([800])
    fs = ImageFont.truetype(str(FONTS / 'Montserrat[wght].ttf'), 17); fs.set_variation_by_axes([600])
    dr.text((20, 22), f'Урок {n}. {TEXTS[str(n)]["title"]} — обложки на одобрение', font=f, fill='#fff')
    for i, k in enumerate(wides):
        x, y = 20 + (i % 3) * (cw + 20), 90 + (i // 3) * (ch + pad + 20)
        S.paste(Image.open(d / k).convert('RGB').resize((cw, ch)), (x, y)); dr.text((x, y + ch + 6), k, font=fs, fill='#ccc')
    y0 = 90 + rows_w * (ch + pad + 20)
    for i, k in enumerate(talls):
        x = 20 + i * (tw + 14)
        S.paste(Image.open(d / k).convert('RGB').resize((tw, th)), (x, y0)); dr.text((x, y0 + th + 6), k.replace('_обложка.jpg', ''), font=fs, fill='#ccc')
    p = WORK / 'sheets' / f'Урок_{n:02}.jpg'; p.parent.mkdir(exist_ok=True); S.save(p, 'JPEG', quality=88)
    print(p)

def install(n):
    T = TEXTS[str(n)]; stamp = datetime.date.today().strftime('%Y%m%d')
    ok = WORK / 'approved.json'
    approved = json.loads(ok.read_text()) if ok.exists() else {}
    if str(n) not in approved: sys.exit(f'урок {n} не одобрен пользователем — не устанавливаю')
    for rel in plan(n):
        src = OUT / f'{n:02}' / rel; dst = COURSE / T['folder'] / rel
        bak = ROOT / f'artifacts/pinterest-course/backup-covers-{stamp}' / T['folder'] / rel
        if dst.exists() and not bak.exists(): bak.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(dst, bak)
        shutil.copy2(src, dst); print(' ', dst.relative_to(ROOT))

if __name__ == '__main__':
    cmd, *a = sys.argv[1:]
    force = '--force' in a; ns = [int(x) for x in a if x.isdigit()] or list(range(1, 43))
    one = next((x for x in a if x[:1] in 'hv' and x[1:].isdigit()), None)
    if cmd == 'giga' and (len(ns) != 1 or not one): sys.exit('одна картинка за запуск: covers_v2.py giga <урок> <h0|h1|h2|v0|v1>')
    if cmd == 'models':
        for m in api('models?pageSize=200')['models']:
            if 'image' in m['name']: print(m['name'], m.get('displayName'))
    for n in ns:
        if cmd == 'gen': gen(n, force)
        elif cmd == 'giga': gen_giga(n, one, force)
        elif cmd == 'render': render(n, next((x for x in a if '/' in x), None))
        elif cmd == 'sheet': sheet(n)
        elif cmd == 'install': install(n)
