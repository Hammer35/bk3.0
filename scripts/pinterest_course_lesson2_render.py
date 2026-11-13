"""Render the checked Remotion slides with frame-exact libass word highlighting."""
from pathlib import Path
import bisect
import json
import math
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
LESSON_ID='3.3' if '--lesson-3.3' in sys.argv else '3.2' if '--lesson-3.2' in sys.argv else '2.5' if '--lesson-2.5' in sys.argv else '2.4' if '--lesson-2.4' in sys.argv else '2.3' if '--lesson-2.3' in sys.argv else '2.2' if '--lesson-2.2' in sys.argv else '2.1' if '--lesson-2.1' in sys.argv else '1.4' if '--lesson-1.4' in sys.argv else '1.3' if '--lesson-1.3' in sys.argv else '1.2'
V2=(LESSON_ID in ('3.2','3.3'))and'--v2' in sys.argv
OUT=ROOT/f'artifacts/pinterest-course/lesson-{LESSON_ID}-vertical-v{"2"if V2 else"1"}'
DATA=ROOT/f'video/pinterest-lesson/public/lesson-{LESSON_ID}/data.json'
VOICE=ROOT/f'video/pinterest-lesson/public/lesson-{LESSON_ID}/voice.wav'
VIDEO=OUT/f'lesson-{LESSON_ID}-vertical-v{"2"if V2 else"1"}.mp4'
FPS=30
# libass uses font metrics for Fontsize. 101 matches the approved CSS 74px
# Manrope caption within one pixel; checked against the Remotion still.
ASS_FONT_SIZE=101


def prepare_font():
    destination=OUT/'fonts/ManropeCourse.ttf'
    if destination.exists():return
    sys.path.insert(0,str(Path.home()/'.local/share/pinterest-video-tools/vector-libs'))
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    font=TTFont(str(ROOT/'video/pinterest-lesson/public/Manrope.ttf'))
    font=instantiateVariableFont(font,{'wght':650},inplace=True)
    for record in font['name'].names:
        if record.nameID in (1,2,3,4,6,16,17):
            name='Regular' if record.nameID in (2,17) else 'ManropeCourse'
            record.string=name.encode(record.getEncoding())
    # The outlines retain weight 650. Mark as regular for unique family lookup.
    font['OS/2'].usWeightClass=400
    destination.parent.mkdir(parents=True,exist_ok=True)
    font.save(destination)


def stamp(frame):
    # Floor to centiseconds: the switch stays after the preceding 30-fps frame.
    cs=frame*100//FPS
    h,rest=divmod(cs,360000);m,rest=divmod(rest,6000);s,cs=divmod(rest,100)
    return f'{h}:{m:02}:{s:02}.{cs:02}'


def slide_starts(d):
    if V2:
        plan_file=ROOT/'video/pinterest-lesson/public/visual-fix-11-12-v2/visual-plan.json'
        plan=json.loads(plan_file.read_text())[f'lesson_{LESSON_ID.replace(".","_")}']
        times=[]
        for shot in plan:
            times.append(shot['start'])
            if 'switchAt' in shot:times.append(shot['switchAt'])
        return [math.ceil(t*FPS-1e-8) for t in times]+[math.ceil(d['duration']*FPS)]
    story=DATA.with_name('storyboard.json')
    times=[x['start'] for x in json.loads(story.read_text())] if LESSON_ID in ('2.3','2.4') else d['sceneStarts'][:-1]
    return [math.ceil(t*FPS-1e-8) for t in times]+[math.ceil(d['duration']*FPS)]


def prepare(font_size):
    prepare_font()
    d=json.loads(DATA.read_text())
    assert not d['preview'] and VOICE.exists()
    count=math.ceil(d['duration']*FPS)
    starts=slide_starts(d)
    concat=['ffconcat version 1.0']
    for i in range(len(starts)-1):
        png=OUT/f'check-{i+1:02}.png'
        assert png.exists(),png
        concat += [f"file '{png}'",'option framerate 30',f'duration {(starts[i+1]-starts[i])/FPS:.9f}']
    concat += [f"file '{OUT/f'check-{len(starts)-1:02}.png'}'",'option framerate 30']
    (OUT/'slides.ffconcat').write_text('\n'.join(concat)+'\n')
    boundaries={0,count}
    for w in d['words']:
        boundaries.update([math.ceil(w['startMs']*.03-1e-8),math.ceil(w['endMs']*.03-1e-8)])
    for p in d['pages']:boundaries.add(math.ceil(p['startMs']*.03-1e-8))
    boundaries=sorted(f for f in boundaries if 0<=f<=count)
    start_ms=[p['startMs'] for p in d['pages']]
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,ManropeCourse,{font_size},&H00E6EEF1,&H00E6EEF1,&H00171B20,&H00171B20,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events=[];highlighted=set()
    for a,b in zip(boundaries,boundaries[1:]):
        if b<=a:continue
        t=a/FPS*1000
        index=bisect.bisect_right(start_ms,t+1e-8)-1
        if index<0:continue
        page=d['pages'][index]
        for i,line in enumerate(page['lines']):
            parts=[]
            for word in line:
                active=word['startMs']<=t+1e-8<word['endMs']
                if active:highlighted.add((word['text'],word['startMs'],word['endMs']))
                color='5CB8F3' if active else 'E6EEF1'
                escaped=word['text'].strip().replace('\\','').replace('{','').replace('}','')
                parts.append(f'{{\\c&H{color}&}}{escaped}')
            y=1700+(i-(len(page['lines'])-1)/2)*91.76
            text=f'{{\\an5\\pos(540,{y:.2f})}}'+' '.join(parts)
            events.append(f'Dialogue: 0,{stamp(a)},{stamp(b)},Caption,,0,0,0,,{text}')
    assert len(highlighted)==len(d['words']),f'Highlight coverage: {len(highlighted)}/{len(d["words"])}'
    (OUT/'captions.ass').write_text(header+'\n'.join(events)+'\n',encoding='utf-8')
    return d,count


