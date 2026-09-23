# BOOSTKLIENT® 3.0 — инфраструктура и развёртывание

## Статус документа

Живой документ.

Цель: зафиксировать инфраструктуру BOOSTKLIENT® 3.0 с приоритетами:
- стабильность;
- отказоустойчивость;
- простота;
- предсказуемость;
- масштабируемость;
- минимальная стоимость на старте.

Главный принцип:
> Инфраструктура должна быть достаточно простой для поддержки одним разработчиком, но не мешать росту продукта.

---

# 1. Базовая схема

Internet
↓
Nginx
↓
Django ASGI
↓
PostgreSQL

Параллельно:

Django / Celery
↓
Valkey
↓
Celery Workers

Отдельно:
- persistent media storage (постоянное файловое хранилище);
- backups;
- monitoring;
- logs;
- external AI providers;
- Pinterest API;
- Telegram / MAX.

---

# 2. Docker

Для BOOSTKLIENT® 3.0 использовать Docker.

Причины:
- одинаковое окружение local / staging / production;
- меньше проблем «у меня работает, на сервере нет»;
- удобно фиксировать версии;
- проще rollback;
- проще перенос на другой сервер;
- проще масштабировать отдельные workers.

На старте использовать Docker Compose.

Не использовать Kubernetes на раннем этапе.

Причина:
> Kubernetes добавляет сложность раньше, чем она реально нужна.

---

# 3. Контейнеры

Предварительные сервисы:
- web — Django ASGI;
- worker-critical;
- worker-generation;
- worker-research;
- worker-analytics;
- worker-notifications;
- celery-beat;
- valkey;
- nginx.

PostgreSQL:
- development — можно в Docker;
- production — предпочтительно отдельный сервис / отдельный сервер / managed DB при наличии бюджета.

---

# 4. Django ASGI

BOOSTKLIENT® 3.0 сразу строится на ASGI.

Причины:
- SSE (потоковые ответы ИИ);
- долгие соединения;
- возможность realtime-функций в будущем;
- не потребуется потом миграция WSGI → ASGI.

Предпочтительный запуск:
- Uvicorn;
или
- Gunicorn + Uvicorn workers.

Окончательный вариант выбирается при первом production deploy.

---

# 5. Nginx

Nginx используется как reverse proxy (входная точка приложения).

Задачи:
- HTTPS;
- proxy к Django;
- static files;
- ограничения upload;
- security headers;
- rate limiting при необходимости;
- gzip/brotli если конфигурация стабильна;
- защита Django от прямого доступа извне.

---

# 6. PostgreSQL

PostgreSQL — главный источник истины.

В production:
- не выставлять публично;
- отдельный пользователь БД;
- минимальные права;
- регулярные backup;
- мониторинг места;
- проверка restore.

При росте первым кандидатом на вынос из основного сервера является PostgreSQL.

---

# 7. Valkey

Valkey используется для:
- Celery broker;
- cache;
- locks;
- временного состояния;
- служебных очередей.

Не является постоянным источником бизнес-данных.

Valkey не должен быть доступен напрямую из интернета.

---

# 8. Celery workers

Очереди разделяются по назначению.

Минимальный набор:
- critical — публикации и критические операции;
- generation — генерация контента;
- research — исследования;
- analytics — аналитика;
- notifications — Telegram / MAX / email;
- low_priority — второстепенные задачи.

Для каждой группы можно запускать отдельные workers.

Это позволяет масштабировать только тот тип нагрузки, который вырос.

---

# 9. Celery Beat

Celery Beat используется для периодических задач:
- очистка временных файлов;
- аналитика;
- синхронизация;
- ежедневные уведомления;
- проверка очередей;
- сезонные задачи;
- service jobs.

Пользовательские индивидуальные расписания при необходимости хранить в БД.

---

# 10. Media Storage на старте

Чтобы не удорожать продукт, на старте использовать local persistent storage.

Важно:
- медиа не хранится внутри Docker-контейнера;
- используется отдельный persistent volume / отдельный диск;
- доступ идёт через StorageService;
- архитектура S3-ready, но внешний S3 не обязателен.

При росте можно перейти на S3-compatible storage без переписывания бизнес-логики.

---

# 11. Media Lifecycle Policy

Автоматическая очистка временных файлов обязательна.

Правило:
> Любой временный файл обязан иметь TTL.

Примеры:
- technical temp files — 24 часа;
- AI drafts — 3–7 дней;
- rejected media — 7 дней;
- unused video drafts — максимально короткий срок;
- approved media — хранить;
- published media — хранить рабочую версию и необходимые thumbnails.

Очистка выполняется через Celery Beat.

---

# 12. Static Files

