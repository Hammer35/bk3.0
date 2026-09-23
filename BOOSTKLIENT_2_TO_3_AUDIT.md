# BOOSTKLIENT® 2.0 → 3.0 — аудит переиспользования

## Статус

Аудит выполнен по архиву BOOSTKLIENT® 2.0, предоставленному пользователем 23 сентября 2026 года.

Цель:

> Не переносить старый проект целиком. Использовать 2.0 как донор проверенных механизмов и бизнес-логики.

Классификация:

- **REUSE** — переносить почти как есть после адаптации импортов/настроек.
- **ADAPT** — логика ценная, но должна быть встроена в новую архитектуру.
- **REFERENCE** — использовать как образец/источник требований, но переписать.
- **DROP** — не переносить в 3.0.

---

# 1. Общий вывод

BOOSTKLIENT® 2.0 уже содержит зрелые решения в нескольких критичных областях:

- Pinterest OAuth;
- публикация изображений и видео;
- очередь публикаций;
- explicit publish confirmation (явное подтверждение публикации);
- восстановление зависших публикаций;
- retry для временных ошибок;
- аналитика;
- Celery Beat;
- подписки и лимиты;
- observability / correlation IDs;
- Pinterest compliance flags;
- lifecycle / purge Pinterest Data;
- тестовая изоляция внешней сети;
- значительный набор тестов.

Это нужно сохранить.

Но 2.0 также содержит архитектурный долг:

- огромные файлы;
- смешение доменов;
- дублирование моделей Pinterest;
- User → PinterestAccount вместо Workspace → Business;
- два разных dependency freeze с конфликтующими версиями;
- Pinterest scraping / competitor research legacy code;
- Chroma/RAG с историческими global fallback путями;
- прямое хранение OAuth tokens в модели;
- большое количество root-level scripts;
- старый UI и Tailwind 3.x;
- логика, которую нельзя переносить без повторной проверки Pinterest policy.

Итог:

> BOOSTKLIENT® 3.0 строится как новый проект. Код 2.0 переносится выборочно по модульным контрактам.

---

# 2. Что обнаружено в 2.0

Основные Django apps:

- `authentication`
- `billing`
- `pinterest_integration`
- `ai_assistant`
- `blog`

Техническая база уже близка к целевой:

- Python 3.12 используется в CI;
- Django 5.2.6;
- Celery 5.3.4;
- Redis в текущей версии;
- PostgreSQL;
- ASGI файл уже присутствует;
- Gunicorn присутствует;
- Tailwind 3.4;
- Celery Beat;
- extensive AI/RAG dependencies.

В проекте найдено около:

- 120 test-файлов;
- 85 migration-файлов.

---

# 3. Критичный вывод по зависимостям

В 2.0 присутствуют два сильно расходящихся набора зависимостей:

## requirements.txt

Содержит точный freeze production-окружения и комментарий о реальном несовместимом dependency graph:

- docling 1.0.2 требует `huggingface_hub<1`;
- transformers 5.8.1 требует `huggingface_hub>=1.5.0`;
- production обходил resolver через полный freeze + `--no-deps`.

## requirements_prod.txt

Содержит уже другие ветки:

- docling 2.73.0;
- langchain 1.2.x вместо 0.3.x;
- langgraph 1.x вместо 0.6.x;
- numpy 2.4.x вместо 1.26.x;
- другие версии OpenAI и связанных библиотек.

Вывод:

> Dependency environment 2.0 не переносить в 3.0.

Для 3.0:

- чистая dependency matrix;
- единый lock-файл;
- никаких `--no-deps` как штатной стратегии;
- AI/RAG библиотеки добавлять только после compatibility gate.

Это подтверждает правильность документа `BOOSTKLIENT_3_STACK_VERSIONS.md`.

---

# 4. REUSE — переносить как проверенные механизмы

## 4.1 Pinterest OAuth flow и token refresh logic

Файлы-доноры:

- `pinterest_integration/services.py`
- `pinterest_integration/tasks.py`
- связанные tests.

Ценно:

