# AGENTS.md — BOOSTKLIENT® 3.0

Django 5.2 модульный монолит для продавцов маркетплейсов: workspace → business → Pinterest-аккаунт → ИИ-стратег. Стек: Python 3.12, PostgreSQL 17, Valkey, Celery, GigaChat (Sber) как единственная LLM, серверные Django-шаблоны и рукописный CSS.

Подробности по подсистемам — в `AGENTS-DETAIL.md`.

## Команды

Всё, что запускает Django, работает **внутри Docker**. Ни venv, ни глобально установленного Django.

    make up            # docker compose up --build
    make test          # docker compose exec web python manage.py test
    make check         # manage.py check
    make migrate       # manage.py migrate
    make makemigrations
    make shell
    make superuser
    make logs

`make clean` — это `docker compose down -v`, **удаляет локальную базу и медиа**.

Точечный тест (класс или метод, точечный путь):

    docker compose exec web python manage.py test apps.strategist.tests.StrategistChatTest --noinput
    docker compose exec web python manage.py test apps.pinterest -v 2 --noinput

Всегда передавайте `--noinput`: оставшаяся от прерванного прогона база `test_boostklient` заставит Django спросить подтверждение, и exec без TTY умрёт с `EOFError: EOF when reading a line` вместо запуска тестов. Тестам нужны запущенные PostgreSQL + Valkey, sqlite-фолбэка нет.

## Проверка

Линтера, форматтера и тайпчекера в репозитории **нет** — не добавляйте и не предполагайте ruff/black/mypy/pytest. Полное определение «проверено» — это то, что гоняет CI (`.github/workflows/ci.yml`):

    manage.py check
    manage.py makemigrations --check --dry-run
    manage.py migrate --noinput
    manage.py test

CI падает, если изменение модели приехало без миграции → коммитьте модель и миграцию одним изменением. Красный CI не игнорируется.

## Правило коммитов

Репозиторий общий, агентов несколько. Прежде чем что-то править или коммитить:

1. Прочитать `.kilo/agent-state/HANDOFF.md` и `.kilo/agent-state/LOG.md` — там видно, кто чем занят.
2. Задать имя **в окружении сессии**: `export AGENT_NAME="<имя>"`.
3. Занять файлы до правки: `.kilo/agent-state/agent.sh claim <имя> <путь> ...`. Второй агент получит отказ до того, как что-то испортит.
4. Коммитить по явным путям, не `git add -A`, и только занятые файлы.
5. После коммита: `agent.sh release <имя> <путь> ...`.

`git config agent.name` использовать **нельзя**: это один общий ключ на весь репозиторий, в нём помещается только одно имя. Второй агент, выполнивший эту команду, молча перезаписывает личность первого, и первый начинает получать отказ на собственных файлах. Это уже происходило в этом репозитории. Хук `.githooks/pre-commit` читает имя только из `AGENT_NAME`; если переменная не задана, он пропускает коммит лишь когда ни один файл в индексе не занят, а иначе отказывает.

Что нельзя, независимо от причины: коммитить в `main`, откатывать или удалять чужую работу, чинить чужое чужими руками без записи в `HANDOFF.md`. `--no-verify` — не способ обойти, а запись о том, что вы о чём-то договорились.

Защита двумя слоями: `.githooks/pre-commit` (локально, работает всегда) и защищённая ветка `main` на GitHub (PR плюс обязательное ревью плюс CI). Поэтому «запрос на подтверждение» для коммитов существует с обеих сторон.

## Чего в проекте нет

Проверено, чтобы не искали:

