# BOOSTKLIENT® 3.0 — Monitoring & Observability

## Статус документа

Живой документ.

Цель: зафиксировать минимально необходимый мониторинг BOOSTKLIENT® 3.0 уже для MVP, чтобы система сама сообщала о технических и бизнес-проблемах до того, как их заметит пользователь.

Главный принцип:
> Технический мониторинг и бизнес-мониторинг одинаково обязательны.

---

# 1. Что должен отвечать мониторинг

В любой момент система должна позволять понять:
- приложение живо или нет;
- PostgreSQL доступен или нет;
- Valkey доступен или нет;
- Celery workers живы или нет;
- очередь растёт или нет;
- публикации идут по расписанию или отстают;
- Pinterest API работает или нет;
- AI provider работает или нет;
- Telegram / MAX уведомления доходят или нет;
- хватает ли диска;
- создаются ли backup;
- заканчивается ли approved buffer;
- сколько задач завершилось ошибкой.

---

# 2. Слои мониторинга

Минимум пять слоёв:

1. Application Monitoring — Django и ошибки приложения.
2. Celery Monitoring — фоновые задачи и очереди.
3. Infrastructure Monitoring — CPU, RAM, disk, PostgreSQL, Valkey, контейнеры.
4. External Services Monitoring — Pinterest, AI providers, Telegram, MAX.
5. Business Monitoring — публикации, approvals, buffer, стратегии и фактический результат автоматизации.

---

# 3. Application Monitoring

Для MVP использовать Sentry или совместимый error tracking сервис.

Отслеживать:
- unhandled exceptions;
- HTTP 500;
- slow requests;
- template errors;
- database errors;
- external API errors;
- user-facing failures;
- Celery task exceptions.

События должны содержать безопасный контекст:
- request_id;
- user_id;
- workspace_id;
- business_id;
- task_id.

Не отправлять в мониторинг:
- пароли;
- OAuth tokens;
- API keys;
- session cookies;
- Authorization headers;
- секреты.

---

# 4. Structured Logging

Логи должны быть структурированными.

Минимальные поля:
- timestamp;
- level;
- service;
- event;
- request_id;
- user_id;
- workspace_id;
- business_id;
- task_id;
- duration_ms;
- result/status.

Лог должен позволять связать:
web request → service → Celery task → external API → final result.

---

# 5. Request ID / Correlation ID

Каждый входящий запрос получает request_id.

Если запрос создаёт Celery task, request_id / correlation_id передаётся дальше.

Это позволяет восстановить всю цепочку одного действия пользователя.

---

# 6. Celery Monitoring

Для первой версии использовать Flower как операционный интерфейс Celery.

Контролировать:
- worker online/offline;
- active tasks;
- queued tasks;
- retries;
- failures;
- execution time;
- worker load;
- revoked tasks.

Flower — вспомогательный инструмент, а не единственный источник мониторинга.

---

# 7. Queue Monitoring

Отдельно отслеживать длину и возраст задач в каждой очереди:
- critical;
- generation;
- research;
- analytics;
- notifications;
- low_priority.

Важно контролировать не только количество задач, но и age of oldest task (возраст самой старой задачи).

Пример:
- generation = 500 задач может быть нормально;
- critical = 5 задач старше 10 минут может быть критично.

---

# 8. Worker Heartbeat

Каждый worker должен регулярно подтверждать, что он жив.

Если critical worker не отвечает — немедленный alert.

Для generation/research допускается более мягкий порог.

---

# 9. Infrastructure Monitoring

Минимальные системные метрики:
- CPU;
- RAM;
- disk usage;
- disk I/O при необходимости;
- container restarts;
- network errors;
- load average;
- uptime.

---

# 10. Disk Monitoring

Особенно важно из-за медиа.

Предварительные пороги:
- 70% — warning;
- 80% — high warning;
- 90% — critical.

При росте диска система должна также показать:
- media usage;
- temporary media usage;
- database usage;
- logs usage.

---

# 11. PostgreSQL Monitoring

Минимально отслеживать:
- доступность;
- disk usage;
- active connections;
- connection saturation;
- slow queries;
- locks;
- deadlocks;
- failed migrations;
- backup status;
- backup age.

Позже добавить:
- query latency;
- cache hit ratio;
- table growth;
- index usage.

---

# 12. Valkey Monitoring

Отслеживать:
- доступность;
- memory usage;
- connected clients;
- blocked clients;
- key count;
- evictions;
- persistence status;
- last successful persistence;
- reconnect events.

Для Celery broker eviction критичных ключей недопустим.

---

# 13. External Services Monitoring

Для каждого внешнего провайдера хранить:
- availability;
- latency;
- error rate;
- rate limit errors;
- authentication errors;
- last successful call.

Провайдеры:
- Pinterest API;
- OpenAI / DeepSeek / другие LLM;
- Telegram;
- MAX;
- email provider;
- marketplace integrations.

---

# 14. Pinterest API Monitoring

Отдельно отслеживать:
- публикации success/fail;
- OAuth errors;
- token refresh errors;
- rate limit;
- API latency;
- API 4xx / 5xx;
- failed board lookup;
- duplicate publish prevention.

---

# 15. AI Monitoring

Для каждого AI-вызова:
- provider;
- model;
- task type;
- latency;
- input tokens;
- output tokens;
- cost;
- success/failure;
- retry;
- fallback.

Отдельно отслеживать:
- резкий рост стоимости;
- рост latency;
- рост invalid structured outputs;
- рост tool call failures.

---

# 16. Business Monitoring

Это обязательный слой.

Система считается сломанной не только когда сервер упал, но и когда бизнес-процесс не выполняется.

