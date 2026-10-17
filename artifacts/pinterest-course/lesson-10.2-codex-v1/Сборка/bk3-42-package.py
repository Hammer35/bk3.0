from pathlib import Path
import csv,hashlib,json,math,re,shutil,subprocess,sys
from PIL import Image
R=Path('/home/evgen/bk3.0');O=R/'artifacts/pinterest-course/lesson-10.2-codex-v1';V=R/'artifacts/pinterest-course/visual-lesson-42-codex-v1';NUM='42';MODULE='10.2';SLUG='Проверка_аккаунта_и_пинов'
PARENT=R/'КУРС_PINTEREST/_АРХИВ_старые_версии/Переделка_с_реальным_аккаунтом';F=PARENT/f'Урок_{NUM}_{SLUG}_Реальные_экраны_v1';STAGE=O/'release-stage-v1';VIDEO=O/'Урок_42_Проверка_аккаунта_и_пинов_Реальные_экраны_v1.mp4';VIDEO_NAME=VIDEO.name;DATA=json.loads((O/'public/lesson-10.2/data.json').read_text());DOC=R/'docs/pinterest-course/урок-10.2-озвучка.txt';SCEN=R/'docs/pinterest-course/урок-10.2-сценарий.md';TEXT=DOC.read_text();PARAS=[p.strip() for p in TEXT.strip().split('\n\n') if p.strip()]
PLATFORMS=['YouTube','Rutube','VK_Видео','VK_Клипы','Instagram','Pinterest','Threads'];CLIPS=[('Клип_01_Основные_условия',1,3),('Клип_02_Проверка_и_шаг',5,7)]
if NUM=='33':CLIPS=[('Клип_01_Проверка_источника',1,3),('Клип_02_Сверка_перед_публикацией',5,7)]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s.rstrip()+'\n',encoding='utf-8')
def verify_decode(p):subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(p),'-f','null','-'],check=True)
def probe(p):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def srt_time(ms):
 h,rest=divmod(round(ms),3600000);m,rest=divmod(rest,60000);s,rest=divmod(rest,1000);return f'{h:02}:{m:02}:{s:02},{rest:03}'
def clip_srt(start,end):
 out=[]
 for page in DATA['pages']:
  a,b=max(page['startMs'],round(start*1000)),min(page['endMs'],round(end*1000))
  if a<b:
   body='\n'.join(' '.join(w['text'].strip() for w in line) for line in page['lines'])
   out.append(f'{len(out)+1}\n{srt_time(a-round(start*1000))} --> {srt_time(b-round(start*1000))}\n{body}')
 return '\n\n'.join(out)+'\n'
def assert_subtitles_bounds(srt,duration):
 def ms(t):
  h,m,s,f=map(int,t.replace(',',':').split(':'));return ((h*60+m)*60+s)*1000+f
 for b in srt.strip().split('\n\n'):
  ts=b.splitlines()[1].split(' --> ');a,z=map(ms,ts);assert 0<=a<z<=round(duration*1000)+100

assert len(PARAS)==7 and len(DATA['sceneStarts'])==8 and VIDEO.exists() and (O/'42.wav').exists()
video_info=probe(VIDEO);audio_path=O/'42.wav';wav_sha=sha(audio_path);video_sha=sha(VIDEO);duration=float(DATA['duration'])
vs=next(x for x in video_info['streams'] if x['codec_type']=='video');as_=next(x for x in video_info['streams'] if x['codec_type']=='audio')
assert (vs['width'],vs['height'])==(1080,1920) and vs['avg_frame_rate']=='30/1'
assert abs(float(video_info['format']['duration'])-duration)<0.15
verify_decode(VIDEO);assert_subtitles_bounds((O/'subtitles.srt').read_text(),duration)
cap_rows=json.loads((V/'capture.json').read_text());used_rows=json.loads((O/'source-provenance.json').read_text());used={x['file'] for x in used_rows}
assert used and all(next(x for x in cap_rows if x['file']==f)['shownToUser'] and next(x for x in cap_rows if x['file']==f).get('account')=='Анна — Порядок дома' for f in used)
for row in used_rows:
 p=V/row['file'];assert sha(p)==row['sha256']
