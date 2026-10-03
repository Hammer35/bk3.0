# Общий канал агентов

Один репозиторий, несколько агентов. Этот файл — единственное место, где видно, кто чем занят.

## Порядок работы

1. **Прочитать этот файл и `LOG.md` до первой правки.**
2. Имя агента в окружении: `export AGENT_NAME="opencode"` (для Codex — `codex`). Общий `git config agent.name` не использовать.
3. Занять файлы до правки:
   `.kilo/agent-state/agent.sh claim opencode apps/strategist/services.py ...`
4. Записать задачу в таблицу «В работе».
5. Коммитить только занятые файлы, по явным путям — не `git add -A`.
6. После коммита освободить их:
   `.kilo/agent-state/agent.sh release opencode apps/strategist/services.py ...`
7. Перенести задачу в «Сделано».

## Как связаться с другим агентом

Единственный канал — файл. Одна строка, одна команда:

    .kilo/agent-state/agent.sh note codex "текст сообщения"

Прочитать ответ:

    cat .kilo/agent-state/LOG.md

Агент-to-agent API не существует. HTTP-API OpenCode (`http://127.0.0.1:4097`) для связи **не годится**: он открывает новую пустую сессию, а не пишет в текущий диалог, и не передаёт контекст. Ошибка `403 OpenCode's free tier can only be used from within OpenCode` — это отказ провайдера модели, а не проблема связи.

## Что запрещает система

| Запрет | Кто запрещает |
|---|---|
| Коммит в `main` | `.githooks/pre-commit` |
| Пуш в `main` без PR | GitHub: защищённая ветка, обязательное ревью |
| Коммит файла, занятого другим агентом | `.githooks/pre-commit` + реестр `claims/` |
| Файл изменён после `git add` | `.githooks/pre-commit` |
| Откат или удаление чужой работы | правило в `AGENTS.md` |

Второй агент получает отказ в `claim` до правки, а не после — когда уже поздно.

## В работе

| Агент | Ветка / worktree | Занятые файлы | Задача |
|---|---|---|---|
| — | `feature/strategist-grounded-answers` | — | Текущий этап завершён Codex; см. итоговую приёмку ниже |

## Предыдущая оценка OpenCode (до приёмки Codex)

- Ничего не блокировано. Применены: правка маршрута «вчера/заказы», снятие политики «один первый шаг», починка CI, барьер честности источников, барьер неподтверждённой длины.
- PR #1 (`feature/strategist-grounded-answers` → `main`) открыт, CI зелёный, ждёт ревью.
- Метод проверки изменён: 3 прогона по 4 вопросам, дефект считается реальным только если повторился в 2 и более прогонах. Одиночное сравнение «до/после» в прошлый раз принимало шум за дефект.
- Честность Стратега измерена. База знаний и извлечение исправны; терялась оговорка «это вывод из правил, а не одобрение модерацией» и добавлялись числа длины, которых в базе нет.
- Закрыто барьером: пропущенная оговорка (было 3/3, стало чисто), обещание уникальности (3/3 чисто), неподтверждённая длина (было 3/3 без оговорки, стало 0/6 с оговоркой).
- Числа длины не вырезаются, а лишаются статуса официальной нормы. Сознательное решение: резать числа опасно, так можно удалить корректный совет; в справке про длину не сказано ничего, поэтому честнее сказать «эвристика, проверь в редакторе».
- Наблюдаемая дисперсия сохраняется: одно и то же число менялось между прогонами (20-50 и 20-70 слов). Это и доказывает выдумку, и означает, что одиночный ответ нельзя использовать как вердикт о качестве.
- Наблюдаемый побочный эффект снятия one-step: на открытый вопрос модель отвечает нумерованным планом из пяти пунктов вместо трёх шагов в прозе.
- Низкий приоритет: «А если было 12 кликов?» не ловится ключевыми словами в `grounded_answers.py:97`. Вопрос контрфактический, дефектом не считается.
- Не проверено: работа барьеров без извлечённого контекста, вопросы не по теме магазина, английский язык ответа.

## Сделано

- `db9e126` — `docs: add repository instructions for coding agents`.
- `69223a6` — `feat(strategist): grounded answers, knowledge sources, arksim harness and critic prototype`. Снимок ранее незакоммиченной работы, чтобы она не потерялась. Замер тестов на этом состоянии: 48 прошли.
- `45d5dea`, `27284bf`, `b7d2f18` — coordination hooks, фиксация branch protection, файловый канал сообщений.
- `bf75e98` — удаление LLM-критика ответов и исправление идентичности агента на `AGENT_NAME`. После удаления: 41 тест `apps.strategist apps.knowledge` проходят, миграций нет.
- `.githooks/pre-commit`, `.kilo/agent-state/` — защита от взаимного затирания.
- `main` на GitHub защищена: PR обязателен, нужно 1 ревью, проверка `django` (CI) и для админов тоже. Прямой пуш в `main` больше не проходит.

