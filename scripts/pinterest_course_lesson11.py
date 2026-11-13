"""Lesson 3.2 release kit: preparing the pin image. No screenshots, drawn cards only."""
import sys
import pinterest_course_lesson2 as media
import pinterest_course_lesson4 as layouts
from pinterest_course_release import ROOT,COURSE,PUBLIC,write,copy,csv_file
v2='--v2' in sys.argv
LESSON=(COURSE/'Исправленные_версии_v2/Урок_11_Подготовка_изображения')if v2 else(COURSE/'Урок_11_Подготовка_изображения')
PLATFORMS=LESSON/'03_Площадки'
DOCS=LESSON/'04_Документы'
SLIDES=LESSON/'05_Слайды'
BUILD=ROOT/f'artifacts/pinterest-course/release-build-lesson11{"v2"if v2 else""}'
VIDEO=ROOT/f'artifacts/pinterest-course/lesson-3.2-vertical-v{"2"if v2 else"1"}'
TEXT=ROOT/'docs/pinterest-course/урок-3.2-озвучка.txt'
DATA=PUBLIC/'lesson-3.2/data.json'
VIDEO_NAME='Урок_11_Подготовка_изображения.mp4'
CLIPS=[('Клип_01_Вертикальный_формат','Какой размер подойдёт для пина?',3,4),
       ('Клип_02_Короткая_надпись','Нужна ли надпись на изображении?',4,5)]
SLIDE_NAMES=['Изображение_показывает_тему','Выбираем_фотографию','Проверяем_исходник','Вертикальный_формат','Короткая_надпись','Права_на_изображение','Ваша_очередь']
SOURCE='https://help.pinterest.com/en/business/article/pin-performance-and-distribution'
RIGHTS='https://policy.pinterest.com/en/community-guidelines'
for name in ['LESSON','PLATFORMS','DOCS','BUILD','VIDEO','TEXT','DATA','VIDEO_NAME','CLIPS']:
 setattr(media,name,globals()[name]);setattr(layouts,name,globals()[name])
media.FRAME_EXACT_CLIPS=False
layouts.GRAPHICS={
 'number':'11','main_title':'Готовим<br>изображение','subtitle':'Вертикально,<br>без размытия',
 'main_rows':[('ПРОПОРЦИИ','2 к 3'),('ХОЛСТ','1000 × 1500 пикселей'),('НАДПИСЬ','Коротко и читаемо')],'main_footer':'Учебный пример Анны',
 'clip_titles':['Вертикальный<br>формат','Короткая<br>надпись'],
 'clip_rows':[[('ПРОПОРЦИИ','Вертикально, 2:3'),('ПРИМЕР','1000 × 1500 пикселей')],[('НАДПИСЬ','Короткая фраза по теме'),('ПРОВЕРКА','Читается ли при уменьшении?')]],
 'clip_footers':['Сохраняйте пропорции предметов','Если приходится всматриваться — сократите'],
 'pin_titles':['Формат<br>изображения','Надпись<br>на пине'],
 'pin_rows':[[('ПРОПОРЦИИ','Вертикально, 2:3'),('ПРИМЕР','1000 × 1500 пикселей')],[('НАДПИСЬ','Короткая фраза по теме'),('ПРОВЕРКА','Читается ли при уменьшении?')]],
 'pin_footers':['Органайзер остаётся виден','Не закрывайте главный предмет'],
 'card_titles':['Проверьте<br>исходник','Формат<br>и надпись','Ваше<br>изображение'],
 'card_rows':[[('ВИДНО ЛИ','Нужные предметы?'),('ЕСТЬ ЛИ','Размытие и искажения?')],[('ПРОПОРЦИИ','2:3'),('НАДПИСЬ','Коротко и читаемо')],[('ГЛАВНЫЙ ПРЕДМЕТ','Виден?'),('НАДПИСЬ','Читается?')]],
 'card_footers':['Исходник · 1/3','Оформление · 2/3','Проверка · 3/3'],
}


