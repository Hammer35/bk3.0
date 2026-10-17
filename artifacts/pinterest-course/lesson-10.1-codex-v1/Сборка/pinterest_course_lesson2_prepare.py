"""Align a supplied Fenrir WAV locally; never synthesize or reuse lesson 1 voice."""
from pathlib import Path
from difflib import SequenceMatcher
import argparse
import json
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
TOOLS=Path.home()/'.local/share/pinterest-video-tools'
PUBLIC=ROOT/'video/pinterest-lesson/public'
LESSON_ID='3.3' if '--lesson-3.3' in sys.argv else '3.2' if '--lesson-3.2' in sys.argv else '3.1' if '--lesson-3.1' in sys.argv else '2.5' if '--lesson-2.5' in sys.argv else '2.4' if '--lesson-2.4' in sys.argv else '2.3' if '--lesson-2.3' in sys.argv else '2.2' if '--lesson-2.2' in sys.argv else '2.1' if '--lesson-2.1' in sys.argv else '1.4' if '--lesson-1.4' in sys.argv else '1.3' if '--lesson-1.3' in sys.argv else '1.2'
OUT=ROOT/f'artifacts/pinterest-course/lesson-{LESSON_ID}-vertical-v1'
TEXT=ROOT/f'docs/pinterest-course/урок-{LESSON_ID}-озвучка.txt'