- **HTMX и Alpine не подключены.** Ни `static/vendor/`, ни `node_modules`, ни одного `hx-*` / `x-data` / `@click` в шаблонах — они есть только в `package.json`, `PRODUCT.md` и `BOOSTKLIENT_3_CODE_RULES.md` §4–6. Фронтенд — серверные шаблоны и 5 рукописных vanilla-JS файлов: `static/js/core/{theme,sidebar,interface-scale,form-confirmation}.js` и `static/js/strategist/chat.js`.
- **`npm run build` нерабочий**: `node_modules` нет, а вывод `static/css/tailwind.css` не подключён ни одним шаблоном. Живой только `scripts/build_css_bundles.py`.
- Кодовых путей OpenAI / Ollama / Telegram / MAX / Ozon нет, несмотря на маркетинговые тексты и упоминания в доках.
- `apps/strategist/admin.py` отсутствует: `AIConversation`, `AIMessage`, `WBImageAnalysis` не видны в `/admin/`.
- Ни network guard'а, ни фабрик в тестах нет; внешние вызовы замоканы через `unittest.mock.patch`.

## Соглашения, отличающиеся от дефолтов Django

- **URL по slug'ам.** `businesses/<workspace_slug>/<business_slug>/`. UUID-роуты существуют только как legacy 301-редиректы (`permanent=True`) — новые не добавлять. Все URL именованные, через `{% url %}` / `reverse()`.
- **Нет доступа → `Http404`, а не `403`**, чтобы не утекать факт существования.
- Никаких inline `<script>` / `<style>` и никакой бизнес-логики в шаблонах.
- `static/css/tokens.css` — единственный источник цветов, отступов и радиусов. Обе темы должны работать; проверяйте светлую **и** тёмную.
- UI не свободная форма: `DESIGN.md` (базовая линия Catalog Workbench, семейство компонентов) и `BOOSTKLIENT_3_DESIGN_SYSTEM.md` обязательны. Скриншот — не спецификация: если компонента или его роли Primary / Secondary / Ghost там нет, сначала зафиксируйте решение в дизайн-системе.
- Пользовательский текст переводим (ru + en) и по-русски.
- Никакого `print()` в production-коде; никаких секретов, токенов и credentials в Git и логах.
- Ошибки fail closed: пользователю русское сообщение, в лог — детали, никогда трейсбек или сырая ошибка API.
- Основная ветка `main`, работа ведётся в `feature/*`.

## Переменные окружения

Settings читают только `os.getenv`; **в Python ничего не грузит `.env`**. Корневой `.env` потребляется интерполяцией Docker Compose, поэтому `manage.py` на хосте не видит ни одной переменной — используйте `docker compose exec`.

Новая настройка = правки в четырёх местах: `config/settings/base.py` (`os.getenv` с безопасным дефолтом) → `compose.yaml` (`x-app-environment`) → `compose.production.yaml` (`x-app-environment`, для секретов `${VAR:?required}`) → `.env.production.example`, если переменная нужна в продакшене.

Подводные камни: `PINTEREST_SCOPES` в settings по умолчанию включает `ads:read`, а оба compose-файла передают дефолт **без** `ads:read`. `production.py` не стартует без `DJANGO_SECRET_KEY` (≥50 символов), `DJANGO_ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`. `PINTEREST_TOKEN_ENCRYPTION_KEY` должен быть валидным Fernet-ключом, и его нельзя ротировать без перешифровки сохранённых токенов.

## Документация

Прочитайте до работы: `BOOSTKLIENT_3_CODE_RULES.md` (источник соглашений, 57 разделов), `BOOSTKLIENT_3_DESIGN_SYSTEM.md`, `BOOSTKLIENT_3_DATA_MODEL.md`, `BOOSTKLIENT_3_TESTING.md`, `BOOSTKLIENT_3_AI_ARCHITECTURE.md`, `GIGACHAT_MODEL_ROUTING.md`.

Протухшее: `START_HERE.md` утверждает, что Pinterest OAuth, ИИ-стратег, `.env` и Python-зависимости отсутствуют — всё это уже есть, доверяйте `compose.yaml` и коду. `DESIGN.md` тоже устарел в одной детали: лендинг грузит `landing.bundle.css`, а не `landing.css`.

Health-эндпоинты: `/health/live/`, `/health/ready/` (Postgres + Valkey, 503 при отказе).