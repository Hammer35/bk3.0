"""Full audit of the finished course folder: every lesson, every creative.

Checks presence, video/image sizes, and that every creative text file
contains title, description, tags and hashtags sections.
Usage: python3 scripts/pub_verify.py [first last]
"""
import json, re, subprocess, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'КУРС_PINTEREST'

LESSON = ['Видео_урока.mp4', 'Текст_урока.txt', 'Цели_урока.txt', 'Задание.txt', 'Проверь_себя.txt', 'Субтитры_урока.srt']
VIDEO = {  # creative -> (w, h)
    'YouTube/Видео_16x9.mp4': (1920, 1080), 'YouTube/Shorts_1.mp4': (1080, 1920), 'YouTube/Shorts_2.mp4': (1080, 1920),
    'VK_Видео/Видео_16x9.mp4': (1920, 1080), 'VK_Клипы/Клип_1.mp4': (1080, 1920), 'VK_Клипы/Клип_2.mp4': (1080, 1920),
    'Rutube/Видео_16x9.mp4': (1920, 1080), 'Rutube/Shorts_1.mp4': (1080, 1920), 'Rutube/Shorts_2.mp4': (1080, 1920),
    'Instagram/Reels_1.mp4': (1080, 1920), 'Instagram/Reels_2.mp4': (1080, 1920), 'Pinterest/Видеопин.mp4': (1000, 1500)}
IMAGE = {
    'YouTube/Обложка_A.jpg': (1280, 720), 'YouTube/Обложка_B.jpg': (1280, 720), 'YouTube/Обложка_C.jpg': (1280, 720),
    'YouTube/Shorts_1_обложка.jpg': (1080, 1920), 'YouTube/Shorts_2_обложка.jpg': (1080, 1920),
    'VK_Видео/Обложка_A.jpg': (1920, 1080), 'VK_Видео/Обложка_B.jpg': (1920, 1080),
    'VK_Клипы/Клип_1_обложка.jpg': (1080, 1920), 'VK_Клипы/Клип_2_обложка.jpg': (1080, 1920),
    'Rutube/Обложка_A.jpg': (1920, 1080), 'Rutube/Обложка_B.jpg': (1920, 1080),
    'Rutube/Shorts_1_обложка.jpg': (1080, 1920), 'Rutube/Shorts_2_обложка.jpg': (1080, 1920),
    'Instagram/Reels_1_обложка.jpg': (1080, 1920), 'Instagram/Reels_2_обложка.jpg': (1080, 1920),
    'Threads/Карточка.jpg': (1080, 1350), 'Pinterest/Пин_A.jpg': (1000, 1500), 'Pinterest/Пин_B.jpg': (1000, 1500)}
TEXTS = ['YouTube/Видео_16x9.txt', 'YouTube/Shorts_1.txt', 'YouTube/Shorts_2.txt', 'VK_Видео/Видео_16x9.txt',
         'VK_Клипы/Клип_1.txt', 'VK_Клипы/Клип_2.txt', 'Rutube/Видео_16x9.txt', 'Rutube/Shorts_1.txt', 'Rutube/Shorts_2.txt',
         'Instagram/Reels_1.txt', 'Instagram/Reels_2.txt', 'Instagram/Карусель.txt', 'Threads/Карточка.txt',
         'Pinterest/Пин_A.txt', 'Pinterest/Пин_B.txt', 'Pinterest/Видеопин.txt']
SECTIONS = ['Название', 'Описание', 'Теги', 'Хэштеги']


def probe(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height:format=duration',
                        '-of', 'json', str(f)], capture_output=True, text=True)
    j = json.loads(r.stdout or '{}')
    s = (j.get('streams') or [{}])[0]
    return s.get('width'), s.get('height'), float(j.get('format', {}).get('duration', 0))


def lesson(n):
    probs = []
    d = next(OUT.glob(f'Урок_{n:02}_*'), None)
    if not d:
        return [f'урок {n}: нет папки']
    for f in LESSON:
        if not (d / f).is_file() or (d / f).stat().st_size == 0:
            probs.append(f'урок {n}: нет {f}')
    for f, (w, h) in VIDEO.items():
        p = d / f
        if not p.is_file():
            probs.append(f'урок {n}: нет {f}'); continue
        W, H, dur = probe(p)
        if (W, H) != (w, h): probs.append(f'урок {n}: {f} {W}×{H}, нужно {w}×{h}')
        if dur < 2: probs.append(f'урок {n}: {f} длительность {dur:.1f} с')
        if f.endswith(('Shorts_1.mp4', 'Shorts_2.mp4')) and dur > 180: probs.append(f'урок {n}: {f} длиннее 3 минут')
    for f, (w, h) in IMAGE.items():
        p = d / f
        if not p.is_file():
            probs.append(f'урок {n}: нет {f}'); continue
        if Image.open(p).size != (w, h): probs.append(f'урок {n}: {f} {Image.open(p).size}, нужно {w}×{h}')
    car = sorted((d / 'Instagram').glob('Карусель_*.jpg'))
    if len(car) < 2: probs.append(f'урок {n}: в карусели {len(car)} слайдов')
    for f in TEXTS:
        p = d / f
        if not p.is_file():
            probs.append(f'урок {n}: нет {f}'); continue
        t = p.read_text(encoding='utf-8')
        for s in SECTIONS:
            if not re.search(rf'^{s}', t, re.M): probs.append(f'урок {n}: в {f} нет раздела «{s}»')
    for old in d.glob('*/Публикация.*'):
        probs.append(f'урок {n}: остался старый файл {old.relative_to(d)}')
    return probs


if __name__ == '__main__':
    a, z = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1, 42)
    allp = []
    for n in range(a, z + 1):
        allp += lesson(n)
    print('\n'.join(allp) if allp else 'замечаний нет')
    print(f'проверено уроков: {z - a + 1}, замечаний: {len(allp)}')