- proactive token refresh;
- refresh expiry handling;
- reconnect state;
- temporary/permanent error handling;
- token refresh Celery task.

Переносить не модель целиком, а сервисную логику.

---

## 4.2 Publish confirmation mechanism

В `pinterest_integration.PinterestPin` уже существует:

- `publish_confirmed_at`;
- `publish_confirmed_by`;
- signature/hash опубликованного payload;
- `has_valid_publish_confirmation()`;
- `require_valid_publish_confirmation()`.

Это очень ценная реализация и напрямую соответствует новым Pinterest Developer Guidelines.

Особенно важно:

> Если Pin изменился после подтверждения, старое подтверждение становится недействительным.

Эту концепцию обязательно переносим в 3.0.

В новой модели она должна жить через:

- PinVersion;
- Approval;
- approval signature / immutable version relation.

---

## 4.3 Publishing recovery

В 2.0 уже реализовано восстановление зависших состояний публикации.

Найдены механизмы:

- stale PUBLISHING recovery;
- requeue;
- scheduled queue reflow;
- retry transient errors;
- account-level dispatcher;
- отдельная обработка image/video;
- защита от повторной публикации.

Это сильный донор для `PublicationService` 3.0.

---

## 4.4 Per-account queue dispatcher

`process_scheduled_pins_task` уже работает как dispatcher:

- находит аккаунты с due pins;
- создаёт отдельную task на account;
- не обрабатывает весь объём в одном цикле.

Эту архитектурную идею сохраняем.

В 3.0 она должна быть разделена по очередям:

- critical;
- generation;
- research;
- analytics;
- notifications.

---

## 4.5 Correlation / observability helpers

`ai_boost/observability.py` содержит:

- request_id;
- run_id;
- task_id;
- ContextVar;
- log filter;
- безопасную normalization correlation IDs.

Это можно переносить почти напрямую в новый `core/observability`.

---

## 4.6 External network guard for tests

`ai_boost/test_network_guard.py` блокирует внешнюю сеть во время тестов.

Это очень полезный механизм:

> тест случайно не должен позвонить в Pinterest/OpenAI/Etsy и изменить реальные данные или потратить деньги.

Перенести в testing infrastructure 3.0.

---

## 4.7 Pinterest policy feature flags

`ai_assistant/services/pinterest_policy_flags.py` уже содержит default-off gates:

- competitor research;
- unofficial Pinterest access;
- Pinterest AI transfer.

Эту идею переносим в новый central Policy/Feature Gate layer.

---

## 4.8 Pinterest data lifecycle / purge logic

В 2.0 уже есть:

- data map;
- retention audit;
- purge commands;
- disconnect cleanup;
- user deletion path;
- Pinterest Data Lifecycle Service.

Не переносить структуру БД один в один, но сохранить правила и тестовые сценарии.

---

## 4.9 Billing concepts

В `billing` уже существуют:

- SubscriptionPlan;
- Payment;
- UserSubscription;
- trial;
- paid period;
- generation quota;
- account limits.

Бизнес-правила тарифов полезны как донор.

Но ownership должен перейти с User на Workspace/Subscription Account architecture.

---

## 4.10 Existing tests

Переносить не все тесты механически, а использовать как regression specification.

Особенно ценные тестовые темы:

- publishing recovery;
- publish confirmation;
- transient Pinterest errors;
- OAuth reconnect;
- analytics compliance;
- data lifecycle;
- subscription/trial;
- content uniqueness;
- marketplace link resolution.

---

# 5. ADAPT — сохранить логику, переписать под новую архитектуру

## 5.1 PinterestAccount model

2.0:

`User → PinterestAccount`

3.0:

`Workspace → Business → PinterestAccount`

Поэтому модель целиком не переносить.

Перенести:

- external Pinterest identifiers;
- token expiry state;
- reconnect state;
- scopes;
- sync timestamps.

Изменить:

- ownership;
- encrypted token storage;
- granular scopes;
- Business relation;
- public UUID;
- status model.

---

## 5.2 PinterestBoard

