# BOOSTKLIENT® 3.0 — Pinterest API v5: возможности, доступ и ограничения

## Статус

Исследование официальных материалов Pinterest, актуальное на 23 сентября 2026 года.

Основные машинные и текстовые источники:

- Pinterest official OpenAPI: https://github.com/pinterest/api-description
- OpenAPI v5 JSON: https://raw.githubusercontent.com/pinterest/api-description/main/v5/openapi.json
- Developer docs: https://developers.pinterest.com/
- Developer Guidelines: https://policy.pinterest.com/en/developer-guidelines
- OAuth/scopes: https://developers.pinterest.com/docs/getting-started/set-up-authentication-and-authorization/
- Access tiers: https://developers.pinterest.com/docs/key-concepts/access-tiers/
- Rate limits: https://developers.pinterest.com/docs/reference/rate-limits/

Официальный OpenAPI на момент исследования сообщает Pinterest REST API **v5.28.0**.

В репозитории BOOSTKLIENT® добавлен скрипт `scripts/pinterest_api_parser.py`, который читает официальный OpenAPI JSON и генерирует актуальный inventory endpoint'ов, OAuth scopes, rate-limit категорий и Sandbox-признаков.

---

# 1. Ключевой вывод

Pinterest API v5 покрывает практически весь нужный нам спектр:

- OAuth и аккаунты;
- Business Access;
- Boards / Board Sections;
- Pins;
- image/video media upload;
- organic analytics;
- Trends;
- ad accounts;
- campaigns;
- ad groups;
- ads;
- targeting;
- audiences;
- customer lists;
- billing;
- catalogs;
- feeds;
- catalog items;
- product groups;
- shopping ads;
- conversion tracking;
- conversion quality;
- ads analytics/reporting;
- lead ads;
- advanced auction;
- business permissions and asset sharing.

Но существуют **политические/продуктовые ограничения Pinterest Developer Guidelines**, которые напрямую меняют архитектуру BOOSTKLIENT®. Они перечислены в разделе «Критичные ограничения».

---

# 2. Доступ приложения: Trial и Standard

После первоначального одобрения приложение получает **Trial access**.

Для продукта, который обслуживает реальных независимых пользователей, нужен **Standard access**.

Trial:

- чтение Pin/Board/Ads/Audiences/Catalogs доступно;
- создание ads/audiences/catalogs доступно;
- Pins и Boards, созданные через Trial, являются Sandbox-сущностями и видны только создателю;
- универсальный лимит — 1000 API-запросов в день на приложение.

Standard:

- реальные Pins/Boards;
- существенно увеличенные rate limits;
- предназначен для production-интеграций.

Для Standard Pinterest требует:

- уже одобренный Trial;
- соответствие Developer Guidelines;
- рабочую Privacy Policy;
- demo video;
- OAuth flow в demo;
- реальную Pinterest-интеграцию, а не wireframe.

Архитектурный вывод:

> Standard access является обязательным условием полноценного production BOOSTKLIENT®.

---

# 3. OAuth

Для SaaS BOOSTKLIENT® основной grant:

**Authorization Code Grant**

Pinterest прямо указывает его как вариант для web apps, работающих от имени множества независимых пользователей, и как единственный grant, предоставляющий полный диапазон возможностей API.

Client Credentials подходит для app-owner / machine-to-machine сценариев и не открывает все чувствительные endpoints.

---

# 4. Токены

Access token:

- срок жизни: 30 дней (2592000 секунд).

Continuous refresh token:

- срок жизни: 60 дней;
- может обновляться неограниченно, если обновление происходит до истечения;
- для приложений, созданных 25 сентября 2025 года или позже, continuous refresh используется автоматически.

Архитектура BOOSTKLIENT® должна:

- хранить expiry timestamps;
- обновлять токены заблаговременно;
- запускать refresh через Celery;
- предупреждать пользователя при невосстановимой авторизационной ошибке;
- уметь переводить PinterestAccount в REAUTH_REQUIRED.

---

# 5. OAuth scopes, которые нас интересуют

Официальная таблица Pinterest содержит:

## Advertising

- `ads:read`
- `ads:write`

Чтение и управление:

- ad accounts;
- campaigns;
- ad groups;
- ads;
- audiences;
- reporting и связанными рекламными объектами в зависимости от endpoint.