## Делегирование

Codex руководит постановкой и приёмкой. Правила: [DELEGATION.md](DELEGATION.md). Поручения — TASK-<id>.md, результаты — RESULT-<id>.md, принятие и итоги — в LOG.md. Файл не запускает агента автоматически.


## Приёмка Codex 3 октября 2026

CLI-запускатель run_opencode.py работает: TASK-004 получил реальный ответ и RESULT-004.md. Итог приёмки — REVIEW-004.md. 71 тест, check и проверки миграций прошли. Два дефекта source_honesty воспроизведены отдельно; защиту целиком не принимаем. Следующий этап — адресное исправление по REVIEW-004, без использования отвергнутых примеров исполнителя. Постоянный демон не установлен; Codex запускает каждое поручение командой run и проверяет status/RESULT.


## Итоговая приёмка Codex — 3 октября 2026

Этап исправления ответов завершён. TASK-005 отклонён, правка исполнителя не применена; исправления внесены Codex после проверки. Финальный живой прогон: 8 сценариев × 3 повтора, 27 ответов, все прошли ограниченную приёмку. 9 ответов через GigaChat-2-Pro, 15 из одобренных источников, 3 из проверки недоступных данных. 81 Django-тест прошёл; check, миграции и diff без ошибок. Web на 8000 перезапущен, readiness HTTP 200. Временные БД оценки удалены.

Добавлен и индексирован официальный источник Review Pin specs (100/800 символов), исправлены отрицательные предупреждения и атрибуция длины, уточнение про CTA, лишний текст одиночного CTA, неподтверждённая уникальность товара и переход на вопрос про вчера после другой темы. Подробности и реальные примеры: docs/ai-knowledge/examples/strategist-release-review-2026-10-03.md.

Незакоммиченные изменения оставлены на feature-ветке для просмотра. Main не менялся, публикация не выполнялась. Полного покрытия всех диалогов нет; реальные API-метрики подключённых Pinterest-профилей данным прогоном не проверены. Следующая работа только по новым дефектам или расширению набора, не повторять завершённые платные прогоны без причины. Постоянного фонового исполнителя нет.


## Расширенное покрытие и делегирование — завершено

36 сценариев, последний полный прогон37 ответов, тройные проверки исправленных случаев, 98 Django-тестов OK. Добавлены сценарии недоступного RAG и границ API/рекламы, синтетическая история, проверка срока источника. Исправления работают на локальном8000, readiness200. Отчёт: docs/ai-knowledge/examples/strategist-expanded-review-2026-10-03.md; набор: strategist-expanded-cases.yaml.

OpenCode действительно исполнял TASK-010/011/012 через Cohere: приёмка REVIEW-010-012.md, результаты отдельными файлами. Несодержательные006/007, тайм-аут008 и403009 отклонены. Поддержка плановых steps3 проверена; ограничение только процессное. В будущем делегировать небольшие чёткие работы, не принимать автоматически оценки критика и не повторять недоступные маршруты без причины.

Незакоммиченное дерево сохранено; main, настройки аккаунтов и .env не менялись. Реальная публикация и реальный Pinterest API не засчитывались живыми проверками. Активных поручений нет, файлы после отчёта освобождены.

## Analytics / tools acceptance завершены

10 analytics AJAX и11 tool-loop AJAX сценариев добавлены. Полный suite119 OK/45.399с. Найден и исправлен500 на JSON array tool result; error AIMessage теперь сохраняет usage уже выполненных model calls. check/migrations/diffcheck OK. TASK013 принят частично; TASK014 не принят (steps cap до анализа), повтор не выполнялся. См. strategist-analytics-review-2026-10-03.md и strategist-tools-review-2026-10-03.md. Live Giga/Pinterest этим этапом не проверялись. Изменения в feature/strategist-grounded-answers, не опубликованы.

## Live Giga tool pilot и актуализация плана

Добавлен tool_fixture mode в evaluator: real Giga+real account/scope validation, synthetic Pinterest transport, isolated unique test DB. 5cases, финальнаяприёмка5/5; все17диагностических ответов34237chat tokens. Prompt запрещает спрашивать account_key и требует точный UUID. Новый backendguard запрещает подстановку другого CONNECTED профиля; явно названные несколько профилей допустимы для сравнения. Исправлен захват завершающей точки @имени. Сценарии live-tools-cases и отчёт live-tools-review, REVIEW015 готовы. TASK015 частичнопринят. План обновлён: runtime critic удалён, DeepEval не подключён, текущая проверка Django/YAML + Codex review. Реальные Pinterest OAuth/API этим этапом не проверены; публикации и commits не выполнялись.

## Pagination / dialogue profile switch завершены

