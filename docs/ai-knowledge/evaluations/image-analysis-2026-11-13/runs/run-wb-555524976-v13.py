"""One requested card, frozen production review function, no retries or labels."""
import csv
import hashlib
import io
import json
import os
import statistics
import sys
import time
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
output = Path('/app/var/strategist-eval/image-analysis/wb-555524976-v13-2026-11-13')
target = output / 'results.json'
if target.exists():
    raise SystemExit('Refusing to overwrite an existing paid run')
source = json.loads((output / 'source.json').read_text())
inventory = list(csv.DictReader((root / 'inventory.csv').open()))
count = len(inventory)
assert count == source['photo_count'] and 1 <= count <= 100
prompt = _image_prompt(source['title'], source['category'])
report = dict(
    schema_version=1, started_at=datetime.now(timezone.utc).isoformat(),
    article=article, source_url=f'https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=MI',
    product_name=source['title'], category=source['category'],
    requested_model='GigaChat-2-Pro', prompt_version=IMAGE_PROMPT_VERSION,
    rating_version=IMAGE_RATING_VERSION, temperature=0.1, max_tokens=450,
    prompt=prompt, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
    code_sha256=hashlib.sha256(Path('/app/apps/strategist/image_analysis_test.py').read_bytes()).hexdigest(),
    automatic_retries=False, selected=count, batch_size=8, max_chat_attempts=2*count,
    labels_confirmed=False, accuracy=None, batch_aborted=False, rows=[],
)

def save():
    stages = [s for row in report['rows'] for s in row['stages']]
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
                            client,file_id,product_name=source['title'],category=source['category'],
                            stages=row['stages'],model='GigaChat-2-Pro',prompt=prompt,
                        )
                        row.update(review=review,score=score,actual=status,label=label,reasons=reasons)
                except ImageReviewError as error:
                    row['error'] = dict(type=type(error).__name__,message=str(error))
                except Exception as error:
                    row['error'] = dict(type=type(error).__name__)
                    report['batch_aborted'] = True
                finally:
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
