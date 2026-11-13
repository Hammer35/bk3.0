# TASK-017: регрессии отказа Pinterest

<!-- runner
{"read_files":["apps/pinterest/tests.py","apps/pinterest/strategist_tools.py"]}
-->

Исполнитель OpenCode, openrouter/qwen/qwen3.8-27b:free.
Codex принимает результат и запускает тесты. Ты не один в проекте;
не изменяй файлы и не отменяй чужие изменения. Твой файл RESULT-017.md
запишет запускатель. Никаких команд, живых API или секретов.
Граф home-evgen-bk3.0 ready, Verify; generation2026-10-03T10:40:55Z;
coverage этих двух файлов metadata_match без зарегистрированных gaps.
Только read _request и примеров tests.PinterestOAuthFlowTest.

Верни ровно два Python test-метода для существующего класса:
1. Ресурс вернул HTTP403: _request сообщает 403, статус CONNECTED
   сохраняется, refresh не вызван; исходный token expires через сутки.
2. Ресурс401, refresh=True, повтор401, profile503: сообщение о
   неподтверждённом доступе, статус CONNECTED сохраняется, ровно3GET.
Все _get/refresh замоканы. Synthetic account создаётся как в соседних
тестах. Не нужны import/class/setup. Не утверждай запуск тестов.
До80строк, без рассуждений. Это code proposal, не семантическая оценка.
