from pathlib import Path
import json,hashlib,shutil
R=Path('/home/evgen/bk3.0');O=R/'artifacts/pinterest-course/lesson-10.2-codex-v1';V=R/'artifacts/pinterest-course/visual-lesson-42-codex-v1'
D=json.loads((O/'public/lesson-10.2/data.json').read_text());static=json.loads((O/'storyboard-static.json').read_text());rows={x['file']:x for x in json.loads((V/'capture.json').read_text())};starts=D['sceneStarts']
assert len(starts)==8 and len(static)==7
story=[];prov=[]
for i,item in enumerate(static):
 src=item.get('sourceScreenshot')
 if src:
  r=rows[src];p=V/src;assert r['shownToUser'] and r['realVisibleBrowser'] and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
  prov.append({'scene':i+1,'file':src,'sha256':r['sha256'],'visibleBrowserCapture':True,'shownToUser':True,'reusedFrom':r.get('reusedFrom','previously shown'),'note':r.get('note','')})
 target=O/f"check-{i+1:02}.png";shutil.copy2(O/f"Превью/static-{i+1:02}.png",target)
 story.append({'start':starts[i],'end':starts[i+1],'paragraph':i,'title':item['title'],'source':src,'note':item['body']})
(O/'storyboard.json').write_text(json.dumps(story,ensure_ascii=False,indent=2)+'\n');(O/'source-provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2)+'\n')
print('Сцены привязаны к ASR:',len(story),'реальных источников:',len(prov))
