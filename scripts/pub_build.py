"""Build per-platform publication kits for the Pinterest course.

Source of truth: artifacts/pinterest-course/publication/NN.yaml (one per lesson).
Output: КУРС_PINTEREST/ПУБЛИКАЦИЯ/Урок_NN_<slug>/<Платформа>/ — one Публикация.md
per platform plus covers, pins and platform-specific video cuts.

Usage:
  python3 scripts/pub_build.py check            # limits + uniqueness for all yaml
  python3 scripts/pub_build.py build 6 [7 ...]   # texts + images (+ video unless --no-video)
"""
from pathlib import Path
import sys, re, json, glob, subprocess, itertools, collections, os, math
import yaml
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'artifacts/pinterest-course/publication'
OUT = ROOT / 'КУРС_PINTEREST'
COURSE = ROOT / 'КУРС_PINTEREST/_АРХИВ_старые_версии/Переделка_с_реальным_аккаунтом'
SHOTS_OLD = ROOT / 'artifacts/pinterest-course/rebuild-all'
MANROPE = ROOT / 'video/pinterest-lesson/public/Manrope.ttf'
OSWALD = ROOT / 'docs/pinterest-course/brand/oswald-regular.ttf'
LOGO = ROOT / 'docs/pinterest-course/brand/boostklient-education-corner.png'

INK, BEIGE, GREY, RED, YEL, DARK, WHITE = '#171b20', '#f1eee6', '#6f7476', '#c8452f', '#f2b632', '#161920', '#ffffff'

# ---------------------------------------------------------------- limits
LIMITS = {
    ('youtube', 'title'): 100, ('youtube', 'description'): 5000, ('youtube', 'comment'): 10000,
    ('shorts', 'title'): 100, ('shorts', 'description'): 5000,
    ('vk_video', 'title'): 100, ('vk_video', 'description'): 5000, ('vk_video', 'post'): 4000,
    ('vk_clip', 'description'): 200,
    ('rutube', 'title'): 100, ('rutube', 'description'): 5000,
    ('reel', 'caption'): 2200, ('carousel', 'caption'): 2200,
    ('threads', 'post'): 500,
    ('pin', 'title'): 100, ('pin', 'description'): 500, ('pin', 'alt'): 500,
    ('video_pin', 'title'): 100, ('video_pin', 'description'): 500,
}

# ---------------------------------------------------------------- lesson sources
def lesson_dir(n):
    ds = sorted(COURSE.glob(f'Урок_{n:02}_*'))
    if n == 27: ds = [d for d in ds if 'v3' in d.name]
    if n == 31: ds = [d for d in ds if 'v2' in d.name]
    assert len(ds) == 1, (n, ds)
    return ds[0]

def clips(n):
    return sorted((lesson_dir(n) / '01_Видео').glob('Клип_*.mp4'))

def shots(n):
    if n <= 15:
        fs = [Path(f) for f in glob.glob(str(SHOTS_OLD / f'{n:02}/*.png'))
              if not re.search(r'final-|upper-|one-created', f)]
    else:
        fs = [Path(f) for f in glob.glob(str(lesson_dir(n) / '05_Слайды/Реальные_скриншоты/*'))]
    good = []
    for f in fs:
        w, h = Image.open(f).size
        if w >= 700 and h >= 380: good.append((w * h, f))
    good.sort(key=lambda x: (-x[0], x[1].name))
    return [f for _, f in good] or [f for f in fs]

# ---------------------------------------------------------------- drawing helpers
def font(size, kind='m', weight=750):
    if kind == 'o': return ImageFont.truetype(str(OSWALD), size)
    f = ImageFont.truetype(str(MANROPE), size)
    f.set_variation_by_axes([weight]); return f

def wrap(text, f, width):
    out = []
    for para in text.split('\n'):
        line = ''
        for w in para.split():
            s = (line + ' ' + w).strip()
            if f.getlength(s) > width and line: out.append(line); line = w
            else: line = s
        out.append(line)
    return '\n'.join(out)

def fit(d, text, box, kind='m', weight=800, maxs=140, mins=22, spacing=0.12, upper=False):
    """Largest font so wrapped text fits box=(x,y,w,h). Returns (font, wrapped, size)."""
    x, y, w, h = box
    t = text.upper() if upper else text
    for s in range(maxs, mins - 1, -2):
        f = font(s, kind, weight); wt = wrap(t, f, w)
        bb = d.multiline_textbbox((0, 0), wt, font=f, spacing=int(s * spacing))
        if bb[2] - bb[0] <= w and bb[3] - bb[1] <= h: return f, wt, s
    f = font(mins, kind, weight); return f, wrap(t, f, w), mins

def text(d, text_, box, fill, kind='m', weight=800, maxs=140, mins=22, upper=False, align='left', valign='top', spacing=0.12):
    f, wt, s = fit(d, text_, box, kind, weight, maxs, mins, spacing, upper)
    x, y, w, h = box
    bb = d.multiline_textbbox((0, 0), wt, font=f, spacing=int(s * spacing))
    th = bb[3] - bb[1]
    if valign == 'middle': y = y + (h - th) // 2
    elif valign == 'bottom': y = y + h - th
    if align == 'center':
        d.multiline_text((x + w // 2, y - bb[1]), wt, font=f, fill=fill, spacing=int(s * spacing), anchor='ma', align='center')
    else:
        d.multiline_text((x, y - bb[1]), wt, font=f, fill=fill, spacing=int(s * spacing))
    return y + th

def shot_fit(path, size, centering=(0.5, 0.35)):
    return ImageOps.fit(Image.open(path).convert('RGB'), size, Image.Resampling.LANCZOS, centering=centering)

def shot_contain(path, size):
    im = Image.open(path).convert('RGB'); im.thumbnail(size, Image.Resampling.LANCZOS); return im

def card(im, radius=18, border=0, border_color=WHITE, shadow=True):
    w, h = im.size; pad = 40 if shadow else 0
    out = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    if shadow:
        sh = Image.new('RGBA', out.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 10, pad + w, pad + h + 10), radius, fill=(0, 0, 0, 110))
        out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(16)))
    mask = Image.new('L', (w, h), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius, fill=255)
    layer = Image.new('RGBA', out.size, (0, 0, 0, 0)); layer.paste(im.convert('RGB'), (pad, pad), mask)
    out = Image.alpha_composite(out, layer)
    if border: ImageDraw.Draw(out).rounded_rectangle((pad, pad, pad + w - 1, pad + h - 1), radius, outline=border_color, width=border)
    return out, pad

def paste_card(bg, im, xy, **kw):
    c, pad = card(im, **kw); bg.paste(c, (xy[0] - pad, xy[1] - pad), c)

def logo(bg, xy, h=56, dark=False):
    lg = Image.open(LOGO).convert('RGBA'); r = h / lg.height
    lg = lg.resize((int(lg.width * r), h), Image.Resampling.LANCZOS)
    if dark:
        plate = Image.new('RGBA', (lg.width + 24, h + 16), BEIGE); plate.paste(lg, (12, 8), lg); lg = plate
    bg.paste(lg, xy, lg)

def badge(d, xy, label, fill, color, size=30, kind='m'):
    f = font(size, kind, 800); w = f.getlength(label)
    d.rounded_rectangle((xy[0], xy[1], xy[0] + w + 36, xy[1] + size + 22), 10, fill=fill)
    d.text((xy[0] + 18, xy[1] + 9), label, font=f, fill=color)

def save(im, path, maxkb=1900):
    im = im.convert('RGB'); path.parent.mkdir(parents=True, exist_ok=True)
    for q in (92, 88, 84, 80, 75):
        im.save(path, 'JPEG', quality=q, optimize=True)
        if path.stat().st_size < maxkb * 1024: break