Сохранить:

- external ID;
- name;
- operational relation to account;
- timestamps.

Но учитывать Pinterest retention policy:

- хранить только разрешённый operational minimum;
- API data cache должен иметь TTL там, где требуется.

---

## 5.3 PinterestPin

В 2.0 это слишком крупная сущность, объединяющая:

- draft;
- generation;
- schedule;
- approval;
- publication;
- analytics;
- media;
- uniqueness.

В 3.0 разделить:

- ContentPlanItem;
- Pin;
- PinVersion;
- Approval;
- Publication;
- MediaAsset;
- PinAnalyticsDaily.

Старую модель использовать как карту требований, но не переносить ORM schema.

---

## 5.4 Scheduler

Логику:

- timezone;
- due dates;
- subscription horizon;
- rescheduling;
- destination publication controls;
- stale recovery;

сохранить.

Но вынести из огромного `ai_assistant/tasks.py` в:

- scheduler/services;
- publishing/services;
- publishing/tasks.

---

## 5.5 Content generation

2.0 содержит большой объём реально работающей логики:

- title/description generation;
- CTA;
- hashtags;
- SEO;
- semantic rewrite;
- uniqueness;
- image generation;
- marketplace generation.

Это нельзя выбрасывать.

Но текущие файлы слишком крупные:

- `content_generation_service.py` ~2590 строк;
- `tasks.py` ~2530 строк.

Перенести функциональность по сервисам:

- ContentPromptBuilder;
- TextGenerationService;
- ImageGenerationService;
- ContentValidator;
- SimilarityService;
- ContentRecipeService.

---

## 5.6 Content uniqueness system

Сохранить:

- content hashes;
- semantic comparison;
- title/description diversity;
- regeneration flow;
- duplicate detection.

Изменить:

- owner scope обязателен;
- не использовать competitor Pinterest data без разрешения;
- similarity history должна быть Business/PinterestAccount scoped;
- хранение embeddings должно соблюдать retention.

---

## 5.7 RAG / document pipeline

В 2.0 есть полноценная инфраструктура:

- DocumentSource;
- ProcessedDocument;
- DocumentChunk;
- Celery document processing;
- Chroma;
- embeddings;
- Docling.

Концепцию можно переиспользовать.

Но текущую dependency graph переносить нельзя.

В 3.0 сначала определить:

- нужен ли Chroma;
- нужен ли pgvector;
- какой embedding provider;
- какие типы knowledge;
- ownership filters;
- retention;
- provider abstraction.

---

## 5.8 Chat orchestration

`CHAT_ORCHESTRATION_PLAN.md` содержит хорошие идеи:

- chat context;
- function calling;
- action tools;
- async work;
- proactive updates.

Но `ChatSession.context_data` не должен стать новым источником истины.

3.0 использует:

- Context Builder;
- BusinessMemory;
- AIJob;
- Tool Calling;
- PostgreSQL source of truth.

Документ 2.0 использовать как reference + partial donor.

---

## 5.9 Storage abstraction

В 2.0 уже есть `ImageStorageService`, но он жёстко зависит от Cloudinary.

Концепцию интерфейса сохранить.

В 3.0:

`StorageService`
→ LocalPersistentStorage
→ later S3Storage.

Cloudinary не является обязательной зависимостью.

---

## 5.10 Authentication

Сохранить:

- validation;
- account lifecycle concepts;
- cleanup flows;
- timezone handling.

Но новая система должна учитывать:

- Workspace membership;
- roles;
- multi-tenant permissions;
- 2FA/admin security.

---

# 6. REFERENCE — использовать как спецификацию, но переписать

## 6.1 ai_assistant/views.py

Размер около 7862 строк.

Это главный архитектурный anti-pattern 2.0.

Использовать как карту существующих функций.

Не переносить код файла в 3.0.

Разделить на domain views/services.

---

## 6.2 ai_assistant/tasks.py

Размер около 2531 строк.

Содержит слишком много разных областей:

- Pinterest publishing;
- documents;
- competitor analysis;
- keywords;
- analytics;
- WB;
- generation.

