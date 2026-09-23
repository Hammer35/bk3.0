# BOOSTKLIENT® 3.0 — модель данных

## Статус документа

Живой документ.

Цель: зафиксировать основные сущности BOOSTKLIENT® 3.0, их связи, ownership (принадлежность), историю изменений и источники истины до начала активной разработки.

Главный принцип:
> Модель данных должна поддерживать рост продукта без болезненных переделок и сохранять историю решений, контента и аналитики.

---

# 1. Базовая иерархия владения

User
↓
Workspace
↓
Business
↓
PinterestAccount

Данные продукта принадлежат Workspace / Business, а не напрямую User.

Это позволяет в будущем поддержать:
- команды;
- агентства;
- сотрудников;
- несколько бизнесов;
- несколько Pinterest-аккаунтов;
- разные роли доступа.

---

# 2. User

Хранит учётную запись пользователя.

Не должен напрямую владеть всей бизнес-логикой проекта.

Ключевые связи:
- Membership;
- Workspace;
- настройки пользователя;
- язык;
- тема интерфейса;
- security settings.

---

# 3. Workspace

Рабочее пространство.

В Workspace могут находиться:
- несколько пользователей;
- несколько Business;
- роли;
- лимиты;
- тариф;
- настройки доступа.

Workspace является одной из основных границ multi-tenant isolation (изоляции пользователей).

---

# 4. Membership / Role

Связывает User и Workspace.

Минимальные роли:
- OWNER;
- ADMIN;
- EDITOR;
- VIEWER.

Каждое критичное действие должно проверять права через Membership / Role.

---

# 5. Business

Представляет конкретный бизнес пользователя.

Поля могут включать:
- name;
- website;
- niche;
- subniche;
- language;
- market;
- audience;
- goals;
- status;
- created_at;
- updated_at;
- archived_at.

Один Workspace может иметь несколько Business.

---

# 6. PinterestAccount

Принадлежит Business.

Хранит:
- внешний Pinterest ID;
- username / account name;
- OAuth connection metadata;
- scopes;
- connection status;
- country / locale;
- publishing settings;
- last sync;
- archived_at.

Секретные токены должны храниться защищённо и не попадать в обычные поля/логи.

---

# 7. Board

Принадлежит конкретному PinterestAccount.

Хранит:
- external Pinterest board ID;
- name;
- description;
- status;
- metadata;
- last sync;
- archived_at.

Pin не должен хранить Board только как строку.

---

# 8. ContentSource — универсальный объект продвижения

ContentSource используется для всего, что пользователь продвигает.

Типы могут включать:
- PRODUCT;
- ARTICLE;
- SERVICE;
- MARKETPLACE_ITEM;
- LANDING_PAGE;
- VIDEO;
- COLLECTION;
- GENERIC_URL;
- другие расширяемые типы.

Это позволяет не создавать отдельную архитектуру под каждый тип бизнеса.

---

# 9. ContentSource — пример полей

Поля могут включать:
- type;
- title;
- url;
- description;
- source_platform;
- external_id;
- category;
- tags;
- price;
- currency;
- status;
- metadata;
- created_at;
- updated_at;
- archived_at.

Медиа не обязательно хранить как простые поля; предпочтительно отдельная связанная сущность MediaAsset.

---

# 10. ContentSourceVersion / Snapshot

ContentSource должен быть версионируемым.

Причина:
- товар меняет цену;
- меняется описание;
- меняются изображения;
- статья обновляется;
- URL может изменять содержимое.

Нужно уметь определить:
> Из какой версии исходных данных был создан конкретный Pin?

Поэтому рекомендуется:
- ContentSource — текущая сущность;
- ContentSourceVersion / ContentSourceSnapshot — историческое состояние.

---

# 11. MediaAsset

Универсальная сущность медиа.

Типы:
- image;
- video;
- generated_image;
- generated_video;
- thumbnail.

Связи возможны с:
- ContentSource;
- PinVersion;
- другими объектами контента.

Хранить:
- storage path / object key;
- mime type;
- dimensions;
- size;
- checksum;
- metadata;
- status.

