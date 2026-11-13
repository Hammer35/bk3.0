"""Diagnostic: change verification prompt only, same JPEG/model/settings."""
import io,json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,'/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from PIL import Image
from apps.strategist.providers import GigaChatProvider
from apps.strategist.image_analysis_test import _stage

root=Path('/app/var/strategist-eval/image-analysis/wb-445965661-2026-11-13')
target=root/'evidence-probe-v1.json'
if target.exists(): raise SystemExit('Refusing to repeat paid probe')
prompt=(
    'Проверь ВСЁ изображение, особенно края и боковые полосы. Не оценивай красоту или пригодность. '
    '1. Есть ли фотоколлаж: отдельные фото-вставки, вертикальная фотоплёнка, подборка одежды с аксессуарами '
    'на разных фонах? Если есть хотя бы одна отдельная фото-вставка — layout=COLLAGE. '
    '2. Найди пояс джинсов и КОНЕЦ каждой штанины: край ткани у обуви, ниже которого джинсов уже нет. '
    'Продолжение штанины за нижний край картинки — OUTSIDE, это НЕ видимый конец. '
    'Крупный план карманов, ягодиц или бёдер не показывает низ штанин. Не додумывай нижние части. '
    'Для каждого конца скажи, виден ли край ткани у обуви (VISIBLE), он находится за границей картинки '
    '(OUTSIDE), закрыт другим предметом (HIDDEN) или определить нельзя (UNCLEAR). '
    'Верни JSON: description (что действительно находится у нижней границы и какие фото-вставки есть), '
    'layout (PHOTO или COLLAGE), waist (VISIBLE, OUTSIDE, HIDDEN или UNCLEAR), '
    'left_hem (VISIBLE, OUTSIDE, HIDDEN или UNCLEAR), right_hem (VISIBLE, OUTSIDE, HIDDEN или UNCLEAR).'
)
report=dict(hypothesis='Observable waist and hems plus explicit photo-strip detection instead of WHOLE conclusion',changed_variable='verification_prompt_only',requested_model='GigaChat-2-Pro',automatic_retries=False,selected=[3,9,13,14,16,1,2,12],prompt=prompt,rows=[],started_at=datetime.now(timezone.utc).isoformat(),batch_aborted=False)
def save(): target.write_text(json.dumps(report,ensure_ascii=False,indent=2))
save()
try:
 with GigaChatProvider()._client() as client:
  for n in report['selected']:
   row=dict(image_number=n,stages=[]); file_id=None; started=time.monotonic()
   try:
    with Image.open(root/'photos'/f'{n:02d}.webp') as im:
     jpeg=io.BytesIO();im.convert('RGB').save(jpeg,'JPEG',quality=84,optimize=True)
    file_id=client.upload_file((f'evidence-{n:02d}.jpg',jpeg.getvalue(),'image/jpeg'),purpose='general').id_
    raw=_stage(client,file_id,prompt,stages=row['stages'],name='verification_probe',model='GigaChat-2-Pro')
    row['check']=json.loads(raw.strip().removeprefix('```json').removesuffix('```'))
   except Exception as error:
    row['error']=type(error).__name__;report['batch_aborted']=True
   finally:
    if file_id:
     try:client.delete_file(file_id)
     except Exception as error:row['file_cleanup_error']=type(error).__name__
    row['seconds']=round(time.monotonic()-started,3);report['rows'].append(row);save()
    print(json.dumps({k:v for k,v in row.items() if k!='stages'},ensure_ascii=False),flush=True)
   if report['batch_aborted']:break
except Exception as error:
 report['provider_error']=type(error).__name__;report['batch_aborted']=True
finally:
 report['finished_at']=datetime.now(timezone.utc).isoformat();save()
