.PHONY: up down logs shell test check migrate makemigrations superuser build rebuild clean

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

shell:
	docker compose exec web python manage.py shell

test:
	docker compose exec web python manage.py test

check:
	docker compose exec web python manage.py check

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

superuser:
	docker compose exec web python manage.py createsuperuser

build:
	docker compose build

rebuild:
	docker compose build --no-cache

clean:
	docker compose down -v