---

# 12. ResearchSnapshot

Исследование должно иметь временной снимок.

Хранит состояние исследования на определённый момент:
- keywords;
- trends;
- competitors;
- niche findings;
- source metadata;
- created_at.

Нужно для ответа на вопрос:
> На каких данных была построена стратегия?

---

# 13. Keyword

Универсальная сущность ключевого слова.

Поля:
- text;
- locale;
- market;
- normalized form;
- metadata.

Не хранить одинаковые ключи бесконтрольно в разных частях проекта.

---

# 14. KeywordCluster

Группирует связанные Keyword.

Используется для:
- research;
- strategy;
- content planning;
- analytics.

---

# 15. Trend

Хранит трендовую информацию:
- keyword / topic;
- period;
- direction;
- score;
- seasonality;
- source;
- snapshot.

Trend не должен рассматриваться как вечный факт.

---

# 16. Competitor

Представляет конкурента в рамках Business / Research.

Хранит:
- public account data;
- source;
- discovered_at;
- metadata;
- archived_at.

---

# 17. CompetitorPin / CompetitorBoard

Публичные объекты конкурентов могут храниться отдельно для анализа.

Это позволяет:
- сравнивать изменения;
- делать Gap Analysis;
- отслеживать темы и паттерны.

---

# 18. Strategy

Strategy — логический объект стратегии.

Она не должна перезаписываться без истории.

Strategy хранит:
- Business;
- status;
- active_version;
- created_at;
- archived_at.

---

# 19. StrategyVersion

Каждое изменение стратегии создаёт новую версию.

Хранить:
- version number;
- goals;
- priorities;
- keyword clusters;
- recommended boards;
- content directions;
- publishing cadence;
- seasonal plans;
- rationale;
- created_by;
- created_at.

---

# 20. StrategyVersion ↔ ResearchSnapshot

Каждая StrategyVersion должна хранить связь с ResearchSnapshot или набором research sources, на основании которых она была построена.

Это критично для аудита и объяснимости ИИ.

Нужно уметь ответить:
> Почему в версии 3 система приняла именно это решение?

---

# 21. DecisionHistory

Отдельная история решений.

Хранить:
- объект;
- старое значение / решение;
- новое значение / решение;
- причина;
- источник данных;
- инициатор: USER / AI / SYSTEM;
- подтверждение пользователя;
- timestamp.

---

# 22. ContentPlan

ContentPlan — план производства и публикации контента.

Он не равен готовым Pin.

Хранит:
- Business;
- StrategyVersion;
- период;
- status;
- created_at.

---

# 23. ContentPlanItem

Главная единица плана.

Связывает:
- StrategyVersion;
- ContentSource;
- Keyword / KeywordCluster;
- Board;
- search intent;
- target date;
- content type;
- priority;
- status.

ContentPlanItem может существовать до генерации Pin.

---

# 24. Происхождение Pin

Pin должен иметь трассируемое происхождение.

Правильная цепочка:

StrategyVersion
↓
ContentPlan
↓
ContentPlanItem
↓
Pin
↓
Publication

Это позволяет связывать результат Pin с конкретной частью стратегии.

---

# 25. Pin

Pin — логический объект Pinterest-контента.

Не должен содержать только текущее состояние без истории.

Хранит:
- ContentPlanItem;
- current_version;
- status;
- created_at;
- archived_at.

---

# 26. PinVersion

Каждая значимая переработка Pin создаёт новую версию.

Хранит:
- title;
- description;
- alt text;
- destination URL;
- MediaAsset;
- keyword mapping;
- metadata;
- generation source;
- quality score;
- created_at.

Approval должен относиться к конкретной PinVersion.

---

# 27. Approval

Approval — отдельная сущность, а не boolean.

Хранит:
- PinVersion;
- status;
- approved_by;
- channel;
- approved_at;
- rejection reason;
- rework request;
- metadata.

Каналы:
- WEB;
- TELEGRAM;
- MAX;
- SYSTEM_AUTOPILOT, если пользователь явно разрешил.

