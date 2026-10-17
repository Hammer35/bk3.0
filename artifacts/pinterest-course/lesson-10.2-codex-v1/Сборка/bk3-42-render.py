from pathlib import Path
import sys
R=Path('/home/evgen/bk3.0');O=R/'artifacts/pinterest-course/lesson-10.2-codex-v1';sys.path.insert(0,str(R/'scripts'))
import pinterest_course_lesson15_render as r
r.ROOT=R;r.LESSON_ID='10.2';r.V2=False;r.OUT=O;r.DATA=O/'public/lesson-10.2/data.json';r.VOICE=O/'42.wav';r.VIDEO=O/'Урок_42_Проверка_аккаунта_и_пинов_Реальные_экраны_v1.mp4'
r.run(preview='--preview' in sys.argv)
