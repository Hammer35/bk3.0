"""Offline symptom replay; frozen baseline answers, no API calls."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from apps.strategist.image_analysis_test import review_image

report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/app/var/strategist-eval/image-analysis/wb-445965661-2026-11-13/results.json')
report = json.loads(report_path.read_text())
failures = []
for row in report['rows']:
    if row['image_number'] not in (3, 9, 13, 14, 16):
        continue
    with patch('apps.strategist.image_analysis_test._stage', side_effect=[s['raw_response'] for s in row['stages']]):
        result = review_image(None, 'offline', product_name=report['product_name'], category=report['category'], stages=[])
    print(row['image_number'], result[2])
    if result[2] == 'recommended':
        failures.append(row['image_number'])
assert not failures, f'Unsafe automatic approvals reproduced: {failures}'
