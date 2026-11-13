# TASK-013: сценарии аналитики

<!-- runner
{"read_files":["apps/strategist/services.py","apps/strategist/advice.py"]}
-->

Исполнитель: OpenCode, openrouter/cohere/north-mini-code:free.
Codex принимает результат; файлы и настройки не менять, команды не запускать.
Граф: home-evgen-bk3.0, Verify, ready, generation 2026-10-03T08:17:41Z.
search_graph нашёл _direct_pinterest_answer, _pinterest_analytics_answer,
_format_pinterest_analytics в services.py. Coverage обоих исходников без
зарегистрированных пробелов; прямое чтение обязательно.

Прочитай только _direct_pinterest_answer и analytics_followup_context.
Верни ровно 6 коротких сценариев: вопрос, предыдущий ответ (если нужен),
ожидаемый выбранный аккаунт/отказ, нужен ли вызов API. Включи:
два профиля без выбора; неизвестный @профиль; переключение @профиля после
аналитики; период 7 после уточнения; пользовательские цифры не API;
вопрос о заказах после аналитики.
Не пиши код, не утверждай запуск тестов. Результат RESULT-013.md.
