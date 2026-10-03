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
| opencode | `feature/strategist-grounded-answers` | `RESULT-001.md`, `HANDOFF.md`, `LOG.md` | TASK-001: правка применена и проверена, ждёт приёмки Codex |
| codex | `feature/strategist-grounded-answers` | нет | выдал TASK-001; исчерпал лимит, приёмка не выполнена |

## Решения, ожидающие владельца

- Ничего не блокировано. Правка маршрута «вчера/заказы» применена по решению владельца: `apps/strategist/services.py` и 4 регрессионных теста, полный набор 63 теста проходит.
- Открытым остаётся пробел в `apps/strategist/grounded_answers.py:97`: «А если было 12 кликов?» не ловится ключевыми словами `исходящ\w*\s+клик\w*` и уходит в LLM. Отдельная задача.

## Сделано

- `db9e126` — `docs: add repository instructions for coding agents`.
- `69223a6` — `feat(strategist): grounded answers, knowledge sources, arksim harness and critic prototype`. Снимок ранее незакоммиченной работы, чтобы она не потерялась. Замер тестов на этом состоянии: 48 прошли.
- `45d5dea`, `27284bf`, `b7d2f18` — coordination hooks, фиксация branch protection, файловый канал сообщений.
- `bf75e98` — удаление LLM-критика ответов и исправление идентичности агента на `AGENT_NAME`. После удаления: 41 тест `apps.strategist apps.knowledge` проходят, миграций нет.
- `.githooks/pre-commit`, `.kilo/agent-state/` — защита от взаимного затирания.
- `main` на GitHub защищена: PR обязателен, нужно 1 ревью, проверка `django` (CI) и для админов тоже. Прямой пуш в `main` больше не проходит.

## Делегирование

Codex руководит постановкой и приёмкой. Правила: [DELEGATION.md](DELEGATION.md). Поручения — TASK-<id>.md, результаты — RESULT-<id>.md, принятие и итоги — в LOG.md. Файл не запускает агента автоматически.
