# AGENTS-DETAIL.md — BOOSTKLIENT® 3.0

Подробности по подсистемам. Базовые команды, проверка и соглашения — в `AGENTS.md`.

## Приложения и слои

| App | Что владеет |
|---|---|
| `apps/core` | `BaseModel` (abstract: `public_id`, timestamps), лендинг, дашборд, health, `ratelimit.py` |
| `apps/accounts` | регистрация/вход, `InterfacePreference` (масштаб шрифта), context processor |
| `apps/workspaces` | tenancy: `Workspace`, `Membership`, `Role`, онбординг, RBAC-гейт |
| `apps/businesses` | CRUD профиля бизнеса |
| `apps/knowledge` | RAG: `KnowledgeDocument`, `KnowledgeChunk`, чанкинг, эмбеддеры, `index_knowledge` |
| `apps/pinterest` | OAuth v5, шифрование и обновление токенов, синк, `strategist_tools.py` (LLM-инструмент: **34** allowlisted read-ресурса) |
| `apps/strategist` | ИИ-стратег, самое крупное приложение (~4.4k LOC) |

Слоистость держится соглашением: views → services (записи) / selectors (чтения) → models. `apps/workspaces/permissions.py::can_manage_businesses` — единственная точка входа для RBAC, через неё проходят все записи в pinterest и business. Изоляция арендаторов покрыта тестами: чужие workspace дают 404, а не 403.

## Стратег: лестница роутинга

`apps/strategist/services.py::respond_to_message` пробует детерминированные пути **до** LLM, в таком порядке:

1. ссылка на магазин WB → 2. ссылка на товар WB → 3. явное чтение Pinterest → 4. инвентарь Pinterest-аккаунтов → 5. ответ по одобренному источнику (без LLM) → 6. исследование ключевых слов → 7. GigaChat с function calling.

При добавлении источника данных:

- добавляйте **ступень лестницы**, а не обходной путь внутри промпта;
- ступень пишет пару `provider` / `model` в `AIMessage`: `gigachat`, `pinterest-api`, `database`, `knowledge`, `wildberries-web`, `wildberries-cdn`, `data-read`. Поле `provider` — свободный `CharField(max_length=32)`, а не enum с `choices`: база эти значения не ограничивает;
- цикл tool-calling ограничен 6 итерациями (`services.py:1054`); любой результат инструмента, содержащий `error`, прерывает цикл с `provider="data-read"`;
- `apps/strategist/advice.py::enforce_advice_boundaries` — финальный regex-гейт, вычищающий обещания про рекламу, ROI и карусели. Не выдавайте утверждения сверх того, что приложение способно проверить;
- модель выбирается динамически: `GigaChatProvider` читает `GET /models` с кэшем 300 с, `GigaChatModelRouter` фильтрует `GIGACHAT_MODEL_PRIORITY` по `apps/strategist/model_catalog.py`. Не хардкодьте id модели; известное исключение — `apps/strategist/wb_vision.py`, он залезает в приватный `GigaChatProvider._client()` и обходит роутер.

## CSS генерируется, но коммитится

`static/css/app.css` и `static/css/landing.bundle.css` — **build-артефакты под Git**, собираемые `scripts/build_css_bundles.py` из `tokens.css`, `base.css`, `components/{buttons,panels,forms,dialogs,interface-scale,workbench}.css`, `shell.css` и `landing.css` для лендинг-бандла. Шаблоны грузят только эти два бандла.

Правьте исходники, затем запускайте `python scripts/build_css_bundles.py` и коммитьте пересобранные бандлы: ручная правка бандла молча перезаписывается. Скрипт же выполняется на этапе сборки в `Dockerfile`.

## Runtime-реальность