def transcribe(voice):
    from faster_whisper import WhisperModel
    import wave
    import numpy as np
    models=sorted((TOOLS/'asr-models/models--Systran--faster-whisper-base/snapshots').glob('*/model.bin'))
    assert models,'Локальная модель Whisper base не найдена.'
    model=WhisperModel(str(models[-1].parent),device='cpu',compute_type='int8',cpu_threads=1,num_workers=1)
    audio=OUT/'asr-input.wav'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-threads','1','-y','-i',str(voice),'-ar','16000','-ac','1',str(audio)],check=True)
    # Read PCM directly, as in lesson 1: installed PyAV lacks metadata_errors.
    with wave.open(str(audio),'rb') as source:
        pcm=np.frombuffer(source.readframes(source.getnframes()),dtype=np.int16).astype(np.float32)/32768
    segments,_=model.transcribe(pcm,language='ru',word_timestamps=True,beam_size=3,vad_filter=False)
    rows=[]
    for segment in segments:
        rows.append({'start':segment.start,'end':segment.end,'text':segment.text,
                     'words':[{'start':w.start,'end':w.end,'word':w.word} for w in segment.words]})
        print(f'{segment.start:.2f}–{segment.end:.2f}',flush=True)
    (OUT/'transcript.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))


def align(voice):
    from PIL import ImageFont
    from pinterest_course_release import srt_time
    assert voice.exists(),voice
    (PUBLIC/f'lesson-{LESSON_ID}').mkdir(parents=True,exist_ok=True)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(voice)]))
    duration=float(info['format']['duration'])
    assert duration>10,'Запись слишком короткая для полного текста.'
    words=TEXT.read_text().split()
    spoken=[w for row in json.loads((OUT/'transcript.json').read_text()) for w in row['words']]
    def norm(text):return re.sub(r'[^а-яёa-z0-9]','',text.lower()).replace('ё','е').replace('pinterest','пинтерест')
    matcher=SequenceMatcher(None,list(map(norm,words)),[norm(w['word']) for w in spoken],autojunk=False)
    anchors={block.a+k:(spoken[block.b+k]['start'],spoken[block.b+k]['end']) for block in matcher.get_matching_blocks() for k in range(block.size)}
    assert len(anchors)/len(words)>=.85,f'Озвучка не совпадает с текстом: {len(anchors)}/{len(words)} слов.'
    times=[]
    for i in range(len(words)):
        if i in anchors:times.append(anchors[i]);continue
        left=max((k for k in anchors if k<i),default=-1)
        right=min((k for k in anchors if k>i),default=len(words))
        a=anchors[left][1] if left>=0 else 0
        b=anchors[right][0] if right<len(words) else duration
        step=max(0,b-a)/(right-left-1)
        offset=i-left-1
        times.append((a+offset*step,a+(offset+1)*step))
    tokens=[{'text':(' ' if i else '')+word,'startMs':round(times[i][0]*1000),'endMs':round(times[i][1]*1000),
             'timingSource':'recognized' if i in anchors else 'interpolated'} for i,word in enumerate(words)]
    # Repair adjacent zero-length tokens together: repairing one at a time can
    # erase the preceding token's duration (for example a dash followed by «к»).
    i=0
    while i<len(tokens):
        if tokens[i]['endMs']!=tokens[i]['startMs']:
            i+=1;continue
        end=i+1
        while end<len(tokens) and tokens[end]['endMs']==tokens[end]['startMs']:end+=1
        count=end-i
        left=max(tokens[i-1]['startMs']+1 if i else 0,tokens[i]['startMs']-34*count)
        right=min(tokens[end]['endMs']-1 if end<len(tokens) else round(duration*1000),tokens[end-1]['endMs']+34*count)
        assert right-left>=count,'Недостаточно времени для разметки группы слов.'
        for offset in range(count):
            tokens[i+offset]['startMs']=left+(right-left)*offset//count
            tokens[i+offset]['endMs']=left+(right-left)*(offset+1)//count
        if i:tokens[i-1]['endMs']=left
        if end<len(tokens):tokens[end]['startMs']=right
        i=end
    assert all(0<=w['startMs']<w['endMs']<=round(duration*1000)+10 for w in tokens),'Некорректные временные отметки.'
    font=ImageFont.truetype(str(PUBLIC/'Manrope.ttf'),64)
    font.set_variation_by_axes([650])
    def lines(group):
        result=[[]]
        for token in group:
            if result[-1] and font.getlength(' '.join(w['text'].strip() for w in result[-1]+[token]))>850:result.append([])
            result[-1].append(token)
        return result
    paragraphs=TEXT.read_text().strip().split('\n\n')
    indices=[];cursor=0
    for paragraph in paragraphs:
        indices.append(cursor);cursor+=len(paragraph.split())
    pages=[];group=[]
    def flush():
        if group:pages.append({'startMs':group[0]['startMs'],'endMs':group[-1]['endMs'],'lines':lines(group)})
    for i,token in enumerate(tokens):
        if group and (i in indices or len(lines(group+[token]))>2):flush();group=[]
        group.append(token)
        if re.search(r'[.!?…][»”"]?$',token['text']):flush();group=[]
    flush()
    assert [w['text'].strip() for p in pages for line in p['lines'] for w in line]==words
    starts=[0]+[tokens[i]['startMs']/1000 for i in indices[1:]]+[duration]
    assert all(a<b for a,b in zip(starts,starts[1:]))
    data={'preview':False,'duration':duration,'sceneStarts':starts,'words':tokens,'pages':pages,
          'recognizedWords':len(anchors),'interpolatedWords':len(words)-len(anchors)}
    (PUBLIC/f'lesson-{LESSON_ID}/data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    shutil.copyfile(voice,PUBLIC/f'lesson-{LESSON_ID}/voice.wav')
    shutil.copyfile(voice,OUT/'voice.wav')
    (OUT/'word-timings.json').write_text(json.dumps(tokens,ensure_ascii=False,indent=2))
    captions=[]
    for i,p in enumerate(pages,1):
        body='\n'.join(' '.join(w['text'].strip() for w in line) for line in p['lines'])
        captions.append(f'{i}\n{srt_time(p["startMs"])} --> {srt_time(p["endMs"])}\n{body}')
    (OUT/'subtitles.srt').write_text('\n\n'.join(captions)+'\n')
    (OUT/'build-info.json').write_text(json.dumps({'duration':duration,'scene_starts':starts,'recognized_words':len(anchors),
                                                'interpolated_words':len(words)-len(anchors)},ensure_ascii=False,indent=2))
    print(f'{duration:.2f} s; {len(words)} words; {len(pages)} pages; {len(words)-len(anchors)} interpolated timings.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--voice',type=Path,required=True)
    parser.add_argument('--transcribe',action='store_true')
    lessons=parser.add_mutually_exclusive_group()
    lessons.add_argument('--lesson-1.3',dest='lesson3',action='store_true')
    lessons.add_argument('--lesson-1.4',dest='lesson4',action='store_true')
    lessons.add_argument('--lesson-2.1',dest='lesson5',action='store_true')
    lessons.add_argument('--lesson-2.2',dest='lesson6',action='store_true')
    lessons.add_argument('--lesson-2.3',dest='lesson7',action='store_true')
    lessons.add_argument('--lesson-2.4',dest='lesson8',action='store_true')
    lessons.add_argument('--lesson-2.5',dest='lesson9',action='store_true')
    lessons.add_argument('--lesson-3.1',dest='lesson10',action='store_true')
    lessons.add_argument('--lesson-3.2',dest='lesson11',action='store_true')
    lessons.add_argument('--lesson-3.3',dest='lesson12',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.transcribe:transcribe(args.voice)
    else:
        lesson_args=['--lesson-3.3'] if args.lesson12 else ['--lesson-3.2'] if args.lesson11 else ['--lesson-3.1'] if args.lesson10 else ['--lesson-2.5'] if args.lesson9 else ['--lesson-2.4'] if args.lesson8 else ['--lesson-2.3'] if args.lesson7 else ['--lesson-2.2'] if args.lesson6 else ['--lesson-2.1'] if args.lesson5 else ['--lesson-1.4'] if args.lesson4 else ['--lesson-1.3'] if args.lesson3 else []
        subprocess.run(['nice','-n','15','taskset','-c','3',str(TOOLS/'asr-venv/bin/python'),__file__,'--voice',str(args.voice),'--transcribe',*lesson_args],check=True)
        align(args.voice)
