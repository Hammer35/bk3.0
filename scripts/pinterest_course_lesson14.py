"""Local lesson 3.5 assembly using supplied voice and real captured screens."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import subprocess

from pinterest_course_release import ROOT, COURSE, PUBLIC, copy, write, csv_file, srt_time

LESSON = COURSE / 'Урок_14_Публикация_первого_пина'
PLATFORMS = LESSON / '03_Площадки'
DOCS = LESSON / '04_Документы'
BUILD = ROOT / 'artifacts/pinterest-course/release-build-lesson14'
VISUAL = ROOT / 'artifacts/pinterest-course/visual-lesson-14'
VIDEO = ROOT / 'artifacts/pinterest-course/lesson-3.5-vertical-v1'
DATA = PUBLIC / 'lesson-3.5/data.json'
TEXT = ROOT / 'docs/pinterest-course/урок-3.5-озвучка.txt'
VIDEO_NAME = 'Урок_14_Публикация_первого_пина.mp4'
CLIPS = [('Клип_01_Настоящая_ссылка', 'Ссылку не придумываем', 4, 5),
         ('Клип_02_Проверка_публикации', 'Проверьте опубликованный пин', 6, 7)]
SLIDES = ['Готовые_части', 'Учебный_черновик', 'Название_и_описание',
          'Альтернативный_текст', 'Настоящая_ссылка', 'Доска_и_проверка', 'После_публикации']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def renderer():
    import pinterest_course_lesson2_render as r
    r.LESSON_ID = '3.5'
    r.V2 = False
    r.OUT = VIDEO
    r.DATA = DATA
    r.VOICE = PUBLIC / 'lesson-3.5/voice.wav'
    r.VIDEO = VIDEO / 'lesson-3.5-vertical-v1.mp4'
    return r


def ffmpeg(args):
    subprocess.run(['nice', '-n', '15', 'taskset', '-c', '3', 'ffmpeg',
                    '-nostdin', '-v', 'error', '-threads', '1', *args], check=True)


def finalize():
    d = json.loads(DATA.read_text())
    assert not d['preview']
    full = VIDEO / 'lesson-3.5-vertical-v1.mp4'
    ffmpeg(['-xerror', '-i', str(full), '-f', 'null', '-'])
    for dest in [LESSON / '01_Видео' / VIDEO_NAME] + [
            PLATFORMS / s / 'Видео' / VIDEO_NAME for s in ['YouTube', 'Rutube', 'VK_Видео']]:
        copy(full, dest)
    for dest in [LESSON / '02_Текст_урока/Субтитры_полного_урока.srt'] + [
            PLATFORMS / s / 'Тексты/Субтитры.srt' for s in ['YouTube', 'Rutube', 'VK_Видео']]:
        copy(VIDEO / 'subtitles.srt', dest)
    copy(TEXT, LESSON / '02_Текст_урока/Текст_озвучки.txt')
    paragraphs = TEXT.read_text().strip().split('\n\n')
    lengths = {}
    for name, _, a, b in CLIPS:
        start, end = d['sceneStarts'][a], d['sceneStarts'][b]
        frames = math.ceil(end * 30 - 1e-8) - math.ceil(start * 30 - 1e-8)
        target = LESSON / f'01_Видео/{name}.mp4'
        ffmpeg(['-y', '-ss', str(start), '-i', str(full), '-t', str(end - start),
                '-map', '0:v:0', '-map', '0:a:0', '-vf',
                f'trim=end_frame={frames},setpts=PTS-STARTPTS', '-c:v', 'libx264',
                '-preset', 'veryfast', '-crf', '19', '-threads', '1', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(target)])
        ffmpeg(['-xerror', '-i', str(target), '-f', 'null', '-'])
        lengths[name] = end - start
        blocks = []
        for page in d['pages']:
            pa, pb = max(page['startMs'], start * 1000), min(page['endMs'], end * 1000)
            if pa < pb:
                text = '\n'.join(' '.join(w['text'].strip() for w in line) for line in page['lines'])
                blocks.append(f'{len(blocks)+1}\n{srt_time(pa-start*1000)} --> {srt_time(pb-start*1000)}\n{text}')
        srt = '\n\n'.join(blocks)
        write(LESSON / f'02_Текст_урока/{name}_субтитры.srt', srt)
        write(LESSON / f'02_Текст_урока/{name}_текст.txt', '\n\n'.join(paragraphs[a:b]))
        for site in ['VK_Клипы', 'Instagram']:
            copy(target, PLATFORMS / site / f'Видео/{name}.mp4')
            write(PLATFORMS / site / f'Тексты/{name}_субтитры.srt', srt)
        print(name, 'готов', flush=True)
    for i, title in enumerate(SLIDES, 1):
        copy(VIDEO / f'final-{i:02}.png', LESSON / f'05_Слайды/{i:02}_{title}.png')
    copy(VISUAL / 'Версии_скриншотов.csv', DOCS / 'Версии_скриншотов.csv')
    for shot in json.loads((VISUAL / 'sha256-manifest.json').read_text()):
        copy(VISUAL / shot, LESSON / '05_Слайды/Реальные_скриншоты' / shot)
    links = '\n'.join(f'- [{title}](../01_Видео/{name}.mp4): {lengths[name]:.2f} с.' for name, title, *_ in CLIPS)
    write(DOCS / 'Что_где_лежит.md', f'''# Урок 14 · Публикация первого пина

- [Полный урок](../01_Видео/{VIDEO_NAME}): {d['duration']:.2f} с.
{links}
- [Озвучка](../06_Озвучка/14.wav), [текст](../02_Текст_урока/Текст_озвучки.txt), [субтитры](../02_Текст_урока/Субтитры_полного_урока.srt).
- [Семь площадок](../03_Площадки), [слайды](../05_Слайды), [задание](Задание_ученику.txt), [источники](Источники_и_оформление.md).

1080×1920, H.264 / AAC, 30 кадров/с. Голос пользователя сохранён. Реальные снимки показаны до монтажа; SHA256 — в [реестре](Версии_скриншотов.csv).
Автоматические тайминги: {len(d['words'])} слов, {d['interpolatedWords']} интерполированных отметок.
Не опубликовано. Пользователь готовое видео и отдельные пины не одобрял.
''')
    csv_file(DOCS / 'Журнал_выпуска.csv', ['Площадка', 'Версия', 'Статус', 'Дата одобрения', 'Дата публикации', 'URL'],
             [[s, '01', 'Собран; отдельно не одобрен; не опубликован', '', '', '']
              for s in ['YouTube', 'Rutube', 'VK Видео', 'VK Клипы', 'Instagram', 'Pinterest', 'Threads']])


def verify():
    import pinterest_course_lesson2 as m
    for name in ['LESSON', 'PLATFORMS', 'DOCS', 'BUILD', 'VIDEO', 'TEXT', 'DATA', 'VIDEO_NAME', 'CLIPS']:
        setattr(m, name, globals()[name])
    m.verify()
    d = json.loads(DATA.read_text())
    assert sha(LESSON / '06_Озвучка/14.wav') == sha(PUBLIC / 'lesson-3.5/voice.wav')
    srt = (VIDEO / 'subtitles.srt').read_text()
    words = ' '.join(' '.join(b.splitlines()[2:]) for b in srt.strip().split('\n\n'))
    assert words.split() == TEXT.read_text().split()
    paragraphs = TEXT.read_text().strip().split('\n\n')
    for name, _, a, b in CLIPS:
        entries = (LESSON / f'02_Текст_урока/{name}_субтитры.srt').read_text().strip().split('\n\n')
        text = ' '.join(' '.join(e.splitlines()[2:]) for e in entries)
        assert text.split() == '\n\n'.join(paragraphs[a:b]).split(), name
        limit = round((d['sceneStarts'][b] - d['sceneStarts'][a]) * 1000)
        for entry in entries:
            stamps = entry.splitlines()[1].split(' --> ')
            times = []
            for stamp in stamps:
                h, m, s, ms = map(int, re.split('[:,]', stamp))
                times.append(((h * 60 + m) * 60 + s) * 1000 + ms)
            assert 0 <= times[0] < times[1] <= limit, (name, times, limit)
    for name in [VIDEO_NAME] + [c[0] + '.mp4' for c in CLIPS]:
        main = LESSON / '01_Видео' / name
        for dest in PLATFORMS.rglob(name):
            assert sha(dest) == sha(main)
    assert len(list((LESSON / '05_Слайды').glob('*.png'))) == 7
    for shot in json.loads((VISUAL / 'sha256-manifest.json').read_text()):
        assert sha(VISUAL / shot) == json.loads((VISUAL / 'sha256-manifest.json').read_text())[shot]
        assert sha(VISUAL / shot) == sha(LESSON / '05_Слайды/Реальные_скриншоты' / shot)
    for f in LESSON.rglob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)', f.read_text()):
            if not link.startswith(('https://', 'http://', '#')):
                assert (f.parent / link.split('#')[0]).exists(), (f, link)
    result = {'duration': d['duration'], 'words': len(d['words']),
              'interpolatedWords': d['interpolatedWords'], 'wavSHA256': sha(PUBLIC / 'lesson-3.5/voice.wav'),
              'files': sum(p.is_file() for p in LESSON.rglob('*')), 'status': 'passed'}
    write(VIDEO / 'verification.json', json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['render', 'preview', 'stills', 'finalize', 'verify'])
    args = parser.parse_args()
    if args.stage == 'render': renderer().run()
    elif args.stage == 'preview': renderer().run(preview=True)
    elif args.stage == 'stills': renderer().extract_stills()
    elif args.stage == 'finalize': finalize()
    else: verify()
