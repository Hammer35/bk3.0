# BOOSTKLIENT® 3.0 — матрица версий и совместимости

## Статус документа

Живой документ.

Цель: исключить неожиданные конфликты версий библиотек, фреймворков и инфраструктурных компонентов в процессе разработки BOOSTKLIENT® 3.0.

Главный принцип:
> Никаких «поставим самое новое и посмотрим». Версии выбираются заранее, проверяются на совместимость и фиксируются.

---

# 1. Зафиксированный базовый стек

| Компонент | Зафиксированная ветка | Роль |
|---|---:|---|
| Python | 3.12.x | основной язык |
| Django | 5.2 LTS | web-framework |
| Celery | 5.6.x | фоновые задачи |
| Redis Server | 7.4.x | broker / cache / временное состояние |
| PostgreSQL | 17.x | основная база данных |
| Psycopg | 3.x | PostgreSQL driver |
| HTMX | 2.0.x | серверная интерактивность |
| Alpine.js | 3.x | лёгкая локальная интерактивность |
| Tailwind CSS | 4.x | стили и дизайн-система |

---

# 2. Python 3.12

Python 3.12 выбран как консервативная стабильная база.

Причины:
- современная версия;
- широкая поддержка сторонними библиотеками;
- совместимость с Django 5.2 LTS;
- совместимость с Celery 5.6;
- совместимость с Psycopg 3;
- меньше риск несовместимости, чем при использовании самой новой ветки Python.

Правило:
> Python major/minor не обновляется без отдельного тестирования всей матрицы.

---

# 3. Django 5.2 LTS

Django 5.2 выбран как LTS (долгосрочно поддерживаемая версия).

Преимущества:
- стабильность;
- длительная поддержка;
- совместимость с Python 3.12;
- меньше риск breaking changes (ломающих изменений).

Переход на Django 6.x — только отдельной задачей после тестирования всего проекта и зависимостей.

---

# 4. Celery + Redis

Использовать:
- Celery 5.6.x;
- Redis Server 7.4.x.

Назначение:
- Celery — фоновые и отложенные задачи;
- Redis — broker (брокер сообщений), cache (кэш), временное состояние и locks (блокировки) при необходимости.

---

# 5. PostgreSQL

Основная база:
**PostgreSQL 17.x**

Причины:
- зрелая версия;
- хорошая поддержка Django;
- длительный срок поддержки;
- нет необходимости использовать самую новую ветку БД.

---

# 6. Psycopg

Использовать:
**Psycopg 3.x**

Перед фиксацией конкретной patch version (исправительной версии) проверить совместимость с:
- Python 3.12;
- PostgreSQL 17;
- Django 5.2.

---

# 7. Frontend stack

Зафиксировано:
- HTMX 2.0.x;
- Alpine.js 3.x;
- Tailwind CSS 4.x.

Принцип:
> Frontend должен оставаться лёгким и не вводить отдельный SPA-layer без необходимости.

---

# 8. Версии зависимостей

Запрещено использовать слишком широкие зависимости без фиксации.

Плохо:
- Django>=5
- celery без версии
- redis без версии
- psycopg без версии

После создания первого стабильного окружения нужно зафиксировать точные patch versions.

Production устанавливает зависимости из lock-файла, а не последние доступные версии.

---

# 9. Python version pinning

Версия Python должна быть явно зафиксирована в:
- .python-version;
- Dockerfile;
- CI configuration;
- deployment configuration.

Local development, CI, staging и production должны использовать одну minor-ветку Python.

---

# 10. Lock-файл

После выбора dependency manager использовать lock-файл.

Допустимые варианты:
- pip-tools;
- uv;
- Poetry.

Окончательный менеджер зависимостей будет выбран отдельно.

Главное правило:
> Production не разрешает зависимости «на лету».

---

# 11. Обновление зависимостей

## Patch updates

Допускаются после:
- проверки changelog;
- запуска тестов;
- smoke tests;
- проверки security notes.

## Minor updates

Требуют отдельной задачи:
- проверить compatibility matrix;
- прогнать тесты;
- проверить worker / retry / scheduling;
- проверить staging.

## Major updates

Примеры:
- Django 5 → 6;
- PostgreSQL 17 → 18;
- Python 3.12 → 3.13.

Только как отдельный upgrade project.

---

# 12. Новая библиотека

Перед добавлением любой новой зависимости проверить:
1. поддерживает ли Python 3.12;
2. поддерживает ли Django 5.2, если интегрируется с Django;
3. не конфликтует ли с Celery 5.6;
4. не требует ли другую версию Redis;
5. не требует ли другую версию PostgreSQL;
6. не тянет ли устаревшие зависимости;
7. активно ли поддерживается;
8. есть ли security issues;
9. совместима ли лицензия;
10. нужна ли библиотека вообще.

---

# 13. Compatibility Gate (ворота совместимости)

Процесс добавления зависимости:

Предложение библиотеки
↓
Проверка документации
↓
Проверка совместимости
↓
Установка в feature branch
↓
Тесты
↓
Проверка dependency resolver
↓
Merge

---

# 14. Среды

Минимальные окружения:
- local development;
- test / CI;
- staging;
- production.

