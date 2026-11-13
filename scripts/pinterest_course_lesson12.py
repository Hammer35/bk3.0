"""Lesson 3.3 release kit: pin title and description. No screenshots, drawn cards only."""
import sys
import pinterest_course_lesson2 as media
import pinterest_course_lesson4 as layouts
from pinterest_course_release import ROOT,COURSE,PUBLIC,write,copy,csv_file
v2='--v2' in sys.argv
LESSON=(COURSE/'Исправленные_версии_v2/Урок_12_Заголовок_и_описание')if v2 else(COURSE/'Урок_12_Заголовок_и_описание')
PLATFORMS=LESSON/'03_Площадки'
DOCS=LESSON/'04_Документы'
SLIDES=LESSON/'05_Слайды'
BUILD=ROOT/f'artifacts/pinterest-course/release-build-lesson12{"v2"if v2 else""}'
VIDEO=ROOT/f'artifacts/pinterest-course/lesson-3.3-vertical-v{"2"if v2 else"1"}'
TEXT=ROOT/'docs/pinterest-course/урок-3.3-озвучка.txt'
DATA=PUBLIC/'lesson-3.3/data.json'
VIDEO_NAME='Урок_12_Заголовок_и_описание.mp4'
CLIPS=[('Клип_01_Пример_Анны','Как написать заголовок для пина?',1,2),
       ('Клип_02_Текст_совпадает','Должен ли текст совпадать с изображением?',2,3)]
SLIDE_NAMES=['Заголовок_и_описание','Пример_Анны','Текст_должен_совпадать_с_фото','Без_громких_слов','Коротко_и_по_делу','Ваша_очередь','Прочитайте_вслух']
SOURCE='https://help.pinterest.com/en/business/article/pin-performance-and-distribution'
for name in ['LESSON','PLATFORMS','DOCS','BUILD','VIDEO','TEXT','DATA','VIDEO_NAME','CLIPS']:
 setattr(media,name,globals()[name]);setattr(layouts,name,globals()[name])
media.FRAME_EXACT_CLIPS=False
layouts.GRAPHICS={
 'number':'12','main_title':'Заголовок<br>и описание','subtitle':'Коротко,<br>без громких слов',
 'main_rows':[('ЗАГОЛОВОК','Одно предложение'),('ОПИСАНИЕ','Что внутри материала'),('ПРОВЕРКА','Прочитать вслух')],'main_footer':'Учебный пример Анны',
 'clip_titles':['Пример<br>Анны','Текст<br>совпадает'],
 'clip_rows':[[('ЗАГОЛОВОК','Как разместить мелочи'),('ОПИСАНИЕ','Вариант с органайзером')],[('ЗАГОЛОВОК','Совпадает с фото?'),('ОПИСАНИЕ','Соответствует статье?')]],
 'clip_footers':['Конкретный вопрос и подробности','Проверьте оба обещания'],
 'pin_titles':['Заголовок<br>для пина','Совпадение<br>с фото'],
 'pin_rows':[[('ЗАГОЛОВОК','Одно предложение'),('ОПИСАНИЕ','Что найдёт человек')],[('ЗАГОЛОВОК И ФОТО','Об одном и том же?'),('БЕЗ ГРОМКИХ СЛОВ','Конкретный вопрос')]],
 'pin_footers':['Читается как одно сообщение','Лучше понятного вопроса'],
 'card_titles':['Пример<br>текста','Без громких<br>слов','Прочитайте<br>вслух'],
 'card_rows':[[('ЗАГОЛОВОК','Как разместить мелочи'),('ОПИСАНИЕ','Вариант с органайзером')],[('ЗАГОЛОВОК','Совпадает с фото?'),('ПОНЯТЕН БЕЗ','Громких обещаний?')],[('ПРОЧИТАЙТЕ','Вслух'),('НЕУДОБНО','Исправьте')]],
 'card_footers':['Текст Анны · 1/3','Проверка · 2/3','Вслух · 3/3'],
}