CSS, JS и иконки:
- собираются при deploy;
- имеют version/hash;
- кэшируются браузером;
- не хранятся как изменяемые runtime-файлы.

---

# 13. Окружения

Использовать минимум три среды:

## Development
Локальная разработка.

## Staging
Тестовая среда, максимально похожая на production.

На staging проверяются:
- migrations;
- Celery;
- Valkey;
- Pinterest API;
- AI;
- темы;
- HTMX;
- security;
- deploy;
- rollback.

## Production
Боевой сервис.

Правило:
> В production не проверяется то, что не было проверено на staging.

---

# 14. CI/CD

GitHub используется как источник кода и точка запуска проверок.

Перед merge:
- install dependencies;
- lock verification;
- tests;
- Django check;
- migrations check;
- dependency scan;
- security scan;
- import checks.

Deploy flow:
main
↓
staging
↓
smoke tests
↓
production

Не использовать ручной хаотичный `git pull` как основной deployment-процесс.

---

# 15. Deployment Strategy

Каждый релиз должен иметь version/tag.

Пример:
`boostklient:3.0.17`

Нельзя использовать `latest` как единственную production-метку.

Это нужно для rollback.

---

# 16. Rollback

Новая версия должна откатываться на предыдущую без сборки проекта заново.

При ошибке:
- остановить новый release;
- вернуть предыдущий image/tag;
- проверить DB compatibility;
- восстановить workers;
- подтвердить health checks.

---

# 17. Миграции базы

Миграции должны быть максимально backward compatible.

Предпочтительный подход:
1. добавить новое поле / таблицу;
2. выпустить код, который умеет работать со старым и новым;
3. перенести данные;
4. только отдельным релизом удалить старое.

Не совмещать необратимую миграцию и большой функциональный релиз без крайней необходимости.

---

# 18. Backup

Минимально резервировать:
- PostgreSQL;
- persistent media;
- важную конфигурацию;
- secrets в защищённом месте.

Backup не считается рабочим, пока не проведён тест restore.

---

# 19. Restore Drill

Регулярно проверять восстановление.

Нужно уметь:
- поднять новую PostgreSQL;
- восстановить backup;
- подключить приложение;
- восстановить media;
- проверить публикации и очереди.

---

# 20. Health Checks

Приложение должно иметь health endpoints.

Минимум проверять:
- Django жив;
- PostgreSQL доступен;
- Valkey доступен.

Отдельно отслеживать:
- worker heartbeat;
- queue backlog;
- failed tasks;
- disk usage;
- DB disk usage.

---

# 21. Graceful Shutdown

При deploy workers и web не должны аварийно убиваться без необходимости.

Нужно дать:
- web завершить активные запросы;
- workers завершить текущие задачи или корректно вернуть их в очередь.

---

# 22. Масштабирование

Первый этап масштабирования:
- увеличить число Celery workers;
- разделить workers по очередям;
- увеличить web replicas;
- вынести PostgreSQL;
- вынести Valkey;
- вынести media в S3-compatible storage.

Не переходить к Kubernetes, пока Docker Compose / обычная оркестрация покрывают нагрузку.

---

# 23. Отказоустойчивость

Критичные принципы:
- PostgreSQL — источник истины;
- Celery tasks идемпотентны;
- публикации защищены idempotency key;
- critical queue отделена;
- данные не хранятся только в контейнере;
- регулярные backup;
- rollback готов;
- staging обязателен;
- health checks обязательны.

---

# 24. Что не усложняем на старте

Не использовать без необходимости:
- Kubernetes;
- service mesh;
- Kafka;
- Elasticsearch;
- отдельный CDN;
- отдельный object storage provider;
- микросервисы;
- сложный event bus.

BOOSTKLIENT® 3.0 на старте остаётся хорошо структурированным Django-монолитом.

---

# 25. Архитектурный стиль

Выбран подход:
**Modular Monolith (модульный монолит)**

Это значит:
- одно Django-приложение как единый продукт;
- чёткие доменные модули;
- отдельные workers;
- отдельные инфраструктурные сервисы;
- возможность позже вынести отдельные тяжёлые части в сервисы.

---

# 26. Главный принцип инфраструктуры

> Сначала простая надёжная система, которую можно понять и восстановить вручную. Масштабирование — по фактической нагрузке, а не заранее.

---

# 27. Зафиксированный стек инфраструктуры

- Docker;
- Docker Compose;
- Django ASGI;
- Uvicorn или Gunicorn + Uvicorn workers;
- Nginx;
- PostgreSQL;
- Valkey;
- Celery;
- Celery Beat;
- local persistent media storage;
- StorageService abstraction;
- Development / Staging / Production;
- GitHub CI/CD;
- versioned releases;
- backup + restore testing;
- health checks;
- rollback.