Нельзя обновлять production напрямую.

---

# 15. CI compatibility checks

CI должен автоматически проверять:
- установку зависимостей;
- Django system checks;
- migrations;
- unit tests;
- integration tests;
- import errors;
- dependency conflicts;
- security scanning.

---

# 16. Django checks

В CI:
`python manage.py check`

Перед production:
`python manage.py check --deploy`

---

# 17. Dependency conflict detection

После каждого изменения зависимостей проверять:
- resolver output;
- incompatible requirements;
- deprecated packages;
- transitive dependencies.

Warnings при установке пакетов нельзя игнорировать без анализа.

---

# 18. Docker

Если используется Docker, версии образов также фиксируются.

Не использовать:
- python:latest;
- postgres:latest;
- redis:latest.

Использовать конкретные ветки Python 3.12, PostgreSQL 17 и Redis 7.4.

---

# 19. PostgreSQL extensions

Любое расширение PostgreSQL фиксируется отдельно.

Например будущий pgvector должен быть отдельно проверен на:
- совместимость с PostgreSQL 17;
- поддержку hosting;
- backup / restore;
- migrations;
- производительность.

---

# 20. Redis client

Различать:
- Redis Server;
- Python redis client.

Redis Server зафиксирован: 7.4.x.

Python package redis фиксируется отдельно в lock-файле и должен быть совместим с Celery 5.6, Python 3.12 и Redis 7.4.

---

# 21. Celery ecosystem

Если добавляются:
- django-celery-beat;
- django-celery-results;
- Flower;

каждый компонент отдельно проверяется на совместимость с Python 3.12, Django 5.2 и Celery 5.6.

---

# 22. HTMX / Alpine

Разделение ответственности:
- HTMX — серверные запросы и HTML partials;
- Alpine — локальное UI-состояние.

При обновлении HTMX проверить:
- hx-* поведение;
- event lifecycle;
- SSE integration;
- CSRF integration;
- history behavior.

При обновлении Alpine проверить:
- x-data;
- x-show;
- x-model;
- handlers;
- CSP compatibility.

---

# 23. Tailwind CSS updates

При обновлении Tailwind проверять:
- build pipeline;
- design tokens;
- dark mode;
- plugins;
- content scanning;
- generated CSS size.

---

# 24. Browser support

Ориентироваться на современные evergreen browsers.

Не добавлять тяжёлые polyfills ради устаревших браузеров без бизнес-причины.

---

# 25. Документ обновляется вместе со стеком

Если меняется Python, Django, Celery, Redis, PostgreSQL, Psycopg, HTMX, Alpine или Tailwind — этот документ обновляется в том же PR/commit.

---

# 26. Нельзя обновлять версии «по пути»

Обновление базового компонента — отдельная задача.

Нельзя во время другой feature-задачи неожиданно менять версию Django, Python, Celery, PostgreSQL, Redis или frontend stack.

---

# 27. Dependency Freeze (заморозка зависимостей)

Перед крупным релизом вводится freeze:
- новые библиотеки не добавляются без критической причины;
- версии не обновляются;
- допускаются только проверенные bugfix / security fix.

---

# 28. AI SDK

AI SDK меняются быстро.

Для OpenAI, DeepSeek и других SDK:
- фиксировать точную версию;
- не использовать latest;
- скрывать SDK за abstraction layer;
- обновлять отдельно;
- тестировать tool calling;
- тестировать streaming;
- тестировать structured outputs;
- тестировать обработку ошибок.

---

# 29. Если появилась несовместимая библиотека

Порядок действий:
1. не менять базовый стек автоматически;
2. найти альтернативу;
3. проверить другую версию пакета;
4. оценить реальную необходимость;
5. только при критической необходимости отдельно обсуждать upgrade базового компонента.

---

# 30. Главный принцип

> Базовый стек меняется редко. Прикладные библиотеки подбираются под него, а не наоборот.

Это защищает проект от ситуации, когда одна новая библиотека заставляет обновить половину системы.

---

# 31. Текущая зафиксированная матрица

**Python 3.12.x**

**Django 5.2 LTS**

**Celery 5.6.x**

**Redis Server 7.4.x**

**PostgreSQL 17.x**

**Psycopg 3.x**

**HTMX 2.0.x**

**Alpine.js 3.x**

**Tailwind CSS 4.x**

Статус:
> Базовая матрица BOOSTKLIENT® 3.0 зафиксирована. Изменение требует отдельного решения и тестирования.

---

# 32. HTMX 2.x — решение по стабильности

Для MVP и первой production-версии BOOSTKLIENT® 3.0 используется:

**HTMX 2.0.x**

Причина:
- приоритет стабильности над новизной;
- более зрелая ветка;
- меньше риск неожиданных breaking changes;
- проще накопить проверенную совместимость с Django, Alpine.js, SSE и CSRF.

Переход на HTMX 4.x допускается только отдельной задачей после проверки:

- совместимости с текущим Django stack;
- Alpine.js;
- SSE;
- CSRF;
- history / navigation behavior;
- всех существующих HTMX partials и компонентов;
- production-like staging.

Обновление HTMX 2.x → 4.x не выполняется автоматически и не совмещается с обычной feature-разработкой.