- **У Celery ровно одна задача**: `apps.pinterest.tasks.refresh_pinterest_tokens`, beat каждые 86400 с. Воркеры слушают `critical,generation,research,analytics,notifications,low_priority`, но `CELERY_TASK_DEFAULT_QUEUE = "low_priority"` — новая задача попадёт туда, если явно не зароучена. Лимиты времени: 270 с мягкий, 300 с жёсткий.
- **Тяжёлая работа синхронна внутри запроса**: синк Pinterest, ответы стратега, чтения WB до `MAX_PAGES = 100` последовательных страниц с `PAGE_DELAY_SECONDS = 0.2`. Стриминга нет.
- **Wildberries использует недокументированные внутренности** (`basket-NN.wbbasket.ru`, `www.wildberries.ru/__internal/u-catalog`) и ставит `trust_env=False`, потому что прокси-IP получают 403. Чтение магазина или бренда требует внешнего помощника на Camoufox, слушающего unix-сокет `/app/.wb_browser.sock`: его нет ни в compose, ни в requirements, поэтому без него `read_store` всегда падает с «Локальный браузер WB недоступен». Скрипт помощника — `scripts/wb_browser_helper.py`.
- `STRATEGIST_PRODUCT_VISION_ENABLED` по умолчанию `false` и отсутствует в `.env.production.example`: анализ изображений WB выключен по дизайну, пока не одобрен API-бюджет.
- Rate limiter в `apps/core/ratelimit.py` **fail closed**: при недоступном Valkey отдаёт 503, а не пропускает запрос.

## База знаний

- Эмбеддинги хранятся как JSONField-векторы, косинусное сходство считается в процессе: каждый поиск выгружает в Python список всех подходящих чанков (`_searchable_chunks`, `services.py:169`) — статус `approved`, scope `global`, язык `ru`, `source_checked <= сегодня`. Ни pgvector, ни ANN-индексов нет.
- `INDEXER_VERSION` в `apps/knowledge/services.py` нужно поднимать при изменении чанкинга, иначе неизменившиеся документы никогда не переиндексируются.
- Источники — одобренные markdown-файлы в `docs/ai-knowledge/knowledge/` с YAML front matter. `manage.py index_knowledge` по умолчанию **dry run**: индексирует только с `--embed`, `--force` переэмбедит неизменившиеся.
- Чанкер пропускает разделы источников и ссылок, `Scope` и `Status` — одночленные enum'ы, извлечение жёстко ограничено `language="ru"`.

## Оценки и вспомогательные скрипты

`scripts/run_strategist_arksim.py` — dry run без `--run`; с `--run` делает реальные платные вызовы API и создаёт и уничтожает временную БД. Зависимость `arksim` лежит в `requirements/eval.txt`, а не в `base.txt`.

## Локализация (ru + en)

Язык-источник — русский: msgid — это русская строка, английский перевод лежит в `locale/en/LC_MESSAGES/django.po`. Ни `xgettext`, ни `msgfmt` в среде нет, поэтому каталог ведёт `scripts/i18n.py` (чистый Python, работает на хосте):

    python3 scripts/i18n.py extract   # пересобрать .po из шаблонов и Python, переводы сохраняются
    python3 scripts/i18n.py compile   # собрать django.mo
    python3 scripts/i18n.py check     # код возврата ≠ 0, если каталог устарел/неполон/сломан

Новая пользовательская строка: обернуть в `{% trans %}` / `{% blocktrans %}` (в Python — `gettext` / `gettext_lazy`, для сообщений, которые только передаются дальше, — `gettext_noop`), затем `extract`, вписать `msgstr`, `compile`. `blocktrans` с `plural`/`count` скриптом не поддерживается. `django.mo` коммитится (исключение в `.gitignore`); `apps.strategist.test_i18n` падает, если .po и .mo разошлись, строка не переведена или в переводе потерян `%(плейсхолдер)s`, поэтому CI это ловит. Переключатель языка — `templates/includes/language_switch.html` (POST на `set_language`).

Не переводится: ответы самого Стратега и тексты из `services.py`, `strategy_chat.py`, `memory.py`, `content_plan.py` (язык диалога задан его системным prompt и правилами ответа, это не интерфейс); картинка на лендинге с подписями «подходит / не подходит»; названия полей моделей в админке.

## Статика и кэш браузера

Стили и скрипты подключаются тегом `{% asset 'css/app.css' %}` (`apps/core/templatetags/assets.py`): к адресу добавляется хеш содержимого файла (`?v=…`), поэтому браузер не использует устаревший файл (сервер не отдаёт `Cache-Control`, и браузер мог держать старый `app.css` часами). Новые CSS/JS в шаблонах подключать только так, а не `{% static %}`. Собранные `app.css` и `landing.bundle.css` нельзя править руками: правки только в исходниках `static/css/**`, затем `python3 scripts/build_css_bundles.py`; тест `apps.core.test_assets` падает, если сборка устарела.