# ---------------------------------------------------------------- covers, one design per platform
def yt_thumb(variant, t, sh, n, path):
    W, H = 1280, 720
    if variant == 0:      # split: ink panel left, screenshot right
        bg = Image.new('RGB', (W, H), INK); d = ImageDraw.Draw(bg)
        bg.paste(shot_fit(sh, (640, H)), (640, 0))
        d.rectangle((600, 0, 640, H), fill=YEL)
        text(d, t, (56, 120, 520, 470), WHITE, 'o', maxs=118, upper=True, valign='middle', spacing=0.05)
        badge(d, (56, 40), f'УРОК {n}', YEL, INK, 28)
        logo(bg, (56, 630), 50, dark=True)
    elif variant == 1:    # full-bleed screenshot, dark gradient, yellow headline bottom
        bg = shot_fit(sh, (W, H), (0.5, 0.25)).convert('RGBA')
        grad = Image.new('L', (1, H)); [grad.putpixel((0, y), int(235 * max(0, (y - 200) / (H - 200)) ** 0.8)) for y in range(H)]
        dark = Image.new('RGBA', (W, H), INK); dark.putalpha(grad.resize((W, H)))
        bg = Image.alpha_composite(bg, dark).convert('RGB'); d = ImageDraw.Draw(bg)
        text(d, t, (56, 390, 1100, 290), YEL, 'o', maxs=120, upper=True, valign='bottom', spacing=0.04)
        d.rectangle((0, 0, 18, H), fill=RED)
        badge(d, (1080, 36), f'#{n}', RED, WHITE, 34, 'o')
    else:                 # beige, tilted screenshot card, ink question
        bg = Image.new('RGB', (W, H), BEIGE); d = ImageDraw.Draw(bg)
        im = shot_contain(sh, (560, 560)); c, pad = card(im, border=8)
        c = c.rotate(-5, expand=True, resample=Image.Resampling.BICUBIC)
        bg.paste(c, (W - c.width + 30, (H - c.height) // 2), c)
        y = text(d, t, (60, 80, 620, 520), INK, 'm', 850, maxs=96, valign='middle')
        d.rectangle((60, y + 26, 300, y + 40), fill=RED)
        logo(bg, (60, 40), 46)
    save(bg, path)

def wide_cover(platform, variant, t, sh, sh2, n, path):
    W, H = 1920, 1080
    bg = Image.new('RGB', (W, H), BEIGE); d = ImageDraw.Draw(bg)
    if platform == 'vk' and variant == 0:     # screenshot top, red band bottom
        bg.paste(shot_fit(sh, (W, 760), (0.5, 0.2)), (0, 0))
        d.rectangle((0, 760, W, H), fill=RED)
        text(d, t, (80, 790, 1500, 260), WHITE, 'm', 850, maxs=104, valign='middle')
        badge(d, (1640, 840), f'Урок {n}', WHITE, RED, 40)
    elif platform == 'vk':                    # ink, centered card, yellow caps above
        d.rectangle((0, 0, W, H), fill=INK)
        text(d, t, (120, 60, 1680, 300), YEL, 'o', maxs=150, upper=True, align='center', valign='middle', spacing=0.04)
        im = shot_contain(sh, (1200, 640)); paste_card(bg, im, ((W - im.width) // 2, 400), border=6)
        logo(bg, (60, H - 100), 60, dark=True)
    elif variant == 0:                        # rutube: yellow column left
        d.rectangle((0, 0, 700, H), fill=YEL)
        bg.paste(shot_fit(sh, (W - 700, H), (0.5, 0.3)), (700, 0))
        text(d, t, (70, 200, 560, 700), INK, 'o', maxs=150, upper=True, valign='middle', spacing=0.04)
        d.text((70, 90), f'УРОК {n:02}', font=font(54, 'o'), fill=RED)
    else:                                      # rutube: beige, two overlapping screenshots
        text(d, t, (90, 80, 860, 900), INK, 'm', 850, maxs=130, valign='middle')
        a = shot_contain(sh, (900, 620)); b = shot_contain(sh2, (760, 520))
        paste_card(bg, a, (960, 110), border=6); paste_card(bg, b, (1060, 1080 - b.height - 90), border=10, border_color=RED)
        logo(bg, (90, 960), 60)
    save(bg, path)

def tall_cover(platform, t, sh, n, path):
    W, H = 1080, 1920
    if platform == 'shorts':
        bg = Image.new('RGB', (W, H), INK); d = ImageDraw.Draw(bg)
        text(d, t, (80, 260, 920, 560), YEL, 'o', maxs=170, upper=True, align='center', valign='middle', spacing=0.03)
        im = shot_contain(sh, (900, 820)); paste_card(bg, im, ((W - im.width) // 2, 900), border=6)
    elif platform == 'vk_clip':
        bg = Image.new('RGB', (W, H), RED); d = ImageDraw.Draw(bg)
        im = shot_contain(sh, (940, 760)); paste_card(bg, im, ((W - im.width) // 2, 200), border=8)
        text(d, t, (80, 1080, 920, 560), WHITE, 'm', 850, maxs=130, align='center', valign='middle')
    else:  # reel: all content inside centre 3:4 window (y 240..1680) for the profile grid
        bg = Image.new('RGB', (W, H), BEIGE); d = ImageDraw.Draw(bg)
        d.rectangle((0, 0, W, 240), fill=INK); d.rectangle((0, 1680, W, H), fill=INK)
        text(d, t, (70, 300, 940, 520), INK, 'm', 850, maxs=120, valign='middle')
        d.rectangle((70, 840, 330, 854), fill=RED)
        im = shot_fit(sh, (940, 720), (0.5, 0.3)); paste_card(bg, im, (70, 900), radius=24)
    save(bg, path)

def carousel(slides, shots_, n, outdir):
    W, H = 1080, 1350; files = []
    for i, s in enumerate(slides, 1):
        if i == 1:
            bg = Image.new('RGB', (W, H), INK); d = ImageDraw.Draw(bg)
            text(d, s['title'], (80, 160, 920, 640), YEL, 'm', 850, maxs=120, valign='middle')
            if s.get('body'): text(d, s['body'], (80, 860, 920, 260), WHITE, 'm', 600, maxs=46)
            d.text((80, 1220), 'листайте →', font=font(36, 'm', 700), fill=GREY)
            logo(bg, (80, 60), 50, dark=True)
        elif i == len(slides):
            bg = Image.new('RGB', (W, H), RED); d = ImageDraw.Draw(bg)
            d.text((80, 90), 'ЗАДАНИЕ', font=font(64, 'o'), fill=YEL)
            y = text(d, s['title'], (80, 220, 920, 420), WHITE, 'm', 850, maxs=84)
            if s.get('body'): text(d, s['body'], (80, y + 60, 920, H - y - 220), WHITE, 'm', 600, maxs=46)
            d.text((80, 1230), 'Сохраните, чтобы вернуться', font=font(34, 'm', 700), fill=WHITE)
        else:
            bg = Image.new('RGB', (W, H), BEIGE); d = ImageDraw.Draw(bg)
            d.text((80, 70), f'{i - 1:02}', font=font(110, 'o'), fill=RED)
            y = text(d, s['title'], (80, 230, 920, 230), INK, 'm', 850, maxs=72)
            sh = shots_[(i - 2) % len(shots_)] if s.get('shot', True) and shots_ else None
            body_h = 330 if sh else 900
            if s.get('body'): y = text(d, s['body'], (80, y + 30, 920, body_h), INK, 'm', 560, maxs=44)
            if sh:
                im = shot_fit(sh, (920, max(300, H - y - 120)), (0.5, 0.3))
                paste_card(bg, im, (80, y + 50), radius=20)
            d.text((W - 160, H - 70), f'{i}/{len(slides)}', font=font(30, 'm', 700), fill=GREY)
        p = outdir / f'Карусель_{i:02}.jpg'; save(bg, p); files.append(p)
    return files

def threads_card(t, sh, path):
    W, H = 1080, 1350
    bg = Image.new('RGB', (W, H), WHITE); d = ImageDraw.Draw(bg)
    d.rectangle((70, 90, 84, 520), fill=RED)
    text(d, t, (120, 90, 880, 560), INK, 'm', 800, maxs=96, valign='top')
    im = shot_fit(sh, (940, 620), (0.5, 0.3)); paste_card(bg, im, (70, 660), radius=16, border=2, border_color='#d9d6cf', shadow=False)
    save(bg, path)

def pin_image(variant, pin, sh, n, path):
    W, H = 1000, 1500
    if variant == 0:     # photo/screen top, headline block bottom
        bg = Image.new('RGB', (W, H), BEIGE); d = ImageDraw.Draw(bg)
        src = Image.open(sh)
        if src.width / src.height > 1.3:   # wide screen: keep it whole as a card
            d.rectangle((0, 0, W, 900), fill=INK)
            im = shot_contain(sh, (900, 800)); paste_card(bg, im, ((W - im.width) // 2, (900 - im.height) // 2), border=6)
        else:
            bg.paste(shot_fit(sh, (W, 900), (0.5, 0.3)), (0, 0))
        d.rectangle((0, 900, W, 912), fill=RED)
        text(d, pin['overlay'], (60, 960, 880, 380), INK, 'm', 850, maxs=96, valign='middle')
        logo(bg, (60, 1400), 50)
    else:                # checklist infographic
        bg = Image.new('RGB', (W, H), INK); d = ImageDraw.Draw(bg)
        y = text(d, pin['overlay'], (60, 80, 880, 380), YEL, 'm', 850, maxs=92)
        y += 50
        pts = pin.get('points', [])
        for k, pt in enumerate(pts, 1):
            d.ellipse((60, y + 4, 122, y + 66), fill=RED); d.text((91, y + 35), str(k), font=font(38, 'm', 850), fill=WHITE, anchor='mm')
            y = text(d, pt, (150, y, 790, 230), WHITE, 'm', 650, maxs=46, mins=26) + 44
        if y < 1100 and sh:
            im = shot_fit(sh, (880, min(420, 1380 - y)), (0.5, 0.3)); paste_card(bg, im, (60, y + 10), radius=16, shadow=False)
        logo(bg, (60, 1410), 50, dark=True)
    save(bg, path)

def hook_png(platform, t, path):
    """Full-frame transparent overlay shown during the first seconds of a short."""
    W, H = 1080, 1920
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    style = {'reel': (BEIGE, INK, RED), 'shorts': (INK, YEL, YEL), 'vk_clip': (RED, WHITE, WHITE), 'video_pin': (YEL, INK, INK), 'rshorts': (INK, YEL, YEL)}[platform]
    box = (60, 560, 960, 520)
    d.rounded_rectangle((box[0], box[1], box[0] + box[2], box[1] + box[3]), 34, fill=style[0])
    d.rectangle((box[0] + 50, box[1] + 50, box[0] + 200, box[1] + 62), fill=style[2])
    text(d, t, (box[0] + 50, box[1] + 100, box[2] - 100, box[3] - 150), style[1], 'm', 850, maxs=96, valign='middle')
    path.parent.mkdir(parents=True, exist_ok=True); im.save(path)

# ---------------------------------------------------------------- video cuts
def cut_video(src, hook, layout, dst):
    """Re-layout a 1080x1920 lesson clip (slide 0..1468, captions band 1468..1920)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if layout == 'safe916':   # slide raised, captions above the bottom UI zone
        filt = ('color=c=0x161920:s=1080x1920:r=30[bg];'
                '[0:v]split[a][b];[a]crop=1080:1468:0:0,scale=820:1114[s];'
                '[b]crop=1080:236:0:1546[c];'
                '[bg][s]overlay=80:150:shortest=1[t1];[t1][c]overlay=0:1280[t2];'
                "[t2][1:v]overlay=0:0:enable='lt(t,2.6)'[v]")
        size = None
    else:                     # pin23: 1000x1500 for Pinterest video pins
        filt = ('color=c=0x161920:s=1000x1500:r=30[bg];'
                '[0:v]split[a][b];[a]crop=1080:1468:0:0,scale=880:1196[s];'
                '[b]crop=1080:236:0:1546,scale=1000:218[c];'
                '[bg][s]overlay=60:40:shortest=1[t1];[t1][c]overlay=0:1250[t2];'
                "[1:v]scale=1000:-2,crop=1000:1500:0:200[h];[t2][h]overlay=0:0:enable='lt(t,2.6)'[v]")
    cmd = ['nice', '-n', '15', 'ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(src), '-loop', '1', '-framerate', '30', '-i', str(hook),
           '-filter_complex', filt, '-map', '[v]', '-map', '0:a:0', '-shortest', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(dst)]
    subprocess.run(cmd, check=True)

def render_wide(src, n, title, dst):
    """1920x1080 long-form cut: slide left at full height, captions and lesson title right."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    bg = Image.new('RGB', (1920, 1080), DARK); d = ImageDraw.Draw(bg)
    d.rectangle((815, 0, 823, 1080), fill=YEL)
    d.text((900, 90), f'УРОК {n}', font=font(64, 'o'), fill=YEL)
    text(d, title, (900, 190, 940, 260), WHITE, 'm', 800, maxs=72)
    d.rectangle((900, 880, 1100, 890), fill=RED)
    logo(bg, (900, 940), 64, dark=True)
    plate = dst.with_suffix('.png'); bg.save(plate)
    filt = ('[1:v]format=yuv420p[bg];[0:v]split[a][b];[a]crop=1080:1468:0:0,scale=794:1080[s];'
            '[b]crop=1080:236:0:1546,scale=1000:218[c];[bg][s]overlay=10:0:shortest=1[t];[t][c]overlay=870:520[v]')
    cmd = ['nice', '-n', '15', 'ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(src), '-loop', '1', '-framerate', '30', '-i', str(plate),
           '-filter_complex', filt, '-map', '[v]', '-map', '0:a:0', '-shortest', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(dst)]
    subprocess.run(cmd, check=True)

# ---------------------------------------------------------------- markdown
def hashtags(tags): return ' '.join('#' + t.lstrip('#') for t in tags)

RULES = '../../ПРАВИЛА_ПЛОЩАДОК.txt'

def block(title, text):
    return [f'**{title}**', '', '```', text.strip(), '```', '']

def head(L, platform, anchor):
    return [f"# {platform} · урок {L['n']}: {L.get('title', L['slug'].replace('_', ' '))}", '',
            f'Порядок загрузки и требования — в файле ПРАВИЛА_ПЛОЩАДОК.txt (папка КУРС_PINTEREST), раздел «{platform}». Ниже — только то, что копируется в поля площадки.', '']

def chapter_block(L, labels):
    import pub_chapters
    times = L.get('_chapter_times') or L.get('chapter_times')
    if times is None:
        ch = pub_chapters.chapters(L['n']); times = [t for t, _ in ch] if ch else []
        L['_chapter_times'] = times
    if not labels or len(times) < len(labels): return ''
    fmt = lambda t: f"{int(t)//60}:{int(t)%60:02d}"
    return '\n'.join(f"{fmt(times[i])} {lab}" for i, lab in enumerate(labels))

def md_youtube(L, y):
    o = head(L, 'YouTube', 'youtube') + ['## Длинное видео · `Видео_16x9.mp4`', '', '| Вариант | Название | Обложка 1280×720 |', '|---|---|---|']
    for i, t in enumerate(y['titles']): o.append(f"| {'ABC'[i]} | {t} | `Обложка_{'ABC'[i]}.jpg` |")
    o += [''] + block('Описание', y['description'].strip() + ('\n\nГлавы:\n' + chapter_block(L, y.get('chapters')) if y.get('chapters') else '') + '\n\n' + hashtags(y['hashtags'])) + block(f"Теги ({len(', '.join(y['tags']))}/500)", ', '.join(y['tags'])) + (block('Закреплённый комментарий — задание к уроку', L['task']['youtube']) + block('Второй комментарий — вопрос зрителям', y['comment']) if L.get('task') else block('Закреплённый комментарий', y['comment']))
    for i, s in enumerate(y['shorts'], 1):
        o += [f'## Shorts {i} · `Shorts_{i}.mp4` · обложка `Shorts_{i}_обложка.jpg`', ''] + block('Название', s['title']) + block('Описание', s['description'] + '\n' + hashtags(s['hashtags']))
    return '\n'.join(o)

def md_vk_video(L, v):
    o = head(L, 'VK Видео', 'vk-видео') + ['## Видео · `Видео_16x9.mp4`', '', '| Вариант | Название | Обложка 1920×1080 |', '|---|---|---|']
    for i, t in enumerate(v['titles']): o.append(f"| {'AB'[i]} | {t} | `Обложка_{'AB'[i]}.jpg` |")
    o += [''] + block('Описание', v['description'].strip() + ('\n\nТаймкоды:\n' + chapter_block(L, v.get('chapters')) if v.get('chapters') else '') + '\n\n' + hashtags(v['hashtags'])) + block('Пост в сообществе', v['post']) + (block('Комментарий под видео — задание к уроку (закрепить)', L['task']['vk_video']) if L.get('task') else [])
    return '\n'.join(o)

def md_vk_clips(L, cl):
    o = head(L, 'VK Клипы', 'vk-клипы')
    for i, c in enumerate(cl, 1):
        body = c['description'].strip() + '\n' + hashtags(c['hashtags'])
        o += [f'## Клип {i} · `Клип_{i}.mp4` · обложка `Клип_{i}_обложка.jpg`', ''] + block(f'Описание ({len(body)}/200)', body)
    return '\n'.join(o)

def md_rutube(L, r):
    o = head(L, 'Rutube', 'rutube') + ['## Видео · `Видео_16x9.mp4`', '', '| Вариант | Название | Обложка 1920×1080 |', '|---|---|---|']
    for i, t in enumerate(r['titles']): o.append(f"| {'AB'[i]} | {t} | `Обложка_{'AB'[i]}.jpg` |")
    o += [''] + block('Описание', r['description'].strip() + ('\n\nТайм-коды:\n' + chapter_block(L, r.get('chapters')) if r.get('chapters') else '')) + block('Теги', ', '.join(r['tags'])) + (block('Комментарий под видео — задание к уроку (закрепить)', L['task']['rutube']) if L.get('task') else [])
    return '\n'.join(o)

def md_instagram(L, ig):
    o = head(L, 'Instagram', 'instagram')
    for i, r in enumerate(ig['reels'], 1):
        o += [f'## Reels {i} · `Reels_{i}.mp4` · обложка `Reels_{i}_обложка.jpg`', ''] + block('Подпись', r['caption'] + '\n' + hashtags(r['hashtags'])) + block('Подпись для пробного показа (вариант Б)', r['trial_caption'])
    c = ig['carousel']
    o += [f"## Карусель · `Карусель_01.jpg` … `Карусель_{len(c['slides']):02}.jpg`", ''] + block('Подпись', c['caption'] + '\n' + hashtags(c['hashtags'])) + (sum((block(f'Альтернативный текст слайда {i}', a) for i, a in enumerate(c['alts'], 1)), []) if c.get('alts') else block('Альтернативный текст первого слайда', c['alt'])) + (block('Первый комментарий под каруселью — задание к уроку (закрепить)', L['task']['instagram']) if L.get('task') else [])
    return '\n'.join(o)

def md_threads(L, t):
    o = head(L, 'Threads', 'threads') + [f"Тема поста: **{t['topic']}**. Картинка к первому посту: `Карточка.jpg`.", '']
    for i, p in enumerate(t['posts'], 1): o += block(f'Пост {i} ({len(p.strip())}/500)', p)
    if L.get('task'): o += block(f"Пост {len(t['posts']) + 1} — задание к уроку ({len(L['task']['threads'].strip())}/500)", L['task']['threads'])
    return '\n'.join(o)

def md_pinterest(L, p):
    o = head(L, 'Pinterest', 'pinterest')
    for i, pin in enumerate(p['pins']):
        o += [f"## Пин {'AB'[i]} · `Пин_{'AB'[i]}.jpg` · доска «{pin['board']}»", ''] + block(f"Название ({len(pin['title'])}/100)", pin['title']) + block(f"Описание ({len((pin['description'].strip() + ' ' + hashtags(pin.get('hashtags', []))).strip())}/500)", (pin['description'].strip() + '\n' + hashtags(pin.get('hashtags', []))).strip()) + block('Альтернативный текст', pin['alt'])
    v = p['video_pin']
    o += [f"## Видеопин · `Видеопин.mp4` · доска «{v['board']}»", ''] + block('Название', v['title']) + block('Описание', (v['description'].strip() + '\n' + hashtags(v.get('hashtags', []))).strip())
    return '\n'.join(o)


def H(L, platform, creative, note=''):
    return [f"# {platform} · урок {L['n']} · {creative}", '',
            f"Этот файл — только для {creative}. {note}Требования площадки — ПРАВИЛА_ПЛОЩАДОК.txt (папка КУРС_PINTEREST), раздел «{platform}».".replace('  ', ' '), '']

def lesson_tags(L):
    """Curated keyword phrases of the lesson (built from real search suggestions), no duplicates."""
    out = []
    for t in L['youtube']['tags'] + L['rutube']['tags']:
        if t.lower() not in [x.lower() for x in out]: out.append(t)
    return out

def pick_tags(L, text, k=6, used=None):
    """Lesson keyword phrases ranked by overlap with this creative's own text; avoids the set already used."""
    stem = lambda w: KWN.get(w, w)[:5]
    tw = {stem(w) for w in words(text)}
    pool = lesson_tags(L)
    sc = sorted(pool, key=lambda t: (-len({stem(w) for w in words(t)} & tw), pool.index(t)))
    out = sc[:k]
    if used is not None:
        key = tuple(sorted(out))
        while key in used and len(sc) > k:
            sc = sc[1:] + sc[:1]; out = sc[:k]; key = tuple(sorted(out))
        used.add(key)
    return out

NOFIELD = 'отдельного поля нет — ключевые слова уже стоят в названии и описании; список для контроля'

def kit(title, desc, tags, tags_note, hts, ht_note, extra=()):
    """Standard creative block: title, description, tags, hashtags (+ extras)."""
    o = block(f'Название (символов: {len(title)})', title) if title else block('Название', 'у этого формата отдельного поля названия нет')
    o += block(f'Описание (символов без хэштегов: {len(desc.strip())})', desc)
    o += block(f'Теги / ключевые слова{" — " + tags_note if tags_note else ""}', ', '.join(tags))
    o += block(f'Хэштеги ({len(hts)} шт.) — {ht_note}', hashtags(hts)) if hts else block('Хэштеги', ht_note)
    for t_, x_ in extra: o += block(t_, x_)
    return o

def creatives(L):
    """{platform_dir: {txt_name: markdown}} — one complete text file per creative, named after it."""
    y, v, r, ig, t, p = L['youtube'], L['vk_video'], L['rutube'], L['instagram'], L['threads'], L['pinterest']
    tk = L.get('task') or {}; TG = lesson_tags(L); U = set()
    END = 'вставить в конец описания'
    o = {k: {} for k in ['YouTube', 'VK_Видео', 'VK_Клипы', 'Rutube', 'Instagram', 'Threads', 'Pinterest']}
    def ab(m, titles, size, letters):
        m += ['## A/B-тест: название и обложка', '', f'| Вариант | Название | Обложка {size} |', '|---|---|---|']
        for i, tt in enumerate(titles): m.append(f"| {letters[i]} | {tt} | Обложка_{letters[i]}.jpg |")
        return m + ['', 'Ниже — вариант A; B/C подставляются вместо названия при тесте.', '']
    # YouTube long
    m = ab(H(L, 'YouTube', 'Видео_16x9.mp4'), y['titles'], '1280×720', 'ABC')
    m += kit(y['titles'][0], y['description'].strip() + ('\n\nГлавы:\n' + chapter_block(L, y.get('chapters')) if y.get('chapters') else ''),
             y['tags'], f"поле «Теги» ({len(', '.join(y['tags']))}/500)", y['hashtags'], END,
             [('Субтитры', 'загрузить Субтитры.srt из этой папки')] + ([('Закреплённый комментарий — задание к уроку', tk['youtube']), ('Второй комментарий — вопрос зрителям', y['comment'])] if tk else [('Закреплённый комментарий', y['comment'])]))
    o['YouTube']['Видео_16x9.txt'] = '\n'.join(m)
    for i, s in enumerate(y['shorts'], 1):
        tg = pick_tags(L, s['title'] + ' ' + s['description'], 6, U)
        o['YouTube'][f'Shorts_{i}.txt'] = '\n'.join(H(L, 'YouTube', f'Shorts_{i}.mp4', f'Обложка — Shorts_{i}_обложка.jpg. ') + kit(s['title'], s['description'].strip(), tg, 'поле «Теги»', s['hashtags'], END))
    # VK Video
    m = ab(H(L, 'VK Видео', 'Видео_16x9.mp4'), v['titles'], '1920×1080', 'AB')
    m += kit(v['titles'][0], v['description'].strip() + ('\n\nТаймкоды:\n' + chapter_block(L, v.get('chapters')) if v.get('chapters') else ''),
             pick_tags(L, v['titles'][0] + ' ' + v['description'], 10, U), NOFIELD, v['hashtags'], END,
             [('Субтитры', 'загрузить Субтитры.srt из этой папки'), ('Пост в сообществе с этим видео', v['post'])] + ([('Комментарий под видео — задание к уроку (закрепить)', tk['vk_video'])] if tk else []))
    o['VK_Видео']['Видео_16x9.txt'] = '\n'.join(m)
    for i, c in enumerate(L['vk_clips'], 1):
        full = c['description'].strip() + ' ' + hashtags(c['hashtags'])
        o['VK_Клипы'][f'Клип_{i}.txt'] = '\n'.join(H(L, 'VK Клипы', f'Клип_{i}.mp4', f'Обложка — Клип_{i}_обложка.jpg. ') + kit('', c['description'].strip(), pick_tags(L, c['description'], 5, U), NOFIELD, c['hashtags'], f'{END}; вместе с описанием {len(full)}/200'))
    # Rutube
    m = ab(H(L, 'Rutube', 'Видео_16x9.mp4'), r['titles'], '1920×1080', 'AB')
    m += kit(r['titles'][0], r['description'].strip() + ('\n\nТайм-коды:\n' + chapter_block(L, r.get('chapters')) if r.get('chapters') else ''),
             r['tags'], 'поле «Теги»', [], 'Rutube хэштеги для поиска не использует — не нужны',
             [('Субтитры', 'загрузить Субтитры.srt из этой папки')] + ([('Комментарий под видео — задание к уроку (закрепить)', tk['rutube'])] if tk else []))
    o['Rutube']['Видео_16x9.txt'] = '\n'.join(m)
    for i, s in enumerate(L['rutube_shorts'], 1):
        o['Rutube'][f'Shorts_{i}.txt'] = '\n'.join(H(L, 'Rutube', f'Shorts_{i}.mp4', f'Обложка — Shorts_{i}_обложка.jpg. По справке Rutube вертикальное видео от 2 секунд до 3 минут попадает в Shorts. ') + kit(s['title'], s['description'], pick_tags(L, s['title'] + ' ' + s['description'], 6, U), 'поле «Теги»', [], 'не нужны: по справке Rutube хэштег #Shorts для попадания в раздел Shorts не требуется'))
    # Instagram
    for i, rr in enumerate(ig['reels'], 1):
        o['Instagram'][f'Reels_{i}.txt'] = '\n'.join(H(L, 'Instagram', f'Reels_{i}.mp4', f'Обложка — Reels_{i}_обложка.jpg. ') + kit('', rr['caption'].strip(), pick_tags(L, rr['caption'], 6, U), NOFIELD, rr['hashtags'], f'{END} (не больше 5)', [('Подпись для пробного показа (вариант Б)', rr['trial_caption'])]))
    c = ig['carousel']; ns = len(c['slides'])
    alts = [(f'Альтернативный текст · Карусель_{i:02}.jpg', a) for i, a in enumerate(c['alts'], 1)] if c.get('alts') else [('Альтернативный текст · Карусель_01.jpg', c['alt'])]
    o['Instagram']['Карусель.txt'] = '\n'.join(H(L, 'Instagram', f'карусели Карусель_01.jpg … Карусель_{ns:02}.jpg', 'Все слайды — один пост. ') + kit('', c['caption'].strip(), pick_tags(L, c['caption'], 6, U), NOFIELD, c['hashtags'], f'{END} (не больше 5)', alts + ([('Первый комментарий — задание к уроку (закрепить)', tk['instagram'])] if tk else [])))
    # Threads
    posts = [(f"{'Описание — пост 1 · прикрепить Карточка.jpg' if i == 1 else f'Пост {i} · ответом в ветке'} ({len(pp.strip())}/500)", pp) for i, pp in enumerate(t['posts'], 1)]
    if tk: posts.append((f"Пост {len(t['posts']) + 1} — задание к уроку, ответом в ветке ({len(tk['threads'].strip())}/500)", tk['threads']))
    o['Threads']['Карточка.txt'] = '\n'.join(H(L, 'Threads', 'Карточка.jpg и ветки постов') + block('Название', 'у Threads поля названия нет') + block('Тема (одна, выбирается в поле «Добавить тему»)', t['topic']) + block('Теги / ключевые слова — ' + NOFIELD, ', '.join(pick_tags(L, ' '.join(t['posts']), 6, U))) + block('Хэштеги', 'не нужны: Threads вместо хэштегов использует одну тему поста') + sum((block(a_, b_) for a_, b_ in posts), []))
    # Pinterest
    PT = 'поле «Отмеченные темы»: вводите по слову и выбирайте совпадающие варианты из подсказок Pinterest'
    for i, pin in enumerate(p['pins']):
        k = 'AB'[i]; full = (pin['description'].strip() + ' ' + hashtags(pin.get('hashtags', []))).strip()
        o['Pinterest'][f'Пин_{k}.txt'] = '\n'.join(H(L, 'Pinterest', f'Пин_{k}.jpg') + kit(pin['title'], pin['description'].strip(), pick_tags(L, pin['title'] + ' ' + pin['description'], 5, U), PT, pin.get('hashtags', []), f'{END}; вместе с описанием {len(full)}/500', [('Доска', pin['board']), (f"Альтернативный текст ({len(pin['alt'])}/500)", pin['alt']), ('Ссылка', 'не указывать, пока нет проверенной страницы урока')]))
    vp = p['video_pin']; full = (vp['description'].strip() + ' ' + hashtags(vp.get('hashtags', []))).strip()
    o['Pinterest']['Видеопин.txt'] = '\n'.join(H(L, 'Pinterest', 'Видеопин.mp4', 'Обложку выбрать из кадров при загрузке. ') + kit(vp['title'], vp['description'].strip(), pick_tags(L, vp['title'] + ' ' + vp['description'], 5, U), PT, vp.get('hashtags', []), f'{END}; вместе с описанием {len(full)}/500', [('Доска', vp['board']), ('Ссылка', 'не указывать, пока нет проверенной страницы урока')]))
    return o


def to_txt(md):
    """Plain-text rendering for people: no markup, opens in any editor."""
    out = []; in_block = False
    for line in md.split('\n'):
        if line.strip() == '```':
            in_block = not in_block
            if in_block: continue
            out.append(''); continue
        if in_block: out.append(line); continue
        line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line).replace('`', '')
        line = line.replace('ПРАВИЛА_ПЛОЩАДОК.md', 'ПРАВИЛА_ПЛОЩАДОК.txt').replace('Проверка_уникальности.md', 'Проверка_уникальности.txt')
        if line.startswith('# '):
            t = line[2:].upper(); out += [t, '=' * len(t)]
        elif line.startswith('## '):
            t = line[3:]; out += ['', t, '-' * len(t)]
        elif re.match(r'^\*\*(.+)\*\*$', line):
            out.append(re.sub(r'^\*\*(.+)\*\*$', r'\1:', line))
        elif line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if all(set(c) <= set('-: ') for c in cells): continue
            out.append('   '.join(cells).replace('**', ''))
        else:
            out.append(line.replace('**', ''))
    txt = '\n'.join(out)
    txt = re.sub(r'\n{3,}', '\n\n', txt).strip() + '\n'
    return txt.replace('\n', '\r\n')   # Windows Notepad friendly, fine everywhere

# ---------------------------------------------------------------- uniqueness
def units(L):
    """Every human-readable text unit: (where, text). Hashtags/tags/boards excluded."""
    n = L['n']; u = []
    y = L['youtube']
    for i, t in enumerate(y['titles']): u.append((f'{n}/YouTube/название {"ABC"[i]}', t))
    for i, t in enumerate(y['thumbs']): u.append((f'{n}/YouTube/обложка {"ABC"[i]}', t))
    u += [(f'{n}/YouTube/описание', y['description']), (f'{n}/YouTube/комментарий', y['comment'])]
    for plat, blk in [('YouTube', y), ('VK Видео', L['vk_video']), ('Rutube', L['rutube'])]:
        for i, lab in enumerate(blk.get('chapters') or [], 1): u.append((f'{n}/{plat}/глава {i}', lab))
    for i, a in enumerate(L['instagram']['carousel'].get('alts') or [], 1):
        if i > 1: u.append((f'{n}/Карусель/alt слайда {i}', a))
    for i, s in enumerate(y['shorts'], 1):
        u += [(f'{n}/Shorts {i}/название', s['title']), (f'{n}/Shorts {i}/описание', s['description']), (f'{n}/Shorts {i}/зацепка', s['hook']), (f'{n}/Shorts {i}/обложка', s['cover'])]
    v = L['vk_video']
    for i, t in enumerate(v['titles']): u.append((f'{n}/VK Видео/название {"AB"[i]}', t))
    for i, t in enumerate(v['covers']): u.append((f'{n}/VK Видео/обложка {"AB"[i]}', t))
    u += [(f'{n}/VK Видео/описание', v['description']), (f'{n}/VK Видео/пост', v['post'])]
    for i, c in enumerate(L['vk_clips'], 1):
        u += [(f'{n}/VK Клип {i}/описание', c['description']), (f'{n}/VK Клип {i}/зацепка', c['hook']), (f'{n}/VK Клип {i}/обложка', c['cover'])]
    r = L['rutube']
    for i, t in enumerate(r['titles']): u.append((f'{n}/Rutube/название {"AB"[i]}', t))
    for i, t in enumerate(r['covers']): u.append((f'{n}/Rutube/обложка {"AB"[i]}', t))
    u.append((f'{n}/Rutube/описание', r['description']))
    for i, s in enumerate(L.get('rutube_shorts', []), 1): u += [(f'{n}/Rutube Shorts {i}/название', s['title']), (f'{n}/Rutube Shorts {i}/описание', s['description'])]
    for i, g in enumerate(L.get('goals', []), 1): u.append((f'{n}/Цели/{i}', g))
    for i, it in enumerate(L.get('quiz', []), 1): u.append((f'{n}/Тест/{i}', it['q'] + ' ' + ' '.join(it['options']) + ' ' + it['why']))
    ig = L['instagram']
    for i, rr in enumerate(ig['reels'], 1):
        u += [(f'{n}/Reels {i}/подпись', rr['caption']), (f'{n}/Reels {i}/пробная подпись', rr['trial_caption']), (f'{n}/Reels {i}/зацепка', rr['hook']), (f'{n}/Reels {i}/обложка', rr['cover'])]
    c = ig['carousel']
    u += [(f'{n}/Карусель/подпись', c['caption']), (f'{n}/Карусель/alt', c['alt'])]
    for i, s in enumerate(c['slides'], 1): u.append((f'{n}/Карусель/слайд {i}', s['title'] + ' ' + s.get('body', '')))
    t = L['threads']
    for i, p in enumerate(t['posts'], 1): u.append((f'{n}/Threads/пост {i}', p))
    u.append((f'{n}/Threads/карточка', t['card']))
    p = L['pinterest']
    for i, pin in enumerate(p['pins']):
        k = 'AB'[i]
        u += [(f'{n}/Pinterest {k}/название', pin['title']), (f'{n}/Pinterest {k}/описание', pin['description']), (f'{n}/Pinterest {k}/alt', pin['alt']), (f'{n}/Pinterest {k}/картинка', pin['overlay'] + ' ' + ' '.join(pin.get('points', [])))]
    for k, name in [('youtube', 'YouTube'), ('vk_video', 'VK Видео'), ('rutube', 'Rutube'), ('instagram', 'Instagram'), ('threads', 'Threads')]:
        if L.get('task') and L['task'].get(k): u.append((f'{n}/{name}/задание', L['task'][k]))
    u += [(f'{n}/Видеопин/название', p['video_pin']['title']), (f'{n}/Видеопин/описание', p['video_pin']['description']), (f'{n}/Видеопин/зацепка', p['video_pin']['hook'])]
    return u

def words(s):
    s = re.sub(r'https?://\S+|#\S+', ' ', s.lower().replace('ё', 'е'))
    return re.findall(r'[a-zа-я0-9]+', s)

def grams(s, k):
    w = words(s); return {tuple(w[i:i + k]) for i in range(len(w) - k + 1)}

KWN = {'pinterest': 'пинтерест', 'пинтересте': 'пинтерест', 'pinterest\'е': 'пинтерест'}

def check(lessons, k=4):
    problems = []
    for L in lessons:
        for (plat, field), lim in LIMITS.items():
            pass
        n = L['n']
        def lim(where, s, key):
            if len(s.strip()) > LIMITS[key]: problems.append(f'{n} {where}: {len(s.strip())} > {LIMITS[key]}')
        y = L['youtube']
        for t in y['titles']: lim('YouTube название', t, ('youtube', 'title'))
        if len(', '.join(y['tags'])) > 500: problems.append(f'{n} YouTube теги > 500')
        lim('YouTube описание', y['description'], ('youtube', 'description'))
        for s in y['shorts']: lim('Shorts название', s['title'], ('shorts', 'title'))
        for t in L['vk_video']['titles']: lim('VK название', t, ('vk_video', 'title'))
        for c in L['vk_clips']:
            lim('VK клип описание', c['description'] + '\n' + hashtags(c['hashtags']), ('vk_clip', 'description'))
        for t in L['rutube']['titles']: lim('Rutube название', t, ('rutube', 'title'))
        for r in L['instagram']['reels']:
            lim('Reels подпись', r['caption'], ('reel', 'caption'))
            if len(r['hashtags']) > 5: problems.append(f'{n} Reels: хештегов {len(r["hashtags"])} > 5')
        if len(L['instagram']['carousel']['hashtags']) > 5: problems.append(f'{n} Карусель: хештегов > 5')
        for p in L['threads']['posts']: lim('Threads пост', p, ('threads', 'post'))
        for pin in L['pinterest']['pins']:
            lim('Пин название', pin['title'], ('pin', 'title')); lim('Пин описание', pin['description'] + ' ' + hashtags(pin.get('hashtags', [])), ('pin', 'description')); lim('Пин alt', pin['alt'], ('pin', 'alt'))
        lim('YouTube комментарий', y['comment'], ('youtube', 'comment'))
        for s in y['shorts']: lim('Shorts описание', s['description'] + hashtags(s['hashtags']), ('shorts', 'description'))
        lim('VK описание', L['vk_video']['description'], ('vk_video', 'description')); lim('VK пост', L['vk_video']['post'], ('vk_video', 'post'))
        lim('Rutube описание', L['rutube']['description'], ('rutube', 'description'))
        lim('Карусель подпись', L['instagram']['carousel']['caption'], ('carousel', 'caption'))
        vp = L['pinterest']['video_pin']; lim('Видеопин название', vp['title'], ('video_pin', 'title')); lim('Видеопин описание', vp['description'], ('video_pin', 'description'))
        if L.get('task'):
            for kk, lim_ in [('threads', 500), ('instagram', 2200), ('youtube', 10000), ('vk_video', 4000), ('rutube', 4000)]:
                if len(L['task'][kk].strip()) > lim_: problems.append(f'{n} задание {kk}: {len(L["task"][kk].strip())} > {lim_}')
        if len(y['hashtags']) > 15: problems.append(f'{n} YouTube: хештегов > 15')
    allu = [x for L in lessons for x in units(L)]
    index = collections.defaultdict(set)
    for where, s in allu:
        for g in grams(s, k): index[g].add(where)
    def legit(ws):
        # alt text must transcribe the lettering of its own image
        # fields of one and the same creative (title, description, alt, lettering) may share words
        study = [w for w in ws if w.split('/')[1] in ('Цели', 'Тест')]
        if study and len(study) < len(ws) and len({w.split('/')[0] for w in ws}) == 1: return True
        heads = {w.rsplit('/', 1)[0] for w in ws}
        if len(heads) == 1 and next(iter(heads)).split('/', 1)[1] in ('Pinterest A', 'Pinterest B', 'Видеопин') and {w.rsplit('/', 1)[1] for w in ws} <= {'название', 'описание', 'alt', 'картинка'}: return True
        if len(ws) != 2: return False
        a, b = sorted(ws)
        pa, pb = a.rsplit('/', 1), b.rsplit('/', 1)
        if pa[0] != pb[0]: return False
        x = {pa[1], pb[1]}
        if x in ({'alt', 'картинка'}, {'alt', 'слайд 1'}, {'описание', 'картинка'}): return True
        m = [t for t in x if t.startswith('alt слайда ')]
        return bool(m) and ('слайд ' + m[0].split()[-1]) in x
    kwg = {}
    for L in lessons:
        f = SRC / 'keywords' / f"{L['n']:02}.json"
        g = set()
        if f.exists():
            for r in json.loads(f.read_text())['keywords'][:80]: g |= {tuple(KWN.get(w, w) for w in t) for t in grams(r['phrase'], k)}
        kwg[L['n']] = g
    def kw_ok(g, ws):
        ls = {w.split('/')[0] for w in ws}
        return len(ls) == 1 and tuple(KWN.get(w, w) for w in g) in kwg.get(int(next(iter(ls))), set())
    dup = {g: ws for g, ws in index.items() if len(ws) > 1 and not legit(ws) and not kw_ok(g, ws)}
    return problems, dup, allu

TASKS = SRC / 'tasks.yaml'

def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        for k, v in b.items(): a[k] = merge(a.get(k), v) if k in a else v
        return a
    if isinstance(a, list) and isinstance(b, list) and b and all(isinstance(x, dict) for x in b) and all(isinstance(x, dict) for x in a):
        return [merge(a[i], b[i]) if i < len(b) else a[i] for i in range(len(a))] + b[len(a):]
    return b

def load(n):
    L = yaml.safe_load((SRC / f'{n:02}.yaml').read_text())
    v2 = SRC / 'v2' / f'{n:02}.yaml'
    if v2.exists(): L = merge(L, yaml.safe_load(v2.read_text()))
    for p_ in L['threads']['posts']: pass
    L['threads']['posts'] = [re.sub(r'\s*#\S+', '', p_).rstrip() for p_ in L['threads']['posts']]
    pf = SRC / 'pins_full.yaml'
    if pf.exists():
        e = (yaml.safe_load(pf.read_text()) or {}).get(n)
        if e:
            L['pinterest']['pins'][1]['description'] = e['b']; L['pinterest']['video_pin']['description'] = e['v']
    if TASKS.exists():
        L['task'] = (yaml.safe_load(TASKS.read_text()) or {}).get(n)
    # Rutube Shorts: the lesson's own clips; title from the clip name, description = the clip's narration
    v3 = SRC / 'v3' / f'{n:02}.yaml'
    E = yaml.safe_load(v3.read_text()) if v3.exists() else {}
    L['goals'], L['quiz'] = E.get('goals', []), E.get('quiz', [])
    L['rutube_shorts'] = []
    for c, s in zip(clips(n)[:2], E.get('rutube_shorts', [])):
        L['rutube_shorts'].append(dict(s, name=s.get('cover') or re.sub(r'^Клип_\d+_', '', c.stem).replace('_', ' ')))
    return L

def all_lessons(): return [load(int(p.stem)) for p in sorted(SRC.glob('[0-9][0-9].yaml'))]

# ---------------------------------------------------------------- build one lesson
def build(n, video=True, images=True):
    L = load(n); d = lesson_dir(n); sh = shots(n); cl = clips(n)
    assert sh, f'нет скриншотов у урока {n}'
    ratio = lambda f: Image.open(f).width / Image.open(f).height
    land = [f for f in sh if ratio(f) > 1.3] or sh
    port = [f for f in sh if ratio(f) <= 1.3] or sh
    S = lambda i: land[i % len(land)]     # wide covers
    T = lambda i: port[i % len(port)]     # tall covers, pins
    A = lambda i: sh[i % len(sh)]
    root = OUT / f"Урок_{n:02}_{L['slug']}"
    P = {k: root / k for k in ['YouTube', 'VK_Видео', 'VK_Клипы', 'Rutube', 'Instagram', 'Threads', 'Pinterest']}
    y, v, r, ig, t, p = L['youtube'], L['vk_video'], L['rutube'], L['instagram'], L['threads'], L['pinterest']
    for k in P.values(): k.mkdir(parents=True, exist_ok=True)
    # the lesson itself: video, narration text, subtitles, assignment
    full = [f for f in (d / '01_Видео').glob('*.mp4') if not f.name.startswith('Клип')][0]
    for src_, dst_ in [(full, root / 'Видео_урока.mp4'), (d / '02_Текст_урока/Субтитры_полного_урока.srt', root / 'Субтитры_урока.srt')]:
        if dst_.exists(): dst_.unlink()
        os.link(src_, dst_)
    title_ = L.get('title', L['slug'].replace('_', ' '))
    narr = (d / '02_Текст_урока/Текст_озвучки.txt')
    narr = narr.read_text().strip() if narr.exists() else '\n'.join(l for l in (d / '02_Текст_урока/Субтитры_полного_урока.srt').read_text().split('\n') if l.strip() and '-->' not in l and not l.strip().isdigit())
    (root / 'Текст_урока.txt').write_text(f"УРОК {n}. {title_.upper()}\n\n{narr}\n".replace('\n', '\r\n'), encoding='utf-8')
    if L.get('task'):
        tk = L['task']; off_ = re.sub(r'^Урок \d+[^\n]*\n+', '', tk['official'].strip()); body = f"ЗАДАНИЕ К УРОКУ {n}. {title_.upper()}\n\n{off_}\n"
        (root / 'Задание.txt').write_text(body.replace('\n', '\r\n'), encoding='utf-8')
        old_ = root / 'Задание_к_уроку.txt'
        if old_.exists(): old_.unlink()
    if L.get('goals'):
        g = f"ЦЕЛИ УРОКА {n}. {title_.upper()}\n\nПосле урока вы сможете:\n" + ''.join(f"{i}. {x}\n" for i, x in enumerate(L['goals'], 1))
        (root / 'Цели_урока.txt').write_text(g.replace('\n', '\r\n'), encoding='utf-8')
    if L.get('quiz'):
        q = [f"ПРОВЕРЬ СЕБЯ. УРОК {n}. {title_.upper()}", '', 'Выберите один вариант. Ответы и объяснения — в конце файла.', '']
        keys = []
        for i, it in enumerate(L['quiz'], 1):
            k = (n + i) % len(it['options'])          # deterministic shuffle: correct answer moves between letters
            opts = it['options'][k:] + it['options'][:k]
            keys.append('АБВГ'[opts.index(it['options'][it['answer'] - 1])])
            q += [f"{i}. {it['q']}"] + [f"   {'АБВГ'[j]}) {o}" for j, o in enumerate(opts)] + ['']
        q += ['ОТВЕТЫ', '']
        for i, it in enumerate(L['quiz'], 1):
            q.append(f"{i} — {keys[i - 1]}. {it['why']}")
        (root / 'Проверь_себя.txt').write_text(('\n'.join(q) + '\n').replace('\n', '\r\n'), encoding='utf-8')
    if images:
        for i, tt in enumerate(y['thumbs']): yt_thumb(i, tt, S(i), n, P['YouTube'] / f"Обложка_{'ABC'[i]}.jpg")
        for i, s in enumerate(y['shorts'], 1): tall_cover('shorts', s['cover'], T(i + 2), n, P['YouTube'] / f'Shorts_{i}_обложка.jpg')
        for i, tt in enumerate(v['covers']): wide_cover('vk', i, tt, S(i + 1), S(i + 2), n, P['VK_Видео'] / f"Обложка_{'AB'[i]}.jpg")
        for i, c in enumerate(L['vk_clips'], 1): tall_cover('vk_clip', c['cover'], T(i), n, P['VK_Клипы'] / f'Клип_{i}_обложка.jpg')
        for i, tt in enumerate(r['covers']): wide_cover('rutube', i, tt, S(i + 2), S(i + 3), n, P['Rutube'] / f"Обложка_{'AB'[i]}.jpg")
        for i, s in enumerate(L['rutube_shorts'], 1): tall_cover('shorts', s['name'], T(i - 1), n, P['Rutube'] / f'Shorts_{i}_обложка.jpg')
        for i, rr in enumerate(ig['reels'], 1): tall_cover('reel', rr['cover'], A(i + 1), n, P['Instagram'] / f'Reels_{i}_обложка.jpg')
        carousel(ig['carousel']['slides'], [A(i + 1) for i in range(len(sh))], n, P['Instagram'])
        threads_card(t['card'], S(3), P['Threads'] / 'Карточка.jpg')
        for i, pin in enumerate(p['pins']): pin_image(i, pin, T(i * 2) if i == 0 else S(1), n, P['Pinterest'] / f"Пин_{'AB'[i]}.jpg")
    for k, files in creatives(L).items():
        for fn, txt in files.items(): (P[k] / fn).write_text(to_txt(txt), encoding='utf-8')
        for old in [P[k] / 'Публикация.txt', P[k] / 'Публикация.md']:
            if old.exists(): old.unlink()
    srt = d / '02_Текст_урока/Субтитры_полного_урока.srt'
    for k in ['YouTube', 'VK_Видео', 'Rutube']:
        dst = P[k] / 'Субтитры.srt'
        if dst.exists(): dst.unlink()
        os.link(srt, dst)
    if video:
        wide = ROOT / 'artifacts/pinterest-course/publication/wide' / f'Урок_{n:02}_16x9.mp4'
        if not wide.exists():
            full = [f for f in (d / '01_Видео').glob('*.mp4') if not f.name.startswith('Клип')][0]
            render_wide(full, n, L.get('title', L['slug'].replace('_', ' ')), wide)
        for k in ['YouTube', 'VK_Видео', 'Rutube']:
            dst = P[k] / 'Видео_16x9.mp4'
            if dst.exists(): dst.unlink()
            os.link(wide, dst)
        tmp = ROOT / 'artifacts/pinterest-course/publication/hooks' / f'{n:02}'
        jobs = []
        for i, c in enumerate(cl[:2]):
            jobs += [('shorts', y['shorts'][i]['hook'], 'safe916', P['YouTube'] / f'Shorts_{i + 1}.mp4', c),
                     ('rshorts', L['rutube_shorts'][i]['name'], 'safe916', P['Rutube'] / f'Shorts_{i + 1}.mp4', c),
                     ('vk_clip', L['vk_clips'][i]['hook'], 'safe916', P['VK_Клипы'] / f'Клип_{i + 1}.mp4', c),
                     ('reel', ig['reels'][i]['hook'], 'safe916', P['Instagram'] / f'Reels_{i + 1}.mp4', c)]
        jobs.append(('video_pin', p['video_pin']['hook'], 'pin23', P['Pinterest'] / 'Видеопин.mp4', cl[0]))
        for plat, hook, layout, dst, src in jobs:
            h = tmp / f'{plat}_{dst.stem}.png'; stamp = h.with_suffix('.json')
            key = json.dumps([hook, layout, str(src), src.stat().st_mtime], ensure_ascii=False)
            if dst.exists() and stamp.exists() and stamp.read_text() == key: continue
            hook_png(plat, hook, h); cut_video(src, h, layout, dst); stamp.write_text(key)
    print(f'урок {n}: готово → {root.relative_to(ROOT)}', flush=True)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'check':
        k = int(os.environ.get('K', 4))
        problems, dup, allu = check(all_lessons(), k)
        for x in problems: print('ЛИМИТ', x)
        for g, ws in sorted(dup.items(), key=lambda x: -len(x[1])): print('ПОВТОР', ' '.join(g), '|', '; '.join(sorted(ws)))
        print(f'единиц текста: {len(allu)}, нарушений лимитов: {len(problems)}, повторов {k}-грамм: {len(dup)}')
    elif cmd == 'stamp':
        # mark already rendered cuts as current (hooks unchanged since render)
        for a in sys.argv[2:]:
            n = int(a); L = load(n); cl = clips(n); root = OUT / f"Урок_{n:02}_{L['slug']}"
            tmp = ROOT / 'artifacts/pinterest-course/publication/hooks' / f'{n:02}'
            jobs = []
            for i, c in enumerate(cl[:2]):
                jobs += [('shorts', L['youtube']['shorts'][i]['hook'], 'safe916', root / 'YouTube' / f'Shorts_{i + 1}.mp4', c),
                         ('vk_clip', L['vk_clips'][i]['hook'], 'safe916', root / 'VK_Клипы' / f'Клип_{i + 1}.mp4', c),
                         ('reel', L['instagram']['reels'][i]['hook'], 'safe916', root / 'Instagram' / f'Reels_{i + 1}.mp4', c)]
            jobs.append(('video_pin', L['pinterest']['video_pin']['hook'], 'pin23', root / 'Pinterest' / 'Видеопин.mp4', cl[0]))
            for plat, hook, layout, dst, src in jobs:
                if dst.exists():
                    h = tmp / f'{plat}_{dst.stem}.png'; h.parent.mkdir(parents=True, exist_ok=True)
                    h.with_suffix('.json').write_text(json.dumps([hook, layout, str(src), src.stat().st_mtime], ensure_ascii=False))
    elif cmd == 'docs':
        for name in ['НАЧАТЬ_ЗДЕСЬ', 'ПРАВИЛА_ПЛОЩАДОК']:
            src = SRC / f'{name}.md'
            (OUT / f'{name}.txt').write_text(to_txt(src.read_text()), encoding='utf-8')
            if (OUT / f'{name}.md').exists(): (OUT / f'{name}.md').unlink()
        if (OUT / 'Проверка_уникальности.md').exists(): (OUT / 'Проверка_уникальности.md').unlink()
        print('документы в txt')
    elif cmd == 'report':
        lessons = all_lessons(); problems, dup, allu = check(lessons, 4)
        chars = sum(len(s) for _, s in allu)
        per = collections.Counter(w.split('/')[1].split(' ')[0] for w, _ in allu)
        o = ['# Проверка уникальности текстов', '',
             f'Проверено уроков: {len(lessons)}. Текстовых блоков: {len(allu)} (названия, описания, подписи, посты, alt, надписи на обложках и пинах, зацепки роликов). Знаков: {chars}.', '',
             'Правило проверки: ни одна последовательность из 4 слов подряд не встречается в двух разных блоках — ни между площадками, ни между уроками. Регистр, ё/е и знаки препинания не учитываются. Хештеги, теги и названия досок не проверяются (это метки, а не текст).',
             'Единственное допустимое совпадение: альтернативный текст картинки дословно передаёт надпись на этой же картинке — так требует сам смысл alt.', '',
             f'**Результат: совпадений — {len(dup)}, нарушений лимитов знаков — {len(problems)}.**', '',
             '## Лимиты, которые проверялись автоматически', '',
             '| Площадка | Поле | Лимит |', '|---|---|---|']
        names = {'youtube': 'YouTube', 'shorts': 'YouTube Shorts', 'vk_video': 'VK Видео', 'vk_clip': 'VK Клипы', 'rutube': 'Rutube', 'reel': 'Instagram Reels',
                 'carousel': 'Instagram карусель', 'threads': 'Threads', 'pin': 'Pinterest пин', 'video_pin': 'Pinterest видеопин'}
        fields = {'title': 'название', 'description': 'описание', 'comment': 'комментарий', 'post': 'пост', 'caption': 'подпись', 'alt': 'альтернативный текст'}
        for (p, f), lim in LIMITS.items(): o.append(f'| {names[p]} | {fields[f]} | {lim} |')
        o += ['| Instagram | хештегов на публикацию | 5 |', '| YouTube | теги, всего знаков | 500 |', '', '## Блоков по площадкам', '']
        for k, v in sorted(per.items()): o.append(f'- {k}: {v}')
        if dup:
            o += ['', '## Совпадения', ''] + [f"- «{' '.join(g)}»: {'; '.join(sorted(ws))}" for g, ws in dup.items()]
        (SRC / 'Проверка_уникальности.txt').write_text(to_txt('\n'.join(o)), encoding='utf-8'); print('отчёт записан')
    elif cmd == 'build':
        args = [a for a in sys.argv[2:] if not a.startswith('--')]
        for a in args: build(int(a), video='--no-video' not in sys.argv)
    elif cmd == 'texts':
        for a in sys.argv[2:]: build(int(a), video=False, images=False)
