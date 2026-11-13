"""Owner-requested completion: reuse saved assessments, verify candidates once."""
import hashlib,io,json,os,sys,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from shutil import copyfile,copytree
from types import SimpleNamespace
sys.path.insert(0,'/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from PIL import Image
from apps.strategist.providers import GigaChatProvider
from apps.strategist.image_analysis_test import IMAGE_PROMPT_VERSION,IMAGE_RATING_VERSION,_image_prompt,_verification_prompt,review_image

parent=Path('/app/var/strategist-eval/image-analysis/wb-555524976-v13-2026-11-13-resume-01')
baseline=json.loads((parent/'results.json').read_text())
probe=json.loads((parent/'photo04-description-v14-probe.json').read_text())
out=parent.with_name('wb-555524976-v14-2026-11-13-complete')
out.mkdir(exist_ok=True)
target=out/'results.json'
if target.exists():raise SystemExit('Refusing to overwrite a paid run')
assert len(baseline['rows'])==11
assert probe['prompt']==_verification_prompt(baseline['product_name'],trousers=True)
for row in baseline['rows']:
 assert row['stages'][0]['prompt']==_image_prompt(baseline['product_name'],baseline['category'])
copyfile(parent/'source.json',out/'source.json');copyfile(parent/'contact-sheet.jpg',out/'contact-sheet.jpg')
copytree(parent/'photos',out/'photos',dirs_exist_ok=True)
report=dict(article='555524976',product_name=baseline['product_name'],category=baseline['category'],
 requested_model='GigaChat-2-Pro',prompt_version=IMAGE_PROMPT_VERSION,rating_version=IMAGE_RATING_VERSION,
 code_sha256=hashlib.sha256(Path('/app/apps/strategist/image_analysis_test.py').read_bytes()).hexdigest(),
 prior_runs=[baseline['previous_run'],str(parent/'results.json')],
 selected=11,automatic_retries=False,max_new_verification_calls=5,
 saved_assessments_reused=True,photo04_verification_source=str(parent/'photo04-description-v14-probe.json'),
 labels_confirmed=False,accuracy=None,rows=[],started_at=datetime.now(timezone.utc).isoformat())
def save():
 report['summary']=dict(processed=len(report['rows']),verdicts=dict(Counter(row['actual'] for row in report['rows'] if row.get('actual'))),errors=sum(bool(row.get('error')) for row in report['rows']))
 temp=target.with_suffix('.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,indent=2));temp.replace(target)
class CachedAssessment:
 def __init__(self,client,row):self.client=client;self.row=row;self.count=0
 def chat(self,request):
  self.count+=1
  saved=self.row['stages'][0] if self.count==1 else probe['stages'][0] if self.row['image_number']==4 else None
  if saved:
   assert request.messages[0].content==saved['prompt']
   return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=saved['raw_response']))],usage=saved.get('usage'),model=saved.get('response_model'))
  return self.client.chat(request)
save()
with GigaChatProvider()._client() as client:
 for old in baseline['rows']:
  n=old['image_number'];row={k:old[k] for k in ('image_number','filename','sha256','width','height','source_url')}
  row.update(stages=[],actual=None,error=None);file_id=None;started=time.monotonic()
  try:
   data=(out/'photos'/row['filename']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
   if n in (2,3,6,8,11):
    with Image.open(io.BytesIO(data)) as im:
     jpeg=io.BytesIO();im.convert('RGB').save(jpeg,'JPEG',quality=84,optimize=True)
    file_id=client.upload_file((f'wb-555524976-{n:02d}-v14.jpg',jpeg.getvalue(),'image/jpeg'),purpose='general').id_
   review,score,status,label,reasons=review_image(CachedAssessment(client,old),file_id or 'saved-stage-only',product_name=baseline['product_name'],category=baseline['category'],stages=row['stages'])
   row.update(review=review,score=score,actual=status,label=label,reasons=reasons)
  except Exception as error:
   row['error']={'type':type(error).__name__}
   if len(error.args)>1 and type(error.args[1]) is int:row['error']['http_status']=error.args[1]
  finally:
   if row['stages']:
    row['stages'][0].update(origin='saved_assessment',source_run=str(parent/'results.json'))
   if n==4 and len(row['stages'])>1:row['stages'][1].update(origin='saved_v14_description_probe',source_run=str(parent/'photo04-description-v14-probe.json'))
   if file_id:
    try:client.delete_file(file_id)
    except Exception as error:row['file_cleanup_error']=type(error).__name__
   row['seconds']=round(time.monotonic()-started,3);report['rows'].append(row);save()
   print(json.dumps({'image':n,'actual':row['actual'],'error':row['error']},ensure_ascii=False),flush=True)
report['finished_at']=datetime.now(timezone.utc).isoformat();save()
assert len(report['rows'])==11 and not any(row['error'] for row in report['rows'])
for row in report['rows']:
 for stage in row['stages']:
  value=json.loads(stage['raw_response'].strip().removeprefix('```json').removesuffix('```'))
  assert isinstance(value.get('description'),str) and value['description'].strip(),row['image_number']
print(json.dumps(report['summary'],ensure_ascii=False),flush=True)