## Billing

- `billing:read`
- `billing:write`

Доступ к billing data / billing profile и разрешённым операциям.

## Business Access

- `biz_access:read`
- `biz_access:write`

Управление business access, members, partners, assets и permissions.

## Boards

- `boards:read`
- `boards:write`
- `boards:read_secret`
- `boards:write_secret`

## Catalogs

- `catalogs:read`
- `catalogs:write`

## Pins

- `pins:read`
- `pins:write`
- `pins:read_secret`
- `pins:write_secret`

## User Accounts

- `user_accounts:read`
- `user_accounts:write`

---

# 6. Важное решение по «полному scope»

BOOSTKLIENT® должен архитектурно поддерживать **весь необходимый спектр Pinterest API**, включая рекламный кабинет.

Но Pinterest рекомендует запрашивать минимально необходимые scopes.

Поэтому не запрашиваем все permissions у каждого пользователя в первом OAuth-окне.

Правильная модель:

## Core Pinterest

При подключении основной organic-функциональности:

- boards read/write;
- pins read/write;
- user account read;
- secret permissions только если пользователь включает работу с secret Boards/Pins.

## Ads module

При включении рекламного кабинета:

- ads read/write;
- billing read/write только для функций, которым это реально нужно;
- biz_access read/write для Business Manager функций.

## Commerce module

При включении каталога:

- catalogs read/write.

То есть:

> продукт поддерживает полный scope, но OAuth расширяется по мере включения пользователем конкретных модулей.

---

# 7. Organic: Boards и Pins

API поддерживает:

## Boards

- получить Board;
- создать;
- обновить;
- удалить;
- получить Pins Board.

## Board Sections

- list;
- create;
- update;
- delete;
- list Pins in section.

## Pins

- get;
- create;
- save;
- delete;
- image Pins;
- video Pins;
- product tagging.

Официальные entity limits:

- до 2000 Boards;
- до 200000 Pins для personal accounts (включая secret/group-board cases, описанные Pinterest).

---

# 8. Video Pins

Pinterest использует отдельный media upload flow:

1. register media upload;
2. получить media_id + upload URL;
3. загрузить video;
4. проверить processing status;
5. создать Pin с media_id и cover image.

После успешного создания Pinterest возвращает Pin ID.

Это хорошо ложится на нашу модель:

MediaAsset → PinVersion → Publication → external_pin_id.

---

# 9. Ad-only Pins

API позволяет создавать Pins специально для рекламы.

Ad-only Pin:

- не распространяется органически;
- добавляется в защищённую Ad-only Pins board;
- затем его ID можно использовать при создании рекламы.

Это нужно заложить в Content / Ads слой BOOSTKLIENT® как отдельный content purpose.

---

# 10. Claimed websites

API поддерживает управление claimed websites:

- verify website;
- get websites;
- unverify website;
- get verification code.

Claimed website важен потому что:

- расширяет organic analytics для контента, ведущего на домен;
- нужен для полноценной shopping/catalog functionality.

---

# 11. Organic analytics

Официальный API поддерживает:

- User Account Analytics;
- Top Pins Analytics;
- Top Video Pins Analytics;
- Single Pin Analytics;
- Multiple Pin Analytics;
- pin_metrics на Pin endpoints.

Особенности:

- до 90 дней lookback для user/Pins organic reporting;
- lifetime reporting для большинства Pins;
- top 50 Pins;
- multiple Pin analytics — до 100 Pin IDs за запрос.

Метрики включают, среди прочего:

- impressions;
- saves;
- engagements;
- pin clicks;
- outbound clicks;
- profile visits;
- follows;
- video views;
- play time;
- audience metrics.

Наша дневная агрегированная аналитика хорошо соответствует API, но правила хранения Pinterest data необходимо учитывать отдельно — см. критичные ограничения.

---

# 12. Trends API

Pinterest Trends API позволяет получать trending keywords.

Доступные возможности документации:

- region;
- trend type;
- interests;
- genders;
- ages;
- growth WoW;
- growth MoM;
- growth YoY;
- weekly normalized time series за прошлый год.

Ограничения:

- до 50 результатов;
- запрос строится для сегодняшней даты;
- нельзя запрашивать произвольную историческую дату;
- API ограниченнее, чем trends.pinterest.com.

