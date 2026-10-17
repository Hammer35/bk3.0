"""Prepare the approved lesson and its local publishing kit; no network calls."""
from pathlib import Path
import csv
import html
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / 'КУРС_PINTEREST'
LESSON = COURSE / 'Урок_01_Что_такое_Pinterest'
BUILD = ROOT / 'artifacts/pinterest-course/release-build'
PUBLIC = ROOT / 'video/pinterest-lesson/public'
BRAND = ROOT / 'docs/pinterest-course/brand'
SOURCE = ROOT / 'artifacts/pinterest-course/lesson-1.1-vertical-v5'
PLATFORMS = LESSON / '03_Площадки'
DOCS = LESSON / '04_Документы'
VIDEO_NAME = 'Урок_01_Что_такое_Pinterest.mp4'
CLIPS = [
    {'id': '01', 'name': 'Клип_01_Пин_и_доска', 'start': 33.0, 'end': 45.0,
     'title': 'Пин и доска: в чём разница?', 'paragraph': 2},
    {'id': '02', 'name': 'Клип_02_Куда_ведёт_ссылка', 'start': 66.4, 'end': 84.0,
     'title': 'Куда должна вести ссылка из пина?', 'paragraph': 4},
]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf-8')


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def csv_file(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(header)
        writer.writerows(rows)


def srt_time(ms):
    h, rest = divmod(round(ms), 3600000)
    m, rest = divmod(rest, 60000)
    s, rest = divmod(rest, 1000)
    return f'{h:02}:{m:02}:{s:02},{rest:03}'


def clip_srt(start, end):
    import re
    def parse(value):
        h, m, s, ms = map(int, re.split('[:,]', value))
        return ((h * 60 + m) * 60 + s) * 1000 + ms
    blocks = []
    for entry in (SOURCE / 'subtitles.srt').read_text().strip().split('\n\n'):
        _, timing, *lines = entry.splitlines()
        a, b = map(parse, timing.split(' --> '))
        a, b = max(a, start * 1000), min(b, end * 1000)
        if a < b:
            blocks.append(f'{len(blocks)+1}\n{srt_time(a-start*1000)} --> {srt_time(b-start*1000)}\n' + '\n'.join(lines))
    return '\n\n'.join(blocks)


def prepare_texts():
    copy(SOURCE / 'lesson-1.1-vertical-v5.mp4', LESSON / '01_Видео' / VIDEO_NAME)
    copy(ROOT / 'docs/pinterest-course/урок-1.1-озвучка.txt', LESSON / '02_Текст_урока/Текст_озвучки.txt')
    copy(SOURCE / 'subtitles.srt', LESSON / '02_Текст_урока/Субтитры_полного_урока.srt')
    paragraphs = (ROOT / 'docs/pinterest-course/урок-1.1-озвучка.txt').read_text().strip().split('\n\n')
    for clip in CLIPS:
        write(LESSON / f"02_Текст_урока/{clip['name']}_текст.txt", paragraphs[clip['paragraph']])
        write(LESSON / f"02_Текст_урока/{clip['name']}_субтитры.srt", clip_srt(clip['start'], clip['end']))
    write(LESSON / '02_Текст_урока/Текст_на_слайдах.txt', '''Урок 1.1. Что такое Pinterest и чем он может быть полезен
Общее оформление: BK / BOOSTKLIENT; УРОК 1.1; номер сцены из 7.

СЛАЙД 1 — Идея начинается с вопроса
Куда поставить лампу?
Как освободить стол?

СЛАЙД 2 — Pinterest: поиск по картинкам
Рабочее место в маленькой комнате
Уютный рабочий уголок
Светлый стол
Учебная схема поиска · фотографии Unsplash

СЛАЙД 3 — Один пин. Целая подборка.
ПИН — Идея рабочего места
ДОСКА
Сохраните идеи в одном месте

СЛАЙД 4 — Идея может вести к вашему проекту
Анна
Вымышленная героиня курса
Пять идей для рабочего стола в маленькой комнате
Пин → статья в блоге

СЛАЙД 5 — Что обещали — туда и ведём
ПИН ОБЕЩАЕТ ИДЕИ → Статья с идеями
ПИН ПОКАЗЫВАЕТ ТОВАР → Товар → Карточка этого товара
Откройте ссылку перед публикацией

СЛАЙД 6 — Переход ещё не покупка
Это разные действия человека
01 Просмотрел пин
02 Перешёл по ссылке
03 Сделал покупку
Результат проверяем по статистике

СЛАЙД 7 — Теперь попробуйте сами
3 пина
По теме вашего проекта
1 Что привлекло внимание?
2 Что хочется сохранить?
3 Куда ведёт ссылка?
В своём пине я покажу…
А по ссылке человек найдёт…

В нижнем поле на всех слайдах — текст озвучки с подсветкой произносимого слова.''')

    title = 'Что такое Pinterest: пины, доски и ссылки | Урок 1'
    intro = '''Первый урок курса BoostKlient «Pinterest для начинающих».
Разберём, как искать идеи по изображениям, чем пин отличается от доски и куда должна вести ссылка из публикации. На учебном примере Анны покажем связь пина со статьёй или карточкой товара. Анна — вымышленная героиня курса.

Задание: найдите три пина по теме своего проекта. Что привлекло внимание? Что хочется сохранить? Куда ведут ссылки? Закончите фразу: «В своём пине я покажу… А по ссылке человек найдёт…».

Переход по ссылке ещё не означает покупку. Показы, сохранения и переходы проверяем по статистике.

Официальные материалы:
https://help.pinterest.com/en/guide/all-about-pinterest
https://help.pinterest.com/en/guide/guide-to-creating-pins'''
    for platform in ['YouTube', 'Rutube', 'VK_Видео']:
        p = PLATFORMS / platform
        copy(SOURCE / 'lesson-1.1-vertical-v5.mp4', p / 'Видео' / VIDEO_NAME)
        copy(SOURCE / 'subtitles.srt', p / 'Тексты/Субтитры.srt')
        write(p / 'Тексты/Название.txt', title)
        description = intro
        if platform == 'YouTube':
            description += '\n\n#Pinterest #Пинтерест #Обучение'
        write(p / 'Тексты/Описание.txt', description)
        write(p / 'Тексты/Комментарий_с_заданием.txt', 'Практика: найдите три пина по теме своего проекта. Напишите свою заготовку: «В своём пине я покажу… А по ссылке человек найдёт…».')
    write(PLATFORMS / 'VK_Видео/Тексты/Пост_к_видео.txt', '''Как связаны Pinterest, ваш блог и товар?

В первом уроке разбираем пины, доски и продолжение по ссылке. В конце — простое задание для вашего проекта.

Что вы хотите показывать в Pinterest: статьи, товары или услуги?''')

    captions = [
        'Пин — отдельная публикация. Доска — тематическая подборка сохранённых пинов. Например, идеи для рабочего места можно собрать вместе, чтобы вернуться к ним позже.\n\nЧто вы собираете на своих досках?',
        'Пин обещает идеи — по ссылке должна открыться статья с этими идеями. Пин показывает конкретный органайзер — продолжением может быть карточка именно этого товара.\n\nПеред публикацией откройте ссылку и сравните страницу с обещанием пина.',
    ]
    for platform in ['VK_Клипы', 'Instagram']:
        for i, clip in enumerate(CLIPS):
            p = PLATFORMS / platform / 'Тексты'
            write(p / f"{clip['name']}_название.txt", clip['title'])
            write(p / f"{clip['name']}_описание.txt", captions[i] + ('\n\n#Pinterest #Пинтерест' if platform == 'Instagram' else ''))
            write(p / f"{clip['name']}_текст_озвучки.txt", paragraphs[clip['paragraph']])
            write(p / f"{clip['name']}_субтитры.srt", clip_srt(clip['start'], clip['end']))
    write(PLATFORMS / 'Instagram/Тексты/Карусель_описание.txt', '''Первое задание по Pinterest — без сложных настроек.

1. Найдите три пина по теме своего проекта.
2. Посмотрите, что привлекло внимание, что хочется сохранить и куда ведут ссылки.
3. Заполните: «В своём пине я покажу… А по ссылке человек найдёт…».

Сохраните карточки, чтобы вернуться к заданию. Какую идею выбрали для своего пина?

#Pinterest #Пинтерест''')

    pin_texts = [
        ('Что такое Pinterest: первый урок для начинающих',
         'Как искать идеи через изображения, чем пин отличается от доски и что человек должен найти по ссылке. Первый урок курса BoostKlient: объяснение, учебный пример и задание — найти три пина по теме своего проекта.',
         'Светлая учебная карточка BoostKlient: «Pinterest для начала». Фотография рабочего места и подпись «Идея → пин → продолжение». Первый урок о пинах, досках и ссылках.'),
        ('От пина к статье: учебный пример Анны',
         'Анна ведёт блог об организации дома. В учебном примере она показывает в пине идею рабочего стола и ведёт к статье с подробностями. Разберите этот путь и сформулируйте продолжение для своего пина. Анна — вымышленная героиня курса.',
         'Карточка BoostKlient «Ваш пин. Что дальше?». Портрет Анны, фотография рабочего места и схема: идея рабочего стола → статья с идеями. Анна обозначена как вымышленная героиня курса.'),
    ]
    for i, (pin_title, description, alt) in enumerate(pin_texts, 1):
        p = PLATFORMS / f'Pinterest/Пин_{i:02}/Тексты'
        write(p / 'Название.txt', pin_title)
        write(p / 'Описание.txt', description)
        write(p / 'Альтернативный_текст.txt', alt)
        assert len(pin_title) <= 100 and len(description) <= 500
    thread_texts = [
        'Пин — отдельная публикация в Pinterest. Доска — подборка сохранённых пинов по теме.\n\nНашли идею рабочего стола? Сохраните пин на доску «Рабочее место», чтобы вернуться к нему позже.\n\nЗадание: найдите три пина по теме своего проекта. Что хочется сохранить — и почему?',
        'Что вы хотите показывать в Pinterest: статьи, товары или услуги?\n\nНачните с одной фразы: «В своём пине я покажу… А по ссылке человек найдёт…».\n\nНапример: покажу идею рабочего стола, а по ссылке будут подробности в статье. Обещание пина и страница по ссылке должны совпадать.\n\nКак бы вы закончили эту фразу для своего проекта?',
    ]
    for i, text in enumerate(thread_texts, 1):
        assert len(text) <= 500
        write(PLATFORMS / f'Threads/Тексты/Пост_{i:02}.txt', text)


def prepare_docs():
    write(COURSE / 'НАЧАТЬ_ЗДЕСЬ.md', '''# Pinterest для начинающих · BoostKlient

[Открыть материалы урока 1](Урок_01_Что_такое_Pinterest/04_Документы/Что_где_лежит.md).

Каждый следующий урок получает свою папку `Урок_02_Название`, `Урок_03_Название` и так далее. Внутри сохраняем одинаковую структуру: видео, текст урока, площадки, документы. Здесь лежат материалы для выпуска; рабочие сборки и старые версии остаются вне этой папки.''')
    write(DOCS / 'Что_где_лежит.md', '''# Урок 1 · Что такое Pinterest

Полный ролик утверждён пользователем 4 октября 2026 года. Это финальная версия с латинским BK, учебной шапочкой и BOOSTKLIENT. Вертикальный формат, 1 минута 52 секунды; голос и титры сохранены.

## Основные файлы

- [Итоговое видео](../01_Видео/Урок_01_Что_такое_Pinterest.mp4).
- [Текст озвучки](../02_Текст_урока/Текст_озвучки.txt), [текст на слайдах](../02_Текст_урока/Текст_на_слайдах.txt), [субтитры](../02_Текст_урока/Субтитры_полного_урока.srt).
- [Главная обложка YouTube, 9:16](../03_Площадки/YouTube/Обложки/Главная_обложка_9x16.jpg) и [вариант 16:9](../03_Площадки/YouTube/Обложки/Обложка_16x9.jpg).
- [Короткие ролики](../01_Видео): «Пин и доска» и «Куда ведёт ссылка». Мысль и озвучка в каждом фрагменте закончены; подсветка слов сохранена.

## Папки площадок

| Папка | Содержимое |
| --- | --- |
| [YouTube](../03_Площадки/YouTube) | Полный урок, две обложки, название, описание, задание, SRT |
| [Rutube](../03_Площадки/Rutube) | Полный урок, обложка, название, описание, задание, SRT |
| [VK Видео](../03_Площадки/VK_Видео) | Полный урок, обложка, название, описание, пост и задание, SRT |
| [VK Клипы](../03_Площадки/VK_Клипы) | Два коротких видео, две обложки, названия, описания, тексты и SRT |
| [Pinterest](../03_Площадки/Pinterest) | Два пина: изображения, названия, описания, альтернативный текст |
| [Instagram](../03_Площадки/Instagram) | Два коротких видео с обложками, карусель из трёх карточек, тексты |
| [Threads](../03_Площадки/Threads) | Два отдельных текста и необязательная карточка задания |

В каждой папке площадки — обычные файлы, без ярлыков. Папку можно перенести отдельно: медиа останутся внутри неё. Тексты для копирования лежат в `Тексты`; инструкции, источники и журнал — только в `04_Документы`.

## Выпуск

Новые обложки, короткие фрагменты и карточки подготовлены к просмотру; их отдельного одобрения ещё нет. Каждый пин одобряется отдельно по изображению, текстам и конечной ссылке. [Порядок выпуска](Порядок_выпуска.md). Адреса ещё не опубликованных уроков не придуманы: [таблица ссылок](Ссылки_на_публикации.csv).

Следующий шаг — посмотреть обложки и пины, затем загрузить полный урок с доступом «по ссылке» для первого теста. На площадки из этой сборки ничего не отправлялось.''')
    write(DOCS / 'Порядок_выпуска.md', '''# Как выпускать урок 1

1. Посмотреть две обложки YouTube, два коротких ролика, оба пина и карусель Instagram. Полное видео уже одобрено; для каждого пина записать отдельное одобрение конкретного изображения, текстов и конечного URL.
2. На YouTube загрузить файл из `YouTube/Видео`, поставить название и описание из `YouTube/Тексты`. Для первого теста выбрать доступ «по ссылке». Вертикальные видео до трёх минут относятся к Shorts; для этого урока основной значок — `Главная_обложка_9x16.jpg`. По текущей справке свой значок Shorts загружается в Studio на компьютере после подтверждения аккаунта. Вариант 16:9 сохранён отдельно. [Классификация](https://support.google.com/youtube/answer/15424877?hl=en), [значки](https://support.google.com/youtube/answer/72431?hl=ru).
3. Загрузить тот же полный урок в Rutube и VK Видео. Медиа, обложка и тексты уже лежат в соответствующих папках. После обработки открыть страницы и проверить воспроизведение, звук и титры на телефоне. На Rutube учесть модерацию. [Загрузка Rutube](https://rutube.ru/info/upload/).
4. Записать реальные адреса в `Ссылки_на_публикации.csv`. Если в описании нужен адрес урока, добавить только проверенный адрес опубликованной страницы. В готовых текстах нет вымышленных ссылок на урок или неподтверждённого «смотрите в профиле».
5. Первый короткий ролик и пин 01 можно выпустить после полного урока; затем текст Threads 01; следующим выходом — второй ролик, пин 02, карусель и текст Threads 02. Даты выбрать после теста, не выпускать всё автоматически в один день.
6. Для VK Клипов вести к версии в VK Видео доступным в аккаунте способом. В Instagram сначала проверить, где доступно размещение ссылки, и только затем добавить призыв к переходу. Для обоих пинов конечный адрес — реальный первый урок; ссылка должна соответствовать обещанию изображения и описания.
7. При загрузке клипов и обложек посмотреть предпросмотр: кнопки площадки не должны закрывать титры, название или BK. Размеры файлов — наши рабочие параметры; действующую обрезку интерфейса проверяем в аккаунте.
8. Открыть каждую опубликованную страницу, проверить видео/изображение, название и ссылку, затем отметить это в `Журнал_выпуска.csv`. Через 7 и 28 дней после фактической публикации записать доступную статистику и вопросы зрителей.

У первого теста есть короткий [лист вопросов](Тест_урока.md). Подготовка файлов не означает загрузку или публикацию.''')
    write(DOCS / 'Тест_урока.md', '''# Первый тест урока

После загрузки с доступом «по ссылке» владелец курса приглашает 3–5 новичков. Ссылка не приватная: получатель может переслать её.

Попросить посмотреть с телефона и ответить:
1. Хорошо ли читаются заголовки и титры? Ничего не обрезается?
2. Понятно ли без перемотки, чем пин отличается от доски?
3. Какая страница должна открыться по ссылке из пина о статье?
4. Получилось ли найти три пина и закончить фразу из задания?
5. В каком месте стало непонятно или захотелось закрыть видео?

Записать конкретный момент видео и ответ. Небольшой тест помогает найти непонятные места; спрос на весь курс по нему не оцениваем.''')
    write(DOCS / 'Источники_и_оформление.md', '''# Источники и оформление

Сборка от 4 октября 2026 года. Исходный урок — 1.1 файла `pinterest_course_russian_final.md`; озвучка — предоставленный владельцем WAV Fenrir `voice-russian-male-fenrir (фенрир)-1791083562532.wav`.

Оформление: утверждённый латинский BK с шапочкой и названием BOOSTKLIENT, Manrope, светлый фон #f1eee6, тёмный #171b20, коралловый акцент. В верхнем левом углу нет красной надписи Pinterest. Обложки и карточки собраны локально из типографики, фотографий и схем; дополнительных генераций и платных вызовов нет. Анна использована только портретом из утверждённого изображения; она — вымышленная героиня курса.

Материалы для содержания:
- [Pinterest: пины, доски и поиск](https://help.pinterest.com/en/guide/all-about-pinterest).
- [Создание пинов и добавление ссылки](https://help.pinterest.com/en/guide/guide-to-creating-pins).

Фотографии:
- Justin Kauffman: [рабочее место с лампой](https://unsplash.com/photos/powered-on-desk-lamp-near-laptop-computer-fpoHihXiMhg).
- ergonofis: [светлый рабочий стол](https://unsplash.com/photos/a-white-desk-with-a-laptop-on-top-of-it-hPCFOFtmNls).
- [Лицензия Unsplash](https://unsplash.com/license). Сохраняем указание источников в этой папке.

Шрифт Manrope — SIL Open Font License; буквы BK и BOOSTKLIENT переведены в контуры из Oswald, также OFL. Шапочка адаптирована из [Lucide graduation-cap](https://lucide.dev/icons/graduation-cap), ISC. Тексты лицензий — в папке `Лицензии`.

Форматы изображений:
- Главная обложка YouTube Shorts: 2160×3840; дополнительная 16:9: 3840×2160. Это рекомендации из [справки YouTube](https://support.google.com/youtube/answer/72431?hl=ru), просмотренной при сборке. Все JPEG меньше 2 МБ.
- Обложки Rutube и VK Видео: 1920×1080. Обложки коротких роликов: 1080×1920. Карусель: 1080×1350. Это выбранные размеры исходников, не заявление о проверенной загрузке в аккаунт.
- Пины: 1000×1500, 2:3; [Pinterest Business рекомендует это соотношение для стандартных изображений](https://business.pinterest.com/en-gb/creative-best-practices/).

Полный MP4 — точная копия одобренной версии 5. Фрагменты: 00:33–00:45 и 01:06,400–01:24,000. Подсветка слов встроена в видео. В исходном полном ролике 23 временные отметки слов приблизительные; остальные перенесены из распознавания. SRT содержит обычные субтитры, без цветной подсветки. Загрузку SRT используем, если она доступна в нужном редакторе; сами титры уже встроены.''')
    for name, source in [('Manrope_OFL.txt', PUBLIC / 'Manrope-OFL.txt'),
                         ('Oswald_OFL.txt', BRAND / 'OFL-Oswald.txt'),
                         ('Lucide_ISC.txt', BRAND / 'LICENSE-Lucide.txt')]:
        copy(source, DOCS / 'Лицензии' / name)
    write(DOCS / 'Задание_ученику.txt', '''Урок 1. Что такое Pinterest

Найдите три пина по теме своего проекта.
Для каждого ответьте:
— Что привлекло внимание?
— Что хочется сохранить?
— Куда ведёт ссылка?

Затем закончите фразу:
«В своём пине я покажу… А по ссылке человек найдёт…».

Получилась первая заготовка для публикации.''')
    csv_file(DOCS / 'Ссылки_на_публикации.csv',
             ['Площадка', 'Материал', 'URL', 'Примечание'],
             [[p, 'Урок 01', '', 'Заполнить после загрузки и проверки страницы'] for p in ['YouTube', 'Rutube', 'VK Видео']] +
             [['Pinterest', f'Пин {i:02}: конечный адрес', '', 'Указать реальный первый урок до отдельного одобрения пина'] for i in [1, 2]])
    rows = [[p, 'Урок 01', 'копия утверждённой версии 5', 'Видео одобрено; оформление подготовлено', '', '', '', '', '', ''] for p in ['YouTube', 'Rutube', 'VK Видео']]
    rows += [[p, c['title'], 'фрагмент финального видео', 'Подготовлен; отдельно не одобрен', '', '', '', '', '', ''] for p in ['VK Клипы', 'Instagram'] for c in CLIPS]
    rows += [['Pinterest', f'Пин {i:02}', '01', 'Подготовлен; требуется отдельное одобрение изображения, текстов и конечного URL', '', '', '', '', '', ''] for i in [1, 2]]
    rows += [['Instagram', 'Карусель задания', '01', 'Подготовлена; отдельно не одобрена', '', '', '', '', '', '']]
    rows += [['Threads', f'Пост {i:02}', '01', 'Подготовлен; отдельно не одобрен', '', '', '', '', '', ''] for i in [1, 2]]
    csv_file(DOCS / 'Журнал_выпуска.csv', ['Площадка', 'Материал', 'Версия', 'Статус', 'Дата одобрения', 'Дата публикации', 'URL', 'Проверка страницы', 'Статистика +7 дней', 'Статистика +28 дней'], rows)


def graphic_html(width, height, content):
    # Local code-native layouts, with absolute geometry matching the approved series.
    return f'''<!doctype html><html lang="ru"><meta charset="utf-8"><style>
    @font-face{{font-family:Manrope;src:url('{(PUBLIC/'Manrope.ttf').as_uri()}');font-weight:200 800}}
    *{{box-sizing:border-box}}html,body{{margin:0;width:{width}px;height:{height}px;overflow:hidden}}
    body{{position:relative;background:#f1eee6;color:#171b20;font-family:Manrope,sans-serif}}
    .at{{position:absolute}}.headline{{font-weight:750;line-height:1.08;letter-spacing:-3px;overflow-wrap:break-word}}
    .photo{{object-fit:cover}}.muted{{color:#6f7476}}.coral{{color:#cd4e3d}}
    .foot{{position:absolute;background:#171b20;color:#f1eee6;left:0;right:0}}
    .row{{display:flex;align-items:center;gap:30px}}.label{{font-weight:650}}
    </style><body>{content}</body></html>'''


def at(text, x, y, width, size, classes='', extra=''):
    return f'<div class="at {classes}" style="left:{x}px;top:{y}px;width:{width}px;font-size:{size}px;{extra}">{text}</div>'


def image(path, x, y, w, h, extra=''):
    return f'<img class="at photo" src="{path.as_uri()}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;{extra}">'


def logo(x=70, y=45, w=320):
    return image(BRAND / 'boostklient-education-corner.svg', x, y, w, w*96/280, 'object-fit:contain')


def pin_board(y, width=920, x=80):
    # A real photograph in one pin and a photo collection; no simulated app chrome.
    unit = width * .37
    out = at('ПИН', x, y, unit, 36, 'label')
    out += image(PUBLIC/'workspace-warm.jpg', x, y+65, unit, 340, 'border-radius:20px')
    out += at('→', x+unit+14, y+200, 90, 70, 'coral')
    bx = x + unit + 114
    bw = width - unit - 114
    out += at('ДОСКА', bx, y, bw, 36, 'label')
    for i in range(4):
        out += image(PUBLIC / ('workspace-warm.jpg' if i%3==0 else 'workspace-light.jpg'), bx+(i%2)*(bw/2+7), y+65+(i//2)*177, bw/2-7, 163, 'border-radius:15px')
    return out


def prepare_graphics():
    BUILD.mkdir(parents=True, exist_ok=True)
    jobs = []
    def add(name, w, h, body, targets, scale=1):
        source = BUILD / f'{name}.html'
        write(source, graphic_html(w, h, body))
        jobs.append({'source': str(source), 'width': w, 'height': h, 'scale': scale,
                     'targets': [str(p) for p in targets]})

    landscape = logo(70, 42, 365) + at('УРОК 01', 1520, 80, 280, 34, 'muted label', 'text-align:right')
    landscape += at('Pinterest<br>с нуля', 80, 260, 1050, 160, 'headline')
    landscape += at('Пины, доски<br>и ссылки', 85, 652, 1060, 62, 'label')
    landscape += image(PUBLIC/'workspace-warm.jpg', 1220, 215, 610, 590, 'border-radius:24px')
    landscape += '<div class="foot" style="top:890px;height:190px;padding:47px 80px;font-size:52px;font-weight:650">Первый урок. Первая идея для вашего проекта.</div>'
    add('cover-landscape',1920,1080,landscape,[PLATFORMS/'YouTube/Обложки/Обложка_16x9.jpg'],2)
    add('cover-video-sites',1920,1080,landscape,[PLATFORMS/f'{p}/Обложки/Обложка_урока.jpg' for p in ['Rutube','VK_Видео']])

    vertical = logo(80,65,350) + at('УРОК 01',760,115,240,32,'muted label','text-align:right')
    vertical += at('Pinterest<br>с нуля',80,300,920,140,'headline')
    vertical += at('Пины, доски и ссылки',85,647,900,49,'label')
    vertical += image(PUBLIC/'workspace-warm.jpg',80,795,920,570,'border-radius:24px')
    vertical += '<div class="foot" style="top:1480px;height:440px;padding:90px 80px;font-size:72px;font-weight:700;line-height:1.18">Начните<br>с первого урока</div>'
    add('cover-youtube-vertical',1080,1920,vertical,[PLATFORMS/'YouTube/Обложки/Главная_обложка_9x16.jpg'],2)

    for i, clip in enumerate(CLIPS):
        content=logo(80,70,350)+at('УРОК 01',760,120,240,32,'muted label','text-align:right')
        if i == 0:
            content+=at('Пин и доска:<br>в чём<br>разница?',80,340,920,114,'headline')
            content+=pin_board(900)
            footer='Один пин.<br>Целая подборка.'
        else:
            content+=at('Куда ведёт<br>ссылка<br>из пина?',80,340,920,114,'headline')
            for j,(a,b) in enumerate([('Идеи','Статья с идеями'),('Товар','Карточка товара')]):
                content+=at(f'<span style="width:230px;display:inline-block">{a}</span><span class="coral" style="margin-right:32px">→</span>{b}',80,915+j*220,920,46,'label','background:white;border-radius:22px;padding:48px 34px')
            footer='Что обещали —<br>туда и ведём.'
        content+=f'<div class="foot" style="top:1480px;height:440px;padding:90px 80px;font-size:70px;font-weight:700;line-height:1.2">{footer}</div>'
        add(f"clip-cover-{i+1}",1080,1920,content,[PLATFORMS/f"{p}/Обложки/{clip['name']}_обложка.jpg" for p in ['VK_Клипы','Instagram']])

    pin_a = logo(65,35,325) + at('УРОК 01',725,92,210,28,'muted label','text-align:right')
    pin_a += at('Pinterest<br>для начала',65,250,870,114,'headline')
    pin_a += at('Пины, доски и ссылки',70,560,860,45,'label')
    pin_a += image(PUBLIC/'workspace-warm.jpg',65,710,870,490,'border-radius:24px')
    pin_a += '<div class="foot" style="top:1280px;height:220px;padding:48px 65px;font-size:44px;font-weight:700;line-height:1.3">Идея → пин → продолжение<br><span style="font-size:31px;font-weight:500">Разбор в первом уроке</span></div>'
    add('pin-01',1000,1500,pin_a,[PLATFORMS/'Pinterest/Пин_01/Изображение.jpg'])

    pin_b=logo(65,35,325)+at('УРОК 01',725,92,210,28,'muted label','text-align:right')
    pin_b+=at('Ваш пин.<br>Что дальше?',65,230,870,116,'headline')
    pin_b+=at('От идеи рабочего стола<br>к статье в блоге',70,540,860,43,'label')
    pin_b+=f'<div class="at" style="left:70px;top:720px;width:140px;height:140px;border-radius:50%;overflow:hidden"><img src="{(PUBLIC/"anna-reference.png").as_uri()}" style="position:absolute;width:368px;left:-112px;top:-102px"></div>'
    pin_b+=at('Пример Анны',245,728,660,42,'label')
    pin_b+=at('Вымышленная героиня курса',245,792,660,29,'muted')
    pin_b+=image(PUBLIC/'workspace-warm.jpg',65,915,870,285,'border-radius:22px')
    pin_b+='<div class="foot" style="top:1280px;height:220px;padding:48px 65px;font-size:46px;font-weight:700;line-height:1.3">Идея → статья с идеями<br><span style="font-size:31px;font-weight:500">Проверьте продолжение по ссылке</span></div>'
    add('pin-02',1000,1500,pin_b,[PLATFORMS/'Pinterest/Пин_02/Изображение.jpg'])

    base=logo(70,40,330)+at('УРОК 01',760,95,245,29,'muted label','text-align:right')
    first=base+at('Pinterest:<br>с чего начать?',70,270,940,110,'headline')
    for i,(a,b) in enumerate([('01','Найдите три пина'),('02','Сравните идеи и ссылки'),('03','Сформулируйте свой пин')]):
        first+=at(f'<span class="coral" style="margin-right:25px">{a}</span>{b}',70,645+i*155,940,48,'label','border-top:2px solid #ccc8bf;padding-top:28px')
    first+='<div class="foot" style="top:1190px;height:160px;padding:45px 70px;font-size:43px;font-weight:650">Задание первого урока · 1/3</div>'
    add('carousel-01',1080,1350,first,[PLATFORMS/'Instagram/Карусель/01_С_чего_начать.jpg'])
    second=base+at('Один пин.<br>Целая доска.',70,270,940,110,'headline')+pin_board(690,940,70)
    second+='<div class="foot" style="top:1190px;height:160px;padding:45px 70px;font-size:43px;font-weight:650">Сохраните идеи по теме · 2/3</div>'
    add('carousel-02',1080,1350,second,[PLATFORMS/'Instagram/Карусель/02_Пин_и_доска.jpg'])
    third=base+at('Идея вашего<br>первого пина',70,245,940,105,'headline')
    third+=at('В своём пине<br>я покажу…',70,580,940,62,'label','background:white;border-radius:22px;padding:35px 40px;line-height:1.2')
    third+=at('А по ссылке<br>человек найдёт…',70,835,940,62,'label','background:white;border-radius:22px;padding:35px 40px;line-height:1.2')
    third+='<div class="foot" style="top:1190px;height:160px;padding:45px 70px;font-size:43px;font-weight:650">Сохраните и заполните · 3/3</div>'
    add('carousel-03',1080,1350,third,[PLATFORMS/'Instagram/Карусель/03_Заготовка_пина.jpg',PLATFORMS/'Threads/Изображения/Карточка_задания.jpg'])
    write(BUILD / 'graphics.json', json.dumps(jobs,ensure_ascii=False,indent=2))
    write(BUILD / 'clips.json', json.dumps(CLIPS,ensure_ascii=False,indent=2))


def render_clips():
    for clip in CLIPS:
        target = LESSON / f"01_Видео/{clip['name']}.mp4"
        command = ['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                   '-threads','1','-ss',str(clip['start']),'-i',str(SOURCE/'lesson-1.1-vertical-v5.mp4'),
                   '-t',str(clip['end']-clip['start']),'-map','0:v:0','-map','0:a:0',
                   '-c:v','libx264','-preset','veryfast','-crf','19','-threads','1',
                   '-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(target)]
        subprocess.run(command,check=True)
        subprocess.run(['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-v','error','-threads','1',
                        '-i',str(target),'-f','null','-'],check=True)
        for p in ['VK_Клипы','Instagram']:
            copy(target, PLATFORMS / f"{p}/Видео/{clip['name']}.mp4")
        print(f"{clip['name']}: {clip['end']-clip['start']:.1f} seconds; decode passed",flush=True)


def verify_package():
    import hashlib
    from PIL import Image
    def sha(path):
        return hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
    expected_video = sha(SOURCE/'lesson-1.1-vertical-v5.mp4')
    for path in [LESSON/'01_Видео'/VIDEO_NAME] + [PLATFORMS/f'{p}/Видео/{VIDEO_NAME}' for p in ['YouTube','Rutube','VK_Видео']]:
        assert sha(path)==expected_video, f'Full video differs: {path}'
    expected_text = (ROOT/'docs/pinterest-course/урок-1.1-озвучка.txt').read_text()
    assert (LESSON/'02_Текст_урока/Текст_озвучки.txt').read_text()==expected_text
    for job in json.loads((BUILD/'graphics.json').read_text()):
        expected_size=(job['width']*job['scale'],job['height']*job['scale'])
        for target in map(Path,job['targets']):
            with Image.open(target) as im:
                assert im.size==expected_size,(target,im.size,expected_size)
                im.verify()
            assert 0 < target.stat().st_size < 2_000_000
    for clip in CLIPS:
        source=LESSON/f"01_Видео/{clip['name']}.mp4"
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name,width,height','-of','json',str(source)]))
        assert abs(float(info['format']['duration'])-(clip['end']-clip['start']))<.08
        assert info['streams'][0]['width']==1080 and info['streams'][0]['height']==1920
        assert [s['codec_name'] for s in info['streams']]==['h264','aac']
        for p in ['VK_Клипы','Instagram']:
            assert sha(source)==sha(PLATFORMS/f"{p}/Видео/{clip['name']}.mp4")
    pins=[]
    for i in [1,2]:
        p=PLATFORMS/f'Pinterest/Пин_{i:02}'
        assets=[p/'Изображение.jpg']+sorted((p/'Тексты').glob('*.txt'))
        fingerprint=hashlib.sha256(''.join(sha(f) for f in assets).encode()).hexdigest()
        pins.append([f'Пин {i:02}','01',fingerprint,'','Ожидает отдельного одобрения; конечный URL ещё не выбран'])
    csv_file(DOCS/'Версии_пинов.csv',['Пин','Версия','SHA256 изображения и текстов','Конечный URL','Статус'],pins)
    write(DOCS/'Одобрение_пинов.md', '''# Два отдельных пина

Посмотреть изображение и три текста в каждой папке `Pinterest/Пин_01` и `Pinterest/Пин_02`. Это две разные публикации; одобрение полного урока к ним не относится.

В `Версии_пинов.csv` записаны версия 01 и контрольная сумма её изображения и текстов. Ссылка пока не выбрана. До публикации добавить реальный адрес первого урока, проверить открываемую страницу и отдельно одобрить каждый полный комплект: изображение, название, описание, альтернативный текст и конечный адрес. Изменение любого элемента после одобрения требует новой проверки этого пина.''')
    files=sorted(p for p in LESSON.rglob('*') if p.is_file())
    assert not any(p.is_symlink() for p in files)
    assert not any(p.suffix in ['.log','.html','.json'] or 'draft' in p.name or '-v4' in p.name for p in files)
    assert set(p.name for p in PLATFORMS.iterdir())=={'YouTube','Rutube','VK_Видео','VK_Клипы','Pinterest','Instagram','Threads'}
    summary={'fullVideoSHA256':expected_video,'files':len(files),'bytes':sum(p.stat().st_size for p in files),'platforms':7,'clipsSeconds':[12.0,17.6],
             'fullVideoExactCopy':True,'narrationExactCopy':True,'allGraphicDimensionsChecked':True,'allClipsDecoded':True}
    write(BUILD/'verification.json',json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    if '--clips' in sys.argv:
        render_clips()
    elif '--verify' in sys.argv:
        verify_package()
    else:
        prepare_texts()
        prepare_docs()
        prepare_graphics()
        print(LESSON)