---

# 28. ApprovalRequest

Можно использовать отдельную сущность для запроса одобрения.

Хранит:
- PinVersion;
- channel;
- sent_at;
- expires_at;
- status;
- secure callback metadata.

---

# 29. Publication

Publication — отдельный объект попытки публикации.

Хранит:
- PinVersion;
- PinterestAccount;
- Board;
- scheduled_at;
- started_at;
- published_at;
- status;
- attempt count;
- idempotency key;
- external Pinterest pin ID;
- response metadata;
- error code;
- error details safe for storage.

---

# 30. PublicationAttempt

При необходимости retries можно вынести в отдельную сущность PublicationAttempt.

Это удобно для:
- диагностики;
- аудита;
- анализа внешних ошибок.

---

# 31. Analytics — принцип хранения

Не хранить всю аналитику одним JSON внутри Pin.

Использовать временные ряды по уровням.

---

# 32. PinAnalyticsDaily

Дневная аналитика конкретного опубликованного Pin.

Примеры:
- impressions;
- saves;
- clicks;
- outbound clicks;
- другие доступные Pinterest metrics.

---

# 33. BoardAnalyticsDaily

Дневная аналитика Board.

---

# 34. AccountAnalyticsDaily

Дневная аналитика PinterestAccount.

---

# 35. ContentSourceAnalyticsDaily

Агрегированная аналитика объекта продвижения.

Позволяет ответить:
> Какие товары / статьи / услуги реально дают результат?

---

# 36. KeywordAnalyticsDaily

Создавать, если данные Pinterest и наша методика позволяют корректно связывать результат с Keyword.

Не выдумывать точность, которой нет в источнике данных.

---

# 37. AIConversation

Хранит chat session / conversation metadata.

Не является постоянной памятью бизнеса.

Полная история имеет отдельную retention policy.

---

# 38. BusinessMemory

Структурированная память бизнеса.

Хранит только извлечённые и подтверждённые факты, необходимые для работы ИИ.

---

# 39. AIJob

Хранит состояние долгой AI-задачи.

Статусы:
- PENDING;
- RUNNING;
- WAITING_INPUT;
- COMPLETED;
- FAILED;
- CANCELLED.

PostgreSQL является источником истины по статусу AIJob.

---

# 40. NotificationChannel

Канал связи пользователя.

Типы:
- EMAIL;
- TELEGRAM;
- MAX;
- WEB;
- PUSH в будущем.

---

# 41. Notification

Хранит факт отправки уведомления:
- channel;
- type;
- status;
- created_at;
- sent_at;
- related object;
- retry metadata.

---

# 42. Soft Delete (мягкое удаление)

Для исторически важных сущностей предпочтительно soft delete / archive.

Кандидаты:
- Business;
- PinterestAccount;
- Board;
- ContentSource;
- Strategy;
- Pin;
- Publication.

Использовать поля вида:
- archived_at;
- deleted_at;
- is_active.

Физическое удаление должно происходить только согласно retention policy и требованиям пользователя/закона.

---

# 43. Почему soft delete важен

Физическое удаление может разрушить:
- аналитику;
- историю решений;
- связи стратегии;
- аудит;
- объяснимость AI.

Поэтому удаление и архивация должны быть разными действиями.

---

# 44. UUID для внешних идентификаторов

Основные сущности должны иметь непредсказуемый внешний идентификатор.

Рекомендация:
- внутренний PK может быть bigint;
- внешний public_id — UUID.

В URL и внешних API использовать UUID / public_id, а не последовательные числовые ID.

Это не заменяет permissions, но уменьшает предсказуемость объектов и улучшает архитектурную стабильность.

---

# 45. Ownership

Каждая сущность должна иметь понятную цепочку ownership.

Пример:

Pin
→ ContentPlanItem
→ ContentPlan
→ Business
→ Workspace

Проверка доступа должна строиться по этой цепочке, а не по случайным user_id полям в каждой таблице.

---

# 46. Single Source of Truth

Для каждой сущности должен быть один источник истины.