def prepare_texts():
 paragraphs=TEXT.read_text().strip().split('\n\n');assert len(paragraphs)==7
 copy(TEXT,LESSON/'06_Озвучка/Текст_озвучки.txt')
 copy(TEXT,LESSON/'02_Текст_урока/Текст_озвучки.txt')
 for name,title,a,b in CLIPS:write(LESSON/f'02_Текст_урока/{name}_текст.txt','\n\n'.join(paragraphs[a:b]))
 title='Как подготовить изображение для пина Pinterest | Урок 11'
 description=f'''Одиннадцатый урок курса BoostKlient «Pinterest для начинающих» — урок 3.2.

Готовим изображение для первого пина вместе с Анной, вымышленной героиней курса. Проверяем исходник, выбираем вертикальные пропорции 2:3 и короткую надпись, которая читается даже при уменьшении.

Официальные рекомендации:
{SOURCE}
{RIGHTS}'''
 for site in ['YouTube','Rutube','VK_Видео']:
  write(PLATFORMS/site/'Тексты/Название.txt',title);write(PLATFORMS/site/'Тексты/Описание.txt',description+('\n\n#Pinterest #Пинтерест #Обучение' if site=='YouTube' else ''));write(PLATFORMS/site/'Тексты/Комментарий_с_заданием.txt','Видно ли главный предмет на вашем изображении после уменьшения? Читается ли надпись?')
 write(PLATFORMS/'VK_Видео/Тексты/Пост_к_видео.txt','Изображение для пина должно быть понятным даже на маленьком экране.\n\nВ одиннадцатом уроке на примере Анны проверяем исходник, выбираем вертикальный формат 2:3 и короткую надпись.')
 captions=['Для обычного пина Pinterest рекомендует вертикальные пропорции 2 к 3. Пример: холст 1000 на 1500 пикселей. Сохраняйте естественные пропорции предметов при кадрировании.',
           'Если нужна надпись — начните с короткой фразы по теме. Расположите текст так, чтобы он не закрывал главный предмет. Уменьшите картинку и проверьте, читается ли фраза.']
 for site in ['VK_Клипы','Instagram']:
  for i,(name,title,a,b) in enumerate(CLIPS):
   write(PLATFORMS/site/f'Тексты/{name}_название.txt',title);write(PLATFORMS/site/f'Тексты/{name}_описание.txt',captions[i]+('\n\n#Pinterest #Пинтерест' if site=='Instagram' else ''));write(PLATFORMS/site/f'Тексты/{name}_текст_озвучки.txt','\n\n'.join(paragraphs[a:b]))
 write(PLATFORMS/'Instagram/Тексты/Карусель_описание.txt','Прежде чем публиковать пин — проверьте изображение.\n\nВидны ли нужные предметы? Вертикальный формат 2:3? Надпись читается при уменьшении?\n\n#Pinterest #Пинтерест')
 pins=[('Какой размер изображения выбрать для пина Pinterest','В одиннадцатом уроке BoostKlient разбираем вертикальный формат 2:3 на примере Анны: холст 1000 × 1500 пикселей.','Карточка BoostKlient: вертикальные пропорции 2 к 3, пример холста.'),
       ('Нужна ли надпись на изображении пина','Короткая фраза по теме, которая не закрывает главный предмет и читается при уменьшении. Одиннадцатый урок курса BoostKlient.','Карточка BoostKlient: короткая надпись и проверка читаемости.')]
 for i,(title,description,alt) in enumerate(pins,1):
  assert len(title)<=100 and len(description)<=500
  for name,text in [('Название.txt',title),('Описание.txt',description),('Альтернативный_текст.txt',alt)]:write(PLATFORMS/f'Pinterest/Пин_{i:02}/Тексты/{name}',text)
 posts=['Изображение для пина должно читаться даже на маленьком экране.\n\nВ одиннадцатом уроке проверяем исходник, выбираем вертикальный формат 2:3 и короткую надпись.',
        'Если берёте чужое изображение — сначала проверьте условия использования. Pinterest требует уважать права на чужой контент.']
 for i,text in enumerate(posts,1):assert len(text)<=500;write(PLATFORMS/f'Threads/Тексты/Пост_{i:02}.txt',text)


