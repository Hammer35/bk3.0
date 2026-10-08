"""Lesson 2.5 release kit: link in profile and website claim, with two approved screenshots."""
import csv
import hashlib
import json
import sys
import pinterest_course_lesson2 as media
import pinterest_course_lesson4 as layouts
from pinterest_course_release import ROOT,COURSE,PUBLIC,write,copy,csv_file
LESSON=COURSE/'Урок_09_Ссылка_и_подтверждение_сайта'
PLATFORMS=LESSON/'03_Площадки'
DOCS=LESSON/'04_Документы'
SLIDES=LESSON/'05_Слайды'
APPROVED=SLIDES/'На_одобрение'
BUILD=ROOT/'artifacts/pinterest-course/release-build-lesson9'
VIDEO=ROOT/'artifacts/pinterest-course/lesson-2.5-vertical-v1'
TEXT=ROOT/'docs/pinterest-course/урок-2.5-озвучка.txt'
DATA=PUBLIC/'lesson-2.5/data.json'
VIDEO_NAME='Урок_09_Ссылка_и_подтверждение_сайта.mp4'
# Clip indices are paragraph indices (0-based) and match sceneStarts boundaries.
CLIPS=[('Клип_01_Ссылка_в_профиле','Где указать ссылку в профиле?',3,4),
       ('Клип_02_Подтверждение_сайта','Ссылка и подтверждение: в чём разница?',4,5)]
SLIDE_NAMES=['Две_задачи','Ссылка_это_адрес','Подтверждение_отдельно','Поле_Веб-сайт','Настройки_подтверждения','Чужие_площадки','Ваша_очередь']
SOURCE='https://help.pinterest.com/en/article/edit-your-profile'
CLAIM='https://help.pinterest.com/en/business/article/claim-your-website'
SCREENSHOTS=[('01_Поле_сайта_в_профиле.png','Поле «Веб-сайт» в профиле','https://ru.pinterest.com/settings/edit-profile/'),
             ('02_Настройки_подтверждения_сайта.png','Раздел «Связать с Pinterest»','https://ru.pinterest.com/settings/claim/')]
for name in ['LESSON','PLATFORMS','DOCS','BUILD','VIDEO','TEXT','DATA','VIDEO_NAME','CLIPS']:
 setattr(media,name,globals()[name]);setattr(layouts,name,globals()[name])
media.FRAME_EXACT_CLIPS=True
layouts.GRAPHICS={
 'number':'09','main_title':'Ссылка и<br>подтверждение','subtitle':'Адрес в профиле и<br>управление сайтом',
 'main_rows':[('ССЫЛКА','Адрес в профиле'),('ПОДТВЕРЖДЕНИЕ','Доступ к сайту'),('ОЧЕРЕДЬ','Ваш аккаунт')],'main_footer':'Учебный аккаунт Анны',
 'clip_titles':['Ссылка<br>в профиле','Подтверждение<br>сайта'],
 'clip_rows':[[('01','Откройте профиль'),('02','Найдите «Веб-сайт»'),('03','Сохраните')],[('01','Откройте настройки'),('02','Найдите «Веб-сайты»'),('03','Поймите разницу')]],
 'clip_footers':['Ссылка — это адрес','Подтверждение — отдельно'],
 'pin_titles':['Адрес в профиле','Подтверждение сайта'],
 'pin_rows':[[('ПРОФИЛЬ','Поле «Веб-сайт»'),('ПОЛЕ','Адрес страницы'),('ДОСТУП','Код не нужен')],[('НАСТРОЙКИ','Связать с Pinterest'),('ПУНКТ','Веб-сайты'),('ДОСТУП','Нужен доступ к сайту')]],
 'pin_footers':['Ссылка — отдельно от подтверждения','Подтверждение здесь не выполняем'],
 'card_titles':['Две задачи','Проверьте поле','Ваша очередь'],
 'card_rows':[[('ССЫЛКА','Адрес в профиле'),('ПОДТВЕРЖДЕНИЕ','Доступ к сайту')],[('ВЕБ-САЙТ','Что стоит в поле?'),('ПУСТО','Можно оставить'),('САЙТ','Адрес страницы')],[('ПРОВЕРКА','Поле «Веб-сайт»'),('ДОСТУП','Кто поможет с сайтом?'),('ИТОГ','Аккаунт подготовлен')]],
 'card_footers':['Разные действия · 1/3','Проверьте с телефона · 2/3','Заполните свою пару · 3/3'],
}