Использовать как карту workflows.

Каждый workflow переносить в своё Django app.

---

## 6.3 pinterest_integration/services.py

Около 2279 строк.

PinterestAPIService содержит большой объём API logic в одном классе.

Использовать как donor/reference.

В 3.0 разделить:

- auth;
- organic pins/boards;
- analytics;
- ads;
- catalogs;
- trends;
- business access;
- conversions.

---

## 6.4 ai_boost/settings.py

Около 1768 строк.

Использовать как список текущих operational settings.

В 3.0 разделить:

- base.py;
- development.py;
- test.py;
- production.py.

---

## 6.5 Deployment scripts

В корне много:

- restart scripts;
- force restart;
- custom production publishing scripts;
- systemd cleanup utilities.

Использовать как знания о реальных production-проблемах.

Но 3.0 deploy строить через Docker / versioned releases / CI/CD.

---

## 6.6 Pinterest compliance documentation

Документы 2.0 очень ценны:

- PINTEREST_DATA_MAP;
- RETENTION_AND_DELETION_POLICY;
- NETWORK_ACCESS_AUDIT;
- OAUTH_SCOPES audit;
- APP_REVIEW package;
- SUPPORT response.

Их использовать как историческую доказательную базу.

Но source of truth 3.0 — новый `BOOSTKLIENT_3_PINTEREST_API.md` + актуальная официальная документация.

---

# 7. DROP — не переносить

## 7.1 Pinterest scraping / unofficial access

Не переносить production-функции:

- Pinterest downloader;
- competitor scraper;
- undocumented Pinterest network access;
- HTML scraping Pinterest;
- legacy Pinterest competitor collection.

Причина:

Pinterest Developer Guidelines.

---

## 7.2 Competitor Pinterest RAG data

Не переносить существующие:

- competitor_patterns;
- CompetitorAnalysisCache;
- чужие Pin/Board datasets;
- derived competitor embeddings;

если нет отдельного письменного разрешения Pinterest.

---

## 7.3 Дублирующая модель ai_assistant.PinterestPin

В 2.0 обнаружены две разные PinterestPin модели:

- `pinterest_integration.PinterestPin`
- `ai_assistant.PinterestPin`

Такого в 3.0 быть не должно.

Один домен — одна каноническая модель.

---

## 7.4 Legacy root scripts

Не переносить хаотично:

- restart_*.sh/py;
- force_restart.py;
- temporary test scripts;
- one-off diagnostic scripts;
- backup copies вида `models.py.bak`;
- случайные root HTML/files.

Если функция нужна — оформить её как:

- management command;
- deployment tool;
- test;
- documented script.

---

## 7.5 requirements freeze 2.0

Не переносить.

Особенно не переносить штатную схему:

`pip install --no-deps`

как способ удерживать несовместимый graph.

---

## 7.6 Старый Tailwind build

2.0 использует Tailwind 3.4.

3.0 зафиксирован на Tailwind 4.x.

Старый build pipeline не переносить.

---

# 8. Тонкие места, найденные в 2.0

## 8.1 Hardcoded max pins

В `PinterestAccount.clean()` обнаружен максимум 100 pins/day.

При этом billing logic в 2.0 уже содержит fallback до 150 pins/day для Pro/tester.

Это внутреннее противоречие.

3.0 не должен дублировать лимиты в нескольких моделях.

Источник истины:

- тариф;
- platform policy;
- user strategy;
- scheduler limits.

---

## 8.2 Trust Sandbox phases

В модели PinterestAccount есть hardcoded `_TRUST_PHASES` с комментариями про Pinterest anti-spam Guardian.

Эту механику нельзя переносить как факт без официального подтверждения Pinterest.

Можно сохранить как экспериментальную внутреннюю heuristic только после отдельного review.

---

## 8.3 OAuth tokens

Access/refresh tokens хранятся напрямую в TextField.

3.0 требует:

- encryption at rest;
- secret-safe logs;
- rotation;
- lifecycle/revoke.

---