Отслеживать:
- pins planned today;
- pins approved today;
- pins published today;
- pins failed today;
- pins overdue;
- average publication delay;
- approved buffer size;
- waiting approval count;
- generation backlog;
- stuck PUBLISHING;
- strategies waiting for user;
- failed approvals;
- notification delivery failures.

---

# 17. Approved Buffer Monitoring

Один из главных показателей системы.

Для каждого PinterestAccount считать:
- approved pins count;
- approved hours/days remaining;
- required daily publishing rate.

Пример состояний:
- GREEN — запас > 2 дней;
- YELLOW — запас 1–2 дня;
- RED — запас < 1 дня;
- CRITICAL — очередь скоро остановится.

---

# 18. Stuck State Detection

Периодическая Celery-задача должна искать зависшие состояния.

Примеры:
- Pin GENERATING слишком долго;
- Pin VALIDATING слишком долго;
- Publication PUBLISHING слишком долго;
- AIJob RUNNING слишком долго;
- Approval WAITING слишком долго.

Для каждого статуса должен существовать max expected duration.

---

# 19. Alerts

Monitoring без alerting недостаточен.

Alert должен содержать:
- что произошло;
- severity;
- какой сервис / business затронут;
- когда началось;
- ссылка на диагностику, если доступна;
- рекомендуемое первое действие.

---

# 20. Severity Levels

Минимум четыре уровня:

INFO
- информационное событие.

WARNING
- проблема появилась, но работа продолжается.

HIGH
- часть функциональности деградировала.

CRITICAL
- риск потери данных, публикаций или полной недоступности.

---

# 21. Alert Channels

Для MVP:
- Telegram для технических alert;
- email как резерв;
- Sentry notifications.

Позже возможны:
- MAX;
- Slack;
- PagerDuty или аналог.

---

# 22. Примеры обязательных alert

CRITICAL:
- Django unavailable;
- PostgreSQL unavailable;
- critical worker offline;
- disk > 90%;
- backup отсутствует дольше допустимого срока;
- массовая ошибка публикаций;
- Pinterest OAuth массово перестал работать.

HIGH:
- critical queue oldest task > порога;
- approved buffer < 1 дня;
- AI provider недоступен;
- рост failed tasks;
- Valkey reconnect loop.

WARNING:
- disk > 70%;
- generation backlog растёт;
- несколько публикаций отстают;
- cost AI выше ожидаемого;
- notification delivery ухудшилось.

---

# 23. Noise Control

Alerts не должны превращаться в спам.

Использовать:
- deduplication;
- cooldown;
- grouping;
- escalation.

Пример:
100 одинаковых ошибок Pinterest за 5 минут = один alert с количеством, а не 100 сообщений.

---

# 24. Health Endpoints

Предусмотреть:
- /health/live — процесс жив;
- /health/ready — приложение готово обслуживать запросы;
- /health/dependencies — состояние PostgreSQL / Valkey / критичных зависимостей.

Health endpoints не должны раскрывать секретную инфраструктурную информацию публично.

---

# 25. Uptime Monitoring

Внешний uptime check должен регулярно проверять публичный endpoint.

Цель:
понять, доступен ли сервис снаружи, а не только внутри сервера.

---

# 26. Backup Monitoring

Для каждого backup хранить:
- started_at;
- finished_at;
- status;
- size;
- checksum;
- location;
- restore_tested_at.

Alert если:
- backup failed;
- backup слишком старый;
- размер резко изменился;
- restore давно не тестировался.

---

# 27. Monitoring Retention

Не хранить все raw logs бесконечно.

Нужно определить сроки хранения:
- application logs;
- audit logs;
- metrics;
- Sentry events;
- worker events.

Audit logs могут иметь другой срок хранения, чем технические логи.

---

# 28. Privacy

Monitoring не должен становиться новой утечкой данных.

Запрещено отправлять в third-party monitoring:
- секреты;
- полный prompt без необходимости;
- OAuth tokens;
- приватный пользовательский контент без явной необходимости;
- файлы пользователей.

---

# 29. MVP Monitoring Stack

Для первой версии зафиксировать:
- Sentry — ошибки Django / Celery;
- Flower — операционный контроль Celery;
- Django structured logging;
- health endpoints;
- host/container metrics;
- PostgreSQL basic metrics;
- Valkey basic metrics;
- Telegram technical alerts;
- business monitoring в PostgreSQL + периодические Celery checks.

Не внедрять Prometheus + Grafana до появления реальной необходимости.

---

# 30. Когда добавлять Prometheus / Grafana

Добавлять если:
- серверов стало несколько;
- workers много;
- Flower и простых метрик недостаточно;
- нужна история временных рядов;
- нужны сложные dashboards;
- нужен capacity planning.

---

# 31. Monitoring Dashboard внутри BOOSTKLIENT®

Для администратора продукта нужен внутренний dashboard.

Минимально:
- system status;
- publication health;
- queue status;
- workers;
- external APIs;
- AI provider status;
- disk;
- backup;
- failures за 24 часа.

Обычным пользователям внутреннюю инфраструктуру не показывать.

---

# 32. User-facing Status

Пользователю показывать только релевантный статус его процессов:
- анализируется;
- генерируется;
- ждёт одобрения;
- опубликовано;
- временная ошибка;
- повторяем попытку.

Не показывать internal stack traces и инфраструктурные детали.

---

# 33. Основной критерий

> Если важный процесс перестал работать, команда должна узнать об этом автоматически раньше пользователя.

---

# 34. Второй критерий

> «Сервер работает» не означает «продукт работает». Бизнес-процесс публикации должен мониториться отдельно.