Pinterest описывает Trends API как решение для agencies, Enterprise clients и partner platforms.

Это нужно отдельно подтвердить при выдаче доступа нашему приложению.

---

# 13. Related / Suggested Terms

API содержит операции:

- List suggested terms;
- List related terms.

Suggested terms:

- популярные запросы, начинающиеся с seed keyword.

Related terms:

- логически связанные запросы для одного или нескольких seed keywords.

Это важный официальный источник для Keyword Research BOOSTKLIENT®.

---

# 14. Advertising API

Pinterest API v5 поддерживает полноценное управление рекламой.

Основная иерархия:

Ad Account
↓
Campaign
↓
Ad Group
↓
Ad

API позволяет:

- читать ad accounts;
- создавать ad accounts в поддерживаемых сценариях;
- создавать/обновлять campaigns;
- создавать/обновлять ad groups;
- создавать/управлять ads;
- задавать objectives;
- targeting;
- bids;
- status;
- creative.

Часть первоначальной настройки рекламодателя всё равно может потребовать перехода в Pinterest UI.

---

# 15. Business Access

Для рекламного кабинета это ключевой модуль.

API поддерживает:

- businesses;
- members;
- partners;
- invites;
- access requests;
- asset permissions;
- business roles;
- ad account/profile sharing;
- revoke membership / partnership.

Pinterest permissions включают отдельные права:

- Admin;
- Analyst;
- Audience;
- Finance;
- Campaign;
- Catalogs;
- Publisher.

BOOSTKLIENT® должен хранить не только scopes токена, но и реальные asset permissions пользователя.

---

# 16. Targeting

Targeting задаётся на уровне Ad Group.

API поддерживает:

- audiences;
- interests;
- keyword targeting;
- demographics;
- geo/location;
- app/device;
- age ranges;
- shopping retargeting;
- targeting strategy.

Документация 2026 отдельно предупреждает о deprecation AGE_BUCKET и переходе к MINIMUM_AGE / MAXIMUM_AGE.

Не хардкодить targeting enums — получать/версионировать согласно API schema.

---

# 17. Audiences

Поддерживаются:

- Customer List;
- Engagement;
- Site Visitor;
- Actalike;
- broad/open targeting;
- Persona (создаётся Pinterest sales team, не через обычный API).

Customer-list / seed audience требует минимум 100 members.

Audience processing может занимать 48–72 часа.

Архитектура:

AudienceJob / external_audience_id / status polling.

---

# 18. Audience Insights

API позволяет получать aggregated insights:

- YOUR_TOTAL_AUDIENCE;
- YOUR_ENGAGED_AUDIENCE;
- PINTEREST_TOTAL_AUDIENCE.

Данные включают categories/interests и affinity.

Для advertiser-level endpoint нужен ad_account_id.

---

# 19. Catalogs / Shopping

API поддерживает:

- catalogs;
- feeds;
- feed processing;
- items;
- batch operations;
- item issues;
- product groups;
- product group promotions;
- diagnostic reports;
- shopping ads.

Feed ingestion:

- обычный feed обновляется Pinterest примерно каждые 24–48 часов;
- можно вручную trigger ingestion с ограничениями;
- для часто меняющихся товаров доступны batch item operations.

Для полного Shopping необходим claimed domain.

---

# 20. Shopping Ads

Поток:

1. Catalog;
2. Product items;
3. Product groups;
4. Campaign;
5. Ad Group;
6. Product group promotion.

Catalog sales / shopping architecture должна быть отдельным функциональным модулем, а не частью обычной organic Pin публикации.

---

# 21. Conversions API

Conversions API поддерживает website/app/offline conversion events.

Можно использовать вместе с Pinterest Tag.

Pinterest предоставляет отдельный Conversion Access Token.

В rate-limit документации Pinterest рекомендует conversion token для sending conversion events и указывает, что он позволяет отправлять conversion-tracking events без обычного OAuth лимита этой категории.

Нужно поддержать:

- event validation;
- deduplication;
- event_id;
- consent;
- hashing необходимых identifiers;
- retries;
- Event Quality Score.

---

# 22. Event Quality Score

API позволяет получать Event Quality Score (EQS) для доступных ad accounts.