## Страница создания пинов и фоновые задачи

`pin_settings.py` — единственное место, где определены допустимые значения настроек генерации (тон, призыв, длина, режим ключа, запретные слова, пожелание ≤500 символов, ссылка, utm, переписывание при блоке) и их очистка; её используют форма (`pin_forms.py`), задача и пресет, поэтому сохранённая задача не может содержать значение, которое страница бы отклонила. `pin_jobs.py` — запуск (`start_job`: проверки, одна активная задача на бизнес, не больше `MAX_ITEMS` пунктов), цикл воркера (`run_job`, идемпотентен: повторная доставка Celery ничего не дублирует), отмена, сводка; `tasks.py` — тонкая обёртка Celery. Задача пишет в `notes` только фиксированные предложения. Запретные слова пользователя применяются проверкой (`strategy_match`), а не просьбой в prompt; пожелание передаётся модели как данные и проверки не отменяет. Ссылка на карточку Wildberries даёт `product_facts` для проверок и prompt (облегчённое чтение карточки без фото). Страница `strategist:pin-generate` доступна только владельцу, администратору и редактору (иначе 404); настройки запоминаются как `GenerationPreset` (доски в пресет не входят). Шаблоны кэшируются: после правки шаблонов в запущенном окружении нужен `docker compose restart web`.

## Одобрение пинов

`Approval` относится к конкретной `PinVersion` (одна запись на версию) и создаётся только функцией `approvals.decide`, которую вызывает веб-вьюха страницы «Пины» (POST, CSRF, права владельца/администратора/редактора, иначе 404). Ни чат, ни модель одобрить пин не могут: команды одобрения нет, и тест это проверяет. Правила: решение только по текущей версии; пин с вердиктом `BLOCK` одобрить нельзя (только отклонить или на переделку); для одобрения нужна отметка «я прочитал замечания и знаю, какие проверки не выполнены», в запись попадают id таких проверок. «На переделку» возвращает пункт плана в генерацию: комментарий человека и причины блокировки идут модели как feedback, новая версия требует нового решения. Решения пишутся в историю решений бизнеса.

## Версии промптов и manifest источников

Любой изменённый шаблон prompt (чат: `prompts.py`; стратегия и контент-план: константа `SYSTEM`; исследование: `SEED_SYSTEM`/`FILTER_SYSTEM`) требует новой версии в `apps/strategist/provenance.py`: поменять константу `*_PROMPT_VERSION` и записать новый хеш в `FINGERPRINTS` (тест `test_provenance` печатает нужный хеш). Ответы модели сохраняют `prompt_version` и `context_manifest`; в manifest кладутся только виды и идентификаторы данных, не их текст, а в чате они видны как «Источники ответа».

## Пины и проверки

`pin_checks.py` — детерминированные проверки версии пина (без модели и сети): наличие и лимиты текста (лимиты читаются из утверждённого источника, при его отсутствии — `not_checked`), соответствие стратегии, ключевая фраза и набивка, обещания и превосходные степени, ссылка, дубли среди пинов бизнеса, alt text. Вердикт: `BLOCK` при любой блокировке, иначе `REVIEW` при любой «нужна оценка», иначе `PASS`; невыполнимые проверки (`product_source`, `url_reachable`, `account_history`, `semantic_review`) перечисляются отдельно и никогда не считаются пройденными. `pin_generation.py` — генерация текста и чат-команды («Создай пины по контент-плану» — до 3 пунктов за раз, «Покажи пины»); одна автоматическая повторная попытка при `BLOCK` с причинами. Правила — `docs/ai-knowledge/knowledge/pinterest-spam-prevention.md` и `docs/PIN_QUALITY_CRITERIA.md`.

## Версии

Запинены намеренно. Смена зависимости требует прохода по матрице совместимости; если после смены версии что-то сломалось, сначала откатывайтесь, а не обновляйте всё подряд. Полный список версий и их назначение — в `BOOSTKLIENT_3_STACK_VERSIONS.md`.