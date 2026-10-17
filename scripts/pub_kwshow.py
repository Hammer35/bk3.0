import json,sys,re
BAD=re.compile(r'скач|герл|girl|тг|телеграм|аниме|обои|рисун|авы|аватар|вход|без регистр|онлайн|официальн|прическ|маникюр|комнат|интерьер|одежд|арт|идеи для|штучк|room|download|видео скач|для телефона|apk|впн|vpn|заблокир|шнурк|какаши|сквиш|сохранен.* фото|темн')
n=int(sys.argv[1]); keep=sys.argv[2] if len(sys.argv)>2 else None
d=json.load(open(f'artifacts/pinterest-course/publication/keywords/{n:02}.json'))
rows=[r for r in d['keywords'] if not BAD.search(r['phrase'])]
print(f"урок {n}: всего {len(d['keywords'])}, после фильтра {len(rows)}")
for r in rows[:int(sys.argv[3]) if len(sys.argv)>3 else 35]: print(r['score'], ','.join(r['sources']), r['phrase'])
