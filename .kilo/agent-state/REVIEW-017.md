# Приёмка TASK-017

Модель `openrouter/qwen/qwen3.8-27b:free`, сессия
`ses_efea3fa3effeo7FXr5h9bMAZmN`, reported tokens28298, cost0.
Официальный OpenCode CLI вернул конкретные два test-метода.
Codex проверил source _request и применил proposal в apps/pinterest/tests.py.

Принято: ресурс403 не запускает refresh при живом токене и не переводит
профиль в REAUTH_REQUIRED; 401 → refresh → 401 → profile503 оставляет
CONNECTED и сообщает неподтверждённое состояние доступа. Все upstream
вызовы в этих regression-тестах замоканы; автор не утверждал запуска.
9 targeted tests Pinterest прошли (включая два предложенных).

В текущем узком задании Qwen показал пригодный code proposal. Это не
универсальная оценка модели и не выбор semantic judge. Subscription
Codex расход не измерен. Product LLM остаётся GigaChat-2-Pro.