assert not F.exists() and not STAGE.exists()
lock=R/'scripts/lock.sh';take=subprocess.run([str(lock),'take','КУРС_PINTEREST','codex',f'пакет урока {NUM}'],capture_output=True,text=True)
if take.returncode:raise RuntimeError('Не удалось взять lock КУРС_PINTEREST; выпуск не создавался')
try:
 STAGE.mkdir(parents=True)
 def stage(rel):return STAGE/rel
 copy(VIDEO,stage(f'01_Видео/{VIDEO_NAME}'));copy(O/'subtitles.srt',stage('02_Текст_урока/Субтитры_полного_урока.srt'));write(stage('02_Текст_урока/Текст_озвучки.txt'),TEXT);copy(audio_path,stage(f'06_Озвучка/{NUM}_Оригинал.wav'))
 helper=O/'Сборка/pinterest_course_release.py'
 sys.path.insert(0,str(helper.parent));import pinterest_course_release as release
 clipinfo=[]
 for clip,a,b in CLIPS:
  start,end=DATA['sceneStarts'][a],DATA['sceneStarts'][b];frames=math.ceil(end*30-1e-8)-math.ceil(start*30-1e-8);target=stage(f'01_Видео/{clip}.mp4')
  subprocess.run(['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-v','error','-threads','1','-y','-ss',str(start),'-i',str(VIDEO),'-t',str(end-start),'-map','0:v:0','-map','0:a:0','-filter_threads','1','-vf','setpts=PTS-STARTPTS','-frames:v',str(frames),'-c:v','libx264','-preset','ultrafast','-crf','18','-threads','1','-c:a','aac','-b:a','128k','-movflags','+faststart',str(target)],check=True)
  verify_decode(target);copy(target,stage(f'03_Площадки/VK_Клипы/Видео/{clip}.mp4'));copy(target,stage(f'03_Площадки/Instagram/Видео/{clip}.mp4'))
  subs=clip_srt(start,end);assert ' '.join(' '.join(x.splitlines()[2:]) for x in subs.strip().split('\n\n')).split()==('\n\n'.join(PARAS[a:b])).split();assert_subtitles_bounds(subs,end-start)
  write(stage(f'02_Текст_урока/{clip}_субтитры.srt'),subs);write(stage(f'02_Текст_урока/{clip}_текст.txt'),'\n\n'.join(PARAS[a:b]));write(stage(f'03_Площадки/VK_Клипы/{clip}_субтитры.srt'),subs);write(stage(f'03_Площадки/Instagram/{clip}_субтитры.srt'),subs);clipinfo.append({'name':clip,'start':start,'end':end,'frames':frames,'sha256':sha(target)})
 for f in used:
  row=next(x for x in cap_rows if x['file']==f);assert row['shownToUser'] and row.get('realVisibleBrowser',True) and row.get('account')=='Анна — Порядок дома';target=stage(f'05_Слайды/Реальные_скриншоты/{f}');copy(V/f,target);assert sha(target)==row['sha256']
 rows=[x for x in cap_rows if x['file'] in used];write(stage('04_Документы/Источники.json'),json.dumps(rows,ensure_ascii=False,indent=2));copy(V/'Версии_скриншотов.csv',stage('04_Документы/Версии_скриншотов.csv'))
 for i in range(1,8):copy(O/f'check-{i:02}.png',stage(f'05_Слайды/Сцена_{i:02}.png'))
 for f in ['storyboard.json','source-provenance.json','build-info.json','word-timings.json','transcript.json','subtitles.srt','captions.ass','slides.ffconcat','audio-generation.json','static-preview-source.json']:
  p=O/f
  if p.exists():copy(p,stage(f'04_Документы/{f}'))
 copy(SCEN,stage('04_Документы/Сценарий.md'));copy(DOC,stage('02_Текст_урока/Текст_озвучки.txt'));write(stage('04_Документы/Источники_и_ограничения.txt'),'Источники и пределы выводов указаны в сценарии. Использованы только ранее показанные реальные экраны аккаунта Анны. Публикации в Pinterest не было.\n')
 build_target=stage('04_Документы/Сборка');build_target.mkdir(parents=True,exist_ok=True)
 for p in (O/'Сборка').iterdir():
  if p.is_file() and p.name!='audio_request.py' and p.suffix in ('.py','.md','.json'):
   try:content=p.read_text(encoding='utf-8')
   except UnicodeDecodeError:continue
   if re.search(r'\bAQ\.[A-Za-z0-9_-]{15,}',content):continue
   copy(p,build_target/p.name)
 cover=Image.open(O/'check-01.png').convert('RGB').crop((0,0,1080,1450));cover_path=stage('05_Слайды/Обложка.jpg');cover.save(cover_path,quality=93)
 title=SCEN.read_text().splitlines()[0].lstrip('# ').strip();description=PARAS[0]+'\n\n'+PARAS[-1]+'\n\nМатериалы и ограничения — в уроке.'
 for platform in PLATFORMS:
  p=stage(f'03_Площадки/{platform}');write(p/'Текст_публикации.txt',title+'\n\n'+description);copy(cover_path,p/'Обложка.jpg')
  if platform in ('YouTube','Rutube','VK_Видео'):
   copy(VIDEO,p/f'Видео/{VIDEO_NAME}');copy(O/'subtitles.srt',p/'Субтитры.srt')
  elif platform in ('VK_Клипы','Instagram'):
   for clip,a,b in CLIPS:copy(stage(f'01_Видео/{clip}.mp4'),p/f'Видео/{clip}.mp4')
  elif platform=='Pinterest':write(p/'Материал.txt','Локально подготовленный материал. Новая публикация не создана.\n')
  elif platform=='Threads':write(p/'Материал.txt','Локальный текстовый пакет. Не опубликован.\n')
 write(stage('04_Документы/Клипы.json'),json.dumps(clipinfo,ensure_ascii=False,indent=2))
 platforms=[p.name for p in (STAGE/'03_Площадки').iterdir() if p.is_dir()];assert sorted(platforms)==sorted(PLATFORMS)
 for p in [STAGE/'01_Видео'/VIDEO_NAME]+[STAGE/f'03_Площадки/{site}/Видео/{VIDEO_NAME}' for site in ('YouTube','Rutube','VK_Видео')]:assert sha(p)==video_sha
 assert sha(STAGE/f'06_Озвучка/{NUM}_Оригинал.wav')==wav_sha
 secret=re.compile(rb'\bAQ\.[A-Za-z0-9_-]{15,}')
 for p in STAGE.rglob('*'):
  if p.is_file() and p.suffix.lower() in ('.py','.md','.txt','.json','.csv'):
   assert not secret.search(p.read_bytes()),f'Credential-like string in {p}'
 verification={'status':'locally_verified_unpublished_package','lesson':NUM,'courseId':MODULE,'videoSha256':video_sha,'audioSha256':wav_sha,'durationSeconds':duration,'videoWidth':vs['width'],'videoHeight':vs['height'],'fps':vs['avg_frame_rate'],'fullDecode':True,'screenshots':len(used),'clips':clipinfo,'platforms':platforms,'credentialScan':'passed','published':False}
 write(stage('04_Документы/release-verification.json'),json.dumps(verification,ensure_ascii=False,indent=2));STAGE.rename(F)
 print(json.dumps({'release':str(F.relative_to(R)),'screenshots':len(used),'clips':2,'platforms':7,'sha256':video_sha},ensure_ascii=False))
except Exception:
 if STAGE.exists():shutil.rmtree(STAGE)
 raise
finally:subprocess.run([str(lock),'free','КУРС_PINTEREST','codex'],capture_output=True,text=True)
