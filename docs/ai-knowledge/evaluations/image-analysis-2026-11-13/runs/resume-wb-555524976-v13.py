"""One requested card, frozen production review function, no retries or labels."""
import csv
import hashlib
import io
import json
import os
import statistics
import sys
import time
from types import SimpleNamespace
from copy import deepcopy
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.conf import settings
from PIL import Image, ImageOps
from apps.strategist.image_analysis_test import (
    IMAGE_PROMPT_VERSION, IMAGE_RATING_VERSION, ImageReviewError,
    _image_prompt, review_image,
)
from apps.strategist.providers import GigaChatProvider

article = '555524976'
root = Path(settings.MEDIA_ROOT) / 'image-analysis-test' / article
previous_dir = Path('/app/var/strategist-eval/image-analysis/wb-555524976-v13-2026-11-13')
previous = json.loads((previous_dir / 'results.json').read_text())
output = previous_dir.with_name(previous_dir.name + '-resume-01')
target = output / 'results.json'
if target.exists():
    raise SystemExit('Refusing to overwrite an existing paid run')
source = json.loads((output / 'source.json').read_text())
inventory = list(csv.DictReader((root / 'inventory.csv').open()))
count = len(inventory)
assert count == source['photo_count'] and 1 <= count <= 100
prompt = _image_prompt(source['title'], source['category'])
assert hashlib.sha256(Path('/app/apps/strategist/image_analysis_test.py').read_bytes()).hexdigest() == previous['code_sha256']
assert prompt == previous['prompt']
assert previous['rows'][0]['actual'] and previous['rows'][1]['error']
report = dict(
    schema_version=1, started_at=datetime.now(timezone.utc).isoformat(),
    article=article, source_url=f'https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=MI',
    product_name=source['title'], category=source['category'],
    requested_model='GigaChat-2-Pro', prompt_version=IMAGE_PROMPT_VERSION,
    rating_version=IMAGE_RATING_VERSION, temperature=0.1, max_tokens=450,
    prompt=prompt, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
    code_sha256=hashlib.sha256(Path('/app/apps/strategist/image_analysis_test.py').read_bytes()).hexdigest(),
    automatic_retries=False, explicit_owner_continuation=True, previous_run=str(previous_dir / 'results.json'), selected=count, batch_size=8, max_new_chat_attempts=19,
    labels_confirmed=False, accuracy=None, batch_aborted=False, rows=[],
)

first = deepcopy(previous['rows'][0])
first['source_run'] = str(previous_dir / 'results.json')
for stage in first['stages']: stage['origin'] = 'previous_run'
report['rows'].append(first)

class ReuseAssessment:
    def __init__(self, client):
        self.client = client
        self.used = False
    def chat(self, request):
        if not self.used:
            self.used = True
            saved = previous['rows'][1]['stages'][0]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=saved['raw_response']))], usage=saved.get('usage'), model=saved.get('response_model'))
        return self.client.chat(request)

def save():
    stages = [s for row in report['rows'] for s in row['stages'] if s.get('origin') not in ('previous_run','reused_assessment')]
    usages = [s['usage'] for s in stages if s.get('usage')]
    latencies = [r['seconds'] for r in report['rows'] if r.get('actual')]
    report['summary'] = dict(
        selected=count, processed=len(report['rows']),
        verdicts=dict(Counter(r['actual'] for r in report['rows'] if r.get('actual'))),
        errors=sum(bool(r.get('error')) for r in report['rows']),
        chat_attempts=len(stages), chat_responses=sum(s.get('raw_response') is not None for s in stages),
        usage_complete=len(usages)==len(stages),
        usage={k:sum(u.get(k) or 0 for u in usages) for k in ('prompt_tokens','completion_tokens','total_tokens')},
        median_seconds=round(statistics.median(latencies),3) if latencies else None,
        money_cost=None,
    )
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    temporary.replace(target)

save()
seen = {}
try:
    with GigaChatProvider()._client() as client:
        for offset in range(0, count, 8):
            if report['batch_aborted']:
                break
            print(json.dumps({'batch':offset//8+1,'images':list(range(offset+1,min(offset+9,count+1)))}),flush=True)
            for item in inventory[offset:offset+8]:
                index = int(item['index'])
                if index == 1:
                    continue
                row = dict(image_number=index, filename=item['file'], sha256=item['sha256'],
                           width=int(item['width']), height=int(item['height']),
                           source_url=item['url'], stages=[], actual=None, error=None)
                started = time.monotonic()
                file_id = None
                try:
                    path = root / item['file']
                    assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
                    with Image.open(path) as im:
                        image = ImageOps.exif_transpose(im).convert('RGB')
                        jpeg = io.BytesIO()
                        image.save(jpeg, 'JPEG', quality=84, optimize=True)
                    digest = hashlib.sha256(jpeg.getvalue()).hexdigest()
                    row['normalized_sha256'] = digest
                    if min(image.size)<600:
                        row.update(actual='skipped_small',label='Пропущено: маленькое фото')
                    elif digest in seen:
                        row.update(actual='skipped_duplicate',duplicate_of=seen[digest],label='Пропущено: дубль')
                    else:
                        seen[digest] = index
                        file_id = client.upload_file((f'wb-{article}-{index:02d}.jpg',jpeg.getvalue(),'image/jpeg'),purpose='general').id_
                        review,score,status,label,reasons = review_image(
                            ReuseAssessment(client) if index == 2 else client,file_id,product_name=source['title'],category=source['category'],
                            stages=row['stages'],model='GigaChat-2-Pro',prompt=prompt,
                        )
                        row.update(review=review,score=score,actual=status,label=label,reasons=reasons)
                except ImageReviewError as error:
                    row['error'] = dict(type=type(error).__name__,message=str(error))
                except Exception as error:
                    row['error'] = dict(type=type(error).__name__)
                    http_status = error.args[1] if len(error.args)>1 and type(error.args[1]) is int else None
                    if http_status is not None: row['error']['http_status'] = http_status
                    if http_status in (401,403,429): report['batch_aborted'] = True
                finally:
                    if index == 2 and row['stages']:
                        row['stages'][0]['origin'] = 'reused_assessment'
                        row['stages'][0]['source_run'] = str(previous_dir / 'results.json')
                        row['previous_failed_attempt'] = {'source_run':str(previous_dir / 'results.json'),'error':previous['rows'][1]['error']}
                    if file_id:
                        try:
                            client.delete_file(file_id)
                        except Exception as error:
                            row['file_cleanup_error'] = type(error).__name__
                    row['seconds'] = round(time.monotonic()-started,3)
                    report['rows'].append(row)
                    save()
                    print(json.dumps({'image':index,'verdict':row['actual'],'score':row.get('score'),'error':row['error'],'seconds':row['seconds']},ensure_ascii=False),flush=True)
                if report['batch_aborted']:
                    break
except Exception as error:
    report.update(provider_error=type(error).__name__,batch_aborted=True)
finally:
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    save()
print(json.dumps({k:v for k,v in report['summary'].items() if k not in ('usage','money_cost')},ensure_ascii=False),flush=True)
