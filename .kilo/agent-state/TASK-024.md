# TASK-024 — проверка форматов метрик
<!-- runner
{"read_files":[".kilo/agent-state/TASK-024.md","apps/strategist/user_metrics.py","apps/strategist/test_user_metrics.py"]}
-->
Статус: завершён с ошибкой исполнителя; проверка Codex в REVIEW-024.md. Исполнитель: OpenCode openrouter/qwen/qwen3.8-27b:free.
Ты не один в проекте. Только чтение указанных файлов, никаких правок или внешних API.
Цель: предложи 10 regression cases для расширения форматов: markdown bullets/таблица,
явно подписанные прошлый/текущий периоды в обратном порядке, числа тыс/млн,
проценты переходов и отличия процентных пунктов от относительного изменения.
Дай готовые tuples (question, expected fragment) Python; добавь опасные входы,
которые должны уточняться: неполные периоды, несколько профилей, дата/цена вместо
счётчика, неоднозначные проценты. Не выводи точное число кликов из округлённого CTR.
Не устанавливай причины и статистическую значимость. Не пересматривай весь проект.
Граф: Verify home-evgen-bk3.0 generation2026-10-04T00:01:26Z, coverage metadata_match
для user_metrics.py/test_user_metrics.py/services.py, gaps не зарегистрированы;
user_metrics_answer102–193,_counts51–99 прочитаны. Бюджет один free CLI запуск,
3 steps/150seconds. Результат RESULT-024.md пишет runner, приёмка Codex.
