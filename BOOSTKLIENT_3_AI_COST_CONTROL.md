# BOOSTKLIENT® 3.0 — AI Cost Control

## Статус документа

Живой документ.

Цель: держать себестоимость AI-функций под контролем и не допустить ситуации, когда расходы на модели съедают маржу продукта.

Главный принцип:
> Для каждой задачи используется минимально достаточная модель по качеству, скорости и цене.

Второй принцип:
> Бизнес-логика не привязана к конкретному AI-провайдеру или одной модели.

---

# 1. Model Router (маршрутизатор моделей)

Все AI-задачи проходят через Model Router.

Он выбирает:
- provider;
- model;
- model class;
- fallback;
- максимальный budget;
- timeout;
- retry policy.

Выбор зависит от:
- типа задачи;
- требуемого качества;
- срочности;
- тарифа пользователя;
- текущей доступности provider;
- стоимости;
- контекстного размера.

---

# 2. Классы моделей

Минимальный набор классов:

## CHEAP / FAST
Для дешёвых и массовых операций.

Примеры:
- классификация;
- извлечение признаков;
- короткий alt text;
- нормализация;
- простой rewrite;
- keyword labeling.

## STANDARD
Для основной генерации.

Примеры:
- Pin title;
- Pin description;
- CTA;
- short recommendations;
- content variants.

## STRONG
Для сложного reasoning и стратегии.

Примеры:
- Strategy 30/60/90;
- анализ ниши;
- перестройка стратегии;
- сложная аналитика;
- multi-step recommendations.

## VISION
Для работы с изображениями.

Примеры:
- image quality check;
- content relevance;
- visual compliance;
- duplicate / similarity assistance.

## EMBEDDING
Для embeddings.

Примеры:
- RAG;
- semantic search;
- duplicate detection;
- clustering.

---

# 3. Task → Model Class

Каждая AI-функция должна иметь заранее заданный model class.

Примеры:
- classify_keyword() → CHEAP;
- generate_alt_text() → CHEAP;
- generate_pin_text() → STANDARD;
- rewrite_pin() → STANDARD;
- build_strategy() → STRONG;
- rebuild_strategy() → STRONG;
- check_image_quality() → VISION;
- create_embedding() → EMBEDDING.

---

# 4. Конкретные модели не хардкодятся

В бизнес-коде нельзя писать:
`model='...'`

Функция запрашивает класс модели, а provider configuration определяет конкретную модель.

Это позволяет:
- менять provider;
- менять модель;
- снижать цену;
- улучшать качество;
- делать A/B tests;
- не переписывать бизнес-логику.

---

# 5. Fallback

Fallback должен быть в том же классе стоимости/качества, если возможно.

Пример:
- primary STANDARD недоступна;
- использовать secondary STANDARD;
- не переключаться автоматически на самую дорогую STRONG модель.

Любой fallback логируется.

---

# 6. Escalation

Дорогая модель используется только если:
- задача изначально STRONG;
- более дешёвая модель не прошла validation;
- confidence ниже порога;
- пользовательский тариф это допускает;
- retry/escalation policy разрешает повышение класса.

Автоматическая escalation должна иметь максимум попыток.

---

# 7. Тарифы и AI Quality

Model Router может учитывать subscription plan.

Пример:

Basic:
- CHEAP + STANDARD;
- STRONG только для стратегии.

Pro:
- STANDARD чаще;
- STRONG для сложных рекомендаций;
- повышенные AI budgets.

Но:
> Тариф не должен менять бизнес-правила или безопасность. Только качество/лимиты/скорость AI.

---

# 8. Cost Budget на операцию

Каждый тип задачи должен иметь внутренний максимальный cost budget.

Примеры классов:
- low;
- medium;
- high.

Конкретные денежные значения задаются конфигурацией и могут меняться без изменения кода.

Если budget превышен:
- остановить дополнительные попытки;
- вернуть REQUIRES_REVIEW;
- либо использовать более дешёвую стратегию.

---

# 9. Cost Tracking

Для каждого AI-вызова хранить минимум:
- provider;
- model;
- model_class;
- task_type;
- input_tokens;
- output_tokens;
- cached_tokens, если provider поддерживает;
- latency;
- estimated_cost;
- user_id;
- workspace_id;
- business_id;
- ai_job_id;
- retry_number;
- fallback_used;
- timestamp.

---

# 10. Основные метрики

Обязательные метрики:

## AI Cost per Pin
Средняя AI-себестоимость одного готового Pin.

## AI Cost per Strategy
Стоимость построения / перестройки стратегии.

## AI Cost per Active User
AI-затраты на активного пользователя в месяц.

## AI Cost per Workspace
Расходы на Workspace.

## AI Cost / Revenue
Доля выручки тарифа, которую съедает AI.

## Retry Cost
Сколько денег уходит на повторы.

