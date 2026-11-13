"""Compose authentic headed-browser captures over existing course audio/captions."""
from pathlib import Path
import json,math,subprocess,hashlib,csv
from PIL import Image,ImageDraw,ImageFont,ImageOps
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/pinterest-course/rebuild-all/01'
SOURCE=ROOT/'artifacts/pinterest-course/lesson-1.1-vertical-v5/lesson-1.1-vertical-v5.mp4'
DATA=ROOT/'video/pinterest-lesson/public/data.json'
VIDEO=OUT/'Урок_01_Реальный_аккаунт.mp4'
SCENES=[('Ищем идеи в Pinterest','02-real-search.png','Реальный поиск в учебном аккаунте Анны.'),('Поиск по конкретной задаче','07-real-search-task.png','Запрос — учебный пример; популярность не измерена.'),('Пин и тематическая доска','08-real-training-board.png','Реальная доска «Рабочее место дома». Здесь сохранены чужие пины.'),('Учебный профиль Анны','01-real-training-profile.png','Анна — вымышленная героиня. Статья в её истории — условный пример.'),('Куда ведёт ссылка из пина','10-real-saved-pin-1107111520940321632.png','Чужой сохранённый пин. Кнопка «Открыть веб-сайт» ведёт на Amazon.'),('Своих публикаций пока нет','09-real-no-created-pins.png','Результаты и продажи не измерялись. Вымышленных цифр нет.'),('Найдите три идеи для проекта','07-real-search-task.png','Реальные результаты поиска. Сформулируйте тему своей публикации.')]
def font(size):
 f=ImageFont.truetype(str(ROOT/'video/pinterest-lesson/public/Manrope.ttf'),size);f.set_variation_by_axes([650]);return f

def wrap(text,f,width):
 lines=['']
 for w in text.split():
  s=(lines[-1]+' '+w).strip()
  if f.getlength(s)>width:lines.append(w)
  else:lines[-1]=s
 return '\n'.join(lines)

def prepare():
 logo=Image.open(ROOT/'artifacts/pinterest-course/lesson-1.1-vertical-v5/final-01.png').convert('RGB').crop((0,0,650,155))
 rows=[]
 for i,(title,name,note) in enumerate(SCENES,1):
  p=OUT/name;assert p.exists(),p
  frame=Image.new('RGB',(1080,1468),'#f1eee6');frame.paste(logo,(0,0));d=ImageDraw.Draw(frame)
  d.text((795,78),f'УРОК 1 · {i}/7',font=font(28),fill='#6f7476')
  d.multiline_text((64,175),wrap(title,font(68),950),font=font(68),fill='#171b20',spacing=6)
  image=Image.open(p).convert('RGB');image.thumbnail((1000,940),Image.Resampling.LANCZOS)
  frame.paste(image,((1080-image.width)//2,355))
  d.multiline_text((64,1330),wrap(note,font(30),950),font=font(30),fill='#6f7476',spacing=6)
  assert d.multiline_textbbox((64,1330),wrap(note,font(30),950),font=font(30),spacing=6)[3]<1468
  frame.save(OUT/f'upper-{i:02}.png')
  rows.append([name,hashlib.sha256(p.read_bytes()).hexdigest(),'Живой учебный аккаунт; видимый браузер','Видимый захват; пользователь отказался от отдельных превью'])
 with (OUT/'Версии_скриншотов.csv').open('w')as stream:
  w=csv.writer(stream);w.writerow(['Файл','SHA256','Источник','Просмотр']);w.writerows(rows)
 (OUT/'scenes.json').write_text(json.dumps(SCENES,ensure_ascii=False,indent=2))

def render():
 data=json.loads(DATA.read_text());starts=[math.ceil(t*30-1e-8)for t in data['sceneStarts']]
 cmd=['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-hide_banner','-y']
 for i in range(7):cmd+=['-threads','1','-framerate','30','-i',str(OUT/f'upper-{i+1:02}.png')]
 cmd+=['-threads','1','-i',str(SOURCE)]
 filt=[]
 for i in range(7):filt.append(f'[{i}:v]format=yuv420p,loop=loop={starts[i+1]-starts[i]-1}:size=1:start=0,setpts=N/(30*TB)[s{i}]')
 filt.append(''.join(f'[s{i}]'for i in range(7))+'concat=n=7:v=1:a=0[upper]')
 filt.append('[7:v]crop=1080:452:0:1468[lower]');filt.append('[upper][lower]vstack=inputs=2:shortest=1[video]')
 cmd+=['-filter_complex_threads','1','-filter_complex',';'.join(filt),'-map','[video]','-map','7:a:0','-r','30','-frames:v',str(starts[-1]),'-c:v','libx264','-preset','ultrafast','-crf','18','-threads','1','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(VIDEO)]
 with (OUT/'render.log').open('w')as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
 print('Первый новый MP4 собран',flush=True)

if __name__=='__main__':
 import sys
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='render':render()