Примеры:
- Pin status — PostgreSQL;
- Approval status — Approval;
- Strategy state — StrategyVersion;
- Publication state — Publication;
- Business memory — BusinessMemory;
- Telegram / MAX только инициируют backend-действия.

---

# 47. История вместо перезаписи

Ключевые сущности не должны терять значимые прошлые состояния.

Версионирование обязательно как минимум для:
- Strategy;
- ContentSource при значимых изменениях;
- Pin.

---

# 48. Границы модулей данных

Предварительное разделение:

accounts:
- User

workspaces:
- Workspace
- Membership

businesses:
- Business
- ContentSource
- ContentSourceVersion
- MediaAsset

pinterest:
- PinterestAccount
- Board

research:
- ResearchSnapshot
- Keyword
- KeywordCluster
- Trend
- Competitor
- CompetitorPin
- CompetitorBoard

strategies:
- Strategy
- StrategyVersion
- DecisionHistory

content:
- ContentPlan
- ContentPlanItem
- Pin
- PinVersion

approvals:
- Approval
- ApprovalRequest

publishing:
- Publication
- PublicationAttempt

analytics:
- PinAnalyticsDaily
- BoardAnalyticsDaily
- AccountAnalyticsDaily
- ContentSourceAnalyticsDaily
- KeywordAnalyticsDaily

strategist:
- BusinessMemory
- AIConversation
- AIJob

notifications:
- NotificationChannel
- Notification

---

# 49. Что не фиксируем преждевременно

Пока не фиксировать жёстко:
- точный список всех полей;
- индексы;
- partitioning;
- конкретные JSON schema;
- retention periods;
- все enum values;
- все analytics metrics.

Это уточняется при проектировании конкретного модуля.

Но базовые сущности и направления связей считаются архитектурно зафиксированными.

---

# 50. Главный критерий модели данных

Система должна уметь ответить на вопросы:

- кто владеет объектом;
- на основании каких данных он появился;
- какая версия использовалась;
- кто и когда изменил;
- кто одобрил;
- что было опубликовано;
- какой результат это дало;
- какая часть стратегии привела к результату.

> Если связь между стратегией, контентом, публикацией и аналитикой теряется — модель данных спроектирована неправильно.

---

# 51. Media lifecycle fields

Для MediaAsset предусмотреть поля, поддерживающие автоматическую очистку:

- lifecycle_type;
- is_temporary;
- expires_at;
- retained_reason;
- checksum;
- deleted_at;
- storage_backend;
- storage_key.

Временные MediaAsset должны автоматически удаляться по expires_at.

Retention (удержание файла) должно быть явным состоянием, а не отсутствием очистки.

---

# 52. Хранение медиа на старте

Для раннего production:

- пользовательские и сгенерированные медиа можно хранить на локальном persistent volume;
- медиа не хранится внутри Docker-контейнера;
- PostgreSQL хранит metadata и storage reference;
- доступ к файлам идёт через StorageService.

При росте система должна позволять перейти на S3-compatible storage без изменения доменной логики.


---

# 53. Pinterest API Data — ограничения хранения

Сущности, полученные из Pinterest API, нельзя автоматически считать обычными permanent records.

Для Pinterest-backed объектов необходимо различать:

- owned/internal data — данные, созданные внутри BOOSTKLIENT®;
- operational references — минимальные ID и служебные поля, необходимые для публикации/синхронизации;
- cached Pinterest data — временно полученные данные API;
- campaign analytics — данные, хранение которых отдельно допускается правилами Pinterest при наличии доступа.

До письменного подтверждения Pinterest:

- не хранить полные копии competitor Pin / Board как постоянную базу;
- не проектировать долгосрочный cache Pinterest Materials;
- использовать TTL для временного Pinterest cache;
- хранить только минимально необходимые operational identifiers, если это допустимо;
- отдельным полем фиксировать source = PINTEREST_API и fetched_at / expires_at.

Retention policy для Pinterest API data должна быть отдельной от собственных данных BOOSTKLIENT®.
