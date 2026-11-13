# TASK-018: безопасные ошибки Pinterest

<!-- runner
{"read_files":["apps/pinterest/tests.py","apps/pinterest/strategist_tools.py"]}
-->
Исполнитель OpenCode, openrouter/qwen/qwen3.8-27b:free.
Ты не один в проекте. Не изменяй файлы, не отменяй чужие изменения.
Только чтение указанных исходников; никаких команд, API, секретов.
RESULT-018.md записывает запускатель. Codex проверяет и применяет.
Граф home-evgen-bk3.0 Verify generation2026-10-03T10:48:43Z,
coverage apps/pinterest/tests.py и strategist_tools.py без зарегистрированных
пропусков, metadata_match. Scope: _request и PinterestOAuthFlowTest.

Верни ровно два Python test-метода для существующего класса, без импортов,
setup/class, до80 строк. Synthetic account как в соседних тестах, срок токена
через сутки, все внешние вызовы замоканы:
1. _get возвращает429: PinterestReadError содержитHTTP429, ровно одинGET,
refresh не вызывается, статус аккаунта остаётсяCONNECTED.
2. _get возвращает200, json() выбрасывает ValueError("private-upstream-secret"):
PinterestReadError сообщает некорректныйJSON, не содержит private-upstream-secret,
ровно одинGET, refresh не вызывается, статусCONNECTED.
Не утверждай, что запускал тесты. Нужен код, не общая смысловая оценка.
