"""Local publishing kit for lesson 1.2. Voice-dependent files are added separately."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from pinterest_course_release import ROOT, COURSE, PUBLIC, BRAND, at, image, logo, graphic_html, write, copy, csv_file

LESSON=COURSE/'Урок_02_Поиск_и_рекомендации'
PLATFORMS=LESSON/'03_Площадки'
DOCS=LESSON/'04_Документы'
BUILD=ROOT/'artifacts/pinterest-course/release-build-lesson2'
VIDEO=ROOT/'artifacts/pinterest-course/lesson-1.2-vertical-v1'
TEXT=ROOT/'docs/pinterest-course/урок-1.2-озвучка.txt'
DATA=PUBLIC/'lesson-1.2/data.json'
VIDEO_NAME='Урок_02_Поиск_и_рекомендации.mp4'
CLIPS=[('Клип_01_Как_уточнить_запрос','Как уточнить запрос в Pinterest?',1,2),
       ('Клип_02_Лента_не_показывает_весь_спрос','Ваша лента — не весь Pinterest',2,4)]
SITES=['YouTube','Rutube','VK_Видео','VK_Клипы','Pinterest','Instagram','Threads']


def prepare_texts():
    paragraphs=TEXT.read_text().strip().split('\n\n')
    copy(TEXT,LESSON/'02_Текст_урока/Текст_озвучки.txt')
    for name,title,a,b in CLIPS:
        write(LESSON/f'02_Текст_урока/{name}_текст.txt','\n\n'.join(paragraphs[a:b]))
    write(LESSON/'02_Текст_урока/Текст_на_слайдах.txt', '''Урок 1.2 · Поиск и рекомендации
Общее оформление: BK / BOOSTKLIENT; УРОК 1.2; номер сцены из 7.

СЛАЙД 1 — Ищем решение, а не просто картинку
Анна — вымышленная героиня курса
Задача: организовать маленький стол
Учебный пример · фотография Unsplash

СЛАЙД 2 — Уточните, что ищете
От общей темы к конкретной задаче
01 Рабочее место дома
02 Хранение на столе
03 Хранение на маленьком столе
Посмотрите доступные уточнения и фильтры
Учебная схема · спрос не измерен

СЛАЙД 3 — Поиск и лента: две разные задачи
ПОИСК — Вы задаёте вопрос
Запрос → связанные идеи
ЛЕНТА — Подборка для вас
Сохранения · запросы · просмотры
В ленте также есть материалы подписок
Учебная схема

СЛАЙД 4 — Ваша лента — не весь Pinterest
Анна — вымышленная героиня курса
В ПРИМЕРЕ АННА СОХРАНЯЛА РЕЦЕПТЫ
В её ленте может быть много еды
Моя лента ≠ интересы всех
Идеи для рабочего места продолжаем искать по своей теме

СЛАЙД 5 — Поиск по изображению
Изображение или объект → похожие идеи
Инструмент доступен не на каждом пине.
Проверьте своё устройство.
Учебная схема визуального поиска

СЛАЙД 6 — Какие вопросы раскрывают пины?
1 Какую задачу раскрывает пин?
2 Что пригодится вашему проекту?
3 Что человек найдёт по ссылке?
Запишите вопрос для своего материала

СЛАЙД 7 — Три запроса. Одна тема.
3 запроса
По одной теме вашего проекта
1 Сравните найденные идеи
2 Запишите три вопроса
3 Выберите один для своего пина
Моя тема…
Мой запрос…
Я отвечу на вопрос…''')
    title='Поиск и рекомендации в Pinterest: как находить идеи | Урок 2'
    description='''Второй урок курса BoostKlient «Pinterest для начинающих».

Разбираем поиск по словам, уточнение запроса, личную ленту и визуальный поиск. На учебном примере Анны объясняем, почему рекомендации одного аккаунта не показывают интересы всех пользователей. Анна — вымышленная героиня курса.

Задание: попробуйте три запроса по одной теме. Сравните найденные идеи, запишите три вопроса, которые раскрывают пины, и выберите один для своей публикации.

Формулировки в уроке — примеры для упражнения. Популярность этих запросов здесь не измерена.

Официальная справка:
https://help.pinterest.com/en/article/search-for-ideas-on-pinterest
https://help.pinterest.com/en/article/tune-your-home-feed
https://help.pinterest.com/en/article/use-visual-search-features'''
    for p in ['YouTube','Rutube','VK_Видео']:
        (PLATFORMS/p/'Видео').mkdir(parents=True,exist_ok=True)
        write(PLATFORMS/p/'Тексты/Название.txt',title)
        write(PLATFORMS/p/'Тексты/Описание.txt',description+('\n\n#Pinterest #Пинтерест #Обучение' if p=='YouTube' else ''))
        write(PLATFORMS/p/'Тексты/Комментарий_с_заданием.txt','Попробуйте три запроса по одной теме. Какие три вопроса раскрывают найденные пины? На какой из них вы готовы ответить своим материалом?')
    write(PLATFORMS/'VK_Видео/Тексты/Пост_к_видео.txt','''Почему в вашей ленте Pinterest не то, что вы ищете?

Во втором уроке разбираем поиск и рекомендации. Покажем, как уточнить запрос и выбрать вопрос для своего пина.

Напишите тему проекта и один вопрос, на который хотите ответить.''')
    captions=[
        'Начните с общей темы, затем уточните задачу. «Рабочее место дома» → «Хранение на столе» → «Хранение на маленьком столе». Посмотрите доступные уточнения и фильтры.\n\nЭто примеры для упражнения; популярность запросов здесь не измерена. Как бы вы уточнили свою тему?',
        'Поиск начинается с вашего запроса. Лента предлагает рекомендации для аккаунта: учитываются сохранения, поиски и просмотры.\n\nЕсли вы сохраняли рецепты, в ленте может быть много еды. Это не показывает интересы всех пользователей. Продолжайте искать по теме своего проекта.',
    ]
    for p in ['VK_Клипы','Instagram']:
        (PLATFORMS/p/'Видео').mkdir(parents=True,exist_ok=True)
        for i,(name,title,a,b) in enumerate(CLIPS):
            write(PLATFORMS/p/f'Тексты/{name}_название.txt',title)
            write(PLATFORMS/p/f'Тексты/{name}_описание.txt',captions[i]+('\n\n#Pinterest #Пинтерест' if p=='Instagram' else ''))
            write(PLATFORMS/p/f'Тексты/{name}_текст_озвучки.txt','\n\n'.join(paragraphs[a:b]))
    write(PLATFORMS/'Instagram/Тексты/Карусель_описание.txt','''Как искать идеи для своего проекта в Pinterest?

Выберите одну тему и попробуйте три запроса: от общего к более конкретному. Сравните найденные пины и запишите три вопроса, которые они раскрывают.

Выберите один вопрос для своей публикации. Заполните: «Моя тема… Мой запрос… Я отвечу на вопрос…».

Личная лента не измеряет интересы всех пользователей. Наши примеры запросов — упражнение, а не данные о спросе.

#Pinterest #Пинтерест''')
    pins=[
        ('Как искать идеи в Pinterest: три запроса по одной теме',
         'Начните с темы своего проекта и уточните задачу. Во втором уроке BoostKlient разбираем поиск, фильтры и личную ленту. Задание: попробовать три запроса, сравнить идеи и выбрать вопрос для своего пина. Популярность примеров не измерена.',
         'Учебная карточка BoostKlient «Как искать идеи?». Три формулировки: рабочее место дома, хранение на столе, хранение на маленьком столе. Второй урок; примеры для упражнения.'),
        ('Ваша лента Pinterest не показывает интересы всех',
         'Поиск начинается с вашего запроса, а лента предлагает подборку для аккаунта. На учебном примере Анны разбираем, почему рецепты в личной ленте не означают отсутствие интереса к рабочему месту. Второй урок о поиске и рекомендациях. Анна — вымышленная героиня курса.',
         'Карточка BoostKlient «Ваша лента — не весь Pinterest». Портрет Анны и схема: сохранения, поиски и просмотры → личная подборка. Анна обозначена как вымышленная героиня курса.'),
    ]
    for i,(title,desc,alt) in enumerate(pins,1):
        assert len(title)<=100 and len(desc)<=500
        p=PLATFORMS/f'Pinterest/Пин_{i:02}/Тексты'
        for filename,text in [('Название.txt',title),('Описание.txt',desc),('Альтернативный_текст.txt',alt)]:write(p/filename,text)
    posts=[
        'В Pinterest поиск и лента решают разные задачи. В поиске вы формулируете вопрос. Лента предлагает подборку для аккаунта с учётом вашей активности.\n\nЕсли вы сохраняли рецепты, в ленте может быть много еды. Это не означает, что идеи рабочего места никому не нужны.\n\nКакую тему попробуете найти через строку поиска?',
        'Попробуйте три запроса по одной теме: от общего к конкретному.\n\nНапример: «рабочее место дома» → «хранение на столе» → «хранение на маленьком столе». Это примеры для упражнения; их популярность здесь не измерена.\n\nКакие вопросы раскрывают найденные пины? Выберите один, на который сможете ответить своим материалом.',
    ]
    for i,text in enumerate(posts,1):
        assert len(text)<=500
        write(PLATFORMS/f'Threads/Тексты/Пост_{i:02}.txt',text)


def prepare_docs():
    write(DOCS/'Что_где_лежит.md','''# Урок 2 · Поиск и рекомендации

Источник: урок 1.2 курса. Тот же утверждённый формат, что у первого ролика: вертикальное видео, BK / BOOSTKLIENT, Manrope, фотографии и учебные схемы, Анна тем же портретом, титры с подсветкой звучащего слова.

## Готово

- [Чистый текст для озвучки Fenrir](../02_Текст_урока/Текст_озвучки.txt): семь абзацев. Озвучивать целиком, без названий файлов и служебных пометок.
- [Текст слайдов](../02_Текст_урока/Текст_на_слайдах.txt).
- [Слайды](../05_Слайды): визуальная подготовка сцен. До новой озвучки нижнее поле показывает примеры размещения текста; подсветка появится по реальным таймингам WAV.
- [Главная обложка YouTube](../03_Площадки/YouTube/Обложки/Главная_обложка_9x16.jpg), [обложка 16:9](../03_Площадки/YouTube/Обложки/Обложка_16x9.jpg).
- [Материалы площадок](../03_Площадки): YouTube, Rutube, VK Видео, VK Клипы, Pinterest, Instagram, Threads. Внутри — отдельные обложки, тексты, два пина и три карточки Instagram.

## Осталось по голосу

Новый WAV второго урока ещё не предоставлен. Поэтому полного MP4, коротких MP4 и SRT пока нет. Голос первого урока здесь не подходит. После WAV определим длительность, разметим слова, соберём видео и два коротких фрагмента, проверим кадры и декодирование и добавим файлы в `01_Видео` и папки площадок.

Каждый пин — отдельный комплект для одобрения изображения, текстов и конечной ссылки. Адреса публикаций пока пустые. Файлы не отправлялись на площадки.''')
    write(DOCS/'Порядок_выпуска.md','''# Выпуск второго урока

1. Озвучить семь абзацев из `02_Текст_урока/Текст_озвучки.txt` голосом Fenrir, как в первом уроке. Сохранить WAV в «Загрузки» и сообщить его имя.
2. После сборки посмотреть полный ролик, короткие фрагменты, обложки, два пина и карусель. У каждого пина отдельно проверить изображение, три текста и реальный конечный URL.
3. Загрузить полный урок в YouTube, Rutube и VK Видео. Названия, описания и обложки лежат в папках площадок. Если вертикальный ролик после озвучки окажется не длиннее трёх минут, YouTube относит его к Shorts; основной значок — 9:16. [Справка YouTube](https://support.google.com/youtube/answer/15424877?hl=en), [значки](https://support.google.com/youtube/answer/72431?hl=ru).
4. Проверить обработанные видео на телефоне. Записать реальные адреса в таблицу ссылок. Добавить ссылки между первым и вторым уроками только после проверки страниц.
5. Выходить постепенно: первый короткий ролик + пин 01 → пост Threads 01 → второй короткий ролик + пин 02 → карусель + пост Threads 02. Конкретные даты выбрать после просмотра и теста.
6. Для VK Клипов вести к уроку в VK Видео доступным в аккаунте способом. Для Instagram сначала проверить способ размещения ссылки. У пинов конечная ссылка должна вести ко второму уроку или странице его выбора.
7. Открыть каждую опубликованную страницу, проверить изображение/видео и ссылки, записать результат в журнал. Наличие файла на компьютере не означает публикацию.

Ссылки на первый и второй урок пока не вставлены в тексты для копирования: их реальные адреса ещё неизвестны.''')
    write(DOCS/'Задание_ученику.txt','''Урок 2 · Поиск и рекомендации

Моя тема:

Три запроса по этой теме:
1.
2.
3.

Сравните найденные пины. Какие вопросы они раскрывают?
1.
2.
3.

Один вопрос для моей публикации:

Вопросы для разбора: какую задачу раскрывает пин; что пригодится вашему проекту; что человек найдёт по ссылке.

Предложенные в уроке запросы — примеры для упражнения, не измерение популярности.''')
    write(DOCS/'Источники_и_оформление.md','''# Источники и оформление

Источник — урок 1.2 файла `pinterest_course_russian_final.md`. Сведения проверены по официальной справке Pinterest 4 октября 2026 года:

- [Поиск, уточнения и фильтры](https://help.pinterest.com/en/article/search-for-ideas-on-pinterest).
- [Лента и материалы подписок](https://help.pinterest.com/en/guide/all-about-pinterest).
- [Сохранения, поиски и просмотры для рекомендаций](https://help.pinterest.com/en/article/tune-your-home-feed).
- [Визуальный поиск по изображению и объекту](https://help.pinterest.com/en/article/use-visual-search-features).

Общие элементы из утверждённого первого урока: латинский BK с шапочкой и названием BOOSTKLIENT, Manrope, цвета #f1eee6 / #171b20, коралловый акцент, тот же портрет Анны. В углу нет красной надписи Pinterest.

Поиск и лента показаны учебными схемами. Фотографии иллюстрируют тему, не являются реальными результатами поиска или работами Анны. Примеры запросов не выдаются за измеренный спрос. Анна — вымышленная героиня курса.

Фотографии: [Justin Kauffman](https://unsplash.com/photos/powered-on-desk-lamp-near-laptop-computer-fpoHihXiMhg), [ergonofis](https://unsplash.com/photos/a-white-desk-with-a-laptop-on-top-of-it-hPCFOFtmNls); [лицензия Unsplash](https://unsplash.com/license). Manrope и Oswald — SIL OFL; шапочка — адаптация [Lucide graduation-cap](https://lucide.dev/icons/graduation-cap), ISC. Тексты лицензий сохранены в подпапке.

Пины — 1000×1500; карточки Instagram — 1080×1350; обложки клипов — 1080×1920. Это размеры подготовленных исходников, обрезку интерфейсом проверяем при загрузке. Заставки YouTube — вертикальная 2160×3840 и горизонтальная 3840×2160; [справка по значкам](https://support.google.com/youtube/answer/72431?hl=ru). Длительность второго видео пока не определена: нужна новая озвучка.

Подготовка локальная. Новые платные генерации и внешние публикации не выполнялись.''')
    for name,path in [('Manrope_OFL.txt',PUBLIC/'Manrope-OFL.txt'),('Oswald_OFL.txt',BRAND/'OFL-Oswald.txt'),('Lucide_ISC.txt',BRAND/'LICENSE-Lucide.txt')]:copy(path,DOCS/'Лицензии'/name)
    rows=[[p,'Урок 02','','Заполнить после публикации и проверки'] for p in ['YouTube','Rutube','VK Видео']]
    rows += [['Pinterest',f'Пин {i:02}: конечный адрес','','Указать реальный второй урок до отдельного одобрения пина'] for i in [1,2]]
    csv_file(DOCS/'Ссылки_на_публикации.csv',['Площадка','Материал','URL','Примечание'],rows)
    rows=[[p,'Урок 02','01','Текст и оформление готовы; MP4 ожидает озвучку','','','',''] for p in ['YouTube','Rutube','VK Видео']]
    rows += [[p,name,'01','Текст и обложка готовы; MP4 ожидает озвучку','','','',''] for p in ['VK Клипы','Instagram'] for name,*_ in CLIPS]
    rows += [['Pinterest',f'Пин {i:02}','01','Подготовлен; отдельное одобрение ещё не получено','','','',''] for i in [1,2]]
    rows += [['Instagram','Карусель задания','01','Подготовлена; отдельно не одобрена','','','','']]
    rows += [['Threads',f'Пост {i:02}','01','Подготовлен; отдельно не одобрен','','','',''] for i in [1,2]]
    csv_file(DOCS/'Журнал_выпуска.csv',['Площадка','Материал','Версия','Статус','Дата одобрения','Дата публикации','URL','Проверка страницы'],rows)
    write(DOCS/'Одобрение_пинов.md','''# Отдельное одобрение пинов

Каждый пин — изображение и три текста в своей папке. Одобрение первого видео или общего оформления не заменяет одобрение этих пинов.

В `Версии_пинов.csv` записана контрольная сумма изображения и текстов версии 01. Конечный адрес пока пустой. Перед публикацией выбрать реальную страницу второго урока, проверить её и отдельно одобрить каждый комплект с конечной ссылкой. При изменении элемента после одобрения требуется новая проверка этого пина.''')
    write(DOCS/'Тест_урока.md','''# Проверка второго урока

После сборки и загрузки с доступом «по ссылке» попросить новичка посмотреть с телефона:
1. Чем поиск отличается от главной ленты?
2. Доказывают ли рецепты в личной ленте, что тема рабочего места никому не нужна?
3. Получилось ли попробовать три запроса и выбрать вопрос для своего пина?
4. Всё ли читается, не закрывают ли кнопки титры и BK?
5. В каком месте возник вопрос или захотелось перемотать?

Записать ответ и конкретный момент. Пока ролик не загружен, успешную проверку воспроизведения на площадке не отмечать.''')
    (LESSON/'01_Видео').mkdir(parents=True,exist_ok=True)
    (LESSON/'05_Слайды').mkdir(parents=True,exist_ok=True)


def prepare_preview_data():
    if DATA.exists() and not json.loads(DATA.read_text()).get('preview',False):return
    captions=[['Теперь найдём идеи','для своего проекта.'],['Начните','со строки поиска.'],
              ['В поиске вы','задаёте вопрос.'],['Личная лента —','подборка для аккаунта.'],
              ['Есть и визуальный','поиск.'],['Когда найдёте','подходящие пины,'],['Попробуйте три запроса','по одной теме.']]
    from PIL import ImageFont
    font=ImageFont.truetype(str(PUBLIC/'Manrope.ttf'),74)
    font.set_variation_by_axes([650])
    wrapped=[]
    for lines in captions:
        rows=['']
        for word in ' '.join(lines).split():
            candidate=(rows[-1]+' '+word).strip()
            if rows[-1] and font.getlength(candidate)>850:rows.append(word)
            else:rows[-1]=candidate
        assert len(rows)<=2,rows
        wrapped.append(rows)
    write(DATA,json.dumps({'preview':True,'duration':140,'sceneStarts':list(range(0,141,20)),
                          'previewCaptions':wrapped,'pages':[],'words':[]},ensure_ascii=False,indent=2))


def prepare_graphics():
    BUILD.mkdir(parents=True,exist_ok=True)
    jobs=[]
    def add(name,w,h,body,targets,scale=1):
        source=BUILD/f'{name}.html'
        write(source,graphic_html(w,h,body))
        jobs.append({'source':str(source),'width':w,'height':h,'scale':scale,'targets':[str(p) for p in targets]})
    def footer(top,height,text,size=62,padding='60px 70px'):
        return f'<div class="foot" style="top:{top}px;height:{height}px;padding:{padding};font-size:{size}px;font-weight:700;line-height:1.2">{text}</div>'
    def base(width=1080):return logo(70,45,330)+at('УРОК 02',width-310,98,240,30,'muted label','text-align:right')
    def query_rows(y,width=920,x=80,size=42):
        out=''
        for i,text in enumerate(['Рабочее место дома','Хранение на столе','Хранение на маленьком столе']):
            out+=at(f'<span class="coral" style="margin-right:24px">0{i+1}</span>{text}',x,y+i*155,width,size,'label','background:white;border-radius:20px;padding:35px 30px')
        return out
    landscape=base(1920)+at('Поиск<br>в Pinterest',80,235,1110,145,'headline')
    landscape+=at('Найдите идеи<br>для своей темы',85,635,1070,56,'label')
    landscape+=image(PUBLIC/'workspace-light.jpg',1260,230,565,570,'border-radius:24px')
    landscape+=footer(890,190,'Три запроса. Одна тема. Свой вопрос.',54,'50px 80px')
    add('lesson2-cover-landscape',1920,1080,landscape,[PLATFORMS/'YouTube/Обложки/Обложка_16x9.jpg'],2)
    add('lesson2-cover-sites',1920,1080,landscape,[PLATFORMS/f'{p}/Обложки/Обложка_урока.jpg' for p in ['Rutube','VK_Видео']])
    vertical=base()+at('Поиск<br>в Pinterest',80,300,920,132,'headline')+at('Найдите идеи для своей темы',85,635,920,44,'label')
    vertical+=image(PUBLIC/'workspace-light.jpg',80,780,920,580,'border-radius:24px')+footer(1480,440,'Три запроса.<br>Одна тема.',74,'90px 80px')
    add('lesson2-cover-vertical',1080,1920,vertical,[PLATFORMS/'YouTube/Обложки/Главная_обложка_9x16.jpg'],2)
    first=base()+at('Как уточнить<br>запрос<br>в Pinterest?',80,300,920,110,'headline')+query_rows(900)
    first+=footer(1480,440,'От темы —<br>к вашей задаче',70,'90px 80px')
    second=base()+at('Ваша лента —<br>не весь<br>Pinterest',80,300,920,112,'headline')
    second+=at('Сохранения<br>Поиски<br>Просмотры',80,835,920,61,'label','background:white;border-radius:22px;padding:38px;line-height:1.4')
    second+=at('↓ Личная подборка',80,1230,920,57,'label')+footer(1480,440,'Лента<br>не измеряет спрос',67,'90px 80px')
    for i,content in enumerate([first,second]):
        add(f'lesson2-clip-{i+1}',1080,1920,content,[PLATFORMS/f'{p}/Обложки/{CLIPS[i][0]}_обложка.jpg' for p in ['VK_Клипы','Instagram']])
    pin1=base(1000)+at('Как искать<br>идеи?',65,250,870,120,'headline')+query_rows(650,870,65,40)
    pin1+=footer(1280,220,'Три запроса по одной теме<br><span style="font-size:30px;font-weight:500">Упражнение второго урока</span>',44,'48px 65px')
    add('lesson2-pin-01',1000,1500,pin1,[PLATFORMS/'Pinterest/Пин_01/Изображение.jpg'])
    pin2=base(1000)+at('Ваша лента —<br>не весь<br>Pinterest',65,225,870,107,'headline')
    pin2+=f'<div class="at" style="left:65px;top:650px;width:140px;height:140px;border-radius:50%;overflow:hidden"><img src="{(PUBLIC/"anna-reference.png").as_uri()}" style="position:absolute;width:368px;left:-112px;top:-102px"></div>'
    pin2+=at('Пример Анны',240,660,695,41,'label')+at('Вымышленная героиня курса',240,724,695,29,'muted')
    pin2+=at('Сохранения · поиски · просмотры',65,880,870,38,'label','background:white;border-radius:22px;padding:32px')
    pin2+=at('↓ Личная подборка',65,1070,870,56,'label')+footer(1280,220,'Ищите по теме своего проекта<br><span style="font-size:30px;font-weight:500">Разбор во втором уроке</span>',40,'48px 65px')
    add('lesson2-pin-02',1000,1500,pin2,[PLATFORMS/'Pinterest/Пин_02/Изображение.jpg'])
    card1=base()+at('Одна тема.<br>Три запроса.',70,260,940,112,'headline')+query_rows(650,940,70,43)
    card1+=footer(1190,160,'Уточняйте задачу · 1/3',43,'45px 70px')
    card2=base()+at('Какие вопросы<br>раскрывает пин?',70,270,940,96,'headline')
    for i,text in enumerate(['Какую задачу решает?','Что пригодится проекту?','Что будет по ссылке?']):card2+=at(f'<span class="coral" style="margin-right:25px">{i+1}</span>{text}',70,665+i*150,940,48,'label','border-top:2px solid #ccc8bf;padding-top:28px')
    card2+=footer(1190,160,'Выберите вопрос для своего пина · 2/3',39,'45px 70px')
    card3=base()+at('Теперь<br>ваша заготовка',70,270,940,105,'headline')
    for i,text in enumerate(['Моя тема…','Мой запрос…','Я отвечу на вопрос…']):card3+=at(text,70,650+i*155,940,53,'label','background:white;border-radius:20px;padding:32px 35px')
    card3+=footer(1190,160,'Сохраните и заполните · 3/3',43,'45px 70px')
    for i,content in enumerate([card1,card2,card3],1):
        targets=[PLATFORMS/f'Instagram/Карусель/{i:02}_Карточка_задания.jpg']
        if i==3:targets.append(PLATFORMS/'Threads/Изображения/Карточка_задания.jpg')
        add(f'lesson2-carousel-{i}',1080,1350,content,targets)
    write(BUILD/'graphics.json',json.dumps(jobs,ensure_ascii=False,indent=2))


def sync_stills():
    for i,title in enumerate(['Задача_Анны','Уточнение_запроса','Поиск_и_лента','Лента_и_интересы','Визуальный_поиск','Вопросы_по_пинам','Задание'],1):
        final=VIDEO/f'final-{i:02}.png'
        assert final.exists(), 'Сначала извлеките кадры итогового MP4: pinterest_course_lesson2_render.py --stills.'
        copy(final,LESSON/f'05_Слайды/{i:02}_{title}.png')


def finalize_media():
    """Copy a checked full video and make clips using the configured lesson."""
    d=json.loads(DATA.read_text())
    assert not d.get('preview'), 'Нужны реальные тайминги нового WAV.'
    full=VIDEO/f'{VIDEO.name}.mp4'
    subprocess.run(['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-v','error','-threads','1','-i',str(full),'-f','null','-'],check=True)
    for target in [LESSON/'01_Видео'/VIDEO_NAME]+[PLATFORMS/f'{p}/Видео/{VIDEO_NAME}' for p in ['YouTube','Rutube','VK_Видео']]:copy(full,target)
    for target in [LESSON/'02_Текст_урока/Субтитры_полного_урока.srt']+[PLATFORMS/f'{p}/Тексты/Субтитры.srt' for p in ['YouTube','Rutube','VK_Видео']]:copy(VIDEO/'subtitles.srt',target)
    print('Full video decoded and copied.',flush=True)
    from pinterest_course_release import srt_time
    clip_durations={}
    for name,_,a,b in CLIPS:
        start,end=d['sceneStarts'][a],d['sceneStarts'][b]
        target=LESSON/f'01_Видео/{name}.mp4'
        # Lesson 2.4 switches slides at ceil(time * 30). Cap only video frames
        # so a fractional clip duration cannot round into the next paragraph;
        # keep the complete requested audio interval. Older kits are unchanged.
        clip_filters=[]
        if getattr(sys.modules[__name__],'FRAME_EXACT_CLIPS',False) and DATA.parent.name in ('lesson-2.4','lesson-2.5'):
            import math
            first=math.ceil(start*30-1e-8);last=math.ceil(end*30-1e-8)
            clip_filters=['-vf',f'trim=end_frame={last-first},setpts=PTS-STARTPTS']
        subprocess.run(['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-v','error','-threads','1','-y','-ss',str(start),'-i',str(full),'-t',str(end-start),'-map','0:v:0','-map','0:a:0',*clip_filters,'-c:v','libx264','-preset','ultrafast','-crf','18','-threads','1','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(target)],check=True)
        subprocess.run(['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-v','error','-threads','1','-i',str(target),'-f','null','-'],check=True)
        clip_durations[name]=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(target)]))
        blocks=[]
        for page in d['pages']:
            pa,pb=max(page['startMs'],start*1000),min(page['endMs'],end*1000)
            if pa<pb:
                text='\n'.join(' '.join(w['text'].strip() for w in line) for line in page['lines'])
                blocks.append(f'{len(blocks)+1}\n{srt_time(pa-start*1000)} --> {srt_time(pb-start*1000)}\n{text}')
        srt='\n\n'.join(blocks)
        write(LESSON/f'02_Текст_урока/{name}_субтитры.srt',srt)
        for p in ['VK_Клипы','Instagram']:
            copy(target,PLATFORMS/f'{p}/Видео/{name}.mp4')
            write(PLATFORMS/f'{p}/Тексты/{name}_субтитры.srt',srt)
        print(f'{name}: decoded and copied.',flush=True)
    return d,clip_durations


def finalize():
    d,clip_durations=finalize_media()
    doc=(DOCS/'Что_где_лежит.md').read_text()
    begin=doc.index('## Осталось по голосу') if '## Осталось по голосу' in doc else doc.index('## Видео собрано')
    end=doc.index('Каждый пин',begin)
    clips='\n'.join(f'- [{title}](../01_Видео/{name}.mp4): {clip_durations[name]:.2f} с.' for name,title,a,b in CLIPS)
    doc=doc[:begin]+f'## Видео собрано\n\n- [Полный урок](../01_Видео/{VIDEO_NAME}): {d["duration"]:.2f} с по WAV.\n{clips}\n- [Субтитры полного урока](../02_Текст_урока/Субтитры_полного_урока.srt); субтитры фрагментов лежат рядом.\n\nПодсветка слов привязана к новой озвучке; временные отметки {d["interpolatedWords"]} слов интерполированы между соседними распознанными словами. Финальное видео ещё не одобрено пользователем.\n\n'+doc[end:]
    doc=doc.replace('До новой озвучки нижнее поле показывает примеры размещения текста; подсветка появится по реальным таймингам WAV.','Кадры актуальной сборки с титрами по новой озвучке.')
    write(DOCS/'Что_где_лежит.md',doc)
    sources=(DOCS/'Источники_и_оформление.md').read_text()
    sources=sources.replace('Длительность второго видео пока не определена: нужна новая озвучка.',
                            f'Озвучка второго урока — предоставленный пользователем файл `2.wav`, {d["duration"]:.2f} секунды. Видео: 1080×1920, 30 кадров/с, MP4 H.264 / AAC. Слайды статичны; титры с подсветкой звучащего слова и полоса прогресса меняются по времени. Временные отметки {d["interpolatedWords"]} слов интерполированы между распознанными соседними словами; их точность ограничена.')
    write(DOCS/'Источники_и_оформление.md',sources)
    order=(DOCS/'Порядок_выпуска.md').read_text()
    order=order.replace('Озвучить семь абзацев из `02_Текст_урока/Текст_озвучки.txt` голосом Fenrir, как в первом уроке. Сохранить WAV в «Загрузки» и сообщить его имя.',
                        'Озвучка `2.wav` получена; полный урок и два коротких фрагмента собраны. Открыть `01_Видео` и проверить готовые ролики с телефона перед выпуском.')
    order=order.replace('Если вертикальный ролик после озвучки окажется не длиннее трёх минут, YouTube относит его к Shorts; основной значок — 9:16.',
                        'Вертикальный ролик длится около двух минут и по справке YouTube относится к Shorts; основной значок — 9:16.')
    write(DOCS/'Порядок_выпуска.md',order)
    index=(COURSE/'НАЧАТЬ_ЗДЕСЬ.md').read_text()
    index=index.replace('Текст и оформление подготовлены; видео ожидает новую озвучку.',
                        'Полный урок, два коротких фрагмента, субтитры, обложки и материалы семи площадок собраны; готовы к просмотру.')
    write(COURSE/'НАЧАТЬ_ЗДЕСЬ.md',index)
    scenario=ROOT/'docs/pinterest-course/урок-1.2-сценарий.md'
    plan=scenario.read_text()
    plan=plan.replace('Выполняются разметка слов и сборка.',
                      f'Собраны полный ролик и два коротких фрагмента. Все файлы MP4 декодированы без ошибок. Временные отметки {d["interpolatedWords"]} слов интерполированы; финальная сборка пока не одобрена пользователем.')
    plan=plan.replace('План коротких фрагментов после получения голоса: сцена 2 «Как уточнить запрос» и сцены 3–4 «Ваша лента не показывает интересы всех». Фрагменты должны сохранить законченную мысль; точные границы выбираем по WAV.',
                      f'Короткие фрагменты: сцена 2 «Как уточнить запрос» ({d["sceneStarts"][1]:.2f}–{d["sceneStarts"][2]:.2f} с) и сцены 3–4 «Ваша лента не показывает интересы всех» ({d["sceneStarts"][2]:.2f}–{d["sceneStarts"][4]:.2f} с). Границы выбраны по предоставленной озвучке.')
    plan=plan.replace('Полный урок и два коротких фрагмента собираем на предоставленной записи `2.wav`.',
                      'Полный урок и два коротких фрагмента собраны на предоставленной записи `2.wav`. Проверенные слайды Remotion смонтированы через FFmpeg; фотографии статичны, титры и полоса прогресса меняются по времени.')
    write(scenario,plan)
    import csv
    journal=list(csv.reader((DOCS/'Журнал_выпуска.csv').open(encoding='utf-8-sig'),delimiter=';'))
    for row in journal[1:]:
        if 'ожидает озвучку' in row[3]:row[3]='Собран; готов к просмотру; отдельно не одобрен'
    csv_file(DOCS/'Журнал_выпуска.csv',journal[0],journal[1:])
    sync_stills()
    print('Full lesson and clips decoded and copied.',flush=True)


def verify():
    from PIL import Image
    for job in json.loads((BUILD/'graphics.json').read_text()):
        for target in map(Path,job['targets']):
            with Image.open(target) as im:
                assert im.size==(job['width']*job['scale'],job['height']*job['scale'])
                im.verify()
            assert 0<target.stat().st_size<2_000_000
    assert (LESSON/'02_Текст_урока/Текст_озвучки.txt').read_bytes()==TEXT.read_bytes()
    assert set(p.name for p in PLATFORMS.iterdir())==set(SITES)
    rows=[]
    for i in [1,2]:
        p=PLATFORMS/f'Pinterest/Пин_{i:02}'
        hashes=[hashlib.sha256(f.read_bytes()).hexdigest() for f in [p/'Изображение.jpg']+sorted((p/'Тексты').glob('*.txt'))]
        rows.append([f'Пин {i:02}','01',hashlib.sha256(''.join(hashes).encode()).hexdigest(),'','Подготовлен; требуется отдельное одобрение с конечным URL'])
    csv_file(DOCS/'Версии_пинов.csv',['Пин','Версия','SHA256 изображения и текстов','Конечный URL','Статус'],rows)
    files=[p for p in LESSON.rglob('*') if p.is_file()]
    assert not any(p.is_symlink() or p.suffix in ['.json','.html','.log'] for p in files)
    print(f'{len(files)} files; 7 platform folders; graphics and exact narration checked.')


if __name__=='__main__':
    if '--sync-stills' in sys.argv:sync_stills()
    elif '--finalize' in sys.argv:finalize()
    elif '--verify' in sys.argv:verify()
    else:
        prepare_texts();prepare_docs();prepare_preview_data();prepare_graphics()
        print(LESSON)