def prepare_texts():
 paragraphs=TEXT.read_text().strip().split('\n\n');assert len(paragraphs)==7
 copy(TEXT,LESSON/'06_Озвучка/Текст_озвучки.txt')
 copy(TEXT,LESSON/'02_Текст_урока/Текст_озвучки.txt')
 for name,title,a,b in CLIPS:write(LESSON/f'02_Текст_урока/{name}_текст.txt','\n\n'.join(paragraphs[a:b]))
 title='Как написать заголовок и описание для пина Pinterest | Урок 12'
 description=f'''Двенадцатый урок курса BoostKlient «Pinterest для начинающих» — урок 3.3.

Объясняем словами, что на изображении и что человек найдёт дальше. Заголовок называет тему коротко, описание добавляет подробности. Вместе они читаются как одно сообщение. Проверяем: текст совпадает с фото и статьёй?

Официальная рекомендация:
{SOURCE}'''
 for site in ['YouTube','Rutube','VK_Видео']:
  write(PLATFORMS/site/'Тексты/Название.txt',title);write(PLATFORMS/site/'Тексты/Описание.txt',description+('\n\n#Pinterest #Пинтерест #Обучение' if site=='YouTube' else ''));write(PLATFORMS/site/'Тексты/Комментарий_с_заданием.txt','Совпадает ли текст вашего пина с изображением и содержимым статьи? Прочитайте заголовок и описание вслух.')
 write(PLATFORMS/'VK_Видео/Тексты/Пост_к_видео.txt','Заголовок и описание должны совпадать с изображением и статьёй.\n\nВ двенадцатом уроке на примере Анны проверяем: текст говорит об одном и том же с фото? Можно понять тему без громких слов?')
 captions=['Пример заголовка Анны: «Как разместить мелочи на маленьком рабочем столе». Описание: «Показываю вариант с настольным органайзером». Такой текст подходит, если фото показывает этот вариант.',
           'Прочитайте заголовок рядом с изображением. Они говорят об одном и том же? Можно ли понять тему без слов «невероятный» и «секрет успеха»? Конкретный вопрос помогает лучше громкого обещания.']
 for site in ['VK_Клипы','Instagram']:
  for i,(name,title,a,b) in enumerate(CLIPS):
   write(PLATFORMS/site/f'Тексты/{name}_название.txt',title);write(PLATFORMS/site/f'Тексты/{name}_описание.txt',captions[i]+('\n\n#Pinterest #Пинтерест' if site=='Instagram' else ''));write(PLATFORMS/site/f'Тексты/{name}_текст_озвучки.txt','\n\n'.join(paragraphs[a:b]))
 write(PLATFORMS/'Instagram/Тексты/Карусель_описание.txt','Заголовок и описание читаются как одно сообщение.\n\nПрежде чем опубликовать пин — проверьте: текст совпадает с фото и статьёй? Понятен без громких слов?\n\n#Pinterest #Пинтерест')
 pins=[('Как написать заголовок для пина Pinterest','В двенадцатом уроке BoostKlient разбираем пример Анны: заголовок называет тему коротко, описание добавляет подробности.','Карточка BoostKlient: пример заголовка и описания.'),
       ('Должен ли заголовок пина совпадать с изображением','Текст и фото должны говорить об одном и том же. Двенадцатый урок курса BoostKlient на примере Анны.','Карточка BoostKlient: проверка совпадения текста и фото.')]
 for i,(title,description,alt) in enumerate(pins,1):
  assert len(title)<=100 and len(description)<=500
  for name,text in [('Название.txt',title),('Описание.txt',description),('Альтернативный_текст.txt',alt)]:write(PLATFORMS/f'Pinterest/Пин_{i:02}/Тексты/{name}',text)
 posts=['Заголовок называет тему коротко, описание добавляет подробности.\n\nВ двенадцатом уроке проверяем: текст совпадает с изображением и статьёй? Понятен без громких обещаний?',
        'Прочитайте заголовок и описание вслух: так легче заметить неудобные фразы и повторения.']
 for i,text in enumerate(posts,1):assert len(text)<=500;write(PLATFORMS/f'Threads/Тексты/Пост_{i:02}.txt',text)