def filters(d):
    ass=OUT/'captions.ass';fonts=OUT/'fonts'
    count=math.ceil(d['duration']*FPS)
    starts=slide_starts(d)
    # Native video composition: remove the sampled caption band, restore the
    # approved field, then render current-word captions and the progress strip.
    # Decode each PNG once; loop cached YUV frames instead of re-decoding PNG
    # and converting RGB on every frame, which is expensive on the laptop.
    scenes=[]
    for i in range(len(starts)-1):
        frames=starts[i+1]-starts[i]
        scenes.append(f'[{i}:v]crop=1080:1468:0:0,pad=1080:1920:0:0:color=0xf1eee6,'
                      f'drawbox=x=0:y=1480:w=iw:h=440:c=0x171b20:t=fill,format=yuv420p,'
                      f'loop=loop={frames-1}:size=1:start=0,setpts=N/(30*TB)[s{i}]')
    return (';'.join(scenes)+';'+''.join(f'[s{i}]' for i in range(len(starts)-1))+
            f'concat=n={len(starts)-1}:v=1:a=0,fps=30:eof_action=pass,ass=filename={ass}:fontsdir={fonts}[slides];'
            f'color=c=0xcd4e3d:s=1080x4:r=30:d={d["duration"]}[progress];'
            f'[slides][progress]overlay=x=-1080+1080*t/{d["duration"]}:y=1468:eval=frame:shortest=1[video]')


def run(preview=False,font_size=ASS_FONT_SIZE):
    d,count=prepare(font_size)
    starts=slide_starts(d)
    command=['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-hide_banner','-loglevel','info','-y']
    for i in range(len(starts)-1):
        command+=['-threads','1','-framerate','30','-i',str(OUT/f'check-{i+1:02}.png')]
    if not preview:command+=['-i',str(VOICE)]
    command+=['-filter_complex_threads','1','-filter_complex',filters(d),'-map','[video]']
    if preview:
        command+=['-ss','2','-frames:v','1','-threads','1','-update','1',str(OUT/'native-caption-check.png')]
    else:
        preset,crf=('ultrafast','18') if '--fast' in sys.argv else ('veryfast','19')
        command+=['-map',f'{len(starts)-1}:a:0','-r','30','-frames:v',str(count),'-c:v','libx264','-preset',preset,'-crf',crf,'-threads','1',
                  '-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-t',str(d['duration']),'-movflags','+faststart',str(VIDEO)]
    log=OUT/('native-preview.log' if preview else 'native-render.log')
    with log.open('w') as output:
        process=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT)
        while True:
            try:
                code=process.wait(timeout=20)
                if code:raise subprocess.CalledProcessError(code,command)
                break
            except subprocess.TimeoutExpired:
                with log.open('rb') as stream:
                    stream.seek(max(0,log.stat().st_size-8192))
                    frames=re.findall(r'frame=\s*(\d+)',stream.read().decode(errors='replace'))
                if frames:print(f'Lesson {LESSON_ID}: {int(frames[-1])*100//count}% encoded.',flush=True)
    if not preview:mux_voice()
    print('Caption preview exported.' if preview else 'Full lesson rendered.',flush=True)


def mux_voice():
    d=json.loads(DATA.read_text())
    video=VIDEO
    temporary=OUT/f'lesson-{LESSON_ID}-with-voice.mp4'
    # Mux the original WAV after video encoding. A frame limit in the video
    # pass must not trim the final partial audio frame or WAV's trailing pause.
    command=['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-v','error','-y','-threads','1',
             '-i',str(video),'-i',str(VOICE),'-map','0:v:0','-map','1:a:0','-c:v','copy',
             '-c:a','aac','-b:a','128k','-threads','1','-t',str(d['duration']),'-movflags','+faststart',str(temporary)]
    subprocess.run(command,check=True)
    temporary.replace(video)


def extract_stills():
    d=json.loads(DATA.read_text())
    frames=[int(start*FPS)+2*FPS for start in d['sceneStarts'][:-1]]
    selected='+'.join(f'eq(n,{frame})' for frame in frames)
    command=['nice','-n','15','taskset','-c','3','ffmpeg','-nostdin','-v','error','-y','-threads','1',
             '-i',str(VIDEO),'-filter_threads','1','-vf',f"select='{selected}'",
             '-fps_mode','vfr','-frames:v','7','-threads','1',str(OUT/'final-%02d.png')]
    subprocess.run(command,check=True)
    assert all((OUT/f'final-{i:02}.png').exists() for i in range(1,8))
    print('Seven frames extracted from the final MP4.',flush=True)


if __name__=='__main__':
    size=int(sys.argv[sys.argv.index('--font-size')+1]) if '--font-size' in sys.argv else ASS_FONT_SIZE
    if '--mux-voice' in sys.argv:mux_voice()
    elif '--stills' in sys.argv:extract_stills()
    else:run('--preview' in sys.argv,size)
