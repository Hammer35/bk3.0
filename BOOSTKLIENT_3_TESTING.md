# BOOSTKLIENT® 3.0 — стратегия тестирования

## Статус документа

Живой документ.

Цель: зафиксировать обязательную стратегию тестирования BOOSTKLIENT® 3.0 так, чтобы критичные бизнес-сценарии, безопасность и отказоустойчивость проверялись автоматически до production.

Главный принцип:
> Тестирование — часть архитектуры, а не финальная стадия перед релизом.

Второй принцип:
> Важнее покрыть критичные бизнес-сценарии, чем гнаться за красивым процентом coverage.

---

# 1. Уровни тестирования

Обязательные уровни:
- Unit Tests (модульные тесты);
- Integration Tests (интеграционные тесты);
- Contract / API Tests (тесты контрактов внешних API);
- End-to-End / E2E (сквозные тесты);
- Security Tests (тесты безопасности);
- Failure / Recovery Tests (тесты отказов и восстановления).

---

# 2. Unit Tests

Проверяют отдельную функцию, сервис или правило в изоляции.

Примеры:
- расчёт лимита;
- переход статуса;
- TTL медиа;
- проверка Approval конкретной версии и отдельного действия пользователя для каждого пина;
- выбор модели ИИ;
- rate-limit backoff;
- валидация Business rules.

Unit tests должны быть:
- быстрыми;
- независимыми;
- без реальных внешних API;
- пригодными для запуска на каждом commit.

---

# 3. Integration Tests

Проверяют связку нескольких внутренних компонентов.

Примеры:
- Django + PostgreSQL;
- Celery + Valkey;
- Strategy → ContentPlan → Pin;
- Approval → Publication;
- Business → PinterestAccount permissions;
- StorageService + MediaAsset.

---

# 4. Contract / API Tests

Нужны для интеграций, где внешний provider может изменить формат ответа.

Приоритетные интеграции:
- Pinterest API;
- OpenAI / DeepSeek / другие LLM;
- Telegram;
- MAX;
- email provider;
- marketplace integrations.

Contract test должен фиксировать:
- обязательные поля;
- типы данных;
- ожидаемые ошибки;
- rate-limit поведение;
- status codes;
- versioned schemas.

---

# 5. E2E Tests

Проверяют реальные пользовательские сценарии от начала до конца.

Ключевой E2E:

регистрация
→ Workspace
→ Business
→ подключение Pinterest
→ стратегия
→ ContentPlan
→ Pin
→ Approval
→ Scheduler
→ Publication
→ Analytics

Для MVP достаточно небольшого набора критичных E2E, а не сотен UI-тестов.

---

# 6. Security Tests

Обязательные сценарии:
- user A не видит Business user B;
- подмена UUID не даёт доступ;
- permissions проверяются на backend;
- CSRF;
- XSS;
- SSRF;
- upload validation;
- OAuth state/ownership;
- AI tool permissions;
- prompt injection boundaries;
- webhook replay;
- Telegram / MAX approval ownership;
- запрет одобрения пина ИИ или системной задачей;
- запрет общего одобрения пакета вместо отдельных действий;
- новая версия пина требует нового одобрения;
- разрешение Pinterest или feature flag не отменяет отдельное одобрение пользователя.

---

# 7. Failure / Recovery Tests

BOOSTKLIENT® должен тестироваться не только в идеальном состоянии.

Обязательные сценарии:
- worker падает во время публикации;
- Valkey временно недоступен;
- Pinterest API возвращает 429;
- Pinterest API возвращает 500;
- LLM timeout;
- LLM invalid structured output;
- PostgreSQL transaction rollback;
- duplicate task delivery;
- publication retry;
- зависший PUBLISHING;
- media storage временно недоступен.

Результат должен быть:
- без дублей;
- без потери статуса;
- с корректным retry;
- с понятным FAILED / recovery state.

---

# 8. Никаких реальных внешних API в обычных тестах

Обычные automated tests не должны:
- публиковать реальные Pins;
- тратить деньги AI API;
- создавать рекламу;
- отправлять реальные Telegram / MAX сообщения;
- менять реальные внешние данные.

Использовать:
- mocks;
- fakes;
- recorded fixtures, если это допустимо;
- local test doubles.

---

# 9. Test Network Guard

Из BOOSTKLIENT® 2.0 переиспользовать идею network guard.

По умолчанию тесты блокируют внешнюю сеть.

Внешний network access разрешается только явно для специальных sandbox/integration suites.

Это защищает от:
- случайной публикации;
- случайных затрат;
- нестабильности тестов;
- зависимости CI от интернета.

---

# 10. Pinterest Sandbox Tests

Реальный Pinterest Sandbox используется отдельно от обычного CI.

Проверять:
- OAuth;
- Boards;
- Pins;
- video upload;
- scopes;
- rate limits;
- error handling;
- publication flow.

Sandbox tests не запускаются автоматически на каждый commit.

---

# 11. AI Tests

