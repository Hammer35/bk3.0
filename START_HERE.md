# BOOSTKLIENT® 3.0 — START HERE

Этот файл нужен для продолжения работы на домашнем ПК без догадок.

## Что уже собрано

Каркас проекта построен как modular monolith (модульный монолит):

- Python 3.12.14;
- Django 5.2.17 LTS;
- PostgreSQL 17.10;
- Valkey 8.1.10;
- Celery 5.6.3;
- ASGI / Uvicorn;
- Docker Compose;
- отдельные settings для development / test / production;
- базовые apps: core, workspaces, businesses;
- модели Workspace / Membership / Business;
- UUID public_id;
- health endpoints;
- Light/Dark theme bootstrap;
- CI в GitHub Actions;
- Nginx config подготовлен, но не включён в локальный dev compose.

## Что сознательно НЕ добавлено

Пока отсутствуют:

- реальные Pinterest credentials;
- реальные AI API keys;
- Telegram/MAX tokens;
- production secrets;
- .env;
- Python venv;
- Pinterest OAuth implementation;
- AI Strategist;
- billing;
- production deploy.

Это сделано намеренно. Никаких секретов в Git.

## Самый простой запуск дома

Нужны только:

1. Git
2. Docker Engine + Docker Compose

Клонировать:

    git clone https://github.com/Hammer35/bk3.0.git
    cd bk3.0

Запустить:

    docker compose up --build

Первый запуск скачает образы, установит Python-зависимости и применит Django migrations.

После запуска:

- приложение: http://localhost:8000/
- live health: http://localhost:8000/health/live/
- readiness: http://localhost:8000/health/ready/
- admin: http://localhost:8000/admin/

Создать администратора:

    docker compose exec web python manage.py createsuperuser

Остановить:

    docker compose down

Данные PostgreSQL, Valkey и media сохраняются в Docker volumes.

## Важно: без .env

Development работает без .env.

В compose находятся ТОЛЬКО безопасные development credentials локальной БД.

Это не production credentials.

Production settings специально не позволят стартовать без DJANGO_SECRET_KEY.

Когда дойдём до реальных Pinterest/OpenAI ключей, секреты будут передаваться runtime-окружением или secrets manager, но не коммититься.

## Важно: без venv

venv не нужен, потому что Python и зависимости находятся внутри Docker image.

Не ставь Django/Celery глобально на домашнюю систему для этого проекта.

Команды запускай через docker compose.

## Полезные команды

    make up
    make down
    make logs
    make check
    make test
    make migrate
    make makemigrations
    make shell
    make superuser

Если make не установлен, эквивалентные docker compose команды можно запускать напрямую.

## Как устроены settings

    config/settings/base.py
    config/settings/development.py
    config/settings/test.py
    config/settings/production.py

development — локальная работа.
test — CI/tests.
production — жёсткие production security checks.

Нельзя переносить development defaults в production.

## Почему Valkey URL называется redis://

Celery/Kombu использует Redis-compatible transport scheme redis://.

Valkey совместим по протоколу. Сам сервер в compose — Valkey, не Redis.

Это отдельно будет проверяться compatibility tests до production согласно нашей матрице.

## Frontend

Сейчас серверный каркас не зависит от Node и запускается без него.

Зафиксированы версии:

- HTMX 2.0.10;
- Alpine.js 3.17.4;
- Tailwind CSS 4.3.3.

package.json уже есть.

Когда понадобится собирать frontend локально:

    npm install
    npm run build

После первого подтверждённого build необходимо закоммитить package-lock.json.

До этого не обновлять версии в package.json случайно.

## CSS сейчас

static/css/app.css — маленький bootstrap CSS, чтобы каркас был читаемым сразу и поддерживал две темы.

assets/css/app.css — точка входа Tailwind 4.

Когда начнётся реальная вёрстка, Tailwind build будет генерировать static/css/app.css.

Не добавлять inline style и script в templates.

## Данные

На текущем этапе созданы только фундаментальные сущности:

User (встроенный Django)
→ Workspace
→ Membership
→ Business

PinterestAccount и остальные домены добавляем следующими отдельными шагами по BOOSTKLIENT_3_DATA_MODEL.md.

Это сделано намеренно, чтобы не создавать 40 пустых моделей заранее.

## Docker volumes

postgres_data — БД.
valkey_data — очередь/cache persistence.
media_data — пользовательские медиа.

Команда:

    docker compose down

НЕ удаляет volumes.

Команда:

    docker compose down -v

УДАЛИТ локальную БД и локальные media. Использовать только если действительно хочешь начать с нуля.

## Миграции

Новые модели:

1. изменить models.py;
2. docker compose exec web python manage.py makemigrations;
3. проверить migration;
4. docker compose exec web python manage.py migrate;
5. запустить tests;
6. commit model + migration одним изменением.

Не редактировать уже применённые migrations задним числом без отдельной причины.

## CI

.github/workflows/ci.yml при push/PR:

- поднимает PostgreSQL;
- поднимает Valkey;
- устанавливает зафиксированные зависимости;
- выполняет Django check;
- проверяет незакоммиченные migrations;
- применяет migrations;
- запускает tests.

Красный CI нельзя игнорировать.

## Nginx

Конфигурация лежит в:

    infra/nginx/nginx.conf

В development Nginx специально не включён.

Локально он только мешал бы отладке.

Перед staging/production он будет включён отдельным deployment compose/config.

## Что делать первым после клонирования

1. docker compose up --build
2. открыть /health/ready/
3. создать superuser
4. зайти /admin/
5. запустить make test
6. убедиться, что GitHub Actions зелёный

Только после этого продолжать feature-разработку.

## Следующий продуктовый шаг

Не менять инфраструктуру без причины.

Следующий логичный слой:

1. accounts/workspace onboarding;
2. Business creation;
3. AI Strategist shell;
4. Pinterest integration adapter;
5. перенос проверенной OAuth/publishing логики из 2.0 по BOOSTKLIENT_2_TO_3_AUDIT.md.

## Если что-то не работает

Не начинай сразу менять версии библиотек.

Сначала:

    docker compose ps
    docker compose logs --tail=200 web
    docker compose logs --tail=200 db
    docker compose logs --tail=200 valkey
    docker compose logs --tail=200 worker

Потом:

    docker compose exec web python manage.py check

Основное правило проекта:

> Если ошибка появилась после изменения версии или dependency — сначала откатить изменение и проверить compatibility matrix, а не обновлять всё подряд.
