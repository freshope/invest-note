dev:
	PYTHONPATH=src poetry run uvicorn invest_note_api.main:create_app --factory --reload --port 8000

stop:
	kill $$(lsof -ti tcp:8000) 2>/dev/null || true

restart: stop
	$(MAKE) dev

test:
	poetry run pytest -v

# DB 마이그레이션(Alembic). URL 은 env.py 가 MIGRATION_DATABASE_URL(없으면 DATABASE_URL,
# .env.local fallback)을 읽는다 — 로컬은 .env.local 에 superuser MIGRATION_DATABASE_URL 권장.
migrate:
	poetry run alembic upgrade head

# 새 마이그레이션 생성: make migrate-new name="add something"
migrate-new:
	poetry run alembic revision -m "$(name)"

.PHONY: dev stop restart test migrate migrate-new