def prepare_docs():
 write(DOCS/'Задание_ученику.txt','Урок 12 · Заголовок и описание\n\nМоё изображение:\n\nЗаголовок (одно предложение):\n\nОписание (что внутри материала и зачем переходить):\n\nПрочитали вслух — текст совпадает с фото и содержимым статьи?')
 sha_manifest={}
 if v2 and (ROOT/'artifacts/pinterest-course/visual-fix-11-12-v2/Версии_скриншотов.csv').exists():
  import csv
  with open(ROOT/'artifacts/pinterest-course/visual-fix-11-12-v2/Версии_скриншотов.csv',encoding='utf-8-sig') as f:
   for row in csv.DictReader(f,delimiter=';'):sha_manifest[row['Файл']]=row['SHA256']
 write(DOCS/'Источники_и_оформление.md',f'''# Источники и оформление

Текст — урок 3.3 «Заголовок и описание» в `pinterest_course_russian_final.md`; голос — предоставленный `12.wav`, PCM 16 бит, 24 кГц, моно, 92.92 с.

Рекомендация о соответствии текста изображению и материалу: {SOURCE}. Сверено 5 октября 2026 года.

Анна — вымышленная учебная героиня.{"" if not v2 else " Учебный исходник органайзера: реальная фотография RDNE Stock project / Pexels (ID 7889221), лицензия свободного использования сверена 8 октября 2026 (artifacts/pinterest-course/visual-fix-11-12-v2/source-license.json). Скриншоты интерфейса: настоящая форма создания пина Pinterest (12-01, 12-02, 12-03, 12-04). Условный пример: статья с пятью идеями по организации стола не создана, ссылка пустая, учебный пин не опубликован. Версии скриншотов зафиксированы в Версии_скриншотов.csv с SHA256:"+(("\n"+"\n".join(f"- {k}: {v[:16]}..." for k,v in sha_manifest.items() if k.startswith("12-"))) if sha_manifest else " реестр не найден.")}

Сборка локальная. Платные генерации и внешние публикации курса не выполнялись.''')
 status='Собран v2 для просмотра; проверяется Codex; пользователь не одобрял'if v2 else'Ожидает визуальный пакет Codex; монтаж после одобрения кадров'
 csv_file(DOCS/'Журнал_выпуска.csv',['Площадка','Материал','Версия','Статус','Дата одобрения','Дата публикации','URL','Проверка страницы'],
  [[site,'Урок 12','02',status,'','','',''] for site in ['YouTube','Rutube','VK Видео']]+
  [[site,name,'02','Подготовлен; финализация после сборки полного урока','','','',''] for site in ['VK Клипы','Instagram'] for name,*_ in CLIPS]+
  [['Pinterest',f'Пин {i:02}','02' if v2 else'01','Подготовлен; требуется отдельное одобрение с конечным URL','','','',''] for i in [1,2]]+
  [['Threads',f'Пост {i:02}','02' if v2 else'01','Подготовлен; отдельно не одобрен','','','','']for i in [1,2]])


def finalize():
 d,lengths=media.finalize_media()
 for i,title in enumerate(SLIDE_NAMES,1):copy(VIDEO/f'final-{i:02}.png',SLIDES/f'{i:02}_{title}.png')
 clips='\n'.join(f'- [{title}](../01_Видео/{name}.mp4): {lengths[name]:.2f} с.' for name,title,*_ in CLIPS)
 write(DOCS/'Что_где_лежит.md',f'''# Урок 12 · Заголовок и описание

- [Полный урок](../01_Видео/{VIDEO_NAME}): {d['duration']:.2f} с.
{clips}
- [Текст озвучки](../06_Озвучка/Текст_озвучки.txt), [субтитры](../02_Текст_урока/Субтитры_полного_урока.srt).
- [Площадки](../03_Площадки): YouTube, Rutube, VK Видео, VK Клипы, Pinterest, Instagram, Threads.
- [Слайды](../05_Слайды): семь кадров итогового MP4.
- [Задание](Задание_ученику.txt), [источники](Источники_и_оформление.md).

MP4 H.264 / AAC, 1080×1920, 30 кадров/с. Подсветка слов по выравниванию: {len(d['words'])} слов, {d['interpolatedWords']} интерполированных отметок.

Видео v2 собрано {d.get('buildDate','дата не указана')}; проверяется Codex, пользователь не одобрял.'''if v2 else"Видео собрано {d.get('buildDate','дата не указана')}.'''")
 print('Lesson 12 finalized.',flush=True)


if __name__=='__main__':
 if '--finalize' in sys.argv:finalize()
 elif '--verify' in sys.argv:media.verify()
 else:prepare_texts();prepare_docs();layouts.prepare_graphics();print(LESSON)
