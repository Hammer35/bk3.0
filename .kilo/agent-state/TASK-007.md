# TASK-007: подготовить расширяемый запускатель тестов

Исполнитель OpenCode CLI, openrouter/openrouter/free. Ты не один в репозитории, чужие изменения не отменяй. Правки приложения и реальные API-запросы запрещены. Верни компактный unified diff для scripts/evaluate_strategist_release.py; Codex проверяет и применяет.

<!-- runner
{"read_files":["scripts/evaluate_strategist_release.py",".kilo/agent-state/TASK-007.md"]}
-->

Прочитай имеющийся запускатель. Сохрани старый режим 8 сценариев × 3 повтора, добавь загрузку YAML cases с полями id/family/business_profile/messages/expected. business_profile: known или empty; messages: 1–2 строки; expected: список критериев. YAML вне RAG. Новые настройки приложения не нужны.

Минимальное расширение evaluate(case_file=None, repetitions=3, output_path='/tmp/strategist-release.json'). В конце вызывай evaluate с globals().get('EVALUATION_CASE_FILE'), globals().get('EVALUATION_REPETITIONS',3), globals().get('EVALUATION_OUTPUT','/tmp/strategist-release.json'). Тогда Codex сможет запускать через manage.py shell -c с exec(..., namespace) внутри Docker.

Требования:
- Валидация YAML и положительного repetitions до создания тестовой БД и любых платных вызовов. Пустой список и повторные ID запрещены, бизнес-профиль проверяется явно, типы сообщений/критериев тоже. Используй установленный PyYAML.
- Изолированная временная БД, копируется только одобренная глобальная база знаний. Создай два фиктивных бизнеса: known (как сейчас) и empty (без ниши/аудитории). Не читай реальные бизнесы/аккаунты.
- В выводе каждой строки сохраняй case_id, family, step (номер сообщения), expected, вопрос, фактический ответ, маршрут модели, usage, время, HTTP-статус. Сохрани repetition и scenario для старого отчёта.
- До следующего запроса проверяй budget 60000 chat tokens (это остановка по уже сообщённому usage, не жёсткая граница счёта). При HTTP-ошибке/тайм-ауте остановись без автоматических повторов. Семантическую оценку не выдумывай: expected сохраняются для независимого ревью.
- При каждом успешном ответе обновляй JSON-файл, чтобы авария не уничтожила транскрипт. finally гарантирует очистку БД даже при ошибке записи. Старый test-name восстановить во вложенном finally.
- Не добавляй библиотеки, модель-судью, фоновый процесс или изменение production settings. Не заявляй тесты выполненными.

Верни только diff, до 180 строк. Не пересказывай весь файл. Путь/граф известны руководителю: home-evgen-bk3.0, generation2026-10-03T07:42:37Z, scripts/evaluate_strategist_release.py coverage no_recorded_issue/metadata_match. Задача ограничена этим файлом; нет нужды сканировать код приложения.