Нужен `ads:read`.

Это полезно для раздела диагностики рекламного tracking.

---

# 23. Ads reporting

Pinterest сообщает о 90+ metrics для organic + ads.

Ads reporting поддерживает:

## Synchronous

Для небольших/быстрых отчётов:

- ad account;
- campaign;
- ad group;
- product group;
- ad.

## Asynchronous

Для:

- больших объёмов;
- исторических отчётов;
- широкого диапазона дат.

Для BOOSTKLIENT®:

- небольшие dashboard widgets → sync;
- регулярная большая аналитика → async + Celery polling.

---

# 24. Lead Ads

Pinterest Lead Ads API поддерживает:

- subscriptions;
- encrypted lead transfer;
- testing API;
- webhook URL;
- lead form-specific subscription.

На момент исследования требуется доступ к Lead Ads beta через Pinterest account team.

Поэтому модуль должен быть feature-flagged и включаться только при подтверждённом доступе.

---

# 25. Advanced Auction

Официальный API/OpenAPI включает Advanced Auction operations и отдельные rate-limit категории:

- advanced_auction_read;
- advanced_auction_write.

Этот функционал включаем в общий API adapter, но UI строим только если feature реально доступна конкретному advertiser.

---

# 26. Billing

Официальный OAuth поддерживает:

- billing:read;
- billing:write.

Кроме OAuth scope, реальный доступ ограничивается Business permissions пользователя (Finance/Admin и т.п.).

Нельзя считать наличие scope достаточным разрешением.

---

# 27. Rate Limits

Pinterest применяет два уровня.

## Universal

Trial:
- 1000 requests/day для всех API requests.

Standard:
- 100 requests/second per user per app для всех API requests.

## Category limits для Standard

На момент исследования:

- ads_analytics — 300/min/user/app;
- ads_conversions — 120000/min/ad account/app при standard OAuth;
- ads_read — 1000/min/user/app;
- ads_write — 400/min/user/app;
- advanced_auction_read — 50/min/user/app;
- advanced_auction_write — 25/min/user/app;
- catalogs_read — 100/min/user/app;
- catalogs_write — 100/min/user/app;
- org_analytics — 60/min/user/app;
- org_read — 1000/min/user/app;
- org_write — 100/min/user/app;
- trends_read — 60/min/user/app.

Pinterest прямо предупреждает, что rate limits могут меняться без уведомления.

Поэтому rate limits нельзя хардкодить как вечные значения.

Нужно читать response headers:

- x-ratelimit-limit;
- x-ratelimit-remaining;
- x-ratelimit-reset.

---

# 28. Rate-limit архитектура BOOSTKLIENT®

Для каждого PinterestAccount / app user:

- rate-limit state;
- per-category limiter;
- retry-after/backoff;
- Celery queue routing;
- jitter;
- monitoring.

Critical publication queue не должна «стрелять» 150 requests одновременно.

---

# 29. Sandbox

Pinterest предоставляет Sandbox и test tokens.

Использовать для:

- OAuth/testing;
- Pins/Boards;
- ads;
- catalogs/shopping;
- supported API flows.

Вся интеграционная разработка должна сначала проходить Sandbox, если endpoint его поддерживает.

Парсер OpenAPI сохраняет поле `x-sandbox` каждого endpoint, поэтому мы можем автоматически строить список поддерживаемых Sandbox операций.

---

# 30. КРИТИЧНО: Pinterest Developer Guidelines — хранение данных

Официальные Developer Guidelines говорят:

> За исключением campaign analytics своего аккаунта или другого аккаунта, владелец которого явно дал доступ, нельзя хранить информацию, полученную через Pinterest Materials/API; вместо этого нужно запрашивать её через API каждый раз.

Это **критичный архитектурный риск** для нашей текущей модели.

Следствие:

Нельзя автоматически считать, что мы вправе постоянно хранить в PostgreSQL:

- чужие Pinterest Pins;
- Boards;
- competitor objects;
- audience/API data;
- Pinterest metadata;

если эти данные были получены именно через Pinterest Materials/API.

До production необходимо получить от Pinterest письменное разъяснение/разрешение для необходимых operational data, либо проектировать API-backed данные как live/ephemeral.