def approved_sources():
 """Check approved screenshot files against the SHA256 recorded in the review CSV."""
 rows=list(csv.reader((DOCS/'Версии_скриншотов.csv').open(encoding='utf-8-sig'),delimiter=';'))[1:]
 assert len(rows)==2 and all(r[5].startswith('Одобрен') for r in rows)
 for row in rows:
  assert hashlib.sha256((APPROVED/row[2]).read_bytes()).hexdigest()==row[3],row[2]
 return rows


def prepare_texts():
 paragraphs=TEXT.read_text().strip().split('\n\n');assert len(paragraphs)==7
 copy(TEXT,LESSON/'06_Озвучка/Текст_озвучки.txt')
 for name,title,a,b in CLIPS:write(LESSON/f'02_Текст_урока/{name}_текст.txt','\n\n'.join(paragraphs[a:b]))
 title='Ссылка на сайт и подтверждение сайта в Pinterest | Урок 9'
 description=f'''Девятый урок курса BoostKlient «Pinterest для начинающих» — урок 2.5.

Указываем адрес сайта в профиле и разбираем, чем он отличается от подтверждения сайта. Учебный аккаунт Анны: поле «Веб-сайт» оставлено пустым, подтверждение не выполняем.

Анна — вымышленная героиня курса. Оба скриншота сняты с настоящих страниц и одобрены пользователем.

Официальные инструкции:
{SOURCE}
{CLAIM}'''
 for site in ['YouTube','Rutube','VK_Видео']:
  write(PLATFORMS/site/'Тексты/Название.txt',title);write(PLATFORMS/site/'Тексты/Описание.txt',description+('\n\n#Pinterest #Пинтерест #Обучение' if site=='YouTube' else ''));write(PLATFORMS/site/'Тексты/Комментарий_с_заданием.txt','Есть ли у вас свой сайт? Указали ли вы адрес в профиле и кто может помочь с подтверждением?')
 write(PLATFORMS/'VK_Видео/Тексты/Пост_к_видео.txt','Ссылка в профиле — это адрес страницы. Подтверждение сайта — отдельная настройка, для неё нужен доступ к сайту.\n\nВ девятом уроке на учебном аккаунте разбираем оба действия. Подтверждение не выполняем, только смотрим настройки.')
 captions=['Ссылка — адрес страницы в профиле. Откройте редактирование профиля и найдите поле «Веб-сайт». В примере поле пустое. Интерфейс на вашем устройстве может отличаться.',
           'Подтверждение — отдельная настройка. В настройках есть пункт «Веб-сайты». Для реального подтверждения нужен доступ к сайту или домену. В уроке мы его не выполняем.']
 for site in ['VK_Клипы','Instagram']:
  for i,(name,title,a,b) in enumerate(CLIPS):
   write(PLATFORMS/site/f'Тексты/{name}_название.txt',title);write(PLATFORMS/site/f'Тексты/{name}_описание.txt',captions[i]+('\n\n#Pinterest #Пинтерест' if site=='Instagram' else ''));write(PLATFORMS/site/f'Тексты/{name}_текст_озвучки.txt','\n\n'.join(paragraphs[a:b]))
 write(PLATFORMS/'Instagram/Тексты/Карусель_описание.txt','Ссылка в профиле и подтверждение сайта — разные задачи.\n\nПервая указывает адрес. Второе доказывает, что сайт ваш, и требует доступа.\n\nСначала определите, есть ли у вас доступ к сайту. Потом решите, нужна ли вам эта настройка.\n\n#Pinterest #Пинтерест')
 pins=[('Ссылка в профиле Pinterest: где указать адрес сайта','В девятом уроке BoostKlient показываем поле «Веб-сайт» в профиле и объясняем, чем ссылка отличается от подтверждения сайта. Учебный аккаунт: поле пустое.','Карточка BoostKlient: поле «Веб-сайт» в профиле, адрес страницы.'),
       ('Подтверждение сайта в Pinterest: что это и зачем','Подтверждение сайта — отдельная настройка. Оно требует доступа к сайту или настройкам домена. В уроке показываем настройки и не выполняем подтверждение.','Карточка BoostKlient: пункт «Веб-сайты» в настройках подтверждения.')]
 for i,(title,description,alt) in enumerate(pins,1):
  assert len(title)<=100 and len(description)<=500
  for name,text in [('Название.txt',title),('Описание.txt',description),('Альтернативный_текст.txt',alt)]:write(PLATFORMS/f'Pinterest/Пин_{i:02}/Тексты/{name}',text)
 posts=['Ссылка в профиле — адрес страницы. Подтверждение сайта — отдельная настройка с доступом.\n\nВ девятом уроке разбираем оба действия на учебном аккаунте. Какой из вариантов вам нужен?',
        'Если у вас есть свой сайт, сначала выясните, кто может помочь с подтверждением.\n\nНа чужих площадках доступа может не быть. Проверьте это до настроек.']
 for i,text in enumerate(posts,1):assert len(text)<=500;write(PLATFORMS/f'Threads/Тексты/Пост_{i:02}.txt',text)