def prepare_docs():
 write(DOCS/'Задание_ученику.txt','Урок 11 · Подготовка изображения\n\nМоё изображение:\n\nВидны ли нужные предметы, нет ли размытия?\n\nПропорции: вертикально, 2:3?\n\nНужна ли надпись, и читается ли она при уменьшении?\n\nИсходник сохранён отдельно?')
 sha_manifest={}
 if v2 and (ROOT/'artifacts/pinterest-course/visual-fix-11-12-v2/Версии_скриншотов.csv').exists():
  import csv
  with open(ROOT/'artifacts/pinterest-course/visual-fix-11-12-v2/Версии_скриншотов.csv',encoding='utf-8-sig') as f:
   for row in csv.DictReader(f,delimiter=';'):sha_manifest[row['Файл']]=row['SHA256']
 write(DOCS/'Источники_и_оформление.md',f'''# Источники и оформление

Текст — урок 3.2 «Подготовка изображения» в `pinterest_course_russian_final.md`; голос — предоставленный `11.wav`, PCM 16 бит, 24 кГц, моно, 149.08 с.

Рекомендации по пропорциям и качеству изображения: {SOURCE}. Права на чужой контент: {RIGHTS}. Сверено 5 октября 2026 года.

Анна — вымышленная учебная героиня.{"" if not v2 else " Учебный исходник органайзера: реальная фотография RDNE Stock project / Pexels (ID 7889221), лицензия свободного использования сверена 8 октября 2026 (artifacts/pinterest-course/visual-fix-11-12-v2/source-license.json). Скриншоты интерфейса: настоящий редактор изображения Photopea (11-01, 11-03, 11-04, 11-05) и локальный просмотр PNG (11-05). Версии скриншотов зафиксированы в Версии_скриншотов.csv с SHA256:"+(("\n"+"\n".join(f"- {k}: {v[:16]}..." for k,v in sha_manifest.items() if k.startswith("11-"))) if sha_manifest else " реестр не найден.")}

Сборка локальная. Платные генерации и внешние публикации курса не выполнялись.''')
 status='Собран v2 для просмотра; проверяется Codex; пользователь не одобрял'if v2 else'Сборка выполняется'
 csv_file(DOCS/'Журнал_выпуска.csv',['Площадка','Материал','Версия','Статус','Дата одобрения','Дата публикации','URL','Проверка страницы'],
  [[site,'Урок 11','02'if v2 else'01',status,'','','',''] for site in ['YouTube','Rutube','VK Видео']]+
  [[site,name,'02'if v2 else'01',status,'','','',''] for site in ['VK Клипы','Instagram'] for name,*_ in CLIPS]+
  [['Pinterest',f'Пин {i:02}','02'if v2 else'01','Подготовлен; требуется отдельное одобрение с конечным URL','','','',''] for i in [1,2]]+
  [['Threads',f'Пост {i:02}','02'if v2 else'01','Подготовлен; отдельно не одобрен','','','','']for i in [1,2]])


def finalize():
 d,lengths=media.finalize_media()
 for i,title in enumerate(SLIDE_NAMES,1):copy(VIDEO/f'final-{i:02}.png',SLIDES/f'{i:02}_{title}.png')
 clips='\n'.join(f'- [{title}](../01_Видео/{name}.mp4): {lengths[name]:.2f} с.' for name,title,*_ in CLIPS)
 write(DOCS/'Что_где_лежит.md',f'''# Урок 11 · Подготовка изображения

- [Полный урок](../01_Видео/{VIDEO_NAME}): {d['duration']:.2f} с.
{clips}
- [Текст озвучки](../06_Озвучка/Текст_озвучки.txt), [субтитры](../02_Текст_урока/Субтитры_полного_урока.srt).
- [Площадки](../03_Площадки): YouTube, Rutube, VK Видео, VK Клипы, Pinterest, Instagram, Threads.
- [Слайды](../05_Слайды): семь кадров итогового MP4.
- [Задание](Задание_ученику.txt), [источники](Источники_и_оформление.md).

MP4 H.264 / AAC, 1080×1920, 30 кадров/с. Подсветка слов по выравниванию: {len(d['words'])} слов, {d['interpolatedWords']} интерполированных отметок.

{'Видео v2 собрано '+d.get('buildDate','дата не указана')+'; проверяется Codex, пользователь не одобрял.'if v2 else'Видео одобрено пользователем 5 октября 2026 года; не опубликовано.'}''')
 print('Lesson 11 finalized.',flush=True)


if __name__=='__main__':
 if '--finalize' in sys.argv:finalize()
 elif '--verify' in sys.argv:media.verify()
 else:prepare_texts();prepare_docs();layouts.prepare_graphics();print(LESSON)
