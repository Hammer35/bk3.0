"""Lesson 3.1 release kit: choosing one topic for the pin. No screenshots, drawn cards only."""
import sys
import pinterest_course_lesson2 as media
import pinterest_course_lesson4 as layouts
from pinterest_course_release import ROOT,COURSE,PUBLIC,write,copy,csv_file
LESSON=COURSE/'Урок_10_Выбор_одной_темы_для_пина'
PLATFORMS=LESSON/'03_Площадки'
DOCS=LESSON/'04_Документы'
SLIDES=LESSON/'05_Слайды'
BUILD=ROOT/'artifacts/pinterest-course/release-build-lesson10'
VIDEO=ROOT/'artifacts/pinterest-course/lesson-3.1-vertical-v1'
TEXT=ROOT/'docs/pinterest-course/урок-3.1-озвучка.txt'
DATA=PUBLIC/'lesson-3.1/data.json'
VIDEO_NAME='Урок_10_Выбор_одной_темы_для_пина.mp4'
CLIPS=[('Клип_01_Заметка_из_трёх_строк','Как составить заметку для пина?',3,4),
       ('Клип_02_Сужаем_тему','Как сузить тему пина?',5,6)]
SLIDE_NAMES=['Один_пин_одна_задача','Статья_в_пять_идей','Обещание_как_в_статье','Заметка_из_трёх_строк','Ваша_очередь','Сужаем_тему','Проверка']
SOURCE='https://help.pinterest.com/en/business/article/pin-performance-and-distribution'
for name in ['LESSON','PLATFORMS','DOCS','BUILD','VIDEO','TEXT','DATA','VIDEO_NAME','CLIPS']:
 setattr(media,name,globals()[name]);setattr(layouts,name,globals()[name])
media.FRAME_EXACT_CLIPS=False
layouts.GRAPHICS={
 'number':'10','main_title':'Одна тема<br>для пина','subtitle':'Один пин.<br>Один вопрос.',
 'main_rows':[('ВОПРОС','Где разместить вещи?'),('ИЗОБРАЖЕНИЕ','Органайзер на столе'),('ПРОДОЛЖЕНИЕ','Статья с идеями')],'main_footer':'Учебный пример Анны',
 'clip_titles':['Заметка<br>из трёх строк','Сужаем<br>тему'],
 'clip_rows':[[('ВОПРОС','Где разместить вещи?'),('ИЗОБРАЖЕНИЕ','Органайзер на столе'),('ПРОДОЛЖЕНИЕ','Статья с идеями')],[('ШИРОКИЙ','Размытый пин'),('УЗКИЙ','Понятная польза')]],
 'clip_footers':['Три строки — ваш план','Сузьте, если не помещается в одно предложение'],
 'pin_titles':['Заметка<br>для пина','Сузьте<br>тему'],
 'pin_rows':[[('ВОПРОС','Где разместить вещи?'),('ИЗОБРАЖЕНИЕ','Органайзер на столе'),('ПРОДОЛЖЕНИЕ','Статья с идеями')],[('ШИРОКИЙ ВОПРОС','Пин получится размытым'),('УЗКИЙ ВОПРОС','Сразу ясна польза')]],
 'pin_footers':['Повторите для своего материала','Проверьте одним предложением'],
 'card_titles':['Одна тема,<br>один вопрос','Три строки<br>заметки','Проверьте<br>свою тему'],
 'card_rows':[[('ПИН','Одна задача'),('ВОПРОС','Понятный и узкий')],[('ВОПРОС','Где разместить вещи?'),('ИЗОБРАЖЕНИЕ','Органайзер на столе'),('ПРОДОЛЖЕНИЕ','Статья с идеями')],[('ПРОЧИТАЙТЕ','Заметку вслух'),('ПОНЯТНО','Да или нет?')]],
 'card_footers':['Один пин · 1/3','Заметка · 2/3','Проверка · 3/3'],
}


