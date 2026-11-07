.PHONY: up down status logs demo admin test web-test e2e
up:
	docker compose up -d --build

down:
	docker compose down

status:
	docker compose ps -a

logs:
	docker compose logs -f api worker web

demo:
	docker compose exec -T api python -m scripts.seed_demo

admin:
	docker compose exec -T api python -m scripts.bootstrap_admin

test:
	.venv/bin/pytest -q backend/tests

web-test:
	npm --prefix frontend test
	npm --prefix frontend run build

e2e:
	npm --prefix frontend run e2e