Real Giga pilot3cases/4answers финально принят. Два этапа8answers/30232chat tokens, syntheticPinterest, embeddings0. Backend regression подтвердил неподтверждённый total после первой страницы; pending_pages guard выдаёт pagination-incomplete, учитываетusage. 3новые регрессии: раннее завершение, complete2pages, six-readcap. Full128tests/44.236с OK, check/migrations/diffcheck OK. TASK016 отклонён (ложныйtotal), Cohere больше неиспользовать как семантического судью. DELEGATION/план/отчёт/статистика обновлены. Коммиты/пуш/main/.env не менялись.

## Публикация и реальный Pinterest API

Commit3862eb8 (61files) опубликован в feature/strategist-grounded-answers, remoteHEAD совпал. Real8GET profile/analytics обоихподключённыхпрофилей HTTP200. Realchat2responses pinterest-api/direct-read/tokens0; профиль, даты, equalperiod comparison и data limitations подтверждены, cachedanalytics обходился только в probe. Сырые ответы/метрики находятся только ignored runtime; созданы2 диагностические беседы локального существующего бизнеса. OpenCode TASK017/Qwen codeproposal принят,2regressions применены:403 сохраняетCONNECTED; profile503 после401 не объявляетOAuth invalid. Full130tests/48.137с OK; check/migrations/diffcheck OK. Отчёт real-pinterest-review и статистика обновлены; завершение публикации следующего commit записывается в LOG. Main не менялся, merge не выполнялся.

## Реальные boards/followers и простой счётчик

TASK018/OpenCode Qwen принят:2regressions429/JSON,reported27613/cost0.
Codex:5board+7count tests,144full OK/51.552с,check/migrations/diffcheckOK.
Real9GET200,обаCONNECTED:4списки+1первичный modeltool profile+
2финальныхcounts+2chatboards. ПервичныйGiga2Pro 11241chat tokens,
одинwrongaccountkeyguard остановил; второй ответ верный. Узкий прямой
count маршрут использует официальный profile.follower_count,неLLM.
Final4chat ответы pinterest-api/direct-read/tokens0. Boards malformedJSON
500 воспроизведён и исправлен typeguard. Raw/private только ignoredruntime.
Отчёт strategist-real-lists-review-2026-10-03.md. Изменения пока не
опубликованы; main/.env не менялись. Далее pins/top_pins selective live
и ограничения,OAuth lifecycle отдельно. Не повторять платные прогоны
без новых дефектов. Освобождаем файлы, постоянного watcher нет.

## Реальные pins/top_pins — завершено

TASK019 OpenCode/Qwen33602reported/cost0:2testmethods приняты, третий
исправлен Codex (ask_tool перезаписывал side_effect). Реальные /pins и
/top_pins доступны обоимпрофилям.11GET:8HTTP200/3HTTP400 при диагностике
pluralметрики. Giga7chat ответов24235reportedtokens, embeddingsнеизмерены;
модель сначала путалаlimit/num_of_pins иOUTBOUND_CLICKS, затем верныечисла
безссылок/availability. Уточнёнtooldescription, добавлен узкийdirecttop
OUTBOUND_CLICK:5URL/metrics/datewarning каждого из2реальныхchat ответов
проверены, tokens0. FormatterHTTP(S)links сescaping добавлен:2реальныхGET
истории подтвердили10anchors.6top+3formatter+3OpenCode tests;
full156OK/51.930с, check/migrations/diffcheckOK. Первыйфинальныйпрогон
прерванrestart137, незасчитан;повторOK. Web8000readyOK. Report real-pins-review.
Featureизмененияэтогоипрошлогоэтапа пока НЕ опубликованы; main/.envне менялись.
Следующийэтап:реальные страницы каталога,OAuth/refresh lifecycle; причины
и сравнения отдельно. Приватныеданные не передавалисьOpenCode/непопалиGit.
Файлы освобождены, активногопроцессаOpenCodeнет; постоянноговотчеранет.

## 4 октября — страницы и OAuth guards

Real6GET200 /pins:3pagesнакаждыйиз2профилей,bookmarksбезизменений,
uniqueIDs,обаCONNECTED. Полныйкаталогнеисчерпан. LiveGiga0.
TASK020/Qwen26330reported/cost0:3методаsuccess/transient/permanent приняты.
Codex8boundary/chat tests:staleDB/отключённый/invalidJSON/malformedtoken/
ciphertext/ужеобновлённыйaccess/дваAJAXпути. Refresh проверяет lockedstate,
responseвалидируется до credentialзамены,invaliddata неуводитCONNECTED
вREAUTH.167fulltestsOK/57.133с,check/migrations/diffcheckOK.
Реальный tokenPOST/принудительнаяротация не выполнялись; failedrefresh
проверенmock-ами. Webперезапущенпослезавершениятестов. Main/.envнеизменялись,
измененияfeature покаНЕопубликованы. Reportpagination-oauth-review2026-10-04.
Далее:смысловые вопросыпричин/рекомендацийсреальнойаналитикой;
каталогполностьювыгружатьтолькоприпродуктовойнеобходимости.
Постоянногоисполнителянет,claimsосвобождаем;контекстOpenCode черезфайлы.