Наш собственный контент ДО отправки в Pinterest, пользовательские исходники, стратегии BOOSTKLIENT® и внутренние данные приложения — это отдельная категория и не являются автоматически Pinterest API data.

---

# 31. КРИТИЧНО: автоматизация публикаций

Pinterest прямо разрешает content marketing tools и Pin schedulers.

Но Developer Guidelines запрещают функции, которые автоматически инициируют действия без того, чтобы пользователь специально рассмотрел каждое действие.

Pinterest приводит прямой пример:

> для scheduled Pin publishing конечный пользователь должен выбрать каждый Pin, который будет опубликован.

Следствие для BOOSTKLIENT®:

- автоматическая генерация допустима как продуктовый класс;
- автоматическая проверка допустима;
- расписание допустимо;
- **каждый Pin перед публикацией пользователь одобряет отдельным действием** независимо от возможных разрешений Pinterest: это обязательное правило BOOSTKLIENT®.

Наш Telegram / MAX Approval Flow становится не просто UX-функцией, а важной частью compliance.

Автоматическое одобрение пинов запрещено правилом продукта. Проверки соответствия требованиям не предсказывают результат в Pinterest и не заменяют отдельного одобрения пользователем.

---

# 32. КРИТИЧНО: bulk approval

Формулировка Pinterest требует, чтобы пользователь выбирал каждый Pin.

Правило BOOSTKLIENT®: показать конкретную версию Pin, получить отдельное действие её одобрения и сохранить пользователя, версию и время.

Кнопки «Одобрить все» и общее одобрение выбранного набора не предусматриваются. Подборки служат для просмотра; по расписанию публикуются только отдельно одобренные пины.

Этот процесс нужно описать Pinterest при Standard access review. Разрешение платформы не отменяет правило отдельного одобрения.

---

# 33. КРИТИЧНО: competitor research

Developer Guidelines запрещают:

- platform insights;
- benchmarking;
- competitor research features;

если нет **explicit written authorization from Pinterest**.

Pinterest прямо указывает, что email-разрешения достаточно.

Следствие:

Модуль «Конкуренты» в текущем плане BOOSTKLIENT® нельзя запускать на Pinterest Materials/API без предварительного письменного разрешения Pinterest.

До получения разрешения:

- feature flag OFF;
- не обещать эту функцию на публичном лендинге как доступную;
- не использовать scraping Pinterest;
- research можно строить на разрешённых собственных/внешних источниках, если это не нарушает правила этих источников.

---

# 34. КРИТИЧНО: scraping

Автоматизированный scraping/data extraction Pinterest запрещён, кроме случаев, явно разрешённых Pinterest.

Следствие:

> BOOSTKLIENT® не должен использовать HTML scraping Pinterest как запасной способ получить недоступные API данные.

Использовать только официально разрешённые API / официальные источники.

---

# 35. КРИТИЧНО: Pinterest data и AI training

Developer Guidelines запрещают использовать Pinterest Materials для:

- training;
- fine-tuning;
- улучшения;
- разработки ML/AI models;

без явного разрешения Pinterest.

Следствие:

BOOSTKLIENT® не обучает и не fine-tune модели на Pinterest API data.

Для inference (разовый анализ моделью) текст правила не даёт такого же прямого запрета, но необходимо:

- соблюдать data-storage rules;
- минимизировать передаваемые данные;
- проверить provider data policy;
- при Standard review раскрыть AI use case Pinterest;
- запросить письменное подтверждение для спорных AI-сценариев.

---

# 36. КРИТИЧНО: рекламные данные

Если BOOSTKLIENT® использует Pinterest API для advertising service:

- применяются Ad Data Terms;
- Pinterest API data должна использоваться для обслуживания и оценки рекламы на Pinterest;
- нельзя использовать её для targeting людей вне Pinterest;
- собственная комиссия BOOSTKLIENT® и Pinterest ad fees должны показываться отдельно;
- если показываем last-click attribution, Pinterest требует рядом равнозначно показывать multi-touch attribution согласно Developer Guidelines.

Это должно быть учтено в Ads Analytics UI и billing UI.

---

# 37. КРИТИЧНО: UI Pinterest

Нельзя копировать/имитировать визуальный дизайн, layout или UX Pinterest без явного разрешения.