def prepare_texts():
 paragraphs=TEXT.read_text().strip().split('\n\n');assert len(paragraphs)==7
 copy(TEXT,LESSON/'06_Озвучка/Текст_озвучки.txt')
 for name,title,a,b in CLIPS:write(LESSON/f'02_Текст_урока/{name}_текст.txt','\n\n'.join(paragraphs[a:b]))
 title='Выбор одной темы для пина Pinterest | Урок 10'
 description=f'''Десятый урок курса BoostKlient «Pinterest для начинающих» — урок 3.1.

Начинаем новый модуль: готовим первый пин вместе с Анной, вымышленной героиней курса. Главное правило — один пин, одна задача, один понятный вопрос. Разбираем заметку из трёх строк: вопрос, изображение, продолжение.

Официальная рекомендация:
{SOURCE}'''
 for site in ['YouTube','Rutube','VK_Видео']:
  write(PLATFORMS/site/'Тексты/Название.txt',title);write(PLATFORMS/site/'Тексты/Описание.txt',description+('\n\n#Pinterest #Пинтерест #Обучение' if site=='YouTube' else ''));write(PLATFORMS/site/'Тексты/Комментарий_с_заданием.txt','Какую одну задачу решает ваш будущий пин? Получилось уместить её в одно предложение?')
 write(PLATFORMS/'VK_Видео/Тексты/Пост_к_видео.txt','Один пин — одна задача, один понятный вопрос.\n\nВ десятом уроке на примере Анны составляем заметку из трёх строк: вопрос, изображение, продолжение. Попробуйте так же для своего материала.')
 captions=['Один пин — одна задача. В примере: куда поместить ручки и блокнот на маленьком столе. Так проще выбрать фото и объяснить, зачем открывать статью.',
           'Широкий вопрос даёт размытый пин. Узкий вопрос сразу показывает пользу. Если тема не помещается в одно предложение — сузьте её.']
 for site in ['VK_Клипы','Instagram']:
  for i,(name,title,a,b) in enumerate(CLIPS):
   write(PLATFORMS/site/f'Тексты/{name}_название.txt',title);write(PLATFORMS/site/f'Тексты/{name}_описание.txt',captions[i]+('\n\n#Pinterest #Пинтерест' if site=='Instagram' else ''));write(PLATFORMS/site/f'Тексты/{name}_текст_озвучки.txt','\n\n'.join(paragraphs[a:b]))
 write(PLATFORMS/'Instagram/Тексты/Карусель_описание.txt','Один пин — одна задача.\n\nПеред оформлением составьте заметку из трёх строк: вопрос, изображение, продолжение. Так проще держать одну тему.\n\n#Pinterest #Пинтерест')
 pins=[('Как выбрать тему для первого пина Pinterest','В десятом уроке BoostKlient разбираем правило «один пин — одна задача» на примере Анны. Заметка из трёх строк помогает удержать тему.','Карточка BoostKlient: заметка из трёх строк — вопрос, изображение, продолжение.'),
       ('Как сузить тему пина, чтобы он не был размытым','Широкий вопрос даёт размытый пин, узкий — понятную пользу. Десятый урок курса BoostKlient на примере Анны.','Карточка BoostKlient: широкий вопрос против узкого вопроса.')]
 for i,(title,description,alt) in enumerate(pins,1):
  assert len(title)<=100 and len(description)<=500
  for name,text in [('Название.txt',title),('Описание.txt',description),('Альтернативный_текст.txt',alt)]:write(PLATFORMS/f'Pinterest/Пин_{i:02}/Тексты/{name}',text)
 posts=['Один пин — одна задача, один понятный вопрос.\n\nВ десятом уроке составляем заметку из трёх строк на примере Анны: вопрос, изображение, продолжение.',
        'Если тема не помещается в одно ясное предложение — сузьте её. Широкий вопрос даёт размытый пин.']
 for i,text in enumerate(posts,1):assert len(text)<=500;write(PLATFORMS/f'Threads/Тексты/Пост_{i:02}.txt',text)


def prepare_docs():
 write(DOCS/'Задание_ученику.txt','Урок 10 · Выбор одной темы для пина\n\nМой материал:\n\nОдна задача, которую решает пин:\n\nЗаметка из трёх строк —\nВопрос:\nИзображение:\nПродолжение:\n\nПрочитали вслух — понятно?')
 write(DOCS/'Источники_и_оформление.md',f'''# Источники и оформление

Текст — урок 3.1 «Выбор одной темы для пина» в `pinterest_course_russian_final.md`; голос — предоставленный `10.wav`, PCM 16 бит, 24 кГц, моно, 85.48 с.

Рекомендация о соответствии изображения и текста странице назначения: {SOURCE}, сверена 5 октября 2026 года.

Анна — вымышленная учебная героиня. Экраны урока — рисованные карточки, не скриншоты интерфейса.

Сборка локальная. Платные генерации и внешние публикации курса не выполнялись.''')
 csv_file(DOCS/'Журнал_выпуска.csv',['Площадка','Материал','Версия','Статус','Дата одобрения','Дата публикации','URL','Проверка страницы'],
  [[site,'Урок 10','01','Сборка выполняется','','','',''] for site in ['YouTube','Rutube','VK Видео']]+
  [[site,name,'01','Сборка выполняется','','','',''] for site in ['VK Клипы','Instagram'] for name,*_ in CLIPS]+
  [['Pinterest',f'Пин {i:02}','01','Подготовлен; требуется отдельное одобрение с конечным URL','','','',''] for i in [1,2]]+
  [['Threads',f'Пост {i:02}','01','Подготовлен; отдельно не одобрен','','','','']for i in [1,2]])


def finalize():
 d,lengths=media.finalize_media()
 for i,title in enumerate(SLIDE_NAMES,1):copy(VIDEO/f'final-{i:02}.png',SLIDES/f'{i:02}_{title}.png')
 clips='\n'.join(f'- [{title}](../01_Видео/{name}.mp4): {lengths[name]:.2f} с.' for name,title,*_ in CLIPS)
 write(DOCS/'Что_где_лежит.md',f'''# Урок 10 · Выбор одной темы для пина

- [Полный урок](../01_Видео/{VIDEO_NAME}): {d['duration']:.2f} с.
{clips}
- [Текст озвучки](../06_Озвучка/Текст_озвучки.txt), [субтитры](../02_Текст_урока/Субтитры_полного_урока.srt).
- [Площадки](../03_Площадки): YouTube, Rutube, VK Видео, VK Клипы, Pinterest, Instagram, Threads.
- [Слайды](../05_Слайды): семь кадров итогового MP4.
- [Задание](Задание_ученику.txt), [источники](Источники_и_оформление.md).

MP4 H.264 / AAC, 1080×1920, 30 кадров/с. Подсветка слов по выравниванию: {len(d['words'])} слов, {d['interpolatedWords']} интерполированных отметок.

Видео одобрено пользователем 5 октября 2026 года; не опубликовано.''')
 print('Lesson 10 finalized.',flush=True)


if __name__=='__main__':
 if '--finalize' in sys.argv:finalize()
 else:prepare_texts();prepare_docs();layouts.prepare_graphics();print(LESSON)
