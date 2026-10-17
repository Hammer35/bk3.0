from pathlib import Path
import sys
R=Path('/home/evgen/bk3.0');O=R/'artifacts/pinterest-course/lesson-10.1-codex-v1';sys.path.insert(0,str(Path(__file__).parent))
import pinterest_course_lesson2_prepare as p
p.ROOT=R;p.LESSON_ID='10.1';p.OUT=O;p.PUBLIC=O/'public';p.TEXT=R/'docs/pinterest-course/урок-10.1-озвучка.txt'
assert not (O/'transcript.json').exists(),'ASR already exists; refusing to repeat'
p.transcribe(O/'41.wav')
p.align(O/'41.wav')