Разделить AI-тесты на уровни.

## Deterministic tests
- schema validation;
- tool selection constraints;
- permission gates;
- context filtering;
- provider adapter.

## Model behavior tests
- expected structured output;
- regression prompts;
- fallback;
- invalid response handling.

Нельзя требовать от generative model побитно одинакового текста.

Проверять структуру, правила и допустимое поведение.

На фиксированных примерах бизнесов проверять соответствие рекомендаций исходным данным и ограничениям, наличие источников фактических утверждений, обозначение гипотез и честное сообщение о недостатке данных. Фиксировать необходимые ручные исправления как показатель качества рекомендаций.

Не оценивать качество стратегии по предполагаемому знанию алгоритмов Pinterest и не требовать гарантированных показов или переходов. Аналитические ответы должны отличать наблюдаемые метрики от недоказанных причин результата.

---

# 12. Critical Test Suite

Без прохождения этих тестов merge запрещён.

Обязательные области:
- ownership;
- permissions;
- Approval;
- double publish protection;
- idempotency;
- OAuth;
- token refresh;
- scheduler;
- publication recovery;
- billing;
- limits;
- AI tool authorization;
- migration/importer;
- Pinterest policy gates.

---

# 13. Coverage

Не ставить 100% code coverage как самоцель.

Ориентир общего покрытия может быть 70–80%, если это помогает контролю качества.

Но обязательное требование:
> 100% критичных бизнес-сценариев должны иметь тест.

Coverage критичных модулей должен быть выше среднего по проекту.

---

# 14. Regression Tests

Каждый найденный production bug должен превращаться в regression test.

Правило:
1. воспроизвести баг тестом;
2. убедиться, что тест падает;
3. исправить код;
4. убедиться, что тест проходит;
5. оставить тест навсегда.

---

# 15. Тесты миграции 2.0 → 3.0

Importer должен иметь отдельные тесты:
- dry-run;
- повторный запуск;
- duplicate protection;
- invalid legacy data;
- ownership mapping;
- User → Workspace / Business mapping;
- token migration;
- skip prohibited Pinterest data;
- rollback batch;
- import report.

---

# 16. Fixtures / Factories

Тестовые данные создаются через factories / fixtures.

Нельзя строить тесты на случайных production dump без необходимости.

Типовые factory:
- User;
- Workspace;
- Business;
- PinterestAccount;
- Board;
- Strategy;
- Pin;
- Approval;
- Publication.

---

# 17. Test Isolation

Каждый тест должен быть независимым.

Запрещено:
- зависеть от порядка запуска;
- использовать общий mutable state;
- зависеть от реального времени без контроля;
- зависеть от внешней сети.

Для времени использовать controllable clock / freeze time там, где нужно.

---

# 18. Database Tests

Проверять:
- transactions;
- constraints;
- unique indexes;
- select_for_update;
- concurrency scenarios;
- soft delete;
- ownership filters;
- migrations.

---

# 19. Celery Tests

Проверять:
- routing по очередям;
- retry;
- backoff;
- acks/recovery;
- idempotency;
- task timeout;
- task cancellation;
- stuck state recovery.

Часть тестов можно выполнять eager mode, но production-like integration tests должны проверять настоящий broker flow.

---

# 20. Performance Tests

Не нужны тяжёлые load tests на каждый commit.

Но перед крупным релизом проверить:
- массовую генерацию;
- публикацию batch;
- очередь approvals;
- большие таблицы;
- analytics;
- scheduler under load.

---

# 21. Smoke Tests

После deployment на staging/production запускать быстрый smoke suite:
- homepage/admin health;
- login;
- DB;
- Valkey;
- Celery;
- key API endpoints;
- static files;
- basic HTMX;
- AI provider availability;
- Pinterest connection health.

---

# 22. CI уровни

## На каждый commit / pull request
- unit;
- быстрые integration;
- critical security;
- lint/check;
- Django check;
- migration check.

## Перед merge в main
- полный critical suite;
- расширенные integration;
- contract tests с mocks;
- importer tests;
- dependency/security checks.

## Перед production
- staging E2E;
- Pinterest Sandbox;
- Celery/Valkey recovery;
- smoke;
- performance sanity;
- rollback test для критичных релизов.

---

# 23. Flaky Tests

Нестабильные тесты нельзя просто перезапускать до зелёного статуса.

Flaky test считается дефектом тестовой инфраструктуры.

Нужно:
- найти причину;
- исправить;
- либо временно quarantine с issue и сроком исправления.

---

# 24. Test Naming

Название теста должно описывать бизнес-сценарий.

Хорошо:
`test_publication_is_not_repeated_when_worker_retries`

Плохо:
`test_case_17`

---

# 25. Главный критерий

> Если ошибка может привести к потере данных, чужому доступу, неправильной публикации, двойной операции или расходу денег — этот сценарий обязан иметь автоматический тест.

---

# 26. Второй критерий

> Тестовая среда не имеет права случайно воздействовать на реальные внешние сервисы.