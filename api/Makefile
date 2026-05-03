dev:
	PYTHONPATH=src poetry run uvicorn invest_note_api.main:create_app --factory --reload --port 8000

stop:
	kill $$(lsof -ti tcp:8000) 2>/dev/null || true

restart: stop
	$(MAKE) dev

test:
	poetry run pytest -v

.PHONY: dev stop restart test
