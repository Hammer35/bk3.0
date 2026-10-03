# Общий канал агентов

Один репозиторий, несколько агентов. Этот файл — единственное место, где видно, кто чем занят.

## Порядок работы

1. **Прочитать этот файл до первой правки.**
2. Имя агента: `git config agent.name "opencode"` — один раз в репозитории.
3. Занять файлы до правки:
   `.kilo/agent-state/agent.sh claim opencode apps/strategist/services.py ...`
4. Записать задачу в таблицу «В работе».
5. Коммитить только занятые файлы, по явным путям — не `git add -A`.
6. После коммита освободить их:
   `.kilo/agent-state/agent.sh release opencode apps/strategist/services.py ...`
7. Перенести задачу в «Сделано».

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
| opencode | `feature/strategist-grounded-answers` | нет | снимок диффа сделан; ждёт решения по блоку «вчера/заказы» |
| codex | неизвестно | — | статус не передан; записать сюда, если работа идёт |

## Решения, ожидающие владельца

- Снимать ли цифровую защиту `not re.search(r"\d", ...)` в маршруте «вчера/заказы».
- Удалять ли LLM-критик ответов (предложение: да, вместе с `GIGACHAT_CRITIC_MODEL` и `model_routing.__init__`).

## Сделано

- `db9e126` — `docs: add repository instructions for coding agents`.
- `69223a6` — `feat(strategist): grounded answers, knowledge sources, arksim harness and critic prototype`. Снимок ранее незакоммиченной работы, чтобы она не потерялась. Замер тестов на этом состоянии: 48 прошли.
- `.githooks/pre-commit`, `.kilo/agent-state/` — защита от взаимного затирания.