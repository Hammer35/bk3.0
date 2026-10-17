from pathlib import Path
import sys
R=Path('/home/evgen/bk3.0');O=R/'artifacts/pinterest-course/lesson-10.1-codex-v1';sys.path.insert(0,str(R/'scripts'))
import pinterest_course_lesson15_render as r
r.ROOT=R;r.LESSON_ID='10.1';r.V2=False;r.OUT=O;r.DATA=O/'public/lesson-10.1/data.json';r.VOICE=O/'41.wav';r.VIDEO=O/'Урок_41_План_первого_месяца_Реальные_экраны_v1.mp4'
r.run(preview='--preview' in sys.argv)