## 8.4 Nullable ownership

`PinterestAccount.user` допускает NULL.

Для 3.0 ownership должен быть строгим и явным через Workspace/Business.

Архивированные объекты не должны становиться orphaned без controlled lifecycle.

---

## 8.5 Scope хранится JSON-строкой в TextField

3.0 должен использовать нормализованный representation:

- JSONField или отдельную granted scope model;
- проверка required scope на каждый API feature.

---

## 8.6 RAG isolation

Существующая documentation уже сама зафиксировала исторические проблемы:

- global fallback;
- Trends без owner;
- competitor collection shared;
- некоторые user_id checks отсутствовали.

В 3.0 retrieval scope должен задаваться до запроса к vector store.

---

# 9. Что переносить первым

Приоритет миграции кода:

## Wave 1 — Pinterest core

1. OAuth refresh behavior.
2. Pinterest API error classification.
3. explicit publish confirmation logic.
4. publication state/recovery.
5. image/video publishing.
6. account-level scheduling dispatcher.
7. tests.

## Wave 2 — Business operations

1. subscription/trial rules;
2. account limits;
3. timezone logic;
4. storage abstraction;
5. notification patterns.

## Wave 3 — Content engine

1. content text generation;
2. semantic rewriting;
3. uniqueness;
4. generation jobs;
5. image generation;
6. marketplace source adapters.

## Wave 4 — AI/RAG

Только после новой AI Architecture:

1. document ingestion concepts;
2. embeddings;
3. retrieval;
4. chat orchestration;
5. tool calling.

---

# 10. Что НЕ мигрировать через DB migration

Не пытаться привести старую ORM schema к новой десятками сложных Django migrations.

Лучший подход:

> новая БД 3.0 + controlled importer.

Преимущества:

- новая чистая schema;
- возможность валидировать каждую запись;
- преобразование User → Workspace/Business;
- удаление legacy data;
- compliance filtering;
- возможность dry-run.

---

# 11. Migration Importer

Создать отдельный модуль:

`migration_v2/`

Он должен:

1. читать экспорт 2.0;
2. не иметь прямого runtime coupling с production 2.0;
3. валидировать данные;
4. преобразовывать в 3.0 schema;
5. создавать migration report;
6. поддерживать dry-run;
7. быть идемпотентным;
8. позволять повторный запуск;
9. иметь rollback/import batch ID.

---

# 12. Что переносить по данным

Кандидаты:

- пользователи;
- subscription state;
- payment history, если юридически/технически требуется;
- connected Pinterest accounts — только при безопасной миграции токенов;
- owned Boards operational references, если Pinterest policy позволяет;
- draft content пользователя;
- approved unpublished content;
- собственная analytics, разрешённая Pinterest;
- собственные настройки;
- marketplace source data.

Не переносить автоматически:

- competitor Pinterest data;
- prohibited scraped Pinterest data;
- global Pinterest RAG data;
- stale API caches;
- legacy temporary files;
- obsolete task results.

---

# 13. Стратегия запуска 3.0

Рекомендуемая схема:

## Phase A

2.0 продолжает обслуживать пользователей.

3.0 разрабатывается отдельно.

## Phase B

Staging importer работает на копии данных 2.0.

## Phase C

Выбирается небольшой тестовый набор пользователей.

## Phase D

Сравниваются:

- OAuth;
- scheduler;
- publishing;
- analytics;
- billing;
- content generation.

## Phase E

Controlled cutover.

## Phase F

2.0 временно остаётся read-only fallback, затем архивируется.

---

# 14. Главный вывод

BOOSTKLIENT® 2.0 не нужно выбрасывать.

Там уже есть дорогая проверенная логика, особенно вокруг Pinterest publishing/compliance.

Но:

> переносим знания и проверенные механизмы, а не старую архитектуру.

Наиболее ценная часть 2.0 для 3.0:

**OAuth → Approval → Scheduler → Publish → Recovery → Analytics → Compliance**

Эту цепочку нужно сохранить максимально бережно и покрыть regression tests до рефакторинга.