Мы можем показывать собственный интерфейс и доказательства работы приложения, но не строить BOOSTKLIENT® как визуальный клон Pinterest.

---

# 38. Что это меняет в текущей архитектуре

## Approval

Сделать обязательным production barrier:

GENERATED
→ VALIDATED
→ WAITING_USER_SELECTION
→ USER_APPROVED
→ QUEUED
→ PUBLISHED

## Autopilot

Автопилот может:

- исследовать разрешённые данные;
- создавать контент;
- планировать;
- проверять;
- рекомендовать;
- подготавливать очередь.

Каждый Pin требует отдельного одобрения пользователем конкретной версии. Разрешения Pinterest на ограниченные функции не отменяют это правило продукта.

## Competitors

Feature gate до письменного authorization.

## Pinterest API Cache

Не проектировать долгосрочную локальную копию Pinterest API как само собой разумеющуюся.

## AI

Не train/fine-tune на Pinterest Materials.

---

# 39. Что надо получить у Pinterest письменно

До коммерческого production желательно заранее отправить Pinterest конкретный use-case документ и получить ответы на следующие вопросы:

1. Разрешён ли наш approval flow через web / Telegram / MAX?
2. Что именно Pinterest считает «user must choose each Pin»?
3. Соответствует ли требованиям отдельное одобрение каждой версии Pin с последующей публикацией по расписанию без изменения одобренного контента?
4. Какие operational identifiers/API metadata разрешено хранить для scheduling, retry и analytics?
5. Можно ли хранить external Pin ID и Board ID как operational references?
6. Какой срок допустим для cache данных API?
7. Разрешён ли competitor research для нашего продукта?
8. Разрешено ли использовать API data как transient LLM inference context без training/fine-tuning?
9. Доступен ли Trends API нашему типу Standard app?
10. Какие Ads/Business/Billing permissions потребуют дополнительного review?
11. Какие Lead Ads / Advanced Auction capabilities доступны нам?
12. Какие ограничения Pinterest хочет видеть в нашем high-volume scheduler?

---

# 40. Pinterest API adapter

В коде не вызывать Pinterest SDK/API напрямую из business services.

Использовать:

`PinterestClient`

и функциональные adapters:

- OrganicPinterestService;
- PinterestAdsService;
- PinterestCatalogService;
- PinterestAnalyticsService;
- PinterestTrendsService;
- PinterestBusinessAccessService;
- PinterestConversionsService.

Это позволит:

- централизовать OAuth;
- rate limits;
- retry;
- logging;
- policy gates;
- Sandbox/Production;
- API version changes.

---

# 41. Машинный parser / inventory

Файл:

`scripts/pinterest_api_parser.py`

Источник:

официальный MIT-licensed OpenAPI Pinterest.

Он извлекает:

- API version;
- endpoint;
- HTTP method;
- operationId;
- tags;
- OAuth scopes;
- security schemes;
- rate-limit category;
- Sandbox support.

Результат:

- `docs/generated/pinterest_api_inventory.json`
- `docs/generated/pinterest_api_inventory.md`

Это позволяет регулярно проверять изменения официального API без ручного обхода сотен endpoint страниц.

---

# 42. Обновление inventory

Рекомендуемый процесс:

- запускать parser вручную при начале интеграционной разработки;
- перед крупным релизом;
- после уведомления Pinterest об изменении API;
- позднее можно добавить scheduled CI job.

При изменении OpenAPI:

- сохранять source SHA-256;
- сравнивать generated inventory;
- проверять удалённые/добавленные endpoints;
- scopes;
- rate-limit categories;
- Sandbox status.

Автоматическое применение изменений API в production запрещено.

---

# 43. Архитектурный итог

BOOSTKLIENT® может развиваться в сторону полноценной Pinterest ecosystem, включая:

- organic;
- automation with explicit user approval;
- analytics;
- research через официально разрешённые API;
- trends;
- catalogs/shopping;
- advertising;
- audiences;
- conversions;
- Business Manager;
- billing;
- Lead Ads / Advanced Auction при доступе.

Но Pinterest compliance должен быть частью архитектуры, а не юридической проверкой «потом».

Главное правило:

> Если Pinterest API технически позволяет действие, это ещё не означает, что Developer Guidelines разрешают продукту выполнять это действие в любой UX-модели.