def prepare_docs():
 rows=approved_sources()
 write(DOCS/'Задание_ученику.txt','Урок 9 · Ссылка и подтверждение сайта\n\nЕсть ли у вас собственный сайт?\n\nУказали ли вы адрес в поле «Веб-сайт»? Какой адрес?\n\nКто может помочь с подтверждением: разработчик, владелец домена или никто?\n\nВ чём разница между ссылкой и подтверждением своими словами?')
 write(DOCS/'Тест_урока.md','''# Проверка девятого урока

После просмотра с телефона попросить новичка объяснить:
1. Чем ссылка в профиле отличается от подтверждения сайта?
2. Где находится поле «Веб-сайт»?
3. Что нужно для подтверждения и почему одной ссылки недостаточно?
4. Что сказано про чужие площадки?
5. Читаются ли скриншоты и подписи? Где понадобилась пауза?

Ответы ученика пока не получены; записать их и моменты перемотки.''')
 links='\n'.join(f"- {n:02}: [{title}]({url}). Файл `{file}`." for n,(file,title,url) in enumerate(SCREENSHOTS,1))
 write(DOCS/'Источники_и_оформление.md',f'''# Источники и оформление

Текст — урок 2.5 «Ссылка на сайт и подтверждение сайта» в `pinterest_course_russian_final.md`; голос — предоставленный `9.wav`, PCM 16 бит, 24 кГц, моно, 143.00 с.

[Настройки профиля]({SOURCE}), [подтверждение сайта]({CLAIM}): официальная справка сверена 5 октября 2026 года.

Оба скриншота сняты с учебного аккаунта и одобрены 5 октября 2026 года. Контрольные суммы — в `Версии_скриншотов.csv`.

{links}

Анна — вымышленная учебная героиня. Поле «Веб-сайт» пустое: сайт для курса не подключаем. Подтверждение не выполнялось, код на сайт и DNS-записи не добавлялись.

Сборка локальная. Платные генерации и внешние публикации курса не выполнялись.''')
 csv_file(DOCS/'Журнал_выпуска.csv',['Площадка','Материал','Версия','Статус','Дата одобрения','Дата публикации','URL','Проверка страницы'],
  [[site,'Урок 09','01','Сборка выполняется','','','',''] for site in ['YouTube','Rutube','VK Видео']]+
  [[site,name,'01','Сборка выполняется','','','',''] for site in ['VK Клипы','Instagram'] for name,*_ in CLIPS]+
  [['Pinterest',f'Пин {i:02}','01','Подготовлен; требуется отдельное одобрение с конечным URL','','','',''] for i in [1,2]]+
  [['Threads',f'Пост {i:02}','01','Подготовлен; отдельно не одобрен','','','','']for i in [1,2]])
 return rows


def finalize():
 approved_sources();d,lengths=media.finalize_media()
 for i,title in enumerate(SLIDE_NAMES,1):copy(VIDEO/f'final-{i:02}.png',SLIDES/f'{i:02}_{title}.png')
 clips='\n'.join(f'- [{title}](../01_Видео/{name}.mp4): {lengths[name]:.2f} с.' for name,title,*_ in CLIPS)
 write(DOCS/'Что_где_лежит.md',f'''# Урок 9 · Ссылка и подтверждение сайта

- [Полный урок](../01_Видео/{VIDEO_NAME}): {d['duration']:.2f} с — около 2:23.
{clips}
- [Текст озвучки](../06_Озвучка/Текст_озвучки.txt), [субтитры](../02_Текст_урока/Субтитры_полного_урока.srt).
- [Площадки](../03_Площадки): YouTube, Rutube, VK Видео, VK Клипы, Pinterest, Instagram, Threads.
- [Слайды](../05_Слайды): семь кадров итогового MP4; [исходники](../05_Слайды/На_одобрение) — два одобренных скриншота.
- [Задание](Задание_ученику.txt), [источники](Источники_и_оформление.md), [одобрение скриншотов](Одобрение_скриншотов.md).

MP4 H.264 / AAC, 1080×1920, 30 кадров/с. Озвучка пользователя; подсветка слов по выравниванию: {len(d['words'])} слов, {d['interpolatedWords']} интерполированных отметок.

Итоговое видео пока не просмотрено пользователем. Подтверждение сайта в уроке не выполняется.''')
 print('Lesson 9 finalized.',flush=True)


if __name__=='__main__':
 if '--finalize' in sys.argv:finalize()
 else:approved_sources();prepare_texts();prepare_docs();layouts.prepare_graphics();print(LESSON)