## Fallback Cost
Сколько денег появляется из-за резервных моделей.

---

# 11. MAX_GENERATION_ATTEMPTS

Нельзя бесконечно повторять генерацию.

Для каждого workflow задаётся предел.

Пример:
- generation attempt 1;
- validation fail;
- generation attempt 2;
- validation fail;
- generation attempt 3;
- REQUIRES_REVIEW.

Не запускать бесконечный цикл AI → validate → regenerate.

---

# 12. Context Budget

Каждая задача должна иметь предел контекста.

Context Builder обязан:
- исключать ненужную историю;
- удалять дубликаты;
- использовать summary;
- отдавать только релевантные данные;
- не прикладывать весь аккаунт без необходимости.

Это одновременно:
- быстрее;
- дешевле;
- безопаснее.

---

# 13. Chat History

Не отправлять всю историю чата при каждом запросе.

Использовать:
- recent window;
- structured memory;
- summaries;
- relevant decision history.

---

# 14. Кэширование

Повторный AI-вызов запрещён, если корректный результат уже существует и данные не изменились.

Кандидаты на кэш:
- анализ сайта;
- classification;
- keyword clustering;
- embeddings;
- public knowledge summaries;
- stable RAG results.

Кэш должен иметь:
- input hash;
- model/version;
- created_at;
- expires_at;
- owner scope.

---

# 15. Embeddings

Embeddings не пересчитываются без причины.

Пересчитать только если:
- контент изменился;
- embedding model изменился;
- schema/version изменились;
- старый embedding invalid.

---

# 16. AI не используется там, где подходит обычный код

Нельзя использовать LLM для:
- арифметики;
- простых SQL-запросов;
- проверки expiry даты;
- permission checks;
- сортировки;
- фильтрации;
- статусов;
- deterministic rules.

Если задачу можно надёжно решить Python/SQL — использовать Python/SQL.

---

# 17. Batch Processing

Где возможно, объединять однотипные дешёвые операции в batch.

Но batch не должен:
- ухудшать трассируемость;
- смешивать данные разных Workspace;
- создавать privacy риск;
- ломать retry/idempotency.

---

# 18. Cost Alerts

Обязательные alerts:
- AI Cost per Pin вырос выше порога;
- Workspace расходует необычно много;
- retry cost резко вырос;
- fallback rate вырос;
- STRONG model usage выше нормы;
- daily AI spend превысил budget;
- provider price/config изменилась.

---

# 19. Anomaly Detection

Система должна обнаруживать аномалии:
- внезапно вырос input context;
- один workflow стал делать больше вызовов;
- один пользователь генерирует аномальный объём;
- loop повторных попыток;
- модель стала возвращать больше invalid outputs.

---

# 20. Billing Safety

Внутренний AI budget и пользовательский тариф — разные сущности.

Пользователь не должен автоматически получать неограниченные дорогие AI-вызовы только потому, что UI позволяет нажать кнопку.

Backend обязан проверять:
- plan limits;
- daily/monthly limits;
- AI budget;
- abuse limits.

---

# 21. Cost Forecast

Перед запуском нового AI workflow нужно оценить:
- calls per user;
- tokens per call;
- retries;
- daily volume;
- monthly volume;
- worst-case cost;
- expected cost.

Новая AI-функция без cost estimate не считается готовой к production.

---

# 22. A/B Model Evaluation

При смене модели сравнивать:
- quality;
- latency;
- cost;
- failure rate;
- validation pass rate;
- user outcome.

Не выбирать модель только потому, что она дешевле или новее.

---

# 23. Provider Price Registry

Стоимость моделей хранится централизованно.

Нельзя размазывать цену токена по коду.

Нужен provider/model price registry:
- input price;
- output price;
- cached input price;
- image/vision price;
- embedding price;
- effective date.

---

# 24. Provider Price Changes

Цена provider может измениться.

Поэтому:
- цены обновляются конфигурацией;
- историческая стоимость фиксируется на момент вызова;
- новый прайс не должен пересчитывать старую финансовую историю.

---

# 25. Cost Dashboard

Администратор должен видеть:
- AI spend today;
- AI spend month;
- by provider;
- by model;
- by task;
- by plan;
- by Workspace;
- per Pin;
- retries;
- fallbacks;
- top expensive workflows.

---

# 26. MVP

Для MVP обязательно:
- Model Router;
- минимум два класса текстовых моделей;
- отдельные VISION и EMBEDDING классы при их использовании;
- cost tracking;
- MAX_GENERATION_ATTEMPTS;
- Context Builder;
- per-task budget;
- AI cost alerts;
- admin cost report.

---

# 27. Главный критерий

> AI-функция считается production-ready только если мы понимаем её качество, скорость и себестоимость.

---

# 28. Второй критерий

> Удорожание конкретного AI-провайдера или модели не должно заставлять переписывать BOOSTKLIENT